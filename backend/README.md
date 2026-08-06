# EB System Backend

Backend único para dois sistemas de negócio distintos:

- Clinic System (atendimento clínico)
- Bakery System (controle de pedidos de produtos para panificadora)

Este README é a visão geral. Regras específicas ficam em READMEs separados:

- `README-CLINIC.md`
- `README-BAKERY.md`

## Contexto da arquitetura

- `apps.authentication`: autenticação, profissionais, memberships e permissões
- `apps.clinic`: agenda, clientes, anamnese, odonto, reminders
- `apps.bakery`: clientes, catálogo, pedidos e lançamentos da padaria
- `core`: settings, urls e middleware

Stack:

- Python 3.12+
- Django + DRF
- PostgreSQL
- JWT (SimpleJWT)
- Deploy backend: Render

## Frontends separados na Vercel

Os frontends são independentes e possuem deploys distintos:

- Frontend Clinic: `../frontend-clinic`
- Frontend Bakery: `../frontend-bakery`

Cada frontend pode ter seu próprio projeto na Vercel, domínio e variáveis de ambiente.

## Setup local rápido

```bash
cd backend
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py runserver
```

## Teste local de reminders

Fluxo mais próximo do ambiente online:

```bash
cd backend
bash dev.sh
```

Esse script sobe o Django e executa o comando canônico de reminders em loop a cada 5 minutos.

Teste manual pontual do comando:

```bash
cd backend
./.venv/bin/python manage.py send_clinic_appointment_reminders --dry-run
```

Variações úteis:

```bash
./.venv/bin/python manage.py send_clinic_appointment_reminders --appointment-id <id>
./.venv/bin/python manage.py send_clinic_appointment_reminders --professional-email <email>
```

Validação:

```bash
./.venv/bin/python manage.py check
./.venv/bin/python -m pytest -q
```

## Documentação operacional

- Índice de docs: `docs/README.md`
- Runbook Regiane (padrão para onboarding): `docs/runbook-regiane-professional-setup.md`
- Guia de campos dinâmicos de anamnese: `docs/anamnesis-field-maintenance-guide.md`
