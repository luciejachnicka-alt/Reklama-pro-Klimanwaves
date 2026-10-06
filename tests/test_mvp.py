import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.domain import economics, margin, number
from app.server import Application, handler
from app.store import Store


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'test.sqlite3')
        self.product=self.store.product(dict(name='TEST ONLY',url='https://example.com/product',source='Automatický test — není produkční údaj',facts='Testovací fixture',economics=dict(sale_price=1210,purchase_cost=400,vat_rate=21,shipping_cost=80,payment_percent=2,payment_fixed=10,returns_cost=30,other_cost=20)))
        self.exp=self.store.experiment(dict(product_id=self.product['id'],name='Test fixture',platform='test',angle='demonstration',audience='test',hook='test',landing_page='https://example.com/product',hypothesis='Pouze testovací hypotéza',success_metric='contribution > 0',creative='Pouze testovací scénář'))

    def orders(self,creative=True):
        return dict(orders=[dict(id='test-order',source='TEST fixture',creative_id=self.exp['id'] if creative else None,occurred_at='2026-10-06T12:00:00+02:00',items=[dict(product_id=self.product['id'],quantity=1,revenue=1210)])])

    def action(self,kind='start_experiment',risk='YELLOW'):
        return self.store.create_action(dict(title='Test',kind=kind,risk=risk,target=self.exp['id'],current_value='draft',proposed_value='running',reason='Test reason',expected_impact='Internal only',confidence='Low'))


