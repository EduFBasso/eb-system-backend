from apps.clients.serializers import ClientSerializer, ClientBasicSerializer
from .serializers_professionals import (
    ProfessionalSerializer,
    ProfessionalBasicSerializer
)
from .serializers_auth import CustomTokenObtainPairSerializer
from rest_framework import serializers
from .models import ProfessionalSettings
from typing import Any, Dict


class ProfessionalSettingsSerializer(serializers.ModelSerializer):
    def validate_work_start_hour(self, value: int) -> int:
        if not (0 <= value <= 23):
            raise serializers.ValidationError("work_start_hour deve estar entre 0 e 23")
        return value

    def validate_work_start_minute(self, value: int) -> int:
        if not (0 <= value <= 59):
            raise serializers.ValidationError("work_start_minute deve estar entre 0 e 59")
        return value

    def validate_work_end_hour(self, value: int) -> int:
        if not (1 <= value <= 24):
            raise serializers.ValidationError("work_end_hour deve estar entre 1 e 24")
        return value

    def validate_work_end_minute(self, value: int) -> int:
        if not (0 <= value <= 59):
            raise serializers.ValidationError("work_end_minute deve estar entre 0 e 59")
        return value

    def validate_slot_minutes(self, value: int) -> int:
        if value not in (5, 10, 15, 20, 30, 45, 60, 90, 120):
            raise serializers.ValidationError(
                "slot_minutes inválido. Use um dos valores: 5, 10, 15, 20, 30, 45, 60, 90, 120"
            )
        return value

    def validate_default_duration_minutes(self, value: int) -> int:
        if value not in (30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360):
            raise serializers.ValidationError(
                "default_duration_minutes inválido. Use um dos valores: 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360"
            )
        return value

    def validate_default_visit_type(self, value: str) -> str:
        if value not in ("consulta", "avaliacao", "retorno", "procedimento", "outro"):
            raise serializers.ValidationError(
                "default_visit_type inválido. Use consulta, avaliacao, retorno, procedimento ou outro"
            )
        return value

    def validate_reminder_minutes_before(self, value: int) -> int:
        if not (1 <= value <= 1440):
            raise serializers.ValidationError(
                "reminder_minutes_before deve estar entre 1 e 1440 minutos."
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        instance = getattr(self, 'instance', None)
        start = attrs.get('work_start_hour', getattr(instance, 'work_start_hour', 8))
        start_minute = attrs.get(
            'work_start_minute', getattr(instance, 'work_start_minute', 0)
        )
        end = attrs.get('work_end_hour', getattr(instance, 'work_end_hour', 18))
        end_minute = attrs.get('work_end_minute', getattr(instance, 'work_end_minute', 0))
        if end == 24 and end_minute != 0:
            raise serializers.ValidationError({
                'work_end_minute': ['work_end_minute deve ser 0 quando work_end_hour for 24']
            })
        start_total = (start * 60) + start_minute
        end_total = (end * 60) + end_minute
        if start_total >= end_total:
            raise serializers.ValidationError({
                'non_field_errors': [
                    'Intervalo inválido: o início deve ser menor que o fim do expediente'
                ]
            })
        return attrs
    class Meta:
        model = ProfessionalSettings
        fields = [
            "work_start_hour",
            "work_start_minute",
            "work_end_hour",
            "work_end_minute",
            "slot_minutes",
            "default_duration_minutes",
            "default_visit_type",
            "confirm_message_enabled",
            "confirm_message_template",
            "pix_key_type",
            "pix_key_value",
            "reminder_enabled",
            "reminder_minutes_before",
        ]
