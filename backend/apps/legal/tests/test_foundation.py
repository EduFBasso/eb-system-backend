import pytest
from rest_framework.test import APIClient, APIRequestFactory

from apps.authentication.models import SystemUser, Tenant, TenantMembership
from apps.legal.models import (
    LegalCase,
    LegalCaseParty,
    LegalClient,
    LegalLawyerProfile,
    LegalPerson,
    LegalRepresentation,
)
from apps.legal.serializers import (
    LegalCasePartySerializer,
    LegalClientSerializer,
    LegalLawyerProfileSerializer,
    LegalRepresentationSerializer,
)
from apps.legal.views.people import LegalLawyerProfileViewSet


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


def _legal_request(user, tenant):
    request = APIRequestFactory().patch("/")
    request.user = user
    request.auth = {"tenant_id": tenant.id, "ecosystem": Tenant.Ecosystem.LEGAL}
    return request


@pytest.mark.django_db
def test_legal_client_update_rejects_person_from_another_tenant(legal_context):
    user, tenant, _, _ = legal_context
    other_tenant = Tenant.objects.create(
        name="Outro Escritorio",
        slug="outro-escritorio",
        ecosystem=Tenant.Ecosystem.LEGAL,
        capabilities={"legal": True},
    )
    TenantMembership.objects.create(
        tenant=other_tenant,
        professional=user,
        role=TenantMembership.Role.MEMBER,
    )
    local_person = LegalPerson.objects.create(
        tenant=tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Pessoa Local",
    )
    foreign_person = LegalPerson.objects.create(
        tenant=other_tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Pessoa Estrangeira",
    )
    client = LegalClient.objects.create(
        tenant=tenant,
        created_by=user,
        person=local_person,
    )

    serializer = LegalClientSerializer(
        client,
        data={"person": foreign_person.id},
        partial=True,
        context={"request": _legal_request(user, tenant)},
    )

    assert not serializer.is_valid()
    assert "person" in serializer.errors


@pytest.mark.django_db
def test_legal_case_party_update_rejects_foreign_case_and_person(legal_context):
    user, tenant, _, _ = legal_context
    other_tenant = Tenant.objects.create(
        name="Outro Escritorio",
        slug="outro-escritorio-party",
        ecosystem=Tenant.Ecosystem.LEGAL,
        capabilities={"legal": True},
    )
    TenantMembership.objects.create(
        tenant=other_tenant,
        professional=user,
        role=TenantMembership.Role.MEMBER,
    )
    local_person = LegalPerson.objects.create(
        tenant=tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Pessoa Local",
    )
    foreign_person = LegalPerson.objects.create(
        tenant=other_tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Pessoa Estrangeira",
    )
    local_case = LegalCase.objects.create(
        tenant=tenant,
        created_by=user,
        title="Processo Local",
    )
    foreign_case = LegalCase.objects.create(
        tenant=other_tenant,
        created_by=user,
        title="Processo Estrangeiro",
    )
    party = LegalCaseParty.objects.create(
        case=local_case,
        person=local_person,
        role=LegalCaseParty.Role.PLAINTIFF,
    )

    serializer = LegalCasePartySerializer(
        party,
        data={"case": foreign_case.id, "person": foreign_person.id},
        partial=True,
        context={"request": _legal_request(user, tenant)},
    )

    assert not serializer.is_valid()
    assert "case" in serializer.errors

    person_serializer = LegalCasePartySerializer(
        party,
        data={"person": foreign_person.id},
        partial=True,
        context={"request": _legal_request(user, tenant)},
    )

    assert not person_serializer.is_valid()
    assert "person" in person_serializer.errors


@pytest.mark.django_db
def test_legal_representation_update_rejects_foreign_lawyer(legal_context):
    user, tenant, _, local_lawyer = legal_context
    other_tenant = Tenant.objects.create(
        name="Outro Escritorio",
        slug="outro-escritorio-representation",
        ecosystem=Tenant.Ecosystem.LEGAL,
        capabilities={"legal": True},
    )
    TenantMembership.objects.create(
        tenant=other_tenant,
        professional=user,
        role=TenantMembership.Role.MEMBER,
    )
    foreign_lawyer = LegalLawyerProfile.objects.create(
        tenant=other_tenant,
        system_user=user,
        oab_number="654321",
        oab_state="RJ",
        official_name="Advogado Estrangeiro",
    )
    person = LegalPerson.objects.create(
        tenant=tenant,
        person_type=LegalPerson.PersonType.INDIVIDUAL,
        name="Parte Local",
    )
    case = LegalCase.objects.create(
        tenant=tenant,
        created_by=user,
        title="Processo Local",
    )
    party = LegalCaseParty.objects.create(
        case=case,
        person=person,
        role=LegalCaseParty.Role.DEFENDANT,
    )
    representation = LegalRepresentation.objects.create(
        party=party,
        lawyer=local_lawyer,
    )

    serializer = LegalRepresentationSerializer(
        representation,
        data={"lawyer": foreign_lawyer.id},
        partial=True,
        context={"request": _legal_request(user, tenant)},
    )

    assert not serializer.is_valid()
    assert "lawyer" in serializer.errors


@pytest.mark.django_db
def test_legal_client_requires_person(legal_context):
    user, tenant, _, _ = legal_context
    serializer = LegalClientSerializer(
        data={},
        context={"request": _legal_request(user, tenant)},
    )

    assert not serializer.is_valid()
    assert "person" in serializer.errors


@pytest.mark.django_db
def test_legal_lawyer_creation_assigns_active_tenant_and_user(legal_context):
    _, tenant, _, _ = legal_context
    user = SystemUser.objects.create_user(
        email="novo-advogado@example.com",
        password="senha-segura-123",
    )
    TenantMembership.objects.create(
        tenant=tenant,
        professional=user,
        role=TenantMembership.Role.MEMBER,
    )
    request = _legal_request(user, tenant)
    view = LegalLawyerProfileViewSet()
    view.request = request
    serializer = LegalLawyerProfileSerializer(
        data={
            "oab_number": "789012",
            "oab_state": "SP",
            "official_name": "Novo Advogado",
        },
        context={"request": request},
    )

    assert serializer.is_valid(), serializer.errors
    view.perform_create(serializer)

    assert serializer.instance.tenant_id == tenant.id
    assert serializer.instance.system_user_id == user.id
