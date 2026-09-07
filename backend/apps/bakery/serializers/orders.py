from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.bakery.models import (
    BakeryCustomer,
    CreditLedgerEntry,
    Order,
    OrderItem,
    Product,
)
from apps.bakery.services.notifications import notify_owner_new_order


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "tenant",
            "name",
            "description",
            "price",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "created_at", "updated_at")


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=Product.objects.all(),
    )
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "tenant",
            "order",
            "product_id",
            "product_name",
            "quantity",
            "unit_price",
            "subtotal",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "tenant",
            "order",
            "unit_price",
            "subtotal",
            "created_at",
            "updated_at",
        )


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    admin_password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    customer_password = serializers.CharField(write_only=True, required=False, allow_blank=False)


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(Order.Status.CONFIRMED, Order.Status.DELIVERED),
    )
    admin_password = serializers.CharField(write_only=True, allow_blank=False)


class OrderSerializer(serializers.ModelSerializer):
    order_number = serializers.SerializerMethodField()
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=BakeryCustomer.objects.all(),
    )
    customer_nickname = serializers.CharField(source="customer.nickname", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = OrderItemInputSerializer(many=True, write_only=True, required=False)
    order_items = OrderItemSerializer(source="items", many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "tenant",
            "customer_id",
            "customer_nickname",
            "status",
            "status_display",
            "delivery_date",
            "shipping_zip_code",
            "shipping_street",
            "shipping_number",
            "shipping_complement",
            "shipping_neighborhood",
            "shipping_city",
            "shipping_state",
            "payment_method",
            "paid_at",
            "notes",
            "total_value",
            "cancellation_reason",
            "cancelled_at",
            "items",
            "order_items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "tenant",
            "status",
            "paid_at",
            "total_value",
            "cancellation_reason",
            "cancelled_at",
            "created_at",
            "updated_at",
        )

    def get_order_number(self, obj: Order) -> str:
        return str(obj.pk)

    def validate(self, attrs):
        request = self.context.get("request")
        tenant = self.context.get("tenant")
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        items = attrs.get("items")

        if tenant is None:
            raise serializers.ValidationError("Active Bakery tenant is required.")
        if customer and customer.tenant_id != tenant.id:
            raise serializers.ValidationError({"customer_id": "Customer belongs to another tenant."})
        if (
            customer
            and request
            and not request.user.is_staff
            and customer.user_id != request.user.id
        ):
            raise serializers.ValidationError({"customer_id": "Customer does not belong to this user."})
        if self.instance is None and not items:
            raise serializers.ValidationError({"items": "At least one order item is required."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        item_payloads = validated_data.pop("items")
        tenant = validated_data["tenant"]
        requested_customer = validated_data.pop("customer")
        customer = BakeryCustomer.objects.select_for_update().get(
            pk=requested_customer.pk,
            tenant=tenant,
        )

        product_ids = [item["product_id"] for item in item_payloads]
        products = {
            product.id: product
            for product in Product.objects.filter(
                tenant=tenant,
                id__in=product_ids,
                is_active=True,
            )
        }
        if len(products) != len(set(product_ids)):
            raise serializers.ValidationError({"items": "One or more products are unavailable."})

        total = sum(
            (
                products[item["product_id"]].price * Decimal(item["quantity"])
                for item in item_payloads
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

        if not customer.is_approved:
            raise serializers.ValidationError({"customer_id": "Customer is not approved."})
        if (
            validated_data.get("payment_method") == Order.PaymentMethod.CREDIT
            and not customer.can_reserve_credit(total)
        ):
            raise serializers.ValidationError(
                {"items": "Order total exceeds the available credit."}
            )

        order = Order.objects.create(customer=customer, **validated_data)
        for item in item_payloads:
            OrderItem.objects.create(
                tenant=tenant,
                order=order,
                product=products[item["product_id"]],
                quantity=item["quantity"],
            )
        order.refresh_from_db(fields=["total_value"])

        if order.payment_method == Order.PaymentMethod.CREDIT:
            CreditLedgerEntry.objects.create(
                tenant=tenant,
                customer=customer,
                order=order,
                entry_type=CreditLedgerEntry.EntryType.DEBIT,
                amount=order.total_value,
                description=f"Credit reservation for order #{order.pk}",
                reference_key=f"order:{order.pk}:debit",
            )
        transaction.on_commit(lambda: notify_owner_new_order(order))
        return order

    def update(self, instance, validated_data):
        if "items" in validated_data:
            raise serializers.ValidationError(
                {"items": "Order items cannot be changed through the order endpoint."}
            )
        return super().update(instance, validated_data)