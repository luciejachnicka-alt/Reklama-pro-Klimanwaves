"""WSGI entry point for a hosted Python web app, including PythonAnywhere.

Uses the same routes, authentication and database as the local HTTP server.
No background thread: analysis is explicitly triggered by the operator.
"""
from email.message import Message
from http import HTTPStatus
from io import BytesIO
from urllib.parse import urlsplit

from .server import Application, handler


def create_wsgi_app(data_dir, public_origin, shop_origin='https://819636.myshoptet.com'):
    parsed = urlsplit(public_origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Veřejná adresa musí být přesný HTTPS origin bez cesty.')
    app = Application(data_dir, shop_origin, public_origin.rstrip('/'))

    class WSGIHandler(handler(app)):
        def send_response(self, code, message=None):
            self.response_status = code
            self.response_headers = []

        def send_header(self, keyword, value):
            self.response_headers.append((keyword, str(value)))

        def end_headers(self):
            pass

    def application(environ, start_response):
        request = object.__new__(WSGIHandler)
        request.command = environ.get('REQUEST_METHOD', 'GET').upper()
        request.path = environ.get('PATH_INFO') or '/'
        if environ.get('QUERY_STRING'):
            request.path += '?' + environ['QUERY_STRING']
        request.headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                request.headers[key[5:].replace('_', '-')] = str(value)
        for key, name in [('CONTENT_TYPE', 'Content-Type'), ('CONTENT_LENGTH', 'Content-Length')]:
            if environ.get(key):
                request.headers[name] = str(environ[key])
        request.rfile = environ.get('wsgi.input', BytesIO())
        request.wfile = BytesIO()
        request.client_address = (environ.get('REMOTE_ADDR', 'unknown'), 0)
        request.response_status = 500
        request.response_headers = []
        try:
            dispatch = {'GET': request.do_GET, 'HEAD': request.do_GET,
                        'POST': request.do_POST, 'OPTIONS': request.do_OPTIONS}
            if request.command in dispatch:
                dispatch[request.command]()
            else:
                request.send(405, {'error': 'Nepodporovaná metoda.'})
                request.response_headers.append(('Allow', 'GET, HEAD, POST, OPTIONS'))
        except Exception:
            # Discard any partial response; never expose request data or credentials.
            request.wfile = BytesIO()
            request.send(500, {'error': 'Interní chyba. Operace nebyla potvrzena.'})
        code = request.response_status
        start_response(f'{code} {HTTPStatus(code).phrase}', request.response_headers)
        return [b'' if request.command == 'HEAD' else request.wfile.getvalue()]

    return application
