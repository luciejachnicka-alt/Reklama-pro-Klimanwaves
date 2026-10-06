"""Small API-first single-tenant server. TLS/auth proxy required for production."""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .store import Store, dump

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'app' / 'static'


def local_secret(path):
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            value = secrets.token_urlsafe(48)
            f.write(value)
        return value


class Application:
    def __init__(self, data_dir, shop_origin='https://819636.myshoptet.com', public_origin=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.chmod(0o700)
        self.store = Store(self.data_dir / 'marketing.sqlite3')
        self.admin_token = os.environ.get('APP_ADMIN_TOKEN') or local_secret(self.data_dir / 'admin-token')
        if len(self.admin_token) < 32:
            raise ValueError('APP_ADMIN_TOKEN musí mít alespoň 32 znaků.')
        self.session_key = local_secret(self.data_dir / 'session-key').encode()
        self.shop_origin = shop_origin.rstrip('/')
        self.public_origin = public_origin.rstrip('/') if public_origin else None
        self.rate_lock = threading.Lock()
        self.rates = {}

    def password_record(self):
        try:
            return json.loads((self.data_dir / 'password.json').read_text())
        except FileNotFoundError:
            return None

    def password_valid(self, password):
        if not isinstance(password, str) or not 1 <= len(password) <= 256:
            return False
        record = self.password_record()
        if not record:
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(record['salt']),
                                n=16384, r=8, p=1).hex()
        return hmac.compare_digest(digest, record['hash'])

    def set_password(self, password):
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError('Heslo musí mít 12 až 256 znaků. Můžete použít delší větu.')
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
        target = self.data_dir / 'password.json'
        temp = self.data_dir / ('password-' + secrets.token_hex(16))
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(dict(salt=salt.hex(), hash=digest), f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)

    def signing_key(self):
        record = self.password_record()
        return self.session_key + (record['hash'].encode() if record else b'')

    def session(self):
        payload = str(int(time.time()) + 8*3600) + '.' + secrets.token_hex(16)
        return payload + '.' + hmac.new(self.signing_key(),payload.encode(),hashlib.sha256).hexdigest()

    def session_valid(self, value):
        try:
            expiry, nonce, signature = value.split('.')
            expected = hmac.new(self.signing_key(),(expiry+'.'+nonce).encode(),hashlib.sha256).hexdigest()
            return int(expiry) > time.time() and hmac.compare_digest(signature,expected)
        except (ValueError,TypeError):
            return False

    def rate(self, key, maximum):
        with self.rate_lock:
            current = int(time.time() // 60)
            self.rates = {k:v for k,v in self.rates.items() if v[0] == current}
            bucket, count = self.rates.get(key, (current,0))
            self.rates[key] = (bucket,count+1)
            return count < maximum


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'Klimanwaves/0.1'

        def log_message(self, fmt, *args):
            # Never record query strings, request bodies, tokens, or personal information.
            print(f'{self.command} {urlsplit(self.path).path} {args[1] if len(args)>1 else ""}', flush=True)

        def send(self, status, data, content_type='application/json; charset=utf-8', cookie=None, cors=False):
            body = dump(data).encode() if content_type.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if cookie:
                self.send_header('Set-Cookie',cookie)
            if cors:
                self.send_header('Access-Control-Allow-Origin',app.shop_origin)
                self.send_header('Vary','Origin')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            auth = self.headers.get('Authorization','')
            if auth.startswith('Bearer ') and hmac.compare_digest(auth[7:],app.admin_token):
                return True
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie',''))
                return 'kw_session' in cookie and app.session_valid(cookie['kw_session'].value)
            except Exception:
                return False

        def same_origin(self):
            origin = self.headers.get('Origin')
            expected = app.public_origin or ('http://' + self.headers.get('Host',''))
            return origin is None or origin == expected

        def json_body(self):
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                raise ValueError('Požadován Content-Type application/json.')
            try:
                size = int(self.headers.get('Content-Length','0'))
            except ValueError:
                raise ValueError('Neplatná délka požadavku.') from None
            if size < 1 or size > 1024*1024:
                raise ValueError('Požadavek musí mít 1 B až 1 MB.')
            data = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Neplatné číslo.')))
            if not isinstance(data,dict):
                raise ValueError('Požadován JSON objekt.')
            return data

        def do_OPTIONS(self):
            if urlsplit(self.path).path != '/api/track' or self.headers.get('Origin') != app.shop_origin:
                return self.send(403,dict(error='Nepovolený origin.'))
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin',app.shop_origin)
            self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Content-Type')
            self.send_header('Vary','Origin')
            self.end_headers()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/health':
                return self.send(200,dict(status='ok',version='0.1.0'))
            if path == '/api/auth/status':
                return self.send(200,dict(password_set=app.password_record() is not None))
            if path == '/api/state':
                if not self.authorized():
                    return self.send(401,dict(error='Přihlaste se do aplikace.'))
                return self.send(200,app.store.snapshot())
            if path == '/api/integrations':
                if not self.authorized():
                    return self.send(401,dict(error='Přihlášení vyžadováno.'))
                return self.send(200,dict(integrations=[
                    dict(name='Shoptet',status='not_connected',capability='Běžný Shoptet: API propojení vyžaduje schválený doplněk. Aplikace jej zatím nemá. Nyní podporuje ruční zadávání dat; přímý import Shoptet exportů zatím není implementován.', docs='https://developers.shoptet.com/api/'),
                    dict(name='GA4',status='not_connected',capability='Vlastní consent-aware tracker. Odesílání do GA4 není implementováno.',docs='https://developers.google.com/analytics/devguides/collection/protocol/ga4'),
                    dict(name='Google Ads',status='not_connected',capability='Ruční import spend, impressions a clicks. OAuth a publikace vyžadují další fázi.',docs='https://developers.google.com/google-ads/api/docs/oauth/overview'),
                    dict(name='Merchant API',status='not_connected',capability='Produktový feed a OAuth vyžadují další fázi.',docs='https://developers.google.com/merchant/api/overview'),
                    dict(name='Meta Ads',status='not_connected',capability='Ruční import dat. Marketing API a oprávnění vyžadují další fázi.',docs='https://developers.facebook.com/docs/marketing-apis/'),
                    dict(name='AI model',status='not_connected',capability='MVP používá transparentní pravidla nad vlastními daty. Generování kreativ modelem není implementováno.',docs='https://platform.openai.com/docs')]))
            files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css','/tracker.js':'tracker.js'}
            if path not in files:
                return self.send(404,dict(error='Nenalezeno.'))
            name=files[path]
            mime='text/html; charset=utf-8' if name.endswith('html') else 'text/css; charset=utf-8' if name.endswith('css') else 'text/javascript; charset=utf-8'
            return self.send(200,(STATIC/name).read_bytes(),mime)

        def do_POST(self):
            path=urlsplit(self.path).path
            try:
                if path == '/api/track':
                    if self.headers.get('Origin') != app.shop_origin:
                        return self.send(403,dict(error='Nepovolený origin.'))
                    if not app.rate(('track',self.client_address[0]),600):
                        return self.send(429,dict(error='Limit událostí.'),cors=True)
                    return self.send(200,app.store.track(self.json_body()),cors=True)
                if not self.same_origin():
                    return self.send(403,dict(error='Nepovolený origin.'))
                if path == '/api/login':
                    if not app.rate(('login',self.client_address[0]),10):
                        return self.send(429,dict(error='Příliš mnoho pokusů. Zkuste to za minutu.'))
                    data = self.json_body()
                    value = data.get('token', '')
                    valid_token = isinstance(value,str) and hmac.compare_digest(value,app.admin_token)
                    if not (valid_token or app.password_valid(data.get('password', ''))):
                        return self.send(401,dict(error='Přihlášení se nezdařilo. Zkontrolujte heslo nebo přístupový klíč.'))
                    secure='; Secure' if app.public_origin and app.public_origin.startswith('https://') else ''
                    return self.send(200,dict(ok=True),cookie='kw_session='+app.session()+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+secure)
                if not self.authorized():
                    return self.send(401,dict(error='Přihlášení vyžadováno.'))
                if path == '/api/logout':
                    return self.send(200,dict(ok=True),cookie='kw_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                data=self.json_body()
                if path == '/api/auth/password':
                    if not app.rate(('password', self.client_address[0]), 10):
                        return self.send(429,dict(error='Příliš mnoho pokusů. Zkuste to za minutu.'))
                    recovery = data.get('token', '')
                    valid_recovery = isinstance(recovery, str) and hmac.compare_digest(recovery, app.admin_token)
                    if app.password_record() and not (valid_recovery or app.password_valid(data.get('current_password', ''))):
                        return self.send(401,dict(error='Pro změnu zadejte současné heslo nebo obnovovací klíč.'))
                    if data.get('password') != data.get('confirmation'):
                        raise ValueError('Zadaná hesla se neshodují.')
                    app.set_password(data.get('password'))
                    secure = '; Secure' if app.public_origin and app.public_origin.startswith('https://') else ''
                    return self.send(200,dict(ok=True),cookie='kw_session='+app.session()+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+secure)
                routes = {'/api/products':app.store.product,'/api/experiments':app.store.experiment,
                          '/api/import/orders':app.store.import_orders,'/api/import/ads':app.store.import_ads,
                          '/api/actions':app.store.create_action,'/api/settings':app.store.update_settings,
                          '/api/leads':app.store.lead,'/api/leads/confirm':app.store.confirm_lead}
                if path in routes:
                    result=routes[path](data)
                elif path == '/api/analyze':
                    result=app.store.analyze()
                elif path.startswith('/api/actions/') and path.endswith('/decision'):
                    result=app.store.decide(path.split('/')[3],data)
                elif path.startswith('/api/products/') and path.endswith('/update'):
                    result=app.store.update_product(path.split('/')[3],data)
                elif path.startswith('/api/leads/') and path.endswith('/delete'):
                    result=app.store.delete_lead(path.split('/')[3])
                else:
                    return self.send(404,dict(error='Nenalezeno.'))
                self.send(200,result)
            except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as e:
                message=str(e) if isinstance(e,ValueError) else 'Neplatná nebo chybějící data; zkontrolujte ID a povinná pole.'
                self.send(400,dict(error=message),cors=path=='/api/track')
            except Exception:
                # Details stay out of responses and logs to avoid exposing customer data.
                self.send(500,dict(error='Interní chyba. Operace nebyla potvrzena.'))
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--data-dir',default=str(ROOT/'.local'))
    args=parser.parse_args()
    if args.host not in {'127.0.0.1','localhost','::1'} and not os.environ.get('APP_PUBLIC_ORIGIN'):
        parser.error('Pro veřejný bind nastavte APP_PUBLIC_ORIGIN a použijte HTTPS reverzní proxy.')
    app=Application(args.data_dir,os.environ.get('SHOP_ORIGIN','https://819636.myshoptet.com'),os.environ.get('APP_PUBLIC_ORIGIN'))
    server=ThreadingHTTPServer((args.host,args.port),handler(app))
    stop=threading.Event()
    def scheduler():
        while not stop.wait(3600):
            try:
                app.store.analyze()
            except Exception:
                print('Plánovaná analýza selhala; spusťte kontrolu ručně.',flush=True)
    threading.Thread(target=scheduler,daemon=True).start()
    print(f'Klimanwaves spuštěn na portu {args.port}; token je v chráněném souboru {app.data_dir}/admin-token (pokud není APP_ADMIN_TOKEN).',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set();server.server_close()


if __name__ == '__main__':
    main()
