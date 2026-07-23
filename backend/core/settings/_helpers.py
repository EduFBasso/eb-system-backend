"""
Primitivos compartilhados entre os módulos de settings.

Não importar este arquivo diretamente no __init__.py — ele é interno (_).
Cada módulo importa o que precisa com: from ._helpers import BASE_DIR, DEBUG, _csv, ...
"""
import os
from pathlib import Path

from decouple import config

# Raiz do projeto: _helpers.py → settings/ → core/ → raiz
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# Detecta ambiente de CI (GitHub Actions)
_IN_CI: bool = os.environ.get('GITHUB_ACTIONS') == 'true'

# Flags globais — usadas em múltiplos módulos de settings
DEBUG: bool = config("DEBUG", default=False, cast=bool)
DEV_ALLOW_LAN_HOSTS: bool = config("DEV_ALLOW_LAN_HOSTS", default=str(DEBUG), cast=bool)
APP_VERSION: str = config("APP_VERSION", default="dev") # type: ignore


def _str(key: str, default: str = "") -> str:
    """Lê variável de ambiente como str com tipo explícito.

    Contorna a ambiguidade nos type stubs do python-decouple, que tipam
    config() sem cast= como bool | Unknown mesmo quando o retorno é str.
    """
    return str(config(key, default=default))


def _csv(key: str, default: str = "") -> list[str]:
    """Lê variável de ambiente como lista separada por vírgula.

    Garante retorno list[str] com tipo explícito — contorna a ambiguidade
    nos type stubs do python-decouple (cast=lambda / Csv() retornam Any).
    """
    raw: str = str(config(key, default=default))
    return [s.strip() for s in raw.split(",") if s.strip()]
