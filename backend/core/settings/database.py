"""
Configuração do banco de dados: PostgreSQL em produção, SQLite em testes/CI.
Inclui guarda contra conexão acidental com DB remoto em modo DEBUG.
"""
from django.core.exceptions import ImproperlyConfigured

from decouple import AutoConfig

from ._helpers import BASE_DIR, DEBUG, _IN_CI  # noqa: F401

config = AutoConfig(search_path=str(BASE_DIR))


def _load_local_env() -> dict[str, str]:
    """Load key=value pairs from backend/.env explicitly.

    This keeps local DB settings deterministic during Gate Zero refactor runs.
    """
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_LOCAL_ENV = _load_local_env()


def _env(key: str, default: str = '') -> str:
    local = _LOCAL_ENV.get(key)
    if local is not None and local != '':
        return local
    return str(config(key, default=default))


def _required_env(key: str) -> str:
    value = _env(key, default='').strip()
    if not value:
        raise ImproperlyConfigured(
            f"{key} must be configured (check backend/.env)."
        )
    return value

# === Banco de Dados ===

_USE_SQLITE_FOR_TESTS: bool = config('TEST_USE_SQLITE', default=False, cast=bool) or _IN_CI

if _USE_SQLITE_FOR_TESTS:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': _env('DB_ENGINE', default='django.db.backends.postgresql'),
            'NAME': _required_env('DB_NAME'),
            'USER': _required_env('DB_USER'),
            'PASSWORD': _required_env('DB_PASSWORD'),
            'HOST': _env('DB_HOST', default='127.0.0.1'),
            'PORT': _env('DB_PORT', default='5432'),
            'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
            'OPTIONS': {'options': '-c client_encoding=UTF8'},
        }
    }

ATOMIC_REQUESTS = True

# Guarda: impede conexão acidental com banco remoto enquanto DEBUG=True.
ALLOW_REMOTE_DB_IN_DEBUG: bool = config(
    "ALLOW_REMOTE_DB_IN_DEBUG", default=False, cast=bool
)
if DEBUG and not ALLOW_REMOTE_DB_IN_DEBUG:
    try:
        _db_host = DATABASES['default'].get('HOST') or ''
    except Exception:
        _db_host = ''
    if _db_host not in ("localhost", "127.0.0.1", ""):
        raise RuntimeError(
            "DEBUG=True com DB_HOST não local ('%s'). Evitando conexão acidental ao banco remoto. "
            "Defina ALLOW_REMOTE_DB_IN_DEBUG=True no .env apenas se tiver certeza." % _db_host
        )
