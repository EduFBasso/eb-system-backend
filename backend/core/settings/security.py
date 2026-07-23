"""
Segurança: CSRF e cabeçalhos HTTPS obrigatórios em produção.
O bloco SECURE_* só é ativado quando DEBUG=False e fora de CI.
"""
from decouple import config

from ._helpers import DEBUG, _IN_CI, _csv

# === CSRF ===

CSRF_TRUSTED_ORIGINS: list[str] = _csv("CSRF_TRUSTED_ORIGINS", "")

# === Segurança HTTPS (Produção) ===

if not DEBUG and not _IN_CI:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
