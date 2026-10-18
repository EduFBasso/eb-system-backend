from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.settings import api_settings

from apps.authentication.models import TenantMembership
from apps.authentication.models import Tenant
from apps.authentication.ecosystems import ecosystem_slugs
from apps.authentication.services.login_identity import resolve_login_email


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login contextualizado por Tenant para os ecossistemas operacionais."""

    username_field = 'login'
    login = serializers.CharField(write_only=True)
    tenant_slug = serializers.SlugField(max_length=140)
    ecosystem = serializers.ChoiceField(
        choices=ecosystem_slugs(),
        default=Tenant.Ecosystem.CLINIC,
        required=False,
        write_only=True,
    )

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
        if tenant is not None and membership is not None:
            token['tenant_id'] = tenant.id
            token['tenant_slug'] = tenant.slug
            token['ecosystem'] = tenant.ecosystem
            token['role'] = membership.role
        return token

    def validate(self, attrs):
        login = attrs.get("login", "").strip()
        password = attrs.get("password")
        tenant_slug = (attrs.get("tenant_slug") or "").strip()
        request = self.context.get("request")

        if not login or not password:
            raise serializers.ValidationError(_("login e password são obrigatórios."))

        ecosystem = attrs.get("ecosystem", Tenant.Ecosystem.CLINIC)
        if ecosystem == Tenant.Ecosystem.BAKERY:
            raise serializers.ValidationError(
                _(
                    "Use o endpoint de login Bakery para validar o status "
                    "específico do cliente."
                )
            )
        try:
            tenant = Tenant.objects.get(
                slug=tenant_slug,
                is_active=True,
                ecosystem=ecosystem,
            )
        except Tenant.DoesNotExist:
            raise serializers.ValidationError(
                _(f"Tenant {ecosystem} não encontrado ou inativo.")
            )

        memberships = (
            TenantMembership.objects
            .select_related("tenant", "professional")
            .filter(
                is_active=True,
                tenant__is_active=True,
                tenant__ecosystem=ecosystem,
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
        if (
            ecosystem == Tenant.Ecosystem.CLINIC
            and self._has_conflicting_clinic_capabilities(tenant.capabilities)
        ):
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
        data['ecosystem'] = tenant.ecosystem
        data['role'] = membership.role
        data['capabilities'] = membership.tenant.capabilities

        return data
