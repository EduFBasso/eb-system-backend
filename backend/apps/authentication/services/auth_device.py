"""Device-session aware JWT authentication.

Separado de authentication.py para evitar import parcial/circular quando
urls importam EmailTokenObtainPairView cedo durante bootstrap do DRF, pois
DRF também carrega DEFAULT_AUTHENTICATION_CLASSES simultaneamente.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions
from django.utils.translation import gettext_lazy as _
from .models import DeviceSession
import logging

_auth_logger = logging.getLogger('auth.device')

class JWTDeviceAuthentication(JWTAuthentication):
    """Estende JWTAuthentication validando sessão de dispositivo ativa.

    Regras:
      - Se header X-Device-Id ausente: comportamento padrão (retrocompat).
      - Se presente: deve existir DeviceSession ativa para (user, device_id).
      - Caso não exista ou esteja inativa -> AuthenticationFailed.
    """

    def authenticate(self, request):  # type: ignore[override]
        raw = request.META.get('HTTP_X_DEVICE_ID') or ''
        device_id = raw.strip()[:64]
        result = super().authenticate(request)
        if not result:
            _auth_logger.debug('JWTDeviceAuthentication: no base JWT result (no token) path=%s device=%s', getattr(request, 'path', ''), device_id)
        if not result:
            return result
        user, validated_token = result
        # Bypass device-session enforcement for session-management endpoints to allow lazy creation.
        try:
            path = getattr(request, 'path', '') or ''
            if path.startswith('/sessions/'):
                _auth_logger.debug('JWTDeviceAuthentication: bypass on sessions endpoint path=%s', path)
                return user, validated_token
        except Exception:
            pass
        if not device_id:
            _auth_logger.debug('JWTDeviceAuthentication: missing device id (bypass) user=%s', user)
            return user, validated_token
        try:
            session = DeviceSession.objects.get(professional=user, device_id=device_id)
        except DeviceSession.DoesNotExist:
            _auth_logger.info('JWTDeviceAuthentication: no session user=%s device=%s', user, device_id)
            raise exceptions.AuthenticationFailed(_('Sessão de dispositivo não encontrada.'), code='no_device_session')
        if not session.is_active:
            _auth_logger.info('JWTDeviceAuthentication: inactive session user=%s device=%s', user, device_id)
            raise exceptions.AuthenticationFailed(_('Sessão de dispositivo revogada/inativa.'), code='inactive_device_session')
        _auth_logger.debug('JWTDeviceAuthentication: ok user=%s device=%s', user, device_id)
        return user, validated_token

__all__ = ["JWTDeviceAuthentication"]
