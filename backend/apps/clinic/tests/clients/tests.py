from rest_framework import status
from rest_framework.test import APITestCase

from apps.clinic.models.anamnesis import (
    AnamneseBase,
    AnamnesePodologia,
)
from apps.clinic.models.clients import Client
from apps.authentication.models import Professional
from apps.authentication.models import Tenant, TenantMembership


class ClientAnamnesisApiTests(APITestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(
            name='Tenant A',
            slug='tenant-a',
            capabilities={'clinic': True, 'podologia': True},
        )
        self.tenant_b = Tenant.objects.create(
            name='Tenant B',
            slug='tenant-b',
            capabilities={'clinic': True, 'odonto': True},
        )

        self.prof_a = Professional.objects.create_user(
            email='pro.a@example.com',
            password='secret123',
            first_name='Pro',
            last_name='A',
        )
        self.prof_b = Professional.objects.create_user(
            email='pro.b@example.com',
            password='secret123',
            first_name='Pro',
            last_name='B',
        )

        # Alguns fluxos de bootstrap podem criar memberships automáticas.
        # Mantemos apenas as memberships explícitas deste teste para evitar flakiness.
        self.prof_a.tenant_memberships.all().delete()
        self.prof_b.tenant_memberships.all().delete()

        TenantMembership.objects.create(
            tenant=self.tenant_a,
            professional=self.prof_a,
            role=TenantMembership.Role.OWNER,
            is_active=True,
        )
        TenantMembership.objects.create(
            tenant=self.tenant_b,
            professional=self.prof_b,
            role=TenantMembership.Role.OWNER,
            is_active=True,
        )

    def test_post_client_with_nested_anamneses_creates_records(self):
        self.client.force_authenticate(user=self.prof_a)

        payload = {
            'first_name': 'Maria',
            'last_name': 'Silva',
            'email': 'maria.silva@example.com',
            'phone': '11999999991',
            'city': 'Campinas',
            'state': 'SP',
            'anamnese_base': {
                'takes_medication': 'Metformina',
                'had_surgery': 'Joelho',
                'is_pregnant': False,
                'pain_sensitivity': 'Moderada',
                'clinical_history': 'Paciente com histórico familiar de diabetes.',
                'sport_activity': 'Caminhada',
                'academic_activity': 'Nenhuma',
            },
            'anamnese_podologia': {
                'footwear_used': 'Tênis',
                'sock_used': 'Algodão',
                'plantar_view_left': 'Arco preservado',
                'plantar_view_right': 'Leve pronação',
                'dermatological_pathologies_left': 'Sem alterações',
                'dermatological_pathologies_right': 'Sem alterações',
                'nail_changes_left': 'Sem alterações',
                'nail_changes_right': 'Sem alterações',
                'deformities_left': 'Nenhuma',
                'deformities_right': 'Nenhuma',
                'sensitivity_test': 'Normal',
                'other_procedures': 'Nenhum',
            },
        }

        response = self.client.post('/register/clients/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('anamnese_base', response.data)
        self.assertIn('anamnese_podologia', response.data)

        created_client = Client.objects.get(id=response.data['id'])
        self.assertEqual(created_client.tenant_id, self.tenant_a.id)

        anamnese_base = AnamneseBase.objects.get(
            client=created_client,
            tenant=self.tenant_a,
            professional=self.prof_a,
        )
        self.assertEqual(anamnese_base.takes_medication, 'Metformina')
        self.assertEqual(anamnese_base.had_surgery, 'Joelho')
        self.assertFalse(anamnese_base.is_pregnant)

        anamnese_podologia = AnamnesePodologia.objects.get(
            anamnese_base__client=created_client,
            anamnese_base__tenant=self.tenant_a,
        )
        self.assertEqual(anamnese_podologia.footwear_used, 'Tênis')
        self.assertEqual(anamnese_podologia.sensitivity_test, 'Normal')

    def test_tenant_isolation_blocks_cross_tenant_client_and_anamnesis_access(self):
        # Dados pertencentes ao Tenant B
        client_b = Client.objects.create(
            tenant=self.tenant_b,
            first_name='Cliente',
            last_name='TenantB',
            phone='11999999992',
        )
        AnamneseBase.objects.create(
            client=client_b,
            tenant=self.tenant_b,
            professional=self.prof_b,
            takes_medication='Sim',
        )

        # Profissional do Tenant A não deve acessar dados do Tenant B
        self.client.force_authenticate(user=self.prof_a)

        list_response = self.client.get('/register/clients/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data, [])

        detail_response = self.client.get(f'/register/clients/{client_b.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_podologia_tenant_does_not_receive_or_accept_odonto_anamnesis(self):
        self.client.force_authenticate(user=self.prof_a)

        response = self.client.post(
            '/register/clients/',
            {
                'first_name': 'Cliente',
                'last_name': 'Podologia',
                'phone': '11999999993',
                'anamnese_odontologia': {'gum_bleeding': True},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('anamnese_odontologia', response.data)

    def test_specialty_fields_are_filtered_by_tenant_capability(self):
        podologia_client = Client.objects.create(
            tenant=self.tenant_a,
            first_name='Cliente',
            last_name='Podologia',
            phone='11999999994',
        )
        odonto_client = Client.objects.create(
            tenant=self.tenant_b,
            first_name='Cliente',
            last_name='Odonto',
            phone='11999999995',
        )

        self.client.force_authenticate(user=self.prof_a)
        podologia_response = self.client.get(
            f'/register/clients/{podologia_client.id}/'
        )
        self.assertIn('anamnese_podologia', podologia_response.data)
        self.assertNotIn('anamnese_odontologia', podologia_response.data)

        self.client.force_authenticate(user=self.prof_b)
        odonto_response = self.client.get(f'/register/clients/{odonto_client.id}/')
        self.assertIn('anamnese_odontologia', odonto_response.data)
        self.assertNotIn('anamnese_podologia', odonto_response.data)
