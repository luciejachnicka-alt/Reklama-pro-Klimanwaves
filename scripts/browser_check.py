"""Optional real-browser end-to-end check using temporary, clearly test-only data."""
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.server import Application,handler
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as directory:
        app=Application(directory)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(app))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1100},timezone_id='Europe/Prague')
                errors=[]
                def page_error(e):
                    errors.append(str(e));print('Browser error:',str(e),flush=True)
                page.on('pageerror',page_error)
                page.goto(base)
                page.locator('#login-form input[name=token]').fill(app.admin_token)
                page.locator('#login-form button').click()
                page.locator('#app-panel:not(.hidden)').wait_for()
                page.locator('#modal [name=password]').fill('Browser test-only passphrase')
                page.locator('#modal [name=confirmation]').fill('Browser test-only passphrase')
                page.locator('#modal button[type=submit]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.locator('#logout').click()
                page.locator('#login-form [name=password]').fill('Browser test-only passphrase')
                page.locator('#login-form button').click()
                page.locator('#app-panel:not(.hidden)').wait_for()
                assert page.locator('.kpi-value').all_text_contents()==['—','—','—','—']
                assert page.locator('#analyze').is_disabled()
                page.locator('[data-explain]').first.click()
                assert 'nepoužívá připojený AI model' in page.locator('#modal-body').inner_text()
                page.locator('#close-modal').click()
                page.locator('.nav[data-view="products"]').click()
                page.locator('#new-product').click()
                values=dict(name='TEST ONLY — browser fixture',url='https://example.com/product',source='Automatický test',facts='Testovací podklad',sale_price='1210',purchase_cost='400',vat_rate='21',shipping_cost='80',payment_percent='2',payment_fixed='10',returns_cost='30',other_cost='20')
                for k,v in values.items():page.locator(f'#modal [name="{k}"]').fill(v)
                page.locator('#modal button[type="submit"]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.locator('.product-card').wait_for()
                assert app.store.snapshot()['products'][0]['break_even_cpa']==435.8
                page.locator('[data-edit-product]').click()
                assert page.locator('#modal [name="sale_price"]').input_value()=='1210'
                page.locator('#modal [name="facts"]').fill('Upravený testovací podklad')
                page.locator('#modal button[type="submit"]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.locator('.nav[data-view="experiments"]').click()
                page.locator('#new-experiment').click()
                for k,v in dict(name='TEST experiment',platform='test',angle='demonstration',audience='TEST audience',hook='TEST hook',landing_page='https://example.com/product',hypothesis='TEST hypothesis',success_metric='Contribution > 0',creative='TEST original brief').items():page.locator(f'#modal [name="{k}"]').fill(v)
                page.locator('#modal button[type="submit"]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.locator('[data-detail]').click();page.locator('#propose-test').click()
                page.locator('#modal').wait_for(state='hidden')
                page.on('dialog',lambda dialog:dialog.accept())
                page.locator('[data-decide="approve"]').click()
                page.locator('[data-decide="rollback"]').wait_for()
                snapshot=app.store.snapshot();e=snapshot['experiments'][0];product=snapshot['products'][0]
                assert e['status']=='running'
                page.locator('.nav[data-view="data"]').click();page.locator('#import-orders').click()
                orders=dict(orders=[dict(id='test-browser-order',source='TEST ONLY',creative_id=e['id'],occurred_at='2026-10-06T12:00:00+02:00',items=[dict(product_id=product['id'],quantity=1,revenue=1210)])])
                for k,v in dict(order_id='test-browser-order',quantity='1',revenue='1210',occurred_at='2026-10-06T12:00',source='TEST ONLY').items():
                    page.locator(f'#modal [name="{k}"]').fill(v)
                page.locator('#modal [name="creative_id"]').select_option(e['id'])
                page.locator('#modal button[type="submit"]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.locator('#import-orders').click();page.locator('#advanced-import').click()
                page.locator('#modal textarea').fill(json.dumps(orders));page.locator('#modal button[type="submit"]').click()
                page.locator('#modal').wait_for(state='hidden')
                assert app.store.snapshot()['totals']['purchases']==1
                page.locator('#import-ads').click()
                for k,v in dict(day='2026-10-06',spend='200',impressions='1000',clicks='100',source='TEST ONLY').items():
                    page.locator(f'#modal [name="{k}"]').fill(v)
                page.locator('#modal button[type="submit"]').click()
                page.locator('#modal').wait_for(state='hidden')
                assert app.store.snapshot()['totals']['profit']==235.8
                page.locator('.nav[data-view="overview"]').click()
                assert '236' in page.locator('.kpi-value').all_text_contents()[3]
                assert page.locator('#analyze').is_enabled()
                assert app.store.snapshot()['data_sources']['ad_records']==1
                page.locator('.metric-help summary').click()
                assert page.locator('.help-grid').is_visible()
                page.set_viewport_size({'width':390,'height':844})
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                # Consent SDK sends nothing before consent and cannot send purchases.
                page.add_script_tag(url=base+'/tracker.js')
                result=page.evaluate("async () => {window.KlimanwavesConfig={endpoint:'https://test.example/api/track'}; return await Klimanwaves.track('product_view');}")
                assert result['skipped']
                for view in ['actions','knowledge','leads','settings','audit']:
                    page.locator(f'.nav[data-view="{view}"]').click()
                    assert page.locator('#view').inner_text()
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                assert not errors,errors
                browser.close()
                print('PASS: empty-data guidance, source explanation, login, product create/edit, experiment, approval, simple order/ad forms, advanced deduplicated import, economics, help, 9 views, mobile, consent SDK. Temporary test data removed.')
        finally:
            server.shutdown();server.server_close()


if __name__=='__main__':main()
