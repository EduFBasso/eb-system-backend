from typing import Any, cast

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.tenancy.permissions import HasTenantCapability

from .models import (
    DentalArcade,
    Tooth,
    Surface,
    Procedure,
    ProcedureNameSuggestion,
    ProductCatalogItem,
)
from .serializers import (
    DentalArcadeDetailSerializer,
    DentalArcadeListSerializer,
    DentalArcadeWriteSerializer,
    ProcedureBulkStatusSerializer,
    ProcedureSerializer,
    SurfaceSerializer,
    ToothSerializer,
)


def _refresh_arcade_status(arcade: DentalArcade) -> None:
    """Recalcula o status da arcada com base nos procedimentos ativos.

    Regra: se todos os procedimentos ativos (is_active=True) estiverem
    concluidos ou cancelados (nenhum PENDING), a arcada passa a COMPLETED.
    Se houver ao menos um PENDING, a arcada volta para PENDING.
    Sem procedimentos ativos, o status nao e alterado.
    """
    active_procs = arcade.procedures.filter(is_active=True)  # pyright: ignore[reportAttributeAccessIssue]
    total = active_procs.count()
    if total == 0:
        return
    pending_count = active_procs.filter(status=Procedure.Status.PENDING).count()
    if pending_count == 0:
        arcade.status = DentalArcade.Status.COMPLETED
        if not arcade.completed_at:
            arcade.completed_at = timezone.now().date()
    else:
        arcade.status = DentalArcade.Status.PENDING
        arcade.completed_at = None
    arcade.save(update_fields=['status', 'completed_at'])


class ProfessionalScopedMixin:
    permission_classes = [permissions.IsAuthenticated, HasTenantCapability('odonto')]

    def current_user(self) -> Any:
        request = cast(Any, getattr(self, 'request', None))
        return getattr(request, 'user', None)

    def current_user_id(self) -> int | None:
        return getattr(self.current_user(), 'id', None)


