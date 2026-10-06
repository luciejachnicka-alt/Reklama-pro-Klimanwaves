"""Generate a secret-free WSGI configuration for an existing PythonAnywhere account."""
import argparse
from pathlib import Path
import sys
from urllib.parse import urlsplit


def wsgi_config(project_dir, data_dir, origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Použijte skutečnou HTTPS adresu webu bez cesty.')
    return (
        '# Generated configuration contains no passwords or API keys.\n'
        'import sys\n'
        f'sys.path.insert(0, {str(project_dir)!r})\n'
        'from app.wsgi import create_wsgi_app\n'
        f'application = create_wsgi_app({str(data_dir)!r}, {origin.rstrip("/")!r})\n'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', required=True, help='Actual HTTPS URL shown by your web host')
    parser.add_argument('--output', required=True, help='New configuration file; existing files are never overwritten')
    parser.add_argument('--data-dir', default=str(Path.home() / '.klimanwaves'))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    try:
        code = wsgi_config(project, Path(args.data_dir).resolve(), args.origin)
        output = Path(args.output).resolve()
        with output.open('x') as file:
            file.write(code)
        output.chmod(0o600)
        print('WSGI konfigurace vytvořena:', output)
        print('Neobsahuje hesla. Vložte její obsah do WSGI souboru zobrazeného na kartě Web hostingu.')
    except (ValueError, OSError):
        print('Konfiguraci nelze vytvořit. Zkontrolujte HTTPS adresu a novou cestu výstupního souboru.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
