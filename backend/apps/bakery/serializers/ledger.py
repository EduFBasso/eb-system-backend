from rest_framework import serializers

from apps.bakery.models import CreditLedgerEntry


class CreditLedgerEntrySerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    customer_nickname = serializers.CharField(source="customer.nickname", read_only=True)
    reference_order_id = serializers.IntegerField(source="order.id", read_only=True)
    transaction_type = serializers.CharField(source="entry_type", read_only=True)
    transaction_date = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = CreditLedgerEntry
        fields = (
            "id",
            "tenant",
            "customer_id",
            "customer_nickname",
            "entry_type",
            "transaction_type",
            "amount",
            "description",
            "order",
            "reference_order_id",
            "reference_key",
            "created_at",
            "transaction_date",
        )
        read_only_fields = fields

    def create(self, validated_data):
        raise serializers.ValidationError("Credit ledger entries are read-only.")

    def update(self, instance, validated_data):
        raise serializers.ValidationError("Credit ledger entries are read-only.")