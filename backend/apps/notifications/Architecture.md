# 📡 Apps Notifications — Motor Global de Mensageria (Telegram)

## 1. Visão Geral e Propósito
O app `apps.notifications` é um módulo **global e agnóstico de negócio** dentro do backend Django. Ele centraliza a infraestrutura de comunicação via Telegram para qualquer ecossistema da plataforma (`clinic`, `bakery` ou futuros apps como `lawyer`), garantindo isolamento total de regras de domínio.

O motor opera como uma função pura de mensageria:
- **Não sabe o que é um paciente, consulta, receita ou pedido.**
- Recebe apenas os parâmetros essenciais (link do destinatário, texto formatado e botões inline opcionais) e executa o despacho via Telegram Bot API.

---

## 2. Estrutura do Módulo

```text
backend/apps/notifications/
├── Architecture.md                  # Documentação de arquitetura do módulo
├── admin.py                         # Registro no Django Admin do vínculo Telegram
├── apps.py                          # Configuração da app (label: 'notifications')
├── models.py                        # TelegramProfessionalLink
├── migrations/
│   └── 0001_initial.py              # Migração state-only (reaproveita a tabela física original)
└── services/
    ├── __init__.py
    └── telegram_client.py           # TelegramBotClient, resolve_bot_token, send_via_link
```

---

## 3. Modelo de Dados (`models.py`)

### `TelegramProfessionalLink`
- **Herança física:** mapeado explicitamente para `db_table = 'clinic_telegramprofessionallink'`. A migração foi executada via `SeparateDatabaseAndState` sem tocar na tabela original do banco de dados (zero perda de dados ou downtime).
- **Campos principais:**
  - `tenant`: `ForeignKey('authentication.Tenant')` — garante isolamento multi-tenant estrito.
  - `professional`: `OneToOneField('authentication.Professional')` — cada usuário profissional possui no máximo um canal ativo por tenant.
  - `bot_token`: token opcional do BotFather privado do profissional. Se nulo, utiliza o bot padrão global do sistema (`TELEGRAM_BOT_TOKEN`).
  - `chat_id`: identificador numérico privado ou de canal no Telegram.
  - `is_active`, `linked_at`, `last_error`: controle de status e auditoria operacional de erro da conexão.
- **Constraint:** `UniqueConstraint(fields=['tenant', 'chat_id'])` impede duplicidade de chat dentro da mesma unidade corporativa.

---

## 4. Camada de Serviços (`services/telegram_client.py`)

- `TelegramBotClient`: cliente HTTP encapsulado via `requests` para os métodos `/sendMessage`, `/getMe` e `/getUpdates` da Telegram Bot API. Trata timeouts, respostas inválidas e levanta `TelegramDeliveryError`.
- `resolve_bot_token(link)`: resolve com precedência o token individual do profissional (`bot_token`), recorrendo ao global de ambiente caso não esteja configurado.
- `send_via_link(link, *, text, reply_markup=None)`: **ponto de entrada universal** para qualquer app do backend. Resolve o token correto, instancia o cliente e despacha a mensagem sem exigir que o chamador conheça a lógica de resolução de credenciais.

---

## 5. Fluxo de Autenticação e Vínculo (Deep-Link `/start`)
A Telegram Bot API não permite iniciar conversas ativamente por número de telefone. O fluxo de pareamento universal ocorre via `/register/` (em `apps/authentication/views/professional_views.py`):
1. **Geração de Token (`link-start`):** cria um token temporário assinado via HMAC (`pid-ts-nonce-signature`) com TTL de 15 minutos e devolve a URL `https://t.me/<bot_username>?start=<token>`.
2. **Ativação pelo Usuário:** o profissional clica no link e toca em "Iniciar" dentro do aplicativo do Telegram, enviando `/start <token>`.
3. **Verificação (`link-verify`):** o backend consome as mensagens recentes do bot via `getUpdates`, valida a assinatura do token e salva o `chat_id` correspondente no `TelegramProfessionalLink`.
4. **Teste de Envio (`test-send`):** valida o canal disparando uma mensagem de confirmação.

---

## 6. Regra de Auditoria
- **Descentralizada:** `apps.notifications` não mantém logs de eventos de negócio. Cada ecossistema mantém sua própria tabela de auditoria se e quando necessário (ex.: `clinic` mantém `ReminderDelivery` vinculado a `Appointment`; `bakery` opera via logs leves sem necessidade de tabela dedicada).
