from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

from app.wsgi import create_wsgi_app
from scripts.pythonanywhere_setup import wsgi_config


class WSGITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.origin = 'https://test.pythonanywhere.com'
        self.application = create_wsgi_app(self.tmp.name, self.origin)
        self.token = (Path(self.tmp.name) / 'admin-token').read_text().strip()

    def request(self, path, method='GET', data=None, cookie=None, origin=None, application=None):
        environ = {}
        setup_testing_defaults(environ)
        raw = json.dumps(data).encode() if data is not None else b''
        environ.update(PATH_INFO=path, REQUEST_METHOD=method, CONTENT_LENGTH=str(len(raw)),
                       QUERY_STRING='',
                       CONTENT_TYPE='application/json', HTTP_HOST='test.pythonanywhere.com',
                       REMOTE_ADDR='127.0.0.1', **{'wsgi.input': BytesIO(raw)})
        if cookie: environ['HTTP_COOKIE'] = cookie
        if origin: environ['HTTP_ORIGIN'] = origin
        result = {}
        def start_response(status, headers, exc_info=None):
            result.update(status=int(status.split()[0]), headers=dict(headers))
        response = validator(application or self.application)(environ, start_response)
        try: result['body'] = b''.join(response)
        finally: response.close()
        return result

    def login(self):
        result = self.request('/api/login', 'POST', {'token': self.token}, origin=self.origin)
        self.assertEqual(result['status'], 200)
        return result['headers']['Set-Cookie']

    def test_static_health_head_and_authentication(self):
        self.assertEqual(self.request('/')['status'], 200)
        self.assertEqual(self.request('/api/health')['status'], 200)
        self.assertEqual(self.request('/', 'HEAD')['body'], b'')
        self.assertEqual(self.request('/api/state')['status'], 401)
        self.assertEqual(self.request('/api/state', cookie=self.login())['status'], 200)

    def test_cookie_origin_and_unsupported_method(self):
        cookie = self.login()
        self.assertIn('Secure', cookie)
        self.assertIn('HttpOnly', cookie)
        self.assertEqual(self.request('/api/analyze', 'POST', {}, cookie, 'https://evil.example')['status'], 403)
        self.assertEqual(self.request('/', 'DELETE')['status'], 405)

    def test_tracking_preflight_and_browser_purchase_refusal(self):
        preflight = self.request('/api/track', 'OPTIONS', origin='https://819636.myshoptet.com')
        self.assertEqual(preflight['status'], 204)
        self.assertEqual(self.request('/api/track', 'POST', {'name': 'purchase'}, origin='https://819636.myshoptet.com')['status'], 400)

    def test_writes_and_session_survive_wsgi_reload(self):
        cookie = self.login()
        product = dict(name='TEST ONLY', url='https://example.com/product', source='TEST',
                       facts='TEST', economics=dict(sale_price=100, purchase_cost=20, vat_rate=0))
        self.assertEqual(self.request('/api/products', 'POST', product, cookie, self.origin)['status'], 200)
        reloaded = create_wsgi_app(self.tmp.name, self.origin)
        state = self.request('/api/state', cookie=cookie, application=reloaded)
        self.assertEqual(len(json.loads(state['body'])['products']), 1)

    def test_config_has_no_secret_and_rejects_http(self):
        code = wsgi_config('/home/test/project', '/home/test/.klimanwaves', self.origin)
        self.assertNotIn(self.token, code)
        compile(code, '<wsgi config>', 'exec')
        with self.assertRaises(ValueError): create_wsgi_app(self.tmp.name, 'http://example.com')
        with self.assertRaises(ValueError): wsgi_config('/project', '/data', 'https://example.com/path')
