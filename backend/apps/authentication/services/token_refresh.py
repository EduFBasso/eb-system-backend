from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.authentication.models import DeviceSession


class DeviceBoundTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        device_id = str(refresh.get("device_id") or "").strip()[:64]
        user_id = refresh.get("user_id")
        if not device_id or not user_id:
            raise InvalidToken(
                _("Refresh token sem vínculo de dispositivo.")
            )

        if not DeviceSession.objects.filter(
            professional_id=user_id,
            device_id=device_id,
            is_active=True,
        ).exists():
            raise InvalidToken(
                _("Sessão de dispositivo revogada ou inexistente.")
            )

        return super().validate(attrs)


class DeviceBoundTokenRefreshView(TokenRefreshView):
    serializer_class = DeviceBoundTokenRefreshSerializer
