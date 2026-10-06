import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .domain import DEFAULT_SETTINGS, economics, margin, number, ratios


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def uid(prefix):
    return prefix + '-' + uuid.uuid4().hex[:12].upper()


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def text(data, key, limit=5000):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{key}: vyplňte text (max. {limit} znaků).')
    return value.strip()


def date(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Datum musí být ISO 8601 s časovým pásmem.') from None


def web_url(value):
    from urllib.parse import urlsplit
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('Použijte platnou HTTPS adresu bez přihlašovacích údajů.')
    return value


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(Path(__file__).with_name('schema.sql').read_text())
            columns = {r[1] for r in db.execute('PRAGMA table_info(orders)')}
            if 'session_id' not in columns:
                db.execute('ALTER TABLE orders ADD COLUMN session_id TEXT')
            db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (dump(DEFAULT_SETTINGS),))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def settings(self, db):
        return json.loads(db.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])

    def audit(self, db, operation, before, after, action=None, actor='správce'):
        db.execute('INSERT INTO audit(action_id,actor,operation,before_value,after_value,occurred_at) VALUES(?,?,?,?,?,?)',
                   (action, actor, operation, dump(before), dump(after), now()))

    def product(self, data):
        p = dict(id=uid('PROD'), name=text(data, 'name', 200), url=web_url(text(data, 'url')),
                 source=text(data, 'source'), facts=text(data, 'facts'), economics=economics(data['economics']))
        with self.connect() as db:
            db.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?)',
                       (p['id'], p['name'], p['url'], p['source'], p['facts'], dump(p['economics']), now()))
            self.audit(db, 'product_created', None, p)
        return p

    def experiment(self, data):
        fields = ('product_id', 'name', 'platform', 'angle', 'audience', 'hook', 'landing_page', 'hypothesis', 'success_metric', 'creative')
        e = {k: text(data, k, 15000 if k == 'creative' else 5000) for k in fields}
        e['landing_page'] = web_url(e['landing_page'])
        e['id'] = uid('CR')
        with self.connect() as db:
            db.execute('INSERT INTO experiments(id,' + ','.join(fields) + ',created_at) VALUES(' + ','.join('?' for _ in range(12)) + ')',
                       (e['id'], *(e[k] for k in fields), now()))
            self.audit(db, 'experiment_created', None, e)
        return e

    def update_product(self, product_id, data):
        updated = dict(name=text(data,'name',200), url=web_url(text(data,'url')), source=text(data,'source'),
                       facts=text(data,'facts'), economics=economics(data['economics']))
        with self.connect() as db:
            old=db.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
            if old is None:
                raise ValueError('Produkt nenalezen.')
            db.execute('UPDATE products SET name=?,url=?,source=?,facts=?,economics=? WHERE id=?',
                       (updated['name'],updated['url'],updated['source'],updated['facts'],dump(updated['economics']),product_id))
            self.audit(db,'internal_product_profile_updated',dict(old),dict(id=product_id,**updated))
        return dict(id=product_id,**updated)

    def import_orders(self, data):
        records = data.get('orders')
        if not isinstance(records, list) or not records or len(records) > 1000:
            raise ValueError('orders musí obsahovat 1 až 1000 objednávek.')
        inserted = duplicate = 0
        with self.connect() as db:
            for item in records:
                order_id, source = text(item, 'id', 200), text(item, 'source', 500)
                occurred = date(item.get('occurred_at'))
                creative = item.get('creative_id') or None
                session = item.get('session_id') or None
                if session is not None and (not isinstance(session, str) or len(session) > 100):
                    raise ValueError('Neplatné session_id.')
                items = item.get('items')
                if not isinstance(items, list) or not items:
                    raise ValueError('Každá objednávka vyžaduje položky items.')
                gross = contribution = 0
                snapshot = []
                for line in items:
                    p = db.execute('SELECT economics FROM products WHERE id=?', (text(line, 'product_id'),)).fetchone()
                    if p is None:
                        raise ValueError('Neznámý produkt.')
                    quantity = number(line.get('quantity'), 'quantity', 10000)
                    if quantity < 1 or not quantity.is_integer():
                        raise ValueError('Množství musí být kladné celé číslo.')
                    revenue = number(line.get('revenue'), 'revenue')
                    e = json.loads(p[0])
                    gross += revenue
                    contribution += margin(e, revenue, quantity)
                    snapshot.append(dict(product_id=line['product_id'], quantity=quantity, revenue=revenue, economics=e))
                existing = db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
                payload = (source, creative, round(gross, 2), round(contribution, 2), dump(snapshot), occurred)
                if existing:
                    previous = tuple(existing[k] for k in ('source', 'creative_id', 'revenue', 'contribution', 'economics_snapshot', 'occurred_at'))
                    # Keep the original economic snapshot on repeated imports after cost settings change.
                    previous_items = json.loads(existing['economics_snapshot'])
                    same_lines = [{k: x[k] for k in ('product_id','quantity','revenue')} for x in previous_items] == [{k: x[k] for k in ('product_id','quantity','revenue')} for x in snapshot]
                    if previous[:3] != payload[:3] or previous[-1] != occurred or not same_lines or existing['session_id'] != session:
                        raise ValueError('ID objednávky již existuje s jiným obsahem. Import nebyl proveden.')
                    duplicate += 1
                    continue
                db.execute('INSERT INTO orders(id,source,creative_id,revenue,contribution,economics_snapshot,occurred_at,imported_at,session_id) VALUES(?,?,?,?,?,?,?,?,?)', (order_id, *payload, now(), session))
                inserted += 1
            self.audit(db, 'orders_imported', None, dict(inserted=inserted, duplicate=duplicate))
        return dict(inserted=inserted, duplicate=duplicate)

    def import_ads(self, data):
        records = data.get('metrics')
        if not isinstance(records, list) or not records or len(records) > 1000:
            raise ValueError('metrics musí obsahovat 1 až 1000 záznamů.')
        with self.connect() as db:
            before = []
            for item in records:
                creative = text(item, 'creative_id')
                day = text(item, 'day', 10)
                if datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d') != day:
                    raise ValueError('Neplatný den.')
                spend = number(item.get('spend'), 'spend')
                impressions = number(item.get('impressions'), 'impressions', 1e12)
                clicks = number(item.get('clicks'), 'clicks', 1e12)
                if not impressions.is_integer() or not clicks.is_integer() or clicks > impressions:
                    raise ValueError('Kliknutí a imprese musí být celá čísla; kliknutí ≤ imprese.')
                old = db.execute('SELECT * FROM ad_metrics WHERE creative_id=? AND day=?', (creative, day)).fetchone()
                before.append(dict(old) if old else None)
                db.execute('INSERT INTO ad_metrics VALUES(?,?,?,?,?,?) ON CONFLICT(creative_id,day) DO UPDATE SET spend=excluded.spend,impressions=excluded.impressions,clicks=excluded.clicks,source=excluded.source',
                           (creative, day, spend, int(impressions), int(clicks), text(item, 'source')))
            self.audit(db, 'ad_metrics_imported', before, records)
        return dict(imported=len(records))

    def track(self, data):
        allowed = {'landing_page', 'product_view', 'add_to_cart', 'checkout'}
        event_name = text(data, 'name')
        if event_name not in allowed:
            raise ValueError('Nákupy, tržby a reklamní imprese se nepřijímají z prohlížeče.')
        if data.get('consent') is not True:
            raise ValueError('Událost vyžaduje analytický souhlas.')
        creative = data.get('creative_id') or None
        attrs = data.get('attribution', {})
        if not isinstance(attrs, dict):
            raise ValueError('Neplatná atribuce.')
        attrs = {k: str(attrs.get(k, ''))[:200] for k in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content')}
        with self.connect() as db:
            existing = db.execute('SELECT * FROM events WHERE id=?', (text(data, 'id', 100),)).fetchone()
            session = text(data, 'session_id', 100)
            if existing:
                if (existing['name'], existing['creative_id'], existing['session_id']) != (event_name, creative, session):
                    raise ValueError('ID události již existuje s jiným obsahem.')
                return dict(inserted=0)
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)', (data['id'], event_name, creative, session, now(), dump(attrs)))
        return dict(inserted=1)

    def create_action(self, data):
        kind = text(data, 'kind')
        if kind not in {'start_experiment', 'pause_experiment', 'external_change', 'budget_change'}:
            raise ValueError('Nepodporovaný typ akce.')
        risk = 'RED' if kind == 'budget_change' else 'YELLOW'
        if kind == 'external_change':
            # Unknown external operations default to RED. Only explicit marketing scopes
            # can be YELLOW; major changes must use their corresponding scope.
            scope = data.get('change_scope', 'unspecified')
            risk = 'YELLOW' if scope in {'ad_copy','landing_content','campaign_creative'} and data.get('risk') != 'RED' else 'RED'
        action = {k: text(data, k) for k in ('title', 'target', 'current_value', 'proposed_value', 'reason', 'expected_impact', 'confidence')}
        if action['confidence'] not in {'Low', 'Medium', 'High'}:
            raise ValueError('Neplatná míra jistoty.')
        action.update(id=uid('ACT'), kind=kind, risk=risk, created_at=now(), updated_at=now())
        with self.connect() as db:
            db.execute('INSERT INTO actions(id,title,kind,risk,target,current_value,proposed_value,reason,expected_impact,confidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       tuple(action[k] for k in ('id','title','kind','risk','target','current_value','proposed_value','reason','expected_impact','confidence','created_at','updated_at')))
            self.audit(db, 'action_proposed', None, action, action['id'])
        return action

    def decide(self, action_id, data):
        decision = text(data, 'decision')
        if decision not in {'approve', 'reject', 'edit', 'rollback'}:
            raise ValueError('Neplatné rozhodnutí.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            a = db.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone()
            if not a:
                raise ValueError('Akce nenalezena.')
            before = dict(a)
            status = a['status']
            if decision == 'rollback':
                if status != 'executed' or a['kind'] not in {'start_experiment','pause_experiment'}:
                    raise ValueError('Rollback není pro tuto akci dostupný.')
                original = json.loads(a['current_value'])
                proposed = json.loads(a['proposed_value'])
                e = db.execute('SELECT status,started_at FROM experiments WHERE id=?', (a['target'],)).fetchone()
                if not e or dict(e) != proposed:
                    raise ValueError('Stav se mezitím změnil. Rollback by přepsal novější změnu.')
                db.execute('UPDATE experiments SET status=?,started_at=? WHERE id=?', (original['status'],original['started_at'],a['target']))
                status = 'rolled_back'
            else:
                if status != 'pending':
                    raise ValueError('Akce již byla rozhodnuta.')
                if decision == 'edit':
                    for key in ('title','proposed_value','reason','expected_impact'):
                        if key in data:
                            value = text(data,key)
                            db.execute('UPDATE actions SET '+key+'=? WHERE id=?', (value,action_id))
                    status = 'pending'
                elif decision == 'reject':
                    status = 'rejected'
                else:
                    if a['risk'] == 'RED' and data.get('confirmation') != action_id:
                        raise ValueError('Riziková akce vyžaduje explicitní potvrzení jejím ID.')
                    if a['kind'] in {'start_experiment','pause_experiment'}:
                        e = db.execute('SELECT status,started_at FROM experiments WHERE id=?', (a['target'],)).fetchone()
                        if not e:
                            raise ValueError('Experiment nenalezen.')
                        intended = 'running' if a['kind'] == 'start_experiment' else 'paused'
                        if e['status'] == intended:
                            raise ValueError('Experiment už má požadovaný stav.')
                        if a['current_value'] != e['status']:
                            raise ValueError('Současný stav se změnil od vytvoření návrhu. Vytvořte nový návrh.')
                        if a['proposed_value'] != intended:
                            raise ValueError('Návrh neodpovídá typu interní akce. Opravte navržený stav.')
                        original = dict(e)
                        proposed = dict(status=intended, started_at=(e['started_at'] or now()) if intended == 'running' else e['started_at'])
                        db.execute('UPDATE actions SET current_value=?,proposed_value=? WHERE id=?', (dump(original),dump(proposed),action_id))
                        db.execute('UPDATE experiments SET status=?,started_at=? WHERE id=?', (proposed['status'],proposed['started_at'],a['target']))
                        status = 'executed'
                    else:
                        # No external adapter is registered. Approval must never pretend execution.
                        status = 'manual_action_required'
            db.execute('UPDATE actions SET status=?,approved_by=?,updated_at=? WHERE id=?',
                       (status, 'správce' if decision == 'approve' else a['approved_by'], now(),action_id))
            after = dict(db.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone())
            self.audit(db, decision, before, after, action_id)
        return after

    def update_settings(self, data):
        validated = {k: number(data.get(k, 0), k, 100000 if k == 'minimum_purchases' else 1e9) for k in DEFAULT_SETTINGS}
        if validated['minimum_purchases'] < 1 or not validated['minimum_purchases'].is_integer():
            raise ValueError('Minimální počet objednávek musí být kladné celé číslo.')
        if validated['max_cpa'] and validated['target_cpa'] > validated['max_cpa']:
            raise ValueError('Cílové CPA nesmí překročit maximální CPA.')
        with self.connect() as db:
            previous = self.settings(db)
            # These limits govern recommendations only; no connector can spend in the MVP.
            self.audit(db, 'internal_limits_updated', previous, validated)
            db.execute('UPDATE settings SET data=? WHERE id=1', (dump(validated),))
        return validated

    def snapshot(self):
        with self.connect() as db:
            settings = self.settings(db)
            products = [dict(r) for r in db.execute('SELECT * FROM products ORDER BY created_at DESC')]
            for p in products:
                p['economics'] = json.loads(p['economics'])
                p['break_even_cpa'] = margin(p['economics'])
            experiments = [dict(r) for r in db.execute('SELECT * FROM experiments ORDER BY created_at DESC')]
            for e in experiments:
                ad = db.execute('SELECT COALESCE(SUM(spend),0) spend,COALESCE(SUM(impressions),0) impressions,COALESCE(SUM(clicks),0) clicks FROM ad_metrics WHERE creative_id=?', (e['id'],)).fetchone()
                orders = db.execute('SELECT COUNT(*) purchases,COALESCE(SUM(revenue),0) revenue,COALESCE(SUM(contribution),0) contribution FROM orders WHERE creative_id=?', (e['id'],)).fetchone()
                e.update(dict(ad));e.update(dict(orders))
                for name in ('landing_page','product_view','add_to_cart','checkout'):
                    metric_key = 'landing_sessions' if name == 'landing_page' else name
                    e[metric_key] = db.execute('SELECT COUNT(DISTINCT session_id) FROM events WHERE creative_id=? AND name=?', (e['id'],name)).fetchone()[0]
                ratios(e)
                if e['purchases'] < settings['minimum_purchases']:
                    e['verdict'] = 'insufficient_data'
                elif e['profit'] <= 0 or (settings['max_cpa'] and e['cpa'] > settings['max_cpa']) or (settings['min_roas'] and e['roas'] is not None and e['roas'] < settings['min_roas']):
                    e['verdict'] = 'losing'
                else:
                    e['verdict'] = 'promising'
            totals = dict(db.execute('SELECT COALESCE(SUM(spend),0) spend,COALESCE(SUM(impressions),0) impressions,COALESCE(SUM(clicks),0) clicks FROM ad_metrics').fetchone())
            totals.update(dict(db.execute('SELECT COUNT(*) purchases,COALESCE(SUM(revenue),0) revenue,COALESCE(SUM(contribution),0) contribution FROM orders').fetchone()))
            totals['visitors'] = db.execute("SELECT COUNT(DISTINCT session_id) FROM events WHERE name='landing_page'").fetchone()[0]
            for event_name in ('product_view', 'add_to_cart', 'checkout'):
                totals[event_name] = db.execute('SELECT COUNT(DISTINCT session_id) FROM events WHERE name=?', (event_name,)).fetchone()[0]
            totals['unattributed_purchases'] = db.execute('SELECT COUNT(*) FROM orders WHERE creative_id IS NULL').fetchone()[0]
            ratios(totals)
            # Total CVR must use measured sessions, not an incompatible blend of all orders and ad clicks.
            matched_sessions = db.execute("SELECT COUNT(DISTINCT o.session_id) FROM orders o JOIN events e ON e.session_id=o.session_id WHERE e.name='landing_page'").fetchone()[0]
            totals['matched_purchase_sessions'] = matched_sessions
            totals['conversion_rate'] = round(matched_sessions / totals['visitors'] * 100, 2) if totals['visitors'] and matched_sessions else None
            totals['attribution_note'] = 'CVR: měřené sessions se spárovanou objednávkou / měřené landing sessions. Chybějící session_id a nesouhlas s měřením omezují úplnost. U reklam: přiřazené objednávky / reklamní kliknutí.'
            actions = [dict(r) for r in db.execute('SELECT * FROM actions ORDER BY created_at DESC')]
            audit = [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]
            learnings = [dict(r) for r in db.execute('SELECT * FROM learnings ORDER BY created_at DESC')]
            leads = [dict(r) for r in db.execute('SELECT id,email,source,relevance,consent_version,consent_at,status,confirmed_at FROM leads ORDER BY consent_at DESC')]
            data_sources = dict(
                products=len(products), orders=totals['purchases'],
                ad_records=db.execute('SELECT COUNT(*) FROM ad_metrics').fetchone()[0],
                tracked_events=db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                last_order_import=db.execute('SELECT MAX(imported_at) FROM orders').fetchone()[0],
                last_ad_import=db.execute("SELECT MAX(occurred_at) FROM audit WHERE operation='ad_metrics_imported'").fetchone()[0],
            )
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo('Europe/Prague')).date().isoformat()
            daily = db.execute('SELECT COALESCE(SUM(spend),0) FROM ad_metrics WHERE day=?', (today,)).fetchone()[0]
            monthly = db.execute('SELECT COALESCE(SUM(spend),0) FROM ad_metrics WHERE substr(day,1,7)=?', (today[:7],)).fetchone()[0]
            alerts = []
            for label, spent, limit in [('Denní',daily,settings['daily_limit']),('Měsíční',monthly,settings['monthly_limit'])]:
                if spent > limit:
                    alerts.append(f'{label} importovaná útrata {spent:.2f} Kč překročila limit {limit:.2f} Kč. Připojené kampaně nejsou automaticky zastaveny.')
            return dict(settings=settings, products=products, experiments=experiments, totals=totals,
                        actions=actions, audit=audit, learnings=learnings, leads=leads, alerts=alerts,
                        daily_spend=daily, monthly_spend=monthly, last_analysis=self.last_analysis, data_sources=data_sources)

    last_analysis = None

    def analyze(self):
        s = self.snapshot()
        created = 0
        with self.connect() as db:
            for e in s['experiments']:
                if e['purchases'] < s['settings']['minimum_purchases']:
                    continue
                finding = ('Kladný odhad příspěvku po reklamě.' if e['profit'] > 0 else 'Záporný odhad příspěvku po reklamě.')
                evidence = {k:e[k] for k in ('spend','purchases','revenue','contribution','profit','cpa','roas')}
                fingerprint = hashlib.sha256(dump([e['id'], evidence]).encode()).hexdigest()
                result = db.execute('INSERT OR IGNORE INTO learnings VALUES(?,?,?,?,?,?)',
                           (fingerprint,e['id'],dump(evidence),finding,'Otestovat jednu variantu hooku při stejném publiku; nejde o důkaz kauzality.',now()))
                created += result.rowcount
            self.audit(db, 'analysis_completed', None, dict(new_learnings=created))
        self.last_analysis = now()
        # Create a specific reviewable action only from our own sufficient evidence.
        for e in s['experiments']:
            product = next(p for p in s['products'] if p['id'] == e['product_id'])
            no_sales_signal = e['purchases'] == 0 and e['clicks'] >= 100 and e['spend'] >= 2 * max(1, product['break_even_cpa'])
            if e['status'] != 'running' or (e['purchases'] < s['settings']['minimum_purchases'] and not no_sales_signal):
                continue
            if not no_sales_signal and e['profit'] >= 0 and (not s['settings']['max_cpa'] or e['cpa'] <= s['settings']['max_cpa']) and (not s['settings']['min_roas'] or e['roas'] is None or e['roas'] >= s['settings']['min_roas']):
                continue
            if any(a['target'] == e['id'] and a['kind'] == 'pause_experiment' and a['status'] == 'pending' for a in s['actions']):
                continue
            self.create_action(dict(title='Pozastavit evidenci ztrátového testu: '+e['name'],kind='pause_experiment',target=e['id'],
                                    current_value=e['status'],proposed_value='paused',reason=f"{e['purchases']} objednávek; {e['clicks']} kliknutí; CPA {str(e['cpa'])+' Kč' if e['cpa'] is not None else 'neznámé'}; odhad příspěvku po reklamě {e['profit']} Kč. Před zásahem ověřte úplnost importů a měření.",
                                    expected_impact='Zastaví interní test. Reklamní kampaň musíte pozastavit ručně; externí API není připojeno.',confidence='Medium'))
        return dict(new_learnings=created, analyzed_at=self.last_analysis)

    def lead(self, data):
        import re
        email = text(data, 'email', 254).lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or data.get('consent') is not True:
            raise ValueError('Platný e-mail a výslovný souhlas jsou povinné.')
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('INSERT INTO leads(id,email,source,relevance,consent_text,consent_version,consent_at,token_hash) VALUES(?,?,?,?,?,?,?,?)',
                       (uid('LEAD'),email,web_url(text(data,'source')),text(data,'relevance'),text(data,'consent_text'),text(data,'consent_version',100),now(),hashlib.sha256(token.encode()).hexdigest()))
            self.audit(db, 'lead_opt_in_pending', None, {'email_hash': hashlib.sha256(email.encode()).hexdigest()})
        # Deliberately no SMTP or unsolicited outreach; authenticated operator gets confirmation token.
        return dict(status='pending_confirmation',confirmation_token=token, note='Token doručte kontaktem, který uživatel odsouhlasil. Žádný e-mail nebyl odeslán.')

    def confirm_lead(self, data):
        with self.connect() as db:
            digest = hashlib.sha256(text(data,'token').encode()).hexdigest()
            lead = db.execute('SELECT id,status FROM leads WHERE token_hash=?', (digest,)).fetchone()
            if not lead or lead['status'] != 'pending_confirmation':
                raise ValueError('Token je neplatný nebo byl použit.')
            db.execute("UPDATE leads SET status='confirmed',confirmed_at=? WHERE id=?", (now(),lead['id']))
            self.audit(db,'lead_confirmed',None,dict(id=lead['id']))
        return dict(status='confirmed')

    def delete_lead(self, lead_id):
        with self.connect() as db:
            if db.execute('DELETE FROM leads WHERE id=?',(lead_id,)).rowcount != 1:
                raise ValueError('Kontakt nenalezen.')
            self.audit(db,'lead_deleted',None,dict(id=lead_id))
        return dict(deleted=True)