class DomainTests(Fixture):
    def test_break_even(self):
        self.assertEqual(margin(self.product['economics']),435.8)

    def test_reject_nan_negative_bool(self):
        for value in [float('nan'),float('inf'),-1,True,'abc']:
            with self.subTest(value=value), self.assertRaises(ValueError):number(value,'test')

    def test_revenue_discount_recalculates_margin(self):
        self.assertEqual(margin(self.product['economics'],605),-52.1)

    def test_order_dedup_and_conflict(self):
        self.assertEqual(self.store.import_orders(self.orders())['inserted'],1)
        self.assertEqual(self.store.import_orders(self.orders())['duplicate'],1)
        data=self.orders();data['orders'][0]['items'][0]['revenue']=100
        with self.assertRaises(ValueError):self.store.import_orders(data)
        self.assertEqual(self.store.snapshot()['totals']['purchases'],1)

    def test_order_import_atomic(self):
        data=self.orders();data['orders'].append(dict(data['orders'][0],id='bad',items=[]))
        with self.assertRaises(ValueError):self.store.import_orders(data)
        self.assertEqual(self.store.snapshot()['totals']['purchases'],0)

    def test_unattributed_order_in_totals_not_experiment(self):
        self.store.import_orders(self.orders(False));s=self.store.snapshot()
        self.assertEqual(s['totals']['purchases'],1)
        self.assertEqual(s['experiments'][0]['purchases'],0)
        self.assertIsNone(s['totals']['conversion_rate'])

    def test_conversion_rate_requires_matched_sessions(self):
        self.store.track(dict(id='e1',name='landing_page',session_id='s1',consent=True))
        self.store.track(dict(id='e2',name='landing_page',session_id='s2',consent=True))
        data=self.orders();data['orders'][0]['session_id']='s1'
        self.store.import_orders(data)
        self.assertEqual(self.store.snapshot()['totals']['conversion_rate'],50)

    def test_cost_update_preserves_historic_economics(self):
        self.store.import_orders(self.orders())
        changed=dict(self.product);changed['economics']=dict(changed['economics'],purchase_cost=800)
        self.store.update_product(changed['id'],changed)
        self.assertEqual(self.store.import_orders(self.orders())['duplicate'],1)
        self.assertEqual(self.store.snapshot()['totals']['contribution'],435.8)

    def test_ads_upsert_not_double_count(self):
        metrics=dict(metrics=[dict(creative_id=self.exp['id'],day='2026-10-06',spend=200,impressions=1000,clicks=100,source='TEST')])
        self.store.import_ads(metrics);self.store.import_ads(metrics);self.store.import_orders(self.orders())
        e=self.store.snapshot()['experiments'][0]
        self.assertEqual(e['spend'],200);self.assertEqual(e['profit'],235.8)
        self.assertEqual(e['cpa'],200);self.assertEqual(e['roas'],6.05)
        self.assertEqual(e['conversion_rate'],1)
        self.assertEqual(e['landing_page'],'https://example.com/product')
        self.assertEqual(e['landing_sessions'],0)

    def test_tracking_no_browser_purchase_no_consent(self):
        data=dict(id='event',name='purchase',creative_id=self.exp['id'],session_id='s',consent=True)
        with self.assertRaises(ValueError):self.store.track(data)
        data.update(name='landing_page',consent=False)
        with self.assertRaises(ValueError):self.store.track(data)
        data['consent']=True
        self.assertEqual(self.store.track(data)['inserted'],1)
        self.assertEqual(self.store.track(data)['inserted'],0)

    def test_approval_executes_and_rollback_restores(self):
        a=self.action();r=self.store.decide(a['id'],dict(decision='approve'))
        self.assertEqual(r['status'],'executed');self.assertEqual(r['approved_by'],'správce')
        self.assertEqual(self.store.snapshot()['experiments'][0]['status'],'running')
        with self.assertRaises(ValueError):self.store.decide(a['id'],dict(decision='approve'))
        self.store.decide(a['id'],dict(decision='rollback'))
        self.assertEqual(self.store.snapshot()['experiments'][0]['status'],'draft')

    def test_rollback_does_not_overwrite_later_change(self):
        a=self.action();self.store.decide(a['id'],dict(decision='approve'))
        with self.store.connect() as db:db.execute("UPDATE experiments SET status='paused'")
        with self.assertRaises(ValueError):self.store.decide(a['id'],dict(decision='rollback'))

    def test_external_approval_never_claims_execution(self):
        a=self.action('external_change');r=self.store.decide(a['id'],dict(decision='approve',confirmation=a['id']))
        self.assertEqual(r['status'],'manual_action_required')
        self.assertEqual(self.store.snapshot()['experiments'][0]['status'],'draft')

    def test_red_requires_exact_confirmation(self):
        a=self.action('budget_change')
        self.assertEqual(a['risk'],'RED')
        with self.assertRaises(ValueError):self.store.decide(a['id'],dict(decision='approve'))
        self.assertEqual(self.store.decide(a['id'],dict(decision='approve',confirmation=a['id']))['status'],'manual_action_required')

    def test_unknown_external_operation_defaults_red(self):
        a=self.action('external_change')
        self.assertEqual(a['risk'],'RED')
        with self.assertRaises(ValueError):self.store.decide(a['id'],dict(decision='approve'))

    def test_edit_and_reject_audited(self):
        a=self.action();self.store.decide(a['id'],dict(decision='edit',reason='New test reason'))
        r=self.store.decide(a['id'],dict(decision='reject'))
        self.assertEqual(r['status'],'rejected');self.assertEqual(r['reason'],'New test reason')
        self.assertEqual(self.store.snapshot()['audit'][0]['operation'],'reject')

    def test_stale_proposal_fails(self):
        a=self.action()
        with self.store.connect() as db:db.execute("UPDATE experiments SET status='paused'")
        with self.assertRaises(ValueError):self.store.decide(a['id'],dict(decision='approve'))

    def test_learning_threshold_and_dedup(self):
        self.store.import_orders(self.orders())
        self.assertEqual(self.store.analyze()['new_learnings'],0)
        with self.store.connect() as db:
            settings=self.store.settings(db);settings['minimum_purchases']=1
        self.store.update_settings(settings)
        self.assertEqual(self.store.analyze()['new_learnings'],1)
        self.assertEqual(self.store.analyze()['new_learnings'],0)

    def test_zero_order_spend_creates_review_not_automatic_pause(self):
        a=self.action();self.store.decide(a['id'],dict(decision='approve'))
        self.store.import_ads(dict(metrics=[dict(creative_id=self.exp['id'],day='2026-10-06',spend=1000,impressions=1000,clicks=100,source='TEST')]))
        self.store.analyze()
        snapshot=self.store.snapshot()
        self.assertEqual(snapshot['experiments'][0]['status'],'running')
        self.assertTrue(any(x['kind']=='pause_experiment' and x['status']=='pending' for x in snapshot['actions']))
        self.assertEqual(len(snapshot['learnings']),0)
        self.store.analyze()
        self.assertEqual(sum(x['kind']=='pause_experiment' for x in self.store.snapshot()['actions']),1)

    def test_lead_opt_in_confirmation_and_erasure(self):
        data=dict(email='test@example.com',source='https://example.com/opt-in',relevance='TEST',consent=True,consent_text='TEST consent',consent_version='test-1')
        lead=self.store.lead(data)
        self.assertEqual(self.store.snapshot()['leads'][0]['status'],'pending_confirmation')
        self.store.confirm_lead(dict(token=lead['confirmation_token']))
        with self.assertRaises(ValueError):self.store.confirm_lead(dict(token=lead['confirmation_token']))
        self.store.delete_lead(self.store.snapshot()['leads'][0]['id'])
        self.assertEqual(self.store.snapshot()['leads'],[])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=Application(self.tmp.name)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.app))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        hs=headers or {}
        if body is not None:hs={'Content-Type':'application/json',**hs}
        c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,hs)
        r=c.getresponse();status=r.status;response_headers=dict(r.getheaders());body=r.read();c.close()
        return status,response_headers,body

    def test_health_and_empty_state_authenticated(self):
        self.assertEqual(self.request('/api/health')[0],200)
        self.assertEqual(self.request('/api/state')[0],401)
        status,_,body=self.request('/api/state',headers={'Authorization':'Bearer '+self.app.admin_token})
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['products'],[])

    def test_session_http_only_and_csrf_blocked(self):
        status,headers,_=self.request('/api/login',dict(token=self.app.admin_token))
        self.assertEqual(status,200);cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie)
        self.assertEqual(self.request('/api/state',headers={'Cookie':cookie})[0],200)
        self.assertEqual(self.request('/api/analyze',{},headers={'Cookie':cookie,'Origin':'https://evil.example'})[0],403)

    def test_track_origin_and_purchase_rejected(self):
        self.assertEqual(self.request('/api/track',dict(name='purchase'),headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/track',dict(name='purchase'),headers={'Origin':self.app.shop_origin})[0],400)

    def test_static_no_path_traversal(self):
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.request('/../.local/admin-token')[0],404)

    def test_unknown_write_requires_auth(self):
        self.assertEqual(self.request('/api/products',{})[0],401)


if __name__=='__main__':unittest.main()
