import pytest
from rest_framework.test import APIClient

from apps.authentication.models import SystemUser, Tenant, TenantMembership
from apps.legal.models import (
    LegalCase,
    LegalCaseParty,
    LegalClient,
    LegalLawyerProfile,
    LegalPerson,
    LegalRepresentation,
)


@pytest.fixture
def legal_context(db):
    user = SystemUser.objects.create_user(
        email="advogado@example.com",
        password="senha-segura-123",
        first_name="Advogado",
        last_name="Legal",
    )
    tenant = Tenant.objects.create(
        name="Escritorio Legal",
        slug="escritorio-legal-foundation",
        ecosystem=Tenant.Ecosystem.LEGAL,
        capabilities={"legal": True},
    )
    membership = TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=TenantMembership.Role.OWNER,
    )
    profile = LegalLawyerProfile.objects.create(
        tenant=tenant,
        system_user=user,
        oab_number="123456",
        oab_state="SP",
        official_name="Advogado Legal",
    )
    return user, tenant, membership, profile


@pytest.mark.django_db
def test_legal_profile_and_case_allow_process_without_client(legal_context):
    user, tenant, _, profile = legal_context

    case = LegalCase.objects.create(
        tenant=tenant,
        created_by=user,
        title="Processo sem cliente cadastrado",
    )

    assert profile.oab_number == "123456"
    assert case.client is None
    assert case.tenant_id == tenant.id


@pytest.mark.django_db
def test_legal_client_belongs_to_tenant(legal_context):
    user, tenant, _, _ = legal_context
    person = LegalPerson.objects.create(
        tenant=tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Cliente Legal",
    )

    client = LegalClient.objects.create(
        tenant=tenant,
        created_by=user,
        person=person,
    )

    assert client.tenant_id == tenant.id
    assert client.person_id == person.id


@pytest.mark.django_db
def test_legal_party_role_is_separate_from_client_relationship(legal_context):
    user, tenant, _, lawyer = legal_context
    person = LegalPerson.objects.create(
        tenant=tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Pessoa Processual",
    )
    case = LegalCase.objects.create(
        tenant=tenant,
        created_by=user,
        title="Processo com partes",
    )
    party = LegalCaseParty.objects.create(
        case=case,
        person=person,
        role=LegalCaseParty.Role.DEFENDANT,
    )
    representation = LegalRepresentation.objects.create(
        party=party,
        lawyer=lawyer,
    )

    assert party.role == LegalCaseParty.Role.DEFENDANT
    assert representation.lawyer_id == lawyer.id


@pytest.mark.django_db
def test_legal_login_uses_shared_token_endpoint(legal_context):
    user, tenant, _, _ = legal_context

    response = APIClient().post(
        "/token/",
        {
            "login": user.email,
            "password": "senha-segura-123",
            "tenant_slug": tenant.slug,
            "ecosystem": "legal",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["ecosystem"] == "legal"
    assert response.data["tenant_id"] == tenant.id
    assert response.data["role"] == TenantMembership.Role.OWNER
