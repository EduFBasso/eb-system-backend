# Clinic System Backend

Este documento descreve regras e operação do domínio clínico.

## Escopo funcional

- cadastro de profissionais e clientes
- agenda com rastreio de estados de consulta
- anamnese geral e anamnese dinâmica por profissional
- lembretes de consulta via Telegram
- histórico financeiro vinculado ao atendimento finalizado (serviços e produtos)

Não é controle de estoque.

## Regras de negócio principais

- cada profissional opera no seu escopo de tenant/membership
- consultas mudam de estado por regras de transição válidas
- lembretes são enviados apenas quando habilitados por flag
- anamnese dinâmica deve seguir seed canônico por especialidade

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

- local: execução manual para simular rotina periódica
- online (Render): monitoramento em janela de 5 em 5 minutos
- feature flag: APPOINTMENT_REMINDERS_ENABLED=true|false

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
