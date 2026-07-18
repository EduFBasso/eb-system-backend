# 🗺️ MIGRATION_GUIDE - Baseline Técnico (Fase 0)

## 📌 Objetivo do Documento
Guiar de forma incremental e controlada a transformação do `clinic-system` em uma arquitetura Multi-Tenant robusta e segura, mitigando riscos de vazamento de dados entre profissionais e clínicas distintas.

---

## 🚦 Regras de Ouro e Governança (Gates Técnicos)
1. **Isolamento Absoluto**: Código que não possui filtro explícito por propriedade de dados (`ownership` ou `tenant_id`) está proibido de ir para produção.
2. **Estratégia de Branches**: Todas as alterações devem ocorrer em branches baseadas em `feature/multi-tenant-*` e revisadas no GitHub antes do merge.
3. **Mecanismo de Rollback**: Toda migração de banco de dados (schema) deve possuir um script de reversão testado localmente.
4. **Legibilidade para IA**: Manter nomenclatura estrita em inglês, modularização de arquivos abaixo de 700 linhas e comentários concisos sobre regras de negócio sensíveis.

---

## 📋 Trilha de Execução por Ondas

### 🔹 Fase 1: Hardening de Isolamento Atual
* Revisar escopos globais e aplicar herança estrita em `get_queryset`.
* Proteger `backend/apps/register/professional_views.py`.
* Implementar testes cross-user para garantir regressão zero.

### 🔹 Fase 2: Introdução da Camada Tenant
* Criar novo app isolado: `backend/apps/tenancy/`.
* Implementar modelos: `Tenant` e `TenantMembership` com campo `role`.
* Injetar "Capabilities" (Feature Flags) via `JSONField` para diferenciar Odonto de Podologia no backend.

### 🔹 Fase 3: Dados Tenant-Aware
* Backfill de dados antigos locais de forma controlada.
* Adaptação de serializers, queries e viewsets sensíveis.

---

## ✅ Checkpoints Executados

### 2026-07-18 — Fase 1 / Hardening inicial de profissionais

**Objetivo:** bloquear acesso global ao diretório completo de profissionais antes da introdução formal de `Tenant`.

**Mudança aplicada:**
* `ProfessionalViewSet` passou a exigir permissão administrativa (`is_superuser` ou `can_manage_professionals`) para ações globais como listagem, leitura, criação, edição, desativação e reativação de profissionais.
* Endpoints de autoatendimento foram preservados para qualquer profissional autenticado:
	* `/register/professionals/me/`
	* `/register/professionals/settings/`
	* `/register/professionals/telegram/link-start/`
	* `/register/professionals/telegram/link-verify/`
	* `/register/professionals/telegram/test-send/`

**Teste adicionado:**
* `backend/apps/register/tests/test_professional_view_permissions.py`

**Validação local:**
```bash
cd backend
.venv/bin/python -m pytest apps/register/tests/test_professional_view_permissions.py -q
.venv/bin/python -m pytest apps/register/tests -q
```

**Resultado:**
* `4 passed` no teste focado de isolamento de profissionais.
* `55 passed` na suíte completa de `apps/register/tests`.

**Próximo gate recomendado:** revisar o próximo ponto de isolamento com maior risco antes de criar schema multi-tenant: `clients`, `agenda`, `odonto` e permissões server-side de capacidades por especialidade.

### 2026-07-18 — Fase 1 / Hardening de clientes e agenda

**Objetivo:** garantir que profissionais comuns não consigam ler, criar ou alterar clientes e agendamentos pertencentes a outro profissional.

