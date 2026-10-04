from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.settings import api_settings

from apps.authentication.models import TenantMembership
from apps.authentication.models import Tenant
from apps.authentication.services.device_sessions import (
    activate_login_session,
    resolve_device_id,
)
from apps.authentication.services.login_identity import resolve_login_email


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login do Clinic com contexto explícito de tenant.

    Cada tenant Clinic deve representar uma única especialidade. O slug
    identifica a empresa na URL; as capabilities identificam a especialidade.
    """

    username_field = 'login'
    login = serializers.CharField(write_only=True)
    device_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    tenant_slug = serializers.SlugField(max_length=140)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("email", None)

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
        device_id = getattr(self, "_login_device_id", None)
        if tenant is not None and membership is not None:
            token['tenant_id'] = tenant.id
            token['tenant_slug'] = tenant.slug
            token['ecosystem'] = 'clinic'
            token['role'] = membership.role
        if device_id:
            token["device_id"] = device_id
        return token

    def validate(self, attrs):
        login = attrs.get("login", "").strip()
        password = attrs.get("password")
        device_id = (attrs.get("device_id") or "").strip()[:64]
        tenant_slug = (attrs.get("tenant_slug") or "").strip()
        request = self.context.get("request")

        if not login or not password:
            raise serializers.ValidationError(_("login e password são obrigatórios."))

        try:
            tenant = Tenant.objects.get(
                slug=tenant_slug,
                is_active=True,
                ecosystem=Tenant.Ecosystem.CLINIC,
            )
        except Tenant.DoesNotExist:
            raise serializers.ValidationError(_("Tenant Clinic não encontrado ou inativo."))

        memberships = (
            TenantMembership.objects
            .select_related("tenant", "professional")
            .filter(
                is_active=True,
                tenant__is_active=True,
                tenant__ecosystem=Tenant.Ecosystem.CLINIC,
            )
        )
        memberships = memberships.filter(tenant=tenant)
        email = resolve_login_email(login, tenant)
        if not email:
            raise serializers.ValidationError(_("Credenciais inválidas ou usuário não encontrado."))
        membership = memberships.filter(professional__email__iexact=email).first()
        if membership is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou usuário não encontrado."))

        user = authenticate(
            username=membership.professional.email,
            password=password,
            request=request,
        )

        if user is None:
            raise serializers.ValidationError(_("Credenciais inválidas ou profissional não encontrado."))

        if not user.is_active:
            raise serializers.ValidationError(_("Essa conta está desativada."))

        membership = TenantMembership.objects.select_related("tenant").get(
            pk=membership.pk,
        )
        tenant = membership.tenant
        if self._has_conflicting_clinic_capabilities(tenant.capabilities):
            raise serializers.ValidationError(
                _("O tenant Clinic possui especialidades conflitantes.")
            )

        self._login_tenant = tenant
        self._login_membership = membership

        device_id = resolve_device_id(device_id, user)
        ua = ""
        ip = None
        if request is not None:
            ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]
            ip = request.META.get("REMOTE_ADDR")
        active_count = activate_login_session(
            user,
            device_id,
            user_agent=ua,
            ip_address=ip,
        )

        self._login_device_id = device_id
        self.user = user
        refresh = self.get_token(user)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)

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
