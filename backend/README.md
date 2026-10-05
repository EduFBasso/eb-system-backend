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

O backend compartilha identidade e tenancy, mas mantém os domínios separados:

- Clinic: `/token/`, `/sessions/`, `/register/`, `/agenda/`, `/inventory/` e `/clinic/`;
- Bakery: `/api/v1/auth/bakery/` e `/api/v1/bakery/`;
- infraestrutura: `/health/` e `/health/full` são endpoints públicos de liveness/readiness.

Toda operação protegida deve usar o JWT atual e o contexto de `tenant_id`,
`ecosystem`, papel e membership ativa. O slug informado pelo frontend não
substitui as verificações de autorização do backend.

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

O backend de produção roda no Render. A configuração de produção exige
`DJANGO_SECRET_KEY`, `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` e as variáveis de e-mail
definidas em `core/settings/production.py`.

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

Esse script sobe o Django e executa o comando canônico de reminders em loop a
cada 60 segundos por padrão.

Validação:

```bash
./.venv/bin/python manage.py check
./.venv/bin/python -m pytest -q
```

## Documentação operacional

- Reset e bootstrap local (padrão de cadastro de administradores): `docs/reset_database_loc.md`
- Guia de campos dinâmicos de anamnese: `docs/anamnesis-field-maintenance-guide.md`
- Tenants por domínio/subdomínio (LAN e Vercel): `docs/local-lan-vercel-tenant-domains-guide.md`

Antes do deploy, executar os testes dos dois frontends, a suíte backend e
confirmar `/health/` e `/health/full` no ambiente publicado. Não registrar
senhas, tokens ou dados pessoais reais nos documentos de teste.
