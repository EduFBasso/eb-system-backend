import pytest

from apps.authentication.models import Professional, Tenant
from apps.bakery.models import BakeryCustomer
from apps.bakery.serializers import BakeryCustomerSerializer


pytestmark = pytest.mark.django_db


def make_tenant(slug: str) -> Tenant:
    return Tenant.objects.create(
        name="Padaria Teste",
        trade_name="Padaria Teste",
        slug=slug,
        ecosystem=Tenant.Ecosystem.BAKERY,
        capabilities={"bakery": True},
    )


def make_customer(tenant: Tenant, nickname: str, status: str = BakeryCustomer.ApprovalStatus.PENDING):
    user = Professional.objects.create_user(
        email=f"{nickname.lower().replace(' ', '-')}@example.test",
        password="test-password",
    )
    return BakeryCustomer.objects.create(
        tenant=tenant,
        user=user,
        nickname=nickname,
        status=status,
        customer_type=BakeryCustomer.CustomerType.COMPANY,
        cnpj="12345678000195",
        phone="19999999999",
        zip_code="13000000",
        street="Rua Teste",
        number="10",
        neighborhood="Centro",
        city="Campinas",
        state="SP",
    )


def test_nickname_duplicate_is_case_and_whitespace_insensitive():
    tenant = make_tenant("padaria-nickname-duplicate")
    make_customer(tenant, "Cliente Central")

    serializer = BakeryCustomerSerializer(
        data={"nickname": "  cliente central  "},
        partial=True,
        context={"tenant": tenant},
    )

    assert not serializer.is_valid()
    assert "nickname" in serializer.errors
    assert "outro identificador" in str(serializer.errors["nickname"])


def test_approved_customer_cannot_change_nickname():
    tenant = make_tenant("padaria-nickname-approved")
    customer = make_customer(
        tenant,
        "Cliente Aprovado",
        status=BakeryCustomer.ApprovalStatus.APPROVED,
    )

    serializer = BakeryCustomerSerializer(
        customer,
        data={"nickname": "Novo Nome"},
        partial=True,
        context={"tenant": tenant},
    )

    assert not serializer.is_valid()
    assert "nickname" in serializer.errors
    assert "não pode alterar" in str(serializer.errors["nickname"])
