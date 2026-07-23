"""
Configurações base do Django: apps, middleware, templates, i18n, arquivos estáticos.
"""
import os

from decouple import config

from ._helpers import APP_VERSION, BASE_DIR, DEBUG, DEV_ALLOW_LAN_HOSTS, _csv, _str  # noqa: F401

# === Segredo ===

SECRET_KEY: str = config("DJANGO_SECRET_KEY", default="fallback-key-only-for-dev") # type: ignore

# === Flags de funcionalidade ===

APPOINTMENT_REMINDERS_ENABLED: bool = config(
    "APPOINTMENT_REMINDERS_ENABLED", default=True, cast=bool
)
ONLINE_MUTATION_LOCK_ENABLED: bool = config(
    "ONLINE_MUTATION_LOCK_ENABLED", default=False, cast=bool
)
ONLINE_MUTATION_LOCK_METHODS: list[str] = [
    s.upper() for s in _csv("ONLINE_MUTATION_LOCK_METHODS", "PUT,PATCH,DELETE")
]
SERVE_MEDIA_FILES: bool = config("SERVE_MEDIA_FILES", default=True, cast=bool)

# === Apps Instalados ===

INSTALLED_APPS = [
    'rest_framework',
    'apps.agenda',
    'apps.anamnesis',
    'apps.clients',
    'apps.odonto',
    'apps.reminders',
    'apps.register',
    'apps.tenancy',
    'apps.inventory',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
]

AUTH_USER_MODEL = 'register.Professional'

# === Middleware ===

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'core.middleware.QueryTimingMiddleware',
    'core.middleware.OnlineMutationLockMiddleware',
    'core.middleware.VersionHeaderMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# === URLs, Templates e WSGI ===

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# === Validação de Senha ===

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# === Internacionalização ===

LOCALE_PATHS = [os.path.join(str(BASE_DIR), 'locale')]
LANGUAGE_CODE = 'pt-br'
TIME_ZONE: str = _str("TIME_ZONE", default="America/Sao_Paulo")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === Arquivos Estáticos e Media ===

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(str(BASE_DIR), 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(str(BASE_DIR), 'media')