**Mudança aplicada:**
* `ClientViewSet` e `ClientBasicViewSet` passaram a filtrar estritamente por `professional_id=request.user.id`, retornando queryset vazio quando não houver usuário autenticado válido.
* `AppointmentViewSet` mantém escopo por `professional_id=request.user.id` e agora também retorna queryset vazio quando não houver usuário autenticado válido.
* A permissão de objeto de agenda passou a exigir ownership também para métodos de leitura, não apenas para mutações.
* `AppointmentSerializer` passou a rejeitar criação/validação de agendamento quando o cliente informado não pertence ao profissional autenticado.
* A regra de pendência de agendamento foi ajustada para considerar o par `client + professional`, evitando leitura de estado fora do escopo do profissional autenticado.

**Testes adicionados:**
* `backend/apps/clients/tests/test_client_isolation.py`
* `backend/apps/agenda/tests/test_appointment_isolation.py`

**Validação local:**
```bash
cd backend
.venv/bin/python -m pytest apps/clients/tests/test_client_isolation.py apps/agenda/tests/test_appointment_isolation.py -q
.venv/bin/python -m pytest apps/clients/tests apps/agenda/tests -q
```

**Resultado:**
* `8 passed` nos testes focados de isolamento de clientes e agendamentos.
* `43 passed` nas suítes próximas de `apps/clients/tests` e `apps/agenda/tests`.

**Próximo gate recomendado:** revisar `odonto` e capacidades server-side por especialidade, porque a UX já oculta o módulo por `specialty`, mas o backend ainda deve ser a autoridade final de acesso.

### 2026-07-18 — Fase 1 / Hardening do módulo odontológico

**Objetivo:** garantir que o módulo odontológico seja isolado por profissional e acessível apenas para profissionais com especialidade odontológica reconhecida pelo backend.

**Mudança aplicada:**
* As rotas de `odonto` passaram a exigir usuário autenticado com especialidade compatível (`odonto`, `dent` ou `ortodont`).
* `DentalArcadeViewSet`, `ToothViewSet`, `SurfaceViewSet` e `ProcedureViewSet` passaram a filtrar por `professional_id=request.user.id`, retornando queryset vazio quando não houver usuário autenticado válido.
* A criação de arcadas continua forçando `professional=request.user` e rejeita clientes de outro profissional.
* `ProcedureSerializer` passou a rejeitar arcada, dente, face ou movimentação de procedimento que atravesse o ownership do profissional autenticado.
* Ações auxiliares de catálogo/sugestões e bulk update foram reforçadas com filtros por `professional_id`.

**Testes adicionados:**
* `backend/apps/odonto/tests/test_odonto_isolation.py`

**Validação local:**
```bash
cd backend
.venv/bin/python -m pytest apps/odonto/tests/test_odonto_isolation.py -q
.venv/bin/python -m pytest apps/register/tests apps/clients/tests apps/agenda/tests apps/odonto/tests -q
```

**Resultado:**
* `9 passed` nos testes focados de isolamento e acesso por especialidade no `odonto`.
* `107 passed` na suíte conjunta dos domínios endurecidos na Fase 1 (`register`, `clients`, `agenda`, `odonto`).

**Próximo gate recomendado:** encerrar a Fase 1 com revisão de diff e, se aprovado, iniciar Fase 2 com o app `tenancy` em schema incremental e sem alterar ainda ownership dos dados existentes.

### 2026-07-18 — Fase 2 / Introdução do app tenancy

**Objetivo:** criar a primeira camada explícita de tenant e substituir gates de acesso por especialidade textual por capabilities controladas no backend.

**Mudança aplicada:**
* Novo app Django `apps.tenancy` registrado em `INSTALLED_APPS`.
* Modelo `Tenant` criado com `name`, `slug`, `capabilities` (`JSONField`), `is_active` e timestamps.
* Modelo `TenantMembership` criado com vínculo para `Tenant`, vínculo para `Professional`, campo `role`, `is_active` e timestamps.
* Permissão customizada `HasTenantCapability(capability_name)` criada em `apps.tenancy.permissions`.
* O módulo `odonto` deixou de depender da string `Professional.specialty` e passou a exigir `HasTenantCapability('odonto')`.
* Administradores Django conseguem gerenciar tenants e memberships pelo admin.

