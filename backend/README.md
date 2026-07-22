<!-- backend\README.md -->

# Backend (Django 5.2.4)

API REST para gerenciamento de clínica multi-especialidade: agenda, clientes, inventário e autenticação profissional.

## Arquitetura Rápida

**Stack**: Django 5.2.4 + PostgreSQL + Django REST Framework + simplejwt
**Auth**: JWT + device sessions + WebAuthn/passkeys
**Multi-tenancy**: Hard-scoped por `Professional` (AUTH_USER_MODEL)

## Estrutura de Apps

| App         | Modelos                                                                   | Responsabilidade                                    |
| ----------- | ------------------------------------------------------------------------- | --------------------------------------------------- |
| `register`  | Professional, DeviceSession, ProfessionalSettings, WebAuthnCredential     | Auth, sessões, identidade profissional              |
| `clients`   | Client                                                                    | Cadastro e anamnese base do cliente                 |
| `agenda`    | Appointment, FinalizeAudit, Encounter, ClinicalRecord, Charge, ChargeItem | Agenda, atendimento, prontuário evolutivo, cobrança |
| `inventory` | Product, Supplier, StockMove, Service, ServiceMaterial                    | Produtos, serviços, BOM, estoque                    |

## Setup Local

### 1) Criar ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Instalar dependências

```bash
pip install -r requirements.txt
```

### 3) Subir banco PostgreSQL (Docker)

```bash
docker-compose -f docker-compose.local.yml up -d db
```

### 3.1) Reaproveitar uma base Docker ja populada (sem migrar dados)

Se voce ja tiver um volume Docker com clientes reais de teste, nao recrie o banco.
Suba o compose apontando para o volume existente:

```bash
DB_DOCKER_VOLUME_NAME=nome_do_volume_existente \
DB_DOCKER_VOLUME_EXTERNAL=true \
docker compose -f docker-compose.local.yml up -d db
```

Regras praticas:

- nao rode `docker compose down -v`
- mantenha `DB_NAME=clinic_local`, `DB_USER=clinic`, `DB_PASSWORD=clinicpass`
- se o volume antigo usar outro nome de container, isso nao importa; o dado reaproveitado vem do volume
- usuario operacional de teste local: `brunadentista@mail.com`

### 4) Migrações

```bash
cd backend
python manage.py migrate
```

### 5) Rodar servidor

**Localhost (dev rápido)**

```bash
python manage.py runserver
```

**Dev completo — servidor + loop de lembretes (somente se o recurso estiver ativado)**

```bash
bash dev.sh
```

Sobe o Django em `0.0.0.0:8000` e simultaneamente roda `send_reminders` a cada 5 minutos em background,
simulando o cron job de produção. Prefixo `[reminders]` nos logs distingue as saídas.
Se `APPOINTMENT_REMINDERS_ENABLED=false`, o comando fica em modo desativado e não envia nada.
Encerre com **Ctrl+C** — ambos os processos são encerrados juntos.

Use `REMINDERS_LOOP_INTERVAL_SECONDS` para override local do intervalo quando precisar depurar.

> **Produção**: não use `dev.sh`. Enquanto reminders estiverem desativados, remova ou pause o cron job do Render. Quando o recurso voltar, reative o job `*/5 * * * * python manage.py send_reminders`.

**LAN (testar em dispositivos na mesma rede)**

```bash
scripts/run-backend-lan.sh
```

Detecta IPs privados automaticamente, configura DJANGO_ALLOWED_HOSTS e CORS.

## Endpoints Principais

**Health**

- `GET /health` — liveness
- `GET /health/full` — readiness + versão + DB status

**Auth**

- `POST /register/auth/totp/verify/` — autenticar com email + TOTP → JWT
- `POST /register/auth/webauthn/login-begin/` — iniciar login com passkey/WebAuthn
- `POST /register/auth/webauthn/login-complete/` — concluir login com passkey/WebAuthn
- `POST /register/auth/logout-device/` — logout + terminar sessão

Observacao: o fluxo antigo por OTP enviado por email nao e mais o fluxo principal do sistema.

**Clientes**

- `GET /register/clients/` — listar
- `POST /register/clients/` — criar
- `GET /register/clients/{id}/` — detalhe (incluindo anamnese completa)
- `PATCH /register/clients/{id}/` — atualizar

**Agenda**

