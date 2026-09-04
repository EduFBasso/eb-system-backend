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

O fluxo simplificado do `Appointment` possui três estados persistidos:

| Status | Significado | Como ocorre |
|---|---|---|
| `scheduled` | Agendado e ativo | Estado inicial e único estado editável |
| `done` | Realizado/concluído | Ação `done` ou promoção automática quando o horário termina |
| `canceled` | Cancelado | `cancel`; compromisso concluído não pode ser cancelado |

`ongoing` foi removido do modelo e não é uma transição válida. O frontend não
deve criar um estado paralelo de “em andamento”: para apresentação, um
`scheduled` cujo `end_at` já passou é promovido diretamente para `done` pelo
backend.

Fluxo normal:

```text
scheduled -> done
scheduled -> canceled
done ------> estado final
canceled --> estado final
```

## ALTERAÇÕES: 

O compromisso não é monitorado em um estado `ongoing` durante o intervalo
agendado. Quando `end_at` passa, o compromisso `scheduled` pode ser promovido
diretamente para `done` durante a leitura da agenda.

O endpoint `POST /agenda/appointments/<id>/finalize/` e os campos de auditoria
de finalização foram removidos. `done` é idempotente e aceito para compromissos
em `scheduled`.

### Tipos e avaliação

O fluxo de agenda foi simplificado para não usar tipo de consulta ou avaliação
como etapas de negócio. A agenda deve tratar o registro como um compromisso,
independentemente do motivo informado.

### Atendimento clínico

`Encounter` é separado de `Appointment`: representa a sessão clínica e pode
estar `open`, `closed` ou `canceled`. O fechamento da sessão usa
`POST /agenda/encounters/<id>/close/` e seu cancelamento usa
`POST /agenda/encounters/<id>/cancel/`. Esses estados não devem ser confundidos
com os três estados do compromisso na agenda.

## Reminders Telegram

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

O vínculo é criado ou atualizado no Django Admin em `Telegram professional
links`. Para usar o token global, mantenha `bot_token` vazio.

## Anamnese fixa por especialidade

O prontuário usa `AnamneseBase`, única por cliente e tenant, com extensões
OneToOne `AnamnesePodologia` e `AnamneseOdontologia`. Os campos fazem parte do
schema Django; não existem seeds de perguntas por profissional.

Documentos de referência:

- docs/runbook-regiane-professional-setup.md
- docs/anamnesis-field-maintenance-guide.md
