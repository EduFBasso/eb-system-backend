# Clinic System Backend

Este documento descreve as regras de negócio e operação do domínio clínico (saúde e procedimentos médicos).

---

## Escopo Funcional

- **Gestão de Clientes/Pacientes**: Cadastro de pacientes com isolamento por `Tenant` (clínica/especialidade).
- **Agendamento de Compromissos**: Marcação, confirmação, cancelamento e rastreamento de consultas e procedimentos.
- **Prontuários e Anamneses**: Formulários médicos estruturados por especialidade (Podologia, Odontologia).
- **Catálogo de Serviços e Produtos**: Lista de procedimentos, tratamentos e materiais clínicos disponíveis.
- **Planos de Tratamento**: Definição de múltiplas sessões com orçamento e acompanhamento de progresso.
- **Cobrança e Faturamento**: Criação de cobranças vinculadas a agendamentos e acompanhamento de status de pagamento.

Foco principal: gestão integrada de atendimentos clínicos com rastreamento de procedimentos e controle de receita.

---

## Regras de Negócio Principais

### Multi-Tenancy Estrito por Especialidade
- **Podologia** e **Odontologia** são clínicas independentes (Tenants separados).
- Dados de pacientes, agendamentos e prontuários ficam **100% isolados por Tenant**.
- Um mesmo paciente pode existir em ambas as clínicas com prontuários completamente distintos (isolamento garantido por `tenant_id`).

### Máquina de Estados de Agendamentos
Os estados válidos de um agendamento são:
- `scheduled`: Agendado e pendente de realização.
- `done`: Concluído e salvo no prontuário.
- `canceled`: Cancelado (e não pode ser revertido para `scheduled`).

### Validações de Anamnese
- Anamneses são estruturadas por especialidade (`AnamneseBase`, `AnamnesePodologia`, `AnamneseOdontologia`).
- Links públicos para preenchimento de anamnese via WhatsApp são gerados e validados com tokens assinados.
- Uma anamnese é única por cliente e tenant.

### Procedimentos Específicos por Especialidade
- **Podologia**: Contextos de procedimento associados a dedos ou regiões de pés (localização numérica: 1–5).
- **Odontologia**: Procedimentos com notação dentária **FDI/ISO 3950** (dentes permanentes 11–48, decíduos 51–85), faces anatômicas (O, M, D, V, L, I) e cálculo de orçamentos estruturados.

### Controle de Lembretes e Notificações
- Lembretes de agendamento podem ser disparados via **Telegram** (se vinculado pelo profissional).
- Cada profissional gerencia seu próprio Bot de Telegram através de um handshake seguro.
- Clientes recebem confirmações via **WhatsApp** ou links de anamnese pública.

---

## Módulo Backend

Domínio no app:

- `apps.clinic`

Submódulos principais:
- `apps.clinic.models.clients` — Pacientes e dados de contato.
- `apps.clinic.models.agenda` — Agendamentos e estado das consultas.
- `apps.clinic.models.inventory` — Serviços, produtos e materiais clínicos.
- `apps.clinic.models.treatment` — Planos de tratamento e sessões.
- `apps.clinic.models.podologia` — Contextos de procedimentos podológicos.
- `apps.clinic.models.odonto` — Contextos de procedimentos odontológicos e notação FDI.

Base compartilhada com o restante da plataforma:

- Autenticação: `apps.authentication`
- Mensageria: `apps.notifications` (Telegram)
- Infraestrutura: `core`

---

## Frontend Correspondente

O frontend separado deste domínio fica em:

- `../frontend-clinic`

Componentes principais:
- **Agenda**: Calendário de agendamentos, criação e edição de compromissos.
- **Clientes**: Cadastro, busca e gestão de pacientes (com filtro por Tenant/especialidade).
- **Catálogo**: Gestão de serviços, produtos e materiais clínicos.
- **Prontuários**: Visualização e preenchimento de anamneses estruturadas.
- **Configurações**: Perfil do profissional, vínculo de Telegram, ajustes de lembretes.

### Ambientes e Rotas
Em desenvolvimento local:
- **Porta**: `5173`
- **URL**: `http://localhost:5173`
- **Prefixo de API**: `/register/`, `/agenda/`, `/clinic/`, `/inventory/`

---

## Deploy Recomendado

- **Frontend**: Projeto dedicado na Vercel, separado do frontend-bakery.
  - Domínio próprio por ambiente (ex: `clinic.yourdomain.com` para produção).
  - Variáveis de ambiente:
    - `VITE_API_BASE`: URL do backend em produção (ex: `https://api.yourdomain.com`).
    - `VITE_PUBLIC_ANAMNESIS_BASE_URL`: URL pública para links de anamnese via WhatsApp.

- **Backend**: Compartilhado na Render com suporte a ambos os ecossistemas.
  - Variáveis de ambiente necessárias:
    - `CORS_ALLOWED_ORIGINS`: Incluir a URL do frontend clinic (`https://clinic.yourdomain.com`).
    - `CSRF_TRUSTED_ORIGINS`: Incluir a mesma URL para proteção CSRF.
    - `TELEGRAM_BOT_TOKEN`: Token do Bot de Telegram para notificações (opcional em staging).

---

## Validação Local

```bash
# Verificar integridade do Django
./.venv/bin/python manage.py check

# Executar testes de integração
./.venv/bin/python -m pytest -q

# Subir o servidor local
./.venv/bin/python manage.py runserver 0.0.0.0:8000

# Subir o frontend clinic em outra aba/terminal
cd ../frontend-clinic
npm run dev
```

---

## Fluxo de Testes Manuais Recomendados

1. **Login e Acesso Multi-Tenant**:
   - Fazer login com Podologia (`rezinha.bas@icloud.com`).
   - Verificar que vê apenas dados da clínica Podologia.
   - Fazer logout e login com Odontologia (`odontologia@consultorio.local`).
   - Verificar que vê apenas dados da clínica Odontologia.

2. **Cadastro de Pacientes**:
   - Cadastrar um paciente em Podologia com telefone `(19) 99855-2882`.
   - Fazer logout e login em Odontologia.
   - Cadastrar o **mesmo paciente** com o mesmo telefone.
   - Verificar que não há conflito (isolamento funciona).

3. **Agendamento e Fluxo de Anamnese**:
   - Criar um agendamento para o paciente em Podologia.
   - Verificar que o link de anamnese público funciona via WhatsApp/celular.
   - Preencher a anamnese e confirmar que o profissional recebe os dados.

4. **Notificações Telegram** (se configurado):
   - Vincular um Bot de Telegram pessoal no painel de Configurações.
   - Enviar um teste de mensagem.
   - Verificar que a mensagem chegou no Telegram do profissional.

---

## Referências

- [Documentação de Reset e Bootstrap Local](docs/reset_database_loc.md)
- [Arquitetura e Roteamento Multitenant](docs/architecture-and-app-routing.md)
- [Guia de Manutenção de Campos de Anamnese](docs/anamnesis-field-maintenance-guide.md)
- [Arquitetura Completa do Backend](ARCHITECTURE.md)