- `GET /agenda/appointments/?start=&end=&status=` — filtrado por range
- `POST /agenda/appointments/` — criar
- `POST /agenda/appointments/{id}/finalize/` — finalizar + audit
- `POST /agenda/appointments/{id}/cancel/` — cancelar

Veja [routes_backend.md](routes_backend.md) para referência completa.

## Configuração

### Arquivo `.env` (obrigatório localmente)

```bash
DEBUG=True
DJANGO_SECRET_KEY=dev-only-key
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173

DB_ENGINE=django.db.backends.postgresql
DB_HOST=127.0.0.1
DB_PORT=55432
DB_NAME=clinic_local
DB_USER=clinic
DB_PASSWORD=clinicpass
```

Para detalhes e opções avançadas, veja [.env](.env).

### Arquivo `.env` para online protegido

Quando quiser testar no servidor online sem permitir alteracoes destrutivas:

```bash
ONLINE_MUTATION_LOCK_ENABLED=True
ONLINE_MUTATION_LOCK_METHODS=PUT,PATCH,DELETE
SERVE_MEDIA_FILES=True
```

Efeito:

- `POST` continua permitido para testes controlados
- `PUT`, `PATCH` e `DELETE` retornam `423 Locked`
- arquivos em `/media/` continuam roteados pelo backend

Importante: para as fotos sobreviverem a restart/deploy no Render, use disco persistente ou storage externo.

## Testes

```bash
# Runner oficial da equipe (sempre no backend com .venv ativo)
python -m pytest -q

# Coleta (diagnóstico rápido de descoberta)
python -m pytest --collect-only -q

# Teste específico
python -m pytest tests/test_health_endpoints.py -q

# Com cobertura
python -m pytest --cov=apps -q
```

Configuração central: [pytest.ini](pytest.ini)

Padrão operacional da equipe:

- usar `pytest` como fonte de verdade para descoberta e execução de testes.
- evitar `python manage.py test` nesta estrutura, pois o DiscoverRunner padrão do Django não reflete toda a suíte em `apps/**/tests` e `tests/`.
- se aparecer `ModuleNotFoundError: No module named 'tests.test_*'`, confirme que você está no diretório `backend`, com `.venv` ativo, e rode novamente `python -m pytest --collect-only -q`.

## Migrações

Ao alterar modelos, gerar migração:

```bash
python manage.py makemigrations
python manage.py migrate
```

Histórico em: `apps/*/migrations/`

## Dependências

Arquivo: [requirements.txt](requirements.txt)

**Atualizado (Sprint 0 - limpeza)**

- setuptools pinned em 80.0.0 (evita warning de simplejwt com pkg_resources)
- Removidos: axios, bcrypt, lxml, colorama, mysqlclient (histórico Windows/testes)
- Mantidos: Django, DRF, JWT, PostgreSQL, Pillow, pytest

## Problemas Comuns

| Erro                             | Solução                                                                |
| -------------------------------- | ---------------------------------------------------------------------- |
| `connection refused` porta 55432 | Banco não subiu: `docker-compose -f docker-compose.local.yml up -d db` |
| Migrações fail                   | Garantir banco ativo + `python manage.py migrate`                      |
| Imports fail                     | Ativar venv: `source .venv/bin/activate`                               |

## Deploy (Render)

Estável em produção. Start command:

```bash
gunicorn clinic_project.wsgi --chdir backend --bind 0.0.0.0:10000 --workers 2
```

Variáveis obrigatórias em produção:

- `DJANGO_SECRET_KEY` (gerar com `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DEBUG=False`
- `DJANGO_ALLOWED_HOSTS=seu-backend.onrender.com,...`
- `CORS_ALLOWED_ORIGINS=https://seu-frontend.vercel.app,...`
- `DB_*` (Postgres gerenciado)

Veja [../../DEPLOY_CHECKLIST.md](../../DEPLOY_CHECKLIST.md) para checklist pré-deploy.

## Próximas Etapas (Roadmap Sprint 1+)

- [x] Novos modelos: `Encounter`, `ClinicalRecord`, `Charge`
- [ ] Integrar `Charge`/`ChargeItem` aos modais de orçamento e cobrança do frontend
- [ ] Integrar `Encounter` ao fluxo de finalização e atendimento em andamento
- [ ] Máquina de estados robusta para `Appointment`
- [ ] Formulários dinâmicos por especialidade
- [ ] RBAC (role-based access control)
- [ ] Mensageria semi-automática com log

**Setup local vs produção**: veja [../../info/local-vs-online-workflow.md](../../info/local-vs-online-workflow.md)
