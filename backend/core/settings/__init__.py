"""
Entry point do package settings — DJANGO_SETTINGS_MODULE = core.settings

Agrega todos os módulos de configuração. A ordem importa apenas para sobrescritas
intencionais (ex.: security sobrescreve valores de base em produção).
"""
from .base import *      # noqa: F401, F403
from .database import *  # noqa: F401, F403
from .auth import *      # noqa: F401, F403
from .cors import *      # noqa: F401, F403
from .email import *     # noqa: F401, F403
from .logging import *   # noqa: F401, F403
from .security import *  # noqa: F401, F403
from .services import *  # noqa: F401, F403
