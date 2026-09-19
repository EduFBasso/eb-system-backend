# backend/apps/authentication/views/professional_views.py
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission, IsAdminUser
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from apps.authentication.models import Professional
from apps.authentication.serializers.serializers import (
    ProfessionalSerializer,
    ProfessionalBasicSerializer,
)
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from apps.authentication.views.clinic_professional import ClinicProfessionalActionsMixin
from apps.authentication.views.clinic_professional import (
    TELEGRAM_LINK_TOKEN_TTL_SECONDS,
    _build_telegram_link_token,
    _parse_telegram_link_token,
)


SELF_SERVICE_ACTIONS = {
    "me",
    "professional_settings",
    "telegram_link_start",
    "telegram_link_verify",
    "telegram_test_send",
}


class CanManageProfessionalDirectory(BasePermission):
    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(view, "action", None) in SELF_SERVICE_ACTIONS:
            return True
        return bool(
            getattr(request.user, "is_superuser", False)
            or getattr(request.user, "can_manage_professionals", False)
        )


@api_view(["POST"])
@permission_classes([IsAdminUser])
def professional_create(request):
    """Cria um profissional com senha para o administrador da plataforma.

    POST /register/auth/professional-create/
    """
    email = (request.data.get("email") or "").strip().lower()
    first_name = (request.data.get("first_name") or "").strip()
    last_name = (request.data.get("last_name") or "").strip()
    password = request.data.get("password") or ""

    if not email or not first_name or not last_name or not password:
        return Response(
            {"message": "email, first_name, last_name e password são obrigatórios."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if Professional.objects.filter(email__iexact=email).exists():
        return Response(
            {"message": "Já existe um profissional com este e-mail."},
            status=status.HTTP_409_CONFLICT,
        )

    professional = Professional.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        display_name=(request.data.get("display_name") or "").strip(),
        specialty=(request.data.get("specialty") or "").strip(),
        register_number=(request.data.get("register_number") or "").strip() or None,
        phone=(request.data.get("phone") or "").strip(),
        city=(request.data.get("city") or "").strip(),
        state=(request.data.get("state") or "").strip()[:2].upper(),
    )

    return Response(
        {"professional": ProfessionalSerializer(professional).data},
        status=status.HTTP_201_CREATED,
    )


class ProfessionalViewSet(ClinicProfessionalActionsMixin, ModelViewSet):
    queryset = Professional.objects.all()
    serializer_class = ProfessionalSerializer
    permission_classes = [IsAuthenticated, CanManageProfessionalDirectory]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superuser", False) or getattr(user, "can_manage_professionals", False):
            return Professional.objects.all()
        return Professional.objects.none()

    def perform_destroy(self, instance: Professional):
        # Soft delete: mark as inactive/deactivated instead of removing rows
        instance.deactivate("desativado via API")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "Profissional desativado."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reativar")
    def reactivate(self, request, pk=None):
        prof = self.get_object()
        prof.reactivate()
        return Response({"detail": "Profissional reativado."})

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Permite ao profissional autenticado visualizar/atualizar seu próprio perfil.
        GET: retorna o perfil profissional completo.
        PATCH: atualiza dados pessoais, comerciais e de contato permitidos.
        """
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)
        if request.method.lower() == "get":
            return Response(ProfessionalSerializer(user).data)
        allowed_fields = {
            "first_name", "last_name", "display_name", "register_number", "specialty",
            "phone", "address", "number", "neighborhood", "zip_code", "city", "state",
            "cnpj", "ui_theme", "lock_odonto_plan_after_print", "odonto_quote_validity_days",
        }
        payload = {k: v for k, v in request.data.items() if k in allowed_fields}
        if not payload:
            return Response({"detail": "No allowed fields to update."}, status=400)
        serializer = ProfessionalSerializer(user, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProfessionalBasicViewSet(ReadOnlyModelViewSet):
    serializer_class = ProfessionalBasicSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # O Navbar usa esta listagem antes do login. O slug delimita o tenant
        # antes de qualquer profissional ser apresentado para autenticação.
        ecosystem = self.request.query_params.get('ecosystem', 'clinic')
        if ecosystem not in {'clinic', 'bakery'}:
            ecosystem = 'clinic'
        tenant_slug = (self.request.query_params.get('tenant_slug') or '').strip()

        if ecosystem == 'clinic' and not tenant_slug:
            return Professional.objects.none()

        filters = {
            'is_superuser': False,
            'is_active': True,
            'tenant_memberships__is_active': True,
            'tenant_memberships__tenant__is_active': True,
            'tenant_memberships__tenant__ecosystem': ecosystem,
        }
        if tenant_slug:
            filters['tenant_memberships__tenant__slug'] = tenant_slug

        return (
            Professional.objects.filter(**filters)
            .exclude(email__iendswith='@local.invalid')
            .distinct()
            .order_by('first_name', 'last_name', 'id')
        )
