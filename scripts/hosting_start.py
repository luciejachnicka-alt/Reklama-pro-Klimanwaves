"""Start a single-instance pilot behind the hosting provider's HTTPS proxy."""
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def hosting_settings(environment):
    origin = environment.get('APP_PUBLIC_ORIGIN')
    if not origin:
        render_origin = environment.get('RENDER_EXTERNAL_URL', '')
        parsed = urlsplit(render_origin)
        if parsed.scheme == 'https' and parsed.hostname and parsed.hostname.endswith('.onrender.com'):
            origin = render_origin
    if not origin:
        raise ValueError('Nastavte APP_PUBLIC_ORIGIN nebo použijte službu Render s RENDER_EXTERNAL_URL.')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('APP_PUBLIC_ORIGIN musí být přesná HTTPS adresa bez cesty a přihlašovacích údajů.')
    if len(environment.get('APP_ADMIN_TOKEN', '')) < 32:
        raise ValueError('V secrets hostingu nastavte APP_ADMIN_TOKEN s alespoň 32 náhodnými znaky.')
    port = int(environment.get('PORT', '8000'))
    if not 1 <= port <= 65535:
        raise ValueError('Neplatný port.')
    directory = Path(environment.get('APP_DATA_DIR', '/data'))
    if not directory.is_absolute():
        raise ValueError('APP_DATA_DIR musí být absolutní cesta na trvalém disku.')
    return origin.rstrip('/'), port, directory


def main():
    try:
        origin, port, directory = hosting_settings(os.environ)
        directory.mkdir(parents=True, exist_ok=True)
        if os.geteuid() == 0:
            # Only a dedicated app volume may be passed as APP_DATA_DIR.
            os.chown(directory, 10001, 10001)
            directory.chmod(0o700)
            os.setgroups([])
            os.setgid(10001)
            os.setuid(10001)
        os.environ['APP_PUBLIC_ORIGIN'] = origin
        os.execv(sys.executable, [sys.executable, '-m', 'app.server', '--host', '0.0.0.0',
                                '--port', str(port), '--data-dir', str(directory)])
    except (ValueError, OSError):
        # Do not log rejected environment-variable contents, especially secrets.
        print('Hosting nelze spustit. Zkontrolujte HTTPS adresu, správcovský secret, port a oprávnění trvalého disku.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