**Migration gerada:**
* `backend/apps/tenancy/migrations/0001_initial.py`

**Testes adicionados/atualizados:**
* `backend/apps/tenancy/tests/test_permissions.py`
* `backend/apps/odonto/tests/test_odonto_isolation.py`

**Validação local:**
```bash
cd backend
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations tenancy
.venv/bin/python -m pytest apps/tenancy/tests apps/odonto/tests/test_odonto_isolation.py -q
```

**Resultado:**
* `manage.py check` sem issues.
* Migration inicial do app `tenancy` gerada com sucesso.
* `14 passed` nos testes focados de `tenancy` e `odonto`.

**Próximo gate recomendado:** criar rotina controlada de seed/backfill local para associar profissionais existentes a tenants antes de migrar dados clínicos para `tenant_id` na Fase 3.

### 2026-07-18 — Fase 3 / Campos tenant e backfill local

**Objetivo:** tornar os dados críticos tenant-aware de forma compatível, mantendo `tenant` opcional enquanto a aplicação ainda usa `professional` como ownership operacional.

**Modelos atualizados:**
* `clients.Client`
* `agenda.Appointment`
* `agenda.FinalizeAudit`
* `agenda.Encounter`
* `agenda.ClinicalRecord`
* `agenda.Charge`
* `agenda.ChargeItem`
* `odonto.DentalArcade`
* `odonto.Tooth`
* `odonto.Surface`
* `odonto.Procedure`
* `odonto.ProcedureNameSuggestion`
* `odonto.ProductCatalogItem`

**Mudança aplicada:**
* Cada modelo crítico recebeu `tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True)`.
* Migrations locais de schema geradas para `clients`, `agenda` e `odonto`.
* Criado backfill idempotente em `apps.tenancy.backfill.backfill_existing_tenants`.
* Criado command manual `python manage.py backfill_tenants` para reexecução controlada.
* Criada data migration `tenancy.0002_backfill_existing_tenants`, executada após as migrations de schema.

**Política segura de backfill:**
* Dados ligados diretamente a `professional` recebem `tenant` apenas quando o profissional possui exatamente um `TenantMembership` ativo em tenant ativo.
* Dados filhos recebem `tenant` a partir do pai já associado:
	* `ChargeItem` a partir de `Charge`.
	* `Tooth` e `Procedure` a partir de `DentalArcade`.
	* `Surface` a partir de `Tooth -> DentalArcade`.
* Profissionais sem tenant ativo ou com múltiplos tenants ativos são ignorados para revisão manual, preservando `tenant=NULL` em vez de inferir incorretamente.

**Migrations geradas:**
* `backend/apps/clients/migrations/0006_client_tenant.py`
* `backend/apps/agenda/migrations/0015_appointment_tenant_charge_tenant_chargeitem_tenant_and_more.py`
* `backend/apps/odonto/migrations/0008_dentalarcade_tenant_procedure_tenant_and_more.py`
* `backend/apps/tenancy/migrations/0002_backfill_existing_tenants.py`

**Validação local:**
```bash
cd backend
.venv/bin/python manage.py makemigrations clients agenda odonto
.venv/bin/python manage.py migrate
.venv/bin/python manage.py backfill_tenants
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python -m pytest apps/tenancy/tests -q
```

**Resultado:**
* Migrations aplicadas localmente com sucesso.
* Backfill local associou os clientes existentes aos tenants criados no Django Admin.
* Reexecução de `backfill_tenants` retornou `0 updated`, confirmando idempotência.
* `makemigrations --check --dry-run`: `No changes detected`.
* `6 passed` na suíte focada de `apps/tenancy/tests`.

**Próximo gate recomendado:** antes de tornar `tenant` obrigatório, atualizar serializers/viewsets para preencher `tenant` em novas criações e introduzir filtros por `tenant_id` junto ao filtro atual por `professional_id`.
