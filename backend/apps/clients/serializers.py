from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import timezone as dt_timezone
from apps.clients.models import Client
from apps.anamnesis.models import AnamneseBase, AnamnesePodologia
import unicodedata, re

# Helpers de normalização (UF/CEP)
def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

_UF_MAP = {
    'ac':'AC','al':'AL','ap':'AP','am':'AM','ba':'BA','ce':'CE','df':'DF','es':'ES','go':'GO','ma':'MA',
    'mt':'MT','ms':'MS','mg':'MG','pa':'PA','pb':'PB','pr':'PR','pe':'PE','pi':'PI','rj':'RJ','rn':'RN',
    'rs':'RS','ro':'RO','rr':'RR','sc':'SC','se':'SE','sp':'SP','to':'TO',
    'acre':'AC','alagoas':'AL','amapa':'AP','amazonas':'AM','bahia':'BA','ceara':'CE','distrito federal':'DF',
    'espirito santo':'ES','goias':'GO','maranhao':'MA','mato grosso':'MT','mato grosso do sul':'MS',
    'minas gerais':'MG','para':'PA','paraiba':'PB','parana':'PR','pernambuco':'PE','piaui':'PI',
    'rio de janeiro':'RJ','rio grande do norte':'RN','rio grande do sul':'RS','rondonia':'RO',
    'roraima':'RR','santa catarina':'SC','sergipe':'SE','sao paulo':'SP','são paulo':'SP','tocantins':'TO',
}

def _normalize_uf(value: str) -> str:
    raw = (value or '').strip()
    if not raw:
        return ''
    if len(raw) == 2 and raw.upper() in _UF_MAP.values():
        return raw.upper()
    key = _strip_accents(raw).lower()
    key = re.sub(r'\s+', ' ', key).strip()
    if key in _UF_MAP:
        return _UF_MAP[key]
    raise serializers.ValidationError("Estado inválido. Use a sigla (ex.: SP) ou o nome completo do estado.")

def _normalize_cep(value: str) -> str:
    raw = (value or '').strip()
    if not raw:
        return ''
    digits = re.sub(r'\D+', '', raw)
    if len(digits) == 8:
        return digits
    raise serializers.ValidationError("CEP inválido. Use 8 dígitos (ex.: 13480460).")


class AnamneseBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnamneseBase
        fields = [
            'id',
            'takes_medication',
            'had_surgery',
            'is_pregnant',
            'pain_sensitivity',
            'clinical_history',
            'sport_activity',
            'academic_activity',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AnamnesePodologiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnamnesePodologia
        fields = [
            'id',
            'footwear_used',
            'sock_used',
            'plantar_view_left',
            'plantar_view_right',
            'dermatological_pathologies_left',
            'dermatological_pathologies_right',
            'nail_changes_left',
            'nail_changes_right',
            'deformities_left',
            'deformities_right',
            'sensitivity_test',
            'other_procedures',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


def _active_anamnese_tenant(context) -> object:
    tenant = context.get('tenant')
    if tenant is not None:
        return tenant

    request = context.get('request')
    user = getattr(request, 'user', None)
    if user is None:
        raise serializers.ValidationError('Usuário autenticado é obrigatório para gravar anamnese.')

    membership = (
        user.tenant_memberships.select_related('tenant')
        .filter(is_active=True, tenant__is_active=True)
        .order_by('created_at', 'id')
        .first()
    )
    if membership is None:
        raise serializers.ValidationError('Nenhum tenant ativo encontrado para o usuário autenticado.')
    return membership.tenant

class ClientSerializer(serializers.ModelSerializer):
    professional = serializers.PrimaryKeyRelatedField(read_only=True)
    tenant = serializers.PrimaryKeyRelatedField(read_only=True)
    anamnese_base = AnamneseBaseSerializer(required=False, allow_null=True)
    anamnese_podologia = AnamnesePodologiaSerializer(required=False, allow_null=True)

    class Meta:
        model = Client
        fields = [
            'id',
            'tenant',
            'professional',
            'first_name',
            'last_name',
            'email',
            'phone',
            'rg',
            'document_type',
            'document_number',
            'sex',
            'marital_status',
            'nationality',
            'profession',
            'address',
            'neighborhood',
            'city',
            'state',
            'postal_code',
            'date_of_birth',
            'address_number',
            'address_complement',
            'created_at',
            'updated_at',
            'anamnese_base',
            'anamnese_podologia',
        ]
        read_only_fields = ['id', 'tenant', 'professional', 'created_at', 'updated_at']
        extra_kwargs = {
            "email": {"required": False, "allow_null": True, "allow_blank": True},
            # Telefone obrigatório e único (modelo aplica unique)
            "phone": {"required": True, "allow_null": False, "allow_blank": False},
            "profession": {"required": False, "allow_null": True, "allow_blank": True},
            "city": {"required": False, "allow_null": True, "allow_blank": True},
            "state": {"required": False, "allow_null": True, "allow_blank": True},
            "postal_code": {"required": False, "allow_null": True, "allow_blank": True},
            "address": {"required": False, "allow_null": True, "allow_blank": True},
            "neighborhood": {"required": False, "allow_null": True, "allow_blank": True},
            "date_of_birth": {"required": False, "allow_null": True},
            "address_number": {"required": False, "allow_null": True, "allow_blank": True},
            "address_complement": {"required": False, "allow_null": True, "allow_blank": True},
            # Campos pessoais adicionais
            "rg": {"required": False, "allow_null": True, "allow_blank": True},
            "document_type": {"required": False, "allow_null": True, "allow_blank": True},
            "document_number": {"required": False, "allow_null": True, "allow_blank": True},
            "sex": {"required": False, "allow_null": True, "allow_blank": True},
            "marital_status": {"required": False, "allow_null": True, "allow_blank": True},
            "nationality": {"required": False, "allow_null": True, "allow_blank": True},
        }

    # Normalizações e validações leves
    def validate_first_name(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError("Nome é obrigatório")
        return v

    def validate_last_name(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError("Sobrenome é obrigatório")
        return v

    def validate_email(self, value):
        if value is None:
            return None
        v = value.strip()
        return v.lower() if v else None

    def validate_phone(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError("Telefone é obrigatório")
        # Normaliza para apenas dígitos; aceita 10 (fixo) ou 11 (celular) no BR
        digits = ''.join(ch for ch in v if ch.isdigit())
        if len(digits) not in (10, 11):
            raise serializers.ValidationError(
                "Telefone inválido. Use DDD + número (10 ou 11 dígitos)."
            )
        return digits

    # cpf removido; profissão agora é um texto opcional
    # Normalizações adicionais
    def validate_state(self, value: str) -> str:
        if value in (None, ''):
            return ''
        return _normalize_uf(value)

    def validate_postal_code(self, value: str) -> str:
        if value in (None, ''):
            return ''
        return _normalize_cep(value)

    def _save_nested_anamneses(self, client: Client, base_data, podologia_data) -> None:
        tenant = _active_anamnese_tenant(self.context)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        def _clean_payload(payload):
            if payload is None:
                return None
            cleaned = {key: value for key, value in payload.items() if value is not None}
            return cleaned or None

        base_payload = _clean_payload(base_data)
        podologia_payload = _clean_payload(podologia_data)

        with transaction.atomic():
            if base_payload is not None:
                AnamneseBase.objects.update_or_create(
                    client=client,
                    tenant=tenant,
                    professional=user,
                    defaults=base_payload,
                )

            if podologia_payload is not None:
                AnamnesePodologia.objects.update_or_create(
                    client=client,
                    tenant=tenant,
                    professional=user,
                    defaults=podologia_payload,
                )

    def create(self, validated_data):
        anamnese_base_data = validated_data.pop('anamnese_base', None)
        anamnese_podologia_data = validated_data.pop('anamnese_podologia', None)
        tenant = _active_anamnese_tenant(self.context)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        with transaction.atomic():
            client = Client.objects.create(
                tenant=tenant,
                professional=user,
                **validated_data,
            )
            self._save_nested_anamneses(client, anamnese_base_data, anamnese_podologia_data)

        return client

    def update(self, instance, validated_data):
        anamnese_base_data = validated_data.pop('anamnese_base', None)
        anamnese_podologia_data = validated_data.pop('anamnese_podologia', None)
        tenant = _active_anamnese_tenant(self.context)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.tenant = tenant
        instance.professional = user

        with transaction.atomic():
            instance.save()
            self._save_nested_anamneses(instance, anamnese_base_data, anamnese_podologia_data)

        return instance


class UTCDateTimeField(serializers.DateTimeField):
    """Serializa sempre em UTC para evitar deslocamento local nos campos anotados.

    Os testes comparam diretamente com o isoformat() do valor salvo (UTC) truncando para minutos.
    DRF converte para TIME_ZONE por padrão (localtime). Forçamos UTC aqui.
    """
    def to_representation(self, value):  # value é um datetime ou None
        if value is None:
            return None
        if timezone.is_aware(value):
            value = value.astimezone(dt_timezone.utc)
        else:  # tornar aware assumindo UTC
            value = value.replace(tzinfo=dt_timezone.utc)
        return value.isoformat()


class ClientBasicSerializer(serializers.ModelSerializer):
    next_appointment_start_at = UTCDateTimeField(read_only=True)
    next_appointment_end_at = UTCDateTimeField(read_only=True)
    next_appointment_title = serializers.CharField(read_only=True)
    next_appointment_visit_type = serializers.CharField(read_only=True)
    next_appointment_notes = serializers.CharField(read_only=True, allow_null=True, allow_blank=True)
    next_appointment_status = serializers.CharField(read_only=True)
    next_appointment_id = serializers.IntegerField(read_only=True)
    last_appointment_start_at = UTCDateTimeField(read_only=True)
    last_appointment_end_at = UTCDateTimeField(read_only=True)
    last_appointment_title = serializers.CharField(read_only=True)
    last_appointment_status = serializers.CharField(read_only=True)
    last_appointment_notes = serializers.CharField(read_only=True)

    class Meta:
        model = Client
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'email',
            'address', 'address_number', 'address_complement', 'neighborhood', 'city', 'state', 'date_of_birth',
            'next_appointment_start_at', 'next_appointment_end_at', 'next_appointment_title', 'next_appointment_visit_type', 'next_appointment_notes', 'next_appointment_status',
            'next_appointment_id',
            'last_appointment_start_at', 'last_appointment_end_at', 'last_appointment_title', 'last_appointment_notes', 'last_appointment_status'
        ]
