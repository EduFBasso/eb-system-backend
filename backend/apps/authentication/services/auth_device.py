"""JWT authentication bound to an active device session."""

from __future__ import annotations

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.authentication.models import DeviceSession

_auth_logger = logging.getLogger("auth.device")


class JWTDeviceAuthentication(JWTAuthentication):
    """Require every JWT to identify an active DeviceSession."""

    def authenticate(self, request):  # type: ignore[override]
        result = super().authenticate(request)
        if not result:
            return None

        user, validated_token = result
        device_id = str(validated_token.get("device_id") or "").strip()[:64]
        if not device_id:
            _auth_logger.info(
                "JWTDeviceAuthentication: missing device claim user=%s",
                user,
            )
            raise exceptions.AuthenticationFailed(
                _("Token sem dispositivo vinculado."),
                code="missing_device_claim",
            )

        header_device_id = (
            request.META.get("HTTP_X_DEVICE_ID") or ""
        ).strip()[:64]
        if header_device_id and header_device_id != device_id:
            _auth_logger.info(
                "JWTDeviceAuthentication: device mismatch user=%s claim=%s header=%s",
                user,
                device_id,
                header_device_id,
            )
            raise exceptions.AuthenticationFailed(
                _("O dispositivo da requisição não corresponde ao token."),
                code="device_mismatch",
            )

        try:
            session = DeviceSession.objects.get(
                professional=user,
                device_id=device_id,
            )
        except DeviceSession.DoesNotExist:
            _auth_logger.info(
                "JWTDeviceAuthentication: no session user=%s device=%s",
                user,
                device_id,
            )
            raise exceptions.AuthenticationFailed(
                _("Sessão de dispositivo não encontrada."),
                code="no_device_session",
            )

        if not session.is_active:
            _auth_logger.info(
                "JWTDeviceAuthentication: inactive session user=%s device=%s",
                user,
                device_id,
            )
            raise exceptions.AuthenticationFailed(
                _("Sessão de dispositivo revogada/inativa."),
                code="inactive_device_session",
            )

        return user, validated_token


__all__ = ["JWTDeviceAuthentication"]
