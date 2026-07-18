from rest_framework import serializers

from apps.clients.models import Client
from .models import DentalArcade, Tooth, Surface, Procedure


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = [
            'id',
            'arcade',
            'tooth',
            'surface',
            'external_item_id',
            'code',
            'name',
            'status',
            'region_raw',
            'faces_raw',
            'started_at',
            'completed_at',
            'patient_amount',
            'paid_amount',
            'paid_at',
            'duration_minutes',
            'notes',
            'is_active',
            'is_product',
            'parent_procedure',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        # On partial updates, fall back to the existing instance values when a
        # field is not present in the incoming payload.
        instance = self.instance
        arcade = attrs.get('arcade', getattr(instance, 'arcade', None))
        tooth = attrs.get('tooth', getattr(instance, 'tooth', None))
        surface = attrs.get('surface', getattr(instance, 'surface', None))
        is_product = attrs.get('is_product', getattr(instance, 'is_product', False))
        parent_procedure = attrs.get(
            'parent_procedure',
            getattr(instance, 'parent_procedure', None),
        )
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if arcade is not None and getattr(user, 'id', None):
            if arcade.professional_id != user.id:
                raise serializers.ValidationError(
                    {'arcade': 'Arcada nao pertence ao profissional autenticado.'}
                )

        if tooth is not None and arcade is not None:
            if tooth.arcade_id != arcade.id:  # pyright: ignore[reportAttributeAccessIssue]
                raise serializers.ValidationError(
                    {'tooth': 'O dente nao pertence a arcada informada.'}
                )

        if surface is not None and arcade is not None:
            if surface.tooth.arcade_id != arcade.id:  # pyright: ignore[reportAttributeAccessIssue]
                raise serializers.ValidationError(
                    {'surface': 'A face nao pertence a arcada informada.'}
                )

        if surface is not None and tooth is not None:
            if surface.tooth_id != tooth.id:  # pyright: ignore[reportAttributeAccessIssue]
                raise serializers.ValidationError(
                    {'surface': 'A face nao pertence ao dente informado.'}
                )

        if parent_procedure is not None:
            if arcade is not None and parent_procedure.arcade_id != arcade.id:
                raise serializers.ValidationError(
                    {
                        'parent_procedure': (
                            'O procedimento pai nao pertence a arcada informada.'
                        )
                    }
                )
            if parent_procedure.is_product:
                raise serializers.ValidationError(
                    {
                        'parent_procedure': (
                            'Produto nao pode ser vinculado a outro produto.'
                        )
                    }
                )

        if is_product:
            if parent_procedure is None:
                raise serializers.ValidationError(
                    {
                        'parent_procedure': (
                            'Produto deve ser vinculado a um procedimento pai.'
                        )
                    }
                )
            if tooth is not None:
                raise serializers.ValidationError(
                    {
                        'tooth': (
                            'Produto nao pode ser salvo diretamente em um dente; '
                            'vincule-o a um procedimento.'
                        )
                    }
                )
            if surface is not None:
                raise serializers.ValidationError(
                    {
                        'surface': (
                            'Produto nao pode ser salvo diretamente em uma face.'
                        )
                    }
                )
        elif parent_procedure is not None:
            raise serializers.ValidationError(
                {
                    'parent_procedure': (
                        'Apenas produtos podem ser vinculados a um procedimento pai.'
                    )
                }
            )

        return attrs


class SurfaceSerializer(serializers.ModelSerializer):
    procedures = ProcedureSerializer(many=True, read_only=True)

    class Meta:
        model = Surface
        fields = [
            'id',
            'tooth',
            'code',
            'label',
            'created_at',
            'updated_at',
            'procedures',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'procedures']


class ToothSerializer(serializers.ModelSerializer):
    surfaces = SurfaceSerializer(many=True, read_only=True)

    class Meta:
        model = Tooth
        fields = [
            'id',
            'arcade',
            'sequence',
            'international_number',
            'external_arcade_row_id',
            'observations',
            'anomalies_bitmap',
            'created_at',
            'updated_at',
            'surfaces',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'surfaces']


class DentalArcadeListSerializer(serializers.ModelSerializer):
    pending_procedures = serializers.SerializerMethodField()
    completed_procedures = serializers.SerializerMethodField()

    class Meta:
        model = DentalArcade
        fields = [
            'id',
            'client',
            'external_treatment_id',
            'status',
            'started_at',
            'completed_at',
            'pending_procedures',
            'completed_procedures',
            'updated_at',
        ]

    def get_pending_procedures(self, obj: DentalArcade) -> int:
        return obj.procedures.filter(status=Procedure.Status.PENDING).count()  # pyright: ignore[reportAttributeAccessIssue]

    def get_completed_procedures(self, obj: DentalArcade) -> int:
        return obj.procedures.filter(status=Procedure.Status.COMPLETED).count()  # pyright: ignore[reportAttributeAccessIssue]


class DentalArcadeDetailSerializer(serializers.ModelSerializer):
    teeth = ToothSerializer(many=True, read_only=True)

    class Meta:
        model = DentalArcade
        fields = [
            'id',
            'client',
            'external_treatment_id',
            'status',
            'started_at',
            'completed_at',
            'notes',
            'created_at',
            'updated_at',
            'teeth',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'teeth']


class DentalArcadeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DentalArcade
        fields = [
            'id',
            'client',
            'external_treatment_id',
            'status',
            'started_at',
            'completed_at',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_client(self, value: Client) -> Client:
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or value.professional_id != user.id:  # pyright: ignore[reportAttributeAccessIssue]
            raise serializers.ValidationError(
                'Cliente nao pertence ao profissional autenticado.',
            )
        return value


class ProcedureBulkStatusSerializer(serializers.Serializer):
    procedure_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    status = serializers.ChoiceField(choices=Procedure.Status.choices)
    completed_at = serializers.DateField(required=False, allow_null=True)
