# backend\apps\register\serializers_auth.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from apps.authentication.models import TenantMembership, DeviceSession


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'
    device_id = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        device_id = (attrs.get("device_id") or "").strip()[:64]

        user = authenticate(username=email, password=password)

        if user is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou profissional não encontrado."))

        if not user.is_active:
            raise serializers.ValidationError(_("Essa conta está desativada."))

        # Exige membership ativa em tenant Clinic
        membership = (
            TenantMembership.objects
            .select_related("tenant")
            .filter(
                professional=user,
                is_active=True,
                tenant__is_active=True,
                tenant__ecosystem="clinic",
            )
            .first()
        )
        if membership is None:
            raise serializers.ValidationError(_("Usuário não possui acesso ao sistema Clinic."))

        data = super().validate(attrs)

        # Mantém o fluxo de senha compatível com proteção por sessão de dispositivo.
        if not device_id:
            device_id = f"pwd-{user.pk}"
        request = self.context.get("request")
        ua = ""
        ip = None
        if request is not None:
            ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]
            ip = request.META.get("REMOTE_ADDR")

        session, created = DeviceSession.objects.get_or_create(
            professional=user,
            device_id=device_id,
            defaults={"user_agent": ua, "ip_address": ip, "is_active": True},
        )
        if not created:
            session.is_active = True
            session.user_agent = ua
            session.ip_address = ip
            # last_seen_at é auto_now=True, não pode entrar em update_fields
            session.save(update_fields=["is_active", "user_agent", "ip_address"])

        max_sessions = getattr(settings, "MAX_ACTIVE_DEVICE_SESSIONS", 2)
        active_qs = DeviceSession.objects.filter(professional=user, is_active=True)
        active_count = active_qs.count()
        if active_count > max_sessions:
            overflow = active_count - max_sessions
            to_close = (
                DeviceSession.objects
                .filter(professional=user, is_active=True)
                .exclude(device_id=device_id)
                .order_by("last_seen_at")[:overflow]
            )
            for s in to_close:
                s.terminate(reason="limit")
            active_count = max_sessions

        data['professional'] = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'register_number': user.register_number,
            'specialty': user.specialty,
        }
        data['tenant_id'] = membership.tenant.id
        data['ecosystem'] = 'clinic'
        data['role'] = membership.role
        data['capabilities'] = membership.tenant.capabilities
        data['active_sessions_count'] = active_count
        data['device_id'] = device_id

        return data