class DentalArcadeViewSet(ProfessionalScopedMixin, viewsets.ModelViewSet):
    queryset = DentalArcade.objects.select_related('client', 'professional')

    def get_queryset(self):
        user_id = self.current_user_id()
        if not user_id:
            return super().get_queryset().none()
        qs = super().get_queryset().filter(professional_id=user_id)

        client_id = self.request.query_params.get('client')
        status_param = self.request.query_params.get('status')
        if client_id:
            qs = qs.filter(client_id=client_id)
        if status_param:
            qs = qs.filter(status=status_param)

        if self.action == 'retrieve':
            qs = qs.prefetch_related(
                Prefetch(
                    'teeth',
                    queryset=Tooth.objects.prefetch_related(
                        Prefetch(
                            'surfaces',
                            queryset=Surface.objects.prefetch_related('procedures'),
                        )
                    ),
                )
            )

        return qs

    def get_serializer_class(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        if self.action == 'list':
            return DentalArcadeListSerializer
        if self.action == 'retrieve':
            return DentalArcadeDetailSerializer
        return DentalArcadeWriteSerializer

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(professional=self.current_user())

    @action(detail=True, methods=['post'], url_path='initialize-default-structure')
    def initialize_default_structure(self, request, pk=None):
        """
        Cria estrutura basica da arcada com 32 dentes e 5 faces por dente.
        Pode ser chamada uma vez por arcada; chamadas repetidas nao duplicam.
        """
        arcade = self.get_object()

        international_numbers = [
            18, 17, 16, 15, 14, 13, 12, 11,
            21, 22, 23, 24, 25, 26, 27, 28,
            48, 47, 46, 45, 44, 43, 42, 41,
            31, 32, 33, 34, 35, 36, 37, 38,
        ]
        surface_codes = ['O', 'PO', 'MO', 'VO', 'LDI']

        created_teeth = 0
        created_surfaces = 0

        for sequence, international_number in enumerate(international_numbers, start=1):
            tooth, tooth_created = Tooth.objects.get_or_create(
                arcade=arcade,
                sequence=sequence,
                defaults={'international_number': international_number},
            )
            if tooth_created:
                created_teeth += 1

            for code in surface_codes:
                _, surface_created = Surface.objects.get_or_create(
                    tooth=tooth,
                    code=code,
                    defaults={'label': code},
                )
                if surface_created:
                    created_surfaces += 1

        return Response(
            {
                'arcade_id': arcade.id,
                'created_teeth': created_teeth,
                'created_surfaces': created_surfaces,
            },
            status=status.HTTP_200_OK,
        )


class ToothViewSet(ProfessionalScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ToothSerializer
    queryset = Tooth.objects.select_related('arcade').all()

    def get_queryset(self):
        user_id = self.current_user_id()
        if not user_id:
            return super().get_queryset().none()
        qs = super().get_queryset().filter(arcade__professional_id=user_id)
        arcade_id = self.request.query_params.get('arcade')
        if arcade_id:
            qs = qs.filter(arcade_id=arcade_id)
        return qs


class SurfaceViewSet(ProfessionalScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = SurfaceSerializer
    queryset = Surface.objects.select_related('tooth', 'tooth__arcade').all()

    def get_queryset(self):
        user_id = self.current_user_id()
        if not user_id:
            return super().get_queryset().none()
        qs = super().get_queryset().filter(tooth__arcade__professional_id=user_id)
        tooth_id = self.request.query_params.get('tooth')
        if tooth_id:
            qs = qs.filter(tooth_id=tooth_id)
        return qs


class ProcedureViewSet(ProfessionalScopedMixin, viewsets.ModelViewSet):
    serializer_class = ProcedureSerializer
    queryset = Procedure.objects.select_related('arcade', 'tooth', 'surface').all()

    def get_queryset(self):
        user_id = self.current_user_id()
        if not user_id:
            return super().get_queryset().none()
        qs = super().get_queryset().filter(arcade__professional_id=user_id)

        arcade_id = self.request.query_params.get('arcade')
        status_param = self.request.query_params.get('status')
        if arcade_id:
            qs = qs.filter(arcade_id=arcade_id)
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        payload = cast(dict[str, Any], serializer.validated_data)
        arcade = payload.get('arcade')
        if arcade is None:
            raise PermissionDenied('Arcada invalida para criacao do procedimento.')
        if arcade.professional_id != self.current_user_id():
            raise PermissionDenied('Arcada nao pertence ao profissional autenticado.')
        instance = serializer.save()
        _refresh_arcade_status(instance.arcade)

    def perform_update(self, serializer: BaseSerializer) -> None:
        instance = serializer.save()
        _refresh_arcade_status(instance.arcade)

    @action(detail=False, methods=['get'], url_path='distinct-names')
    def distinct_names(self, request):
        """
        Retorna lista de nomes únicos de procedimentos do usuário autenticado.
        Opcionalmente filtra por arcade_id via query param.
        Retorna: {"names": ["Nome 1", "Nome 2", ...]}
        """
        proc_qs = self.get_queryset().filter(
            name__isnull=False,
            name__gt='',  # apenas nomes não vazios
        ).values_list('name', flat=True).distinct().order_by('name')

        suggestion_qs = ProcedureNameSuggestion.objects.filter(
            professional_id=self.current_user_id(),
            name__isnull=False,
            name__gt='',
        ).values_list('name', flat=True)

        names = sorted(set(proc_qs).union(set(suggestion_qs)), key=str.lower)
        return Response({'names': names}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='suggest-name')
    def suggest_name(self, request):
        """
        Salva um novo nome de procedimento na lista de sugestões.
        Cria um procedimento vazio (apenas com nome) para registrar a sugestão.
        
        Body: {"name": "Novo Procedimento", "arcade_id": 123}
        Retorna: {"id": procedure_id, "name": "Novo Procedimento", "message": "..."}
        """
        payload = request.data
        name = payload.get('name', '').strip() if payload else ''
        arcade_id = payload.get('arcade_id')

        if not name:
            return Response(
                {'error': 'Nome do procedimento é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar se o arcade pertence ao usuário
        if arcade_id:
            try:
                arcade = DentalArcade.objects.get(
                    id=arcade_id,
                    professional_id=self.current_user_id(),
                )
            except DentalArcade.DoesNotExist:
                raise PermissionDenied('Arcada nao pertence ao profissional autenticado.')
        else:
            return Response(
                {'error': 'arcade_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar se o nome já existe (case-insensitive) em qualquer fonte
        existing_proc = Procedure.objects.filter(
            arcade__professional=self.current_user(),
            name__iexact=name,
        ).first()
        existing_suggestion = ProcedureNameSuggestion.objects.filter(
            professional_id=self.current_user_id(),
            name__iexact=name,
        ).first()

        existing = existing_suggestion or existing_proc

        if existing:
            return Response(
                {
                    'message': 'Este nome já existe na lista.',
                    'id': existing.id,
                    'name': existing.name,
                },
                status=status.HTTP_200_OK,
            )

        # Criar sugestao isolada de procedimento (sem poluir tabela Procedure)
        try:
            suggestion = ProcedureNameSuggestion.objects.create(
                professional=self.current_user(),
                name=name,
            )
            return Response(
                {
                    'message': f'Nome "{name}" adicionado à lista de sugestões.',
                    'id': suggestion.id,
                    'name': suggestion.name,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {'error': f'Erro ao salvar sugestão: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['get'], url_path='products/distinct-names')
    def products_distinct_names(self, request):
        """
        Retorna catalogo de produtos: nome + ultimo valor utilizado.
        Opcionalmente filtra por arcade_id via query param.
        Retorna: {"catalog": [{"name": "Botox", "last_value": "150.00"}, ...]}
        """
        proc_qs = self.get_queryset().filter(
            is_product=True,
            name__isnull=False,
            name__gt='',
        )

        proc_names = set(
            proc_qs.values_list('name', flat=True).distinct().order_by('name')
        )
        catalog_qs = ProductCatalogItem.objects.filter(
            professional_id=self.current_user_id(),
            name__isnull=False,
            name__gt='',
        )
        catalog_names = set(catalog_qs.values_list('name', flat=True))

        all_names = sorted(proc_names.union(catalog_names), key=str.lower)

        catalog = []
        for name in all_names:
            item = catalog_qs.filter(name__iexact=name).order_by('-id').first()
            if item and item.last_value is not None:
                last_value = str(item.last_value)
            else:
                last_proc = proc_qs.filter(name__iexact=name).order_by('-id').first()
                last_value = (
                    str(last_proc.patient_amount)
                    if last_proc and last_proc.patient_amount is not None
                    else None
                )
            catalog.append({'name': name, 'last_value': last_value})

        return Response({'catalog': catalog})

    @action(detail=False, methods=['post'], url_path='products/suggest-name')
    def products_suggest_name(self, request):
        """
        Salva ou atualiza um produto na lista de sugestões (catalogo).
        Aceita valor opcional para persistir o ultimo preco utilizado.

        Body: {"name": "Botox", "arcade_id": 123, "value": "150.00"}
        Retorna: {"id": ..., "name": ..., "message": "..."}
        """
        from decimal import Decimal, InvalidOperation

        payload = request.data
        name = payload.get('name', '').strip() if payload else ''
        arcade_id = payload.get('arcade_id')
        raw_value = payload.get('value')

        if not name:
            return Response(
                {'error': 'Nome do produto é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if arcade_id:
            try:
                arcade = DentalArcade.objects.get(
                    id=arcade_id,
                    professional_id=self.current_user_id(),
                )
            except DentalArcade.DoesNotExist:
                raise PermissionDenied('Arcada nao pertence ao profissional autenticado.')
        else:
            return Response(
                {'error': 'arcade_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        patient_amount = None
        if raw_value is not None:
            try:
                patient_amount = Decimal(str(raw_value).replace(',', '.'))
            except (InvalidOperation, ValueError):
                pass

        existing = ProductCatalogItem.objects.filter(
            professional_id=self.current_user_id(),
            name__iexact=name,
        ).order_by('-id').first()

        if existing:
            update_fields = []
            if patient_amount is not None:
                existing.last_value = patient_amount
                update_fields.append('last_value')
            if update_fields:
                existing.save(update_fields=update_fields)
            return Response(
                {
                    'message': 'Catalogo de produto atualizado.',
                    'id': existing.id,
                    'name': existing.name,
                },
                status=status.HTTP_200_OK,
            )

        try:
            prod = ProductCatalogItem.objects.create(
                professional=self.current_user(),
                name=name,
                last_value=patient_amount,
            )
            return Response(
                {
                    'message': f'Produto "{name}" adicionado ao catálogo.',
                    'id': prod.id,
                    'name': prod.name,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {'error': f'Erro ao salvar produto: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'], url_path='bulk-status')
    def bulk_status(self, request):
        serializer = ProcedureBulkStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = cast(dict[str, Any], serializer.validated_data)

        procedure_ids = payload['procedure_ids']
        new_status = payload['status']
        completed_at = payload.get('completed_at')

        qs = self.get_queryset().filter(id__in=procedure_ids)

        # Collect affected arcades before the bulk update
        arcade_ids = list(qs.values_list('arcade_id', flat=True).distinct())

        update_data: dict[str, Any] = {'status': new_status}
        if new_status == Procedure.Status.COMPLETED:
            update_data['completed_at'] = completed_at
        else:
            update_data['completed_at'] = None

        updated_count = qs.update(**update_data)

        # Recalculate status for each affected arcade
        for arcade_obj in DentalArcade.objects.filter(
            id__in=arcade_ids,
            professional_id=self.current_user_id(),
        ):
            _refresh_arcade_status(arcade_obj)

        return Response(
            {'updated': updated_count, 'status': new_status},
            status=status.HTTP_200_OK,
        )
