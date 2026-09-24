from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from rest_framework_simplejwt.settings import api_settings

from apps.authentication.models import TenantMembership, DeviceSession


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login do Clinic com contexto explícito de tenant.

    Cada tenant Clinic deve representar uma única especialidade. O slug
    identifica a empresa na URL; as capabilities identificam a especialidade.
    """

    username_field = 'email'
    device_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    tenant_slug = serializers.SlugField(required=False, allow_blank=True, max_length=140)

    @staticmethod
    def _has_conflicting_clinic_capabilities(capabilities):
        capabilities = capabilities or {}
        modules = capabilities.get('modules') if isinstance(capabilities, dict) else None
        odonto = capabilities.get('odonto') is True or (
            isinstance(modules, dict) and modules.get('odonto') is True
        )
        podologia = capabilities.get('podologia') is True or (
            isinstance(modules, dict) and modules.get('podologia') is True
        )
        return odonto and podologia

    def get_token(self, user):
        token = super().get_token(user)
        tenant = getattr(self, '_login_tenant', None)
        membership = getattr(self, '_login_membership', None)
        if tenant is not None and membership is not None:
            token['tenant_id'] = tenant.id
            token['tenant_slug'] = tenant.slug
            token['ecosystem'] = 'clinic'
            token['role'] = membership.role
        return token

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        device_id = (attrs.get("device_id") or "").strip()[:64]
        tenant_slug = (attrs.get("tenant_slug") or "").strip()

        user = authenticate(username=email, password=password)

        if user is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou profissional não encontrado."))

        if not user.is_active:
            raise serializers.ValidationError(_("Essa conta está desativada."))

        memberships = (
            TenantMembership.objects
            .select_related("tenant")
            .filter(
                professional=user,
                is_active=True,
                tenant__is_active=True,
                tenant__ecosystem="clinic",
            )
        )
        if tenant_slug:
            memberships = memberships.filter(tenant__slug=tenant_slug)

        membership_count = memberships.count()
        if membership_count == 0:
            raise serializers.ValidationError(_("Usuário não possui acesso ao sistema Clinic."))
        if not tenant_slug and membership_count > 1:
            raise serializers.ValidationError(
                _("tenant_slug é obrigatório quando o profissional possui mais de uma clínica ativa.")
            )

        membership = memberships.first()
        tenant = membership.tenant
        if self._has_conflicting_clinic_capabilities(tenant.capabilities):
            raise serializers.ValidationError(
                _("O tenant Clinic possui especialidades conflitantes.")
            )

        self._login_tenant = tenant
        self._login_membership = membership

        self.user = user
        refresh = self.get_token(user)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)

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
            for session_to_close in to_close:
                session_to_close.terminate(reason="limit")
            active_count = max_sessions

        data['professional'] = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'display_name': user.display_name,
            'register_number': user.register_number,
            'specialty': user.specialty,
            'ui_theme': user.ui_theme,
            'lock_odonto_plan_after_print': user.lock_odonto_plan_after_print,
            'odonto_quote_validity_days': user.odonto_quote_validity_days,
            'phone': str(user.phone) if user.phone else '',
            'city': user.city,
            'state': user.state,
            'address': user.address,
            'number': user.number,
            'neighborhood': user.neighborhood,
            'zip_code': user.zip_code,
            'cnpj': user.cnpj,
            'capabilities': membership.tenant.capabilities,
        }
        data['tenant_id'] = membership.tenant.id
        data['tenant_slug'] = membership.tenant.slug
        data['ecosystem'] = 'clinic'
        data['role'] = membership.role
        data['capabilities'] = membership.tenant.capabilities
        data['active_sessions_count'] = active_count
        data['device_id'] = device_id

        return data
