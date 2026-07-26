from rest_framework import status
from rest_framework.test import APITestCase

from apps.anamnesis.models import (
    AnamnesisField,
    AnamnesisResponse,
    AnamneseBase,
    AnamnesePodologia,
)
from apps.clients.models import Client
from apps.register.models import Professional
from apps.tenancy.models import Tenant, TenantMembership


class ClientAnamnesisApiTests(APITestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name='Tenant A', slug='tenant-a')
        self.tenant_b = Tenant.objects.create(name='Tenant B', slug='tenant-b')

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
        self.assertEqual(created_client.professional_id, self.prof_a.id)

        anamnese_base = AnamneseBase.objects.get(
            client=created_client,
            tenant=self.tenant_a,
            professional=self.prof_a,
        )
        self.assertEqual(anamnese_base.takes_medication, 'Metformina')
        self.assertEqual(anamnese_base.had_surgery, 'Joelho')
        self.assertFalse(anamnese_base.is_pregnant)

        anamnese_podologia = AnamnesePodologia.objects.get(
            client=created_client,
            tenant=self.tenant_a,
            professional=self.prof_a,
        )
        self.assertEqual(anamnese_podologia.footwear_used, 'Tênis')
        self.assertEqual(anamnese_podologia.sensitivity_test, 'Normal')

    def test_tenant_isolation_blocks_cross_tenant_client_and_anamnesis_access(self):
        # Dados pertencentes ao Tenant B
        client_b = Client.objects.create(
            tenant=self.tenant_b,
            professional=self.prof_b,
            first_name='Cliente',
            last_name='TenantB',
            phone='11999999992',
        )
        field_b = AnamnesisField.objects.create(
            professional=self.prof_b,
            code='takes_medication',
            sector='Histórico',
            sector_order=0,
            label='Toma medicação?',
            field_type='radio',
            options=['Sim', 'Não'],
            order=0,
        )
        AnamnesisResponse.objects.create(
            client=client_b,
            field=field_b,
            field_label_snap='Toma medicação?',
            value='Sim',
        )

        # Profissional do Tenant A não deve acessar dados do Tenant B
        self.client.force_authenticate(user=self.prof_a)

        list_response = self.client.get('/register/clients/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data, [])

        detail_response = self.client.get(f'/register/clients/{client_b.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        anamnesis_response = self.client.get(f'/anamnesis/responses/?client={client_b.id}')
        self.assertEqual(anamnesis_response.status_code, status.HTTP_200_OK)
        self.assertEqual(anamnesis_response.data, [])
