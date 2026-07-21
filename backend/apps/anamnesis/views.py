from __future__ import annotations

from typing import cast

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from apps.clients.models import Client
from .models import AnamnesisField, AnamnesisResponse
from .serializers import (
    AnamnesisFieldSerializer,
    AnamnesisResponseSerializer,
    AnamnesisResponseBulkSerializer,
)


def _get_active_tenant(user):
    """Resolve the active tenant from the authenticated user's memberships."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    membership = (
        user.tenant_memberships.select_related('tenant')
        .filter(is_active=True, tenant__is_active=True)
        .order_by('created_at', 'id')
        .first()
    )
    if membership:
        return membership.tenant
    return None


class AnamnesisFieldViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns the active anamnesis fields for the authenticated professional.
    GET /anamnesis/fields/           → all active fields for this professional
    GET /anamnesis/fields/?client=5  → same (client param ignored, kept for convenience)
    """
    serializer_class = AnamnesisFieldSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[AnamnesisField]:  # type: ignore[override]
        tenant = _get_active_tenant(self.request.user)
        if tenant is None:
            return AnamnesisField.objects.none()

        return AnamnesisField.objects.filter(
            professional__tenant_memberships__tenant=tenant,
            professional__tenant_memberships__is_active=True,
            professional__tenant_memberships__tenant__is_active=True,
            is_active=True,
        ).distinct().order_by('sector_order', 'order')


class AnamnesisResponseViewSet(viewsets.ModelViewSet):
    """
    CRUD for anamnesis responses.
    GET  /anamnesis/responses/?client=5  → all responses for a client
    POST /anamnesis/responses/bulk_save/ → upsert many responses at once
    """
    serializer_class = AnamnesisResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[AnamnesisResponse]:  # type: ignore[override]
        req = cast(DRFRequest, self.request)
        tenant = _get_active_tenant(req.user)
        if tenant is None:
            return AnamnesisResponse.objects.none()

        qs = AnamnesisResponse.objects.filter(
            field__professional__tenant_memberships__tenant=tenant,
            field__professional__tenant_memberships__is_active=True,
            field__professional__tenant_memberships__tenant__is_active=True,
            client__professional__tenant_memberships__tenant=tenant,
        ).select_related('field')

        client_id = req.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)

        return qs

    @action(detail=False, methods=['post'], url_path='bulk_save')
    def bulk_save(self, request):
        """
        Upserts all anamnesis responses for a client in one request.
        Body: { "client": <id>, "responses": [{"field": <id>, "value": "..."}, ...] }
        """
        tenant = _get_active_tenant(request.user)
        if tenant is None:
            raise PermissionDenied('Nenhum tenant ativo encontrado para o usuário autenticado.')

        serializer = AnamnesisResponseBulkSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        data: dict = serializer.validated_data  # type: ignore[assignment]

        client_id = data['client']
        client = get_object_or_404(
            Client,
            pk=client_id,
            professional__tenant_memberships__tenant=tenant,
            professional__tenant_memberships__is_active=True,
            professional__tenant_memberships__tenant__is_active=True,
        )

        saved = []
        submitted_field_ids: set[int] = set()
        for item in data['responses']:
            field: AnamnesisField = item['field']
            value: str = item['value']

            submitted_field_ids.add(field.id)

            if value == '':
                AnamnesisResponse.objects.filter(
                    client=client,
                    field=field,
                ).delete()
                continue

            obj, _ = AnamnesisResponse.objects.update_or_create(
                client=client,
                field=field,
                defaults={
                    'field_label_snap': field.label,
                    'value': value,
                },
            )
            saved.append(obj)

        AnamnesisResponse.objects.filter(
            client=client,
            field__professional__tenant_memberships__tenant=tenant,
            field__professional__tenant_memberships__is_active=True,
            field__professional__tenant_memberships__tenant__is_active=True,
        ).exclude(field_id__in=submitted_field_ids).delete()

        return Response(
            AnamnesisResponseSerializer(saved, many=True).data,
            status=status.HTTP_200_OK,
        )



