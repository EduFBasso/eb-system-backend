"""
Configuração do banco de dados: PostgreSQL em produção, SQLite em testes/CI.
Inclui guarda contra conexão acidental com DB remoto em modo DEBUG.
"""
import os

from decouple import config

from ._helpers import BASE_DIR, DEBUG, _IN_CI  # noqa: F401

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
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='clinic'),
            'USER': config('DB_USER', default='clinic'),
            'PASSWORD': config('DB_PASSWORD', default='clinic'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
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
