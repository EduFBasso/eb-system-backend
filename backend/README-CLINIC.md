# Clinic System Backend

Este documento descreve regras e operação do domínio clínico.

## Escopo funcional

- cadastro de profissionais e clientes
- agenda e ciclo de vida dos compromissos
- anamnese geral e anamnese dinâmica por profissional
- lembretes de consulta via Telegram
- histórico financeiro vinculado ao atendimento finalizado (serviços e produtos)

Não é controle de estoque.

## Regras de negócio principais

- cada profissional opera no seu escopo de tenant/membership
- compromissos pertencem ao tenant ativo, ao profissional autenticado e a um cliente da mesma clínica
- a agenda não usa o estado `ongoing`; o estado persistido é resolvido por um fluxo curto e explícito
- lembretes são enviados apenas quando habilitados por flag
- anamnese dinâmica deve seguir seed canônico por especialidade

## Agenda e compromissos

### Conceito

`Appointment` representa a reserva de um horário na agenda. Ele controla o
profissional, o cliente, o intervalo de tempo, o local, as observações e o
estado operacional do compromisso. O compromisso é isolado pelo tenant ativo e
não pode ser criado para cliente de outra clínica.

Rotas principais:

- `GET/POST /agenda/appointments/`
- `GET/PATCH /agenda/appointments/<id>/`
- `POST /agenda/appointments/<id>/done/`
- `POST /agenda/appointments/<id>/cancel/`
- `GET /agenda/appointments/next/`

Regras de criação e edição:

- não é permitido criar ou reagendar um compromisso para o passado;
- `end_at` deve ser posterior a `start_at`;
- não pode haver sobreposição de horários ativos para o mesmo profissional e
  tenant;
- compromissos cancelados liberam o horário e não participam do conflito;
- o cliente não pode ser trocado depois da criação;
- a exclusão física é bloqueada para preservar o histórico; use `cancel`;
- somente compromissos em `scheduled` podem ser editados genericamente;
- mudanças de status não são feitas por `PATCH` genérico, mas pelas ações
	dedicadas.

### Status do compromisso

O fluxo simplificado do `Appointment` possui quatro estados persistidos:

| Status | Significado | Como ocorre |
|---|---|---|
| `scheduled` | Agendado e ativo | Estado inicial e único estado editável |
| `pending` | Pendente de fechamento | Promoção automática quando o horário termina |
| `done` | Realizado/concluído | `done`, somente depois de `pending` |
| `canceled` | Cancelado | `cancel`; compromisso concluído não pode ser cancelado |

`ongoing` foi removido do modelo e não é uma transição válida. O frontend não
deve criar um estado paralelo de “em andamento”: para apresentação, um
`scheduled` cujo `end_at` já passou é exibido como pendente, até que a leitura
da agenda persista essa promoção no backend.

Fluxo normal:

```text
scheduled -> pending -> done
scheduled ----------------> canceled
pending -------------------> canceled
done -----------------------> estado final
canceled --------------------> estado final
```

O compromisso não é monitorado em um estado `ongoing` durante o intervalo
agendado. Portanto, não há regra de negócio para exibir o botão `Finalizar`
enquanto a consulta está em andamento. Quando `end_at` passa, o compromisso
`scheduled` pode ser promovido para `pending` durante a leitura da agenda. A
ação do profissional é então resolver o pendente com `done` ou `cancel`.

O endpoint `POST /agenda/appointments/<id>/finalize/` e os campos de auditoria
de finalização foram removidos. `done` é idempotente, mas só é aceito depois de
o compromisso estar em `pending`.

### Tipos e avaliação

O fluxo de agenda foi simplificado para não usar tipo de consulta ou avaliação
como etapas de negócio. A agenda deve tratar o registro como um compromisso,
independentemente do motivo informado.

No contrato atual ainda existe o campo legado `visit_type`, com os valores
`consulta`, `retorno` e `outro`, enviado pelo frontend e aceito pelo backend.
Ele é apenas informativo e não altera status, permissões, conflitos ou
transições. Sua remoção definitiva exige uma migração coordenada do serializer,
modelo/migrações e frontend.

Da mesma forma, “avaliação” não é um status nem uma etapa do compromisso. O
campo opcional `assessment` ainda aparece no modelo de `Encounter` e o tipo
`assessment` ainda aparece em `ClinicalRecord`; esses campos legados não devem
ser usados para decidir o ciclo de vida da agenda.

### Atendimento clínico

`Encounter` é separado de `Appointment`: representa a sessão clínica e pode
estar `open`, `closed` ou `canceled`. O fechamento da sessão usa
`POST /agenda/encounters/<id>/close/` e seu cancelamento usa
`POST /agenda/encounters/<id>/cancel/`. Esses estados não devem ser confundidos
com os quatro estados do compromisso na agenda.

## Reminders Telegram

Comando canônico:

```bash
./.venv/bin/python manage.py send_clinic_appointment_reminders
```

Flags:

```bash
./.venv/bin/python manage.py send_clinic_appointment_reminders --dry-run
./.venv/bin/python manage.py send_clinic_appointment_reminders --appointment-id <id>
./.venv/bin/python manage.py send_clinic_appointment_reminders --professional-email <email>
```

Operação:

- local: `bash dev.sh` sobe o Django e o loop de lembretes em paralelo; o intervalo padrão é 60 segundos
- online (Render): monitoramento em janela de 5 em 5 minutos
- feature flag: APPOINTMENT_REMINDERS_ENABLED=true|false

Telegram global:

- `TELEGRAM_BOT_TOKEN` é lido do ambiente pelo backend;
- o envio usa o token privado da profissional quando preenchido;
- para usar o token global, deve existir um vínculo Telegram ativo para a
	profissional com `bot_token` vazio;
- sem vínculo Telegram ativo, o lembrete é ignorado;
- nunca coloque o valor do token em documentação, commits ou logs.

Preparação do vínculo para teste:

```bash
./.venv/bin/python manage.py link_professional_telegram_chat \
	--email <email-da-profissional> \
	--chat-id <chat-id-do-telegram>
```

O comando cria um vínculo ativo sem `bot_token` privado, habilitando o uso de
`TELEGRAM_BOT_TOKEN` pelo serviço de reminders.

## Anamnese dinâmica

Seed canônico por profissional:

```bash
./.venv/bin/python manage.py seed_anamnesis --professional-email <email> --seed <seed>
```

Normalização com desativação de campos fora do padrão:

```bash
./.venv/bin/python manage.py seed_anamnesis --professional-email <email> --seed <seed> --deactivate-missing
```

Documentos de referência:

- docs/runbook-regiane-professional-setup.md
- docs/anamnesis-field-maintenance-guide.md
