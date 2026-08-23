from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from apps.clinic.models.anamnesis import AnamneseOdontologia
from apps.clinic.serializers.anamnesis import DentalAnamnesisSerializer


class DentalAnamnesisViewSet(viewsets.ModelViewSet):
    """
    [SOLID - Single Responsibility Principle]
    Controlador que expõe os ganchos de API para recebimento, validação
    e armazenamento do prontuário odontológico, isolado estritamente por Tenant.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DentalAnamnesisSerializer

    def get_queryset(self):
        # [Segurança Multi-tenant] Restringe a busca apenas para dados da clínica do usuário logado
        membership = self.request.user.tenant_memberships.filter(is_active=True).first()
        if not membership:
            return AnamneseOdontologia.objects.none()
        return AnamneseOdontologia.objects.filter(anamnese_base__tenant=membership.tenant)

    def create(self, request, *args, **kwargs):
        """Sobrescreve o método de criação padrão para devolver mensagens limpas de sucesso."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response(
            {"message": "Anamnese odontológica salva com sucesso total!"},
            status=status.HTTP_201_CREATED
        )
