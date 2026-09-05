import random
import string
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from rest_framework import filters, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.authentication.models import Professional, Tenant, TenantMembership
from apps.bakery.models import BakeryCustomer, BakeryCustomerAuditLog
from apps.bakery.serializers import BakeryCustomerSerializer
from utils.cep_lookup import lookup_via_cep
from utils.pagination import StandardResultsSetPagination
from utils.permissions import HasActiveBakeryTenant, IsBakeryOwner, IsCustomerOrAdmin, get_active_tenant

from .base import BakeryTenantScopedMixin


class BakeryCustomerViewSet(BakeryTenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = BakeryCustomerSerializer
    permission_classes = (HasActiveBakeryTenant, IsCustomerOrAdmin)
    pagination_class = StandardResultsSetPagination
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("nickname", "company_name", "cpf", "cnpj", "phone")
    ordering_fields = ("nickname", "status", "created_at", "credit_limit")
    ordering = ("nickname",)
    queryset = BakeryCustomer.objects.select_related("tenant", "user")

    def _is_owner(self) -> bool:
        if getattr(self.request.user, "is_staff", False):
            return True
        membership = getattr(self, "bakery_membership", None)
        if membership:
            return membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
        from utils.permissions import _get_bakery_membership
        m = _get_bakery_membership(self.request)
        return bool(m and m.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN))

    def get_queryset(self):
        tenant = self.get_active_tenant()
        queryset = super().get_queryset().filter(tenant=tenant)
        if not self._is_owner():
            queryset = queryset.filter(user=self.request.user)

        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def perform_create(self, serializer):
        tenant = self.get_active_tenant()
        user = serializer.validated_data.get("user")
        if not self._is_owner() or user is None:
            user = self.request.user
        serializer.save(tenant=tenant, user=user)

    @staticmethod
    def _build_customer_email(tenant_id: int, phone: str) -> str:
        digits = ''.join(ch for ch in str(phone or '') if ch.isdigit())
        return f'bakery-customer+t{tenant_id}-p{digits}@local.invalid'

    @staticmethod
    def _password_cache_key(customer_id: int) -> str:
        return f'bakery:customer:{customer_id}:plain-password'

    @staticmethod
    def _generate_password(length: int = 8) -> str:
        alphabet = string.ascii_letters + string.digits
        return ''.join(random.choice(alphabet) for _ in range(length))

    @staticmethod
    def _normalize_secret_input(value) -> str:
        # Defensive: copy/paste on mobile/desktop can include hidden unicode chars.
        return ''.join(ch for ch in str(value or '') if ch not in '\u00A0\u200B\u200C\u200D\u2060\uFEFF').strip()

    def _require_admin_password(self, request):
        membership = getattr(self, "bakery_membership", None)
        if membership is None:
            from utils.permissions import _get_bakery_membership
            membership = _get_bakery_membership(request)
        is_management = bool(
            (membership and membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN))
            or getattr(request.user, "is_staff", False)
        )
        if not is_management:
            return Response(
                {'detail': 'Apenas o owner ou administrador pode executar esta ação.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        admin_password = self._normalize_secret_input(
            request.data.get('admin_password') or request.data.get('password')
        )
        if not admin_password:
            return Response(
                {'detail': 'admin_password é obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.check_password(admin_password):
            return Response(
                {'detail': 'Senha do administrador incorreta.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return None

    @staticmethod
    def _parse_credit_limit(raw_value):
        try:
            limit = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if limit <= Decimal('0'):
            return None
        return limit

    def _resolve_registration_tenant(self, request) -> Tenant | None:
        if getattr(request, "user", None) and request.user.is_authenticated:
            try:
                tenant = get_active_tenant(request.user, self.capability_name)
                if tenant:
                    return tenant
            except Exception:
                pass

        tenant_slug = (
            request.data.get("tenant_slug")
            or request.headers.get("X-Tenant-Slug")
            or request.query_params.get("tenant_slug")
        )
        if tenant_slug:
            tenant = (
                Tenant.objects.filter(
                    slug=str(tenant_slug).strip(),
                    is_active=True,
                )
                .first()
            )
            if tenant and (
                tenant.ecosystem == Tenant.Ecosystem.BAKERY
                or tenant.has_capability(self.capability_name)
            ):
                return tenant

        bakery_tenants = Tenant.objects.filter(
            is_active=True,
            ecosystem=Tenant.Ecosystem.BAKERY,
        )
        if bakery_tenants.count() == 1:
            return bakery_tenants.first()

        return None

    @action(
        detail=False,
        methods=["post"],
        url_path="register",
        permission_classes=[AllowAny],
    )
    @transaction.atomic
    def register(self, request):
        tenant = self._resolve_registration_tenant(request)
        if tenant is None:
            return Response(
                {'detail': 'Tenant Bakery não encontrado ou inativo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.active_tenant = tenant

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = str(serializer.validated_data.get('phone') or '')
        nickname = str(serializer.validated_data.get('nickname') or 'Cliente').strip() or 'Cliente'
        if TenantMembership.objects.filter(
            tenant=tenant,
            login_alias__iexact=nickname,
        ).exists():
            return Response(
                {'detail': 'Já existe um cliente com este apelido neste tenant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_user, _created = Professional.objects.get_or_create(
            email=self._build_customer_email(tenant.id, phone),
            defaults={
                'first_name': nickname[:50],
                'last_name': 'Bakery',
                'is_staff': False,
                'is_active': True,
            },
        )

        membership, _membership_created = TenantMembership.objects.get_or_create(
            tenant=tenant,
            professional=customer_user,
            defaults={
                'role': TenantMembership.Role.MEMBER,
                'is_active': True,
                'login_alias': nickname,
            },
        )
        if not membership.login_alias:
            membership.login_alias = nickname
        if not membership.is_active:
            membership.is_active = True
        membership.save(update_fields=['login_alias', 'is_active', 'updated_at'])

        try:
            customer = serializer.save(tenant=tenant, user=customer_user)
        except IntegrityError:
            return Response(
                {'detail': 'Não foi possível concluir o cadastro. Verifique se este cliente já existe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.bakery.services.notifications import notify_owner_new_customer
        transaction.on_commit(lambda: notify_owner_new_customer(customer))

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], url_path='approve')
    @transaction.atomic
    def approve_customer(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        if customer.status == BakeryCustomer.ApprovalStatus.APPROVED:
            return Response({'detail': 'Cliente já está aprovado.'}, status=status.HTTP_400_BAD_REQUEST)

        credit_limit = self._parse_credit_limit(request.data.get('credit_limit'))
        if credit_limit is None:
            return Response(
                {'detail': 'Limite de crédito inválido. Informe um valor maior que zero.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password_plain_text = str(request.data.get('password') or '').strip() or self._generate_password()

        customer.user.set_password(password_plain_text)
        customer.user.save(update_fields=['password'])

        previous_status = customer.status
        customer.status = BakeryCustomer.ApprovalStatus.APPROVED
        customer.approved_by = request.user
        customer.approved_at = timezone.now()
        customer.credit_limit = credit_limit
        customer.save(update_fields=['status', 'approved_by', 'approved_at', 'credit_limit', 'updated_at'])

        cache.set(self._password_cache_key(customer.id), password_plain_text, timeout=60 * 60 * 24 * 30)

        BakeryCustomerAuditLog.objects.create(
            tenant=customer.tenant,
            customer=customer,
            action=BakeryCustomerAuditLog.Action.APPROVED,
            admin_user=request.user,
            details={
                'previous_status': previous_status,
                'new_status': customer.status,
                'credit_limit': str(credit_limit),
            },
        )

        payload = self.get_serializer(customer).data
        payload['password_plain_text'] = password_plain_text
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    @transaction.atomic
    def reject_pending_customer(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        if customer.status != BakeryCustomer.ApprovalStatus.PENDING:
            return Response(
                {'detail': 'Apenas cadastros pendentes podem ser recusados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_id = customer.id
        nickname = customer.nickname
        customer_user = customer.user

        try:
            customer.delete()
        except ProtectedError:
            return Response(
                {'detail': 'Não foi possível remover este cadastro por vínculos existentes.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache.delete(self._password_cache_key(customer_id))

        # Limpa o usuário técnico quando ele não é mais usado por nenhum perfil bakery.
        if (
            customer_user
            and customer_user.email.endswith('@local.invalid')
            and not customer_user.bakery_customer_profiles.exists()
        ):
            customer_user.delete()

        return Response(
            {
                'detail': 'Cadastro pendente recusado e removido permanentemente.',
                'deleted_customer_id': customer_id,
                'nickname': nickname,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='update-credit-limit')
    @transaction.atomic
    def update_credit_limit(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        credit_limit = self._parse_credit_limit(request.data.get('credit_limit'))
        if credit_limit is None:
            return Response(
                {'detail': 'Limite de crédito inválido. Informe um valor maior que zero.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_credit_limit = customer.credit_limit
        customer.credit_limit = credit_limit
        customer.save(update_fields=['credit_limit', 'updated_at'])

        BakeryCustomerAuditLog.objects.create(
            tenant=customer.tenant,
            customer=customer,
            action=BakeryCustomerAuditLog.Action.CREDIT_LIMIT_UPDATED,
            admin_user=request.user,
            details={
                'previous_credit_limit': str(previous_credit_limit),
                'new_credit_limit': str(customer.credit_limit),
            },
        )

        return Response(self.get_serializer(customer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='set-password')
    @transaction.atomic
    def set_password(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        password_plain_text = str(request.data.get('password') or '').strip() or self._generate_password()

        customer.user.set_password(password_plain_text)
        customer.user.save(update_fields=['password'])
        cache.set(self._password_cache_key(customer.id), password_plain_text, timeout=60 * 60 * 24 * 30)

        return Response(
            {
                'detail': 'Senha definida com sucesso.',
                'password_plain_text': password_plain_text,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='reveal-password')
    def reveal_password(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        password_plain_text = cache.get(self._password_cache_key(customer.id))
        if not password_plain_text:
            # Compatibilidade operacional: clientes aprovados antes deste fluxo
            # podem não ter senha cacheada. Geramos uma nova senha sob confirmação
            # do admin para manter continuidade do atendimento.
            password_plain_text = self._generate_password()
            customer.user.set_password(password_plain_text)
            customer.user.save(update_fields=['password'])
            cache.set(self._password_cache_key(customer.id), password_plain_text, timeout=60 * 60 * 24 * 30)

            return Response(
                {
                    'password_plain_text': password_plain_text,
                    'detail': 'Nova senha gerada para o cliente, pois a senha anterior não estava disponível.',
                },
                status=status.HTTP_200_OK,
            )

        return Response({'password_plain_text': password_plain_text}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='block')
    @transaction.atomic
    def block_customer(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        previous_status = customer.status

        customer.status = BakeryCustomer.ApprovalStatus.BLOCKED
        customer.blocked_by = request.user
        customer.blocked_at = timezone.now()
        customer.save(update_fields=['status', 'blocked_by', 'blocked_at', 'updated_at'])

        BakeryCustomerAuditLog.objects.create(
            tenant=customer.tenant,
            customer=customer,
            action=BakeryCustomerAuditLog.Action.BLOCKED,
            admin_user=request.user,
            details={
                'previous_status': previous_status,
                'new_status': customer.status,
                'reason': request.data.get('reason') or 'Bloqueado via painel administrativo',
            },
        )

        return Response(self.get_serializer(customer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='unblock')
    @transaction.atomic
    def unblock_customer(self, request, pk=None):
        denied = self._require_admin_password(request)
        if denied is not None:
            return denied

        customer = self.get_object()
        previous_status = customer.status

        customer.status = BakeryCustomer.ApprovalStatus.APPROVED
        customer.blocked_by = None
        customer.blocked_at = None
        customer.save(update_fields=['status', 'blocked_by', 'blocked_at', 'updated_at'])

        BakeryCustomerAuditLog.objects.create(
            tenant=customer.tenant,
            customer=customer,
            action=BakeryCustomerAuditLog.Action.UNBLOCKED,
            admin_user=request.user,
            details={
                'previous_status': previous_status,
                'new_status': customer.status,
                'reason': request.data.get('reason') or 'Desbloqueado via painel administrativo',
            },
        )

        return Response(self.get_serializer(customer).data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="lookup-cep",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def lookup_cep(self, request):
        zip_code = request.data.get("zip_code") or request.data.get("cep") or ""
        result = lookup_via_cep(str(zip_code))

        if result is None:
            return Response(
                {"detail": "CEP não encontrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "street": result.street,
                "neighborhood": result.neighborhood,
                "city": result.city,
                "state": result.state,
                "zip_code": result.zip_code,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        previous = self.get_object()
        previous_status = previous.status
        previous_credit_limit = previous.credit_limit
        customer = serializer.save(tenant=self.get_active_tenant(), user=previous.user)

        action = None
        details = {}
        if customer.status != previous_status:
            if customer.status == BakeryCustomer.ApprovalStatus.APPROVED:
                action = BakeryCustomerAuditLog.Action.APPROVED
            elif customer.status == BakeryCustomer.ApprovalStatus.BLOCKED:
                action = BakeryCustomerAuditLog.Action.BLOCKED
            elif previous_status == BakeryCustomer.ApprovalStatus.BLOCKED:
                action = BakeryCustomerAuditLog.Action.UNBLOCKED
            details["previous_status"] = previous_status
            details["new_status"] = customer.status
        elif customer.credit_limit != previous_credit_limit:
            action = BakeryCustomerAuditLog.Action.CREDIT_LIMIT_UPDATED
            details["previous_credit_limit"] = str(previous_credit_limit)
            details["new_credit_limit"] = str(customer.credit_limit)

        if action:
            BakeryCustomerAuditLog.objects.create(
                tenant=self.get_active_tenant(),
                customer=customer,
                action=action,
                admin_user=self.request.user,
                details=details,
            )