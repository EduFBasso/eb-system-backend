# Clinic Management Commands

This folder contains operational and migration commands for the Clinic domain.

## Naming Policy

- Use English, action-first names.
- Do not use personal names in command filenames.
- Prefix legacy data workflows with `import_legacy_` or `reconcile_legacy_`.

## Command Inventory

| Canonical command | Purpose | Typical context |
|---|---|---|
| `approve_legacy_dental_reconciliation` | Promotes high-confidence reconciliation suggestions and creates review queues. | Legacy dental migration |
| `export_legacy_podology_json` | Exports legacy SQLite client + podology anamnesis columns to nested JSON payload. | Podology legacy extraction |
| `generate_legacy_dental_reconciliation_suggestions` | Generates assisted matching suggestions between legacy patient names and local clients. | Legacy dental migration |
| `import_legacy_basic_clinic_data` | Purifies podology JSON and optionally imports basic personal/address data into target tenant/professional. | Production-safe basic data import |
| `import_legacy_dental_arcade_data` | Imports dental arcade/procedure CSV exports into odonto models (`DentalArcade`, `Tooth`, `Surface`, `Procedure`). | Legacy dental migration |
| `import_legacy_dental_patients_xlsx` | Imports patients from legacy ERP spreadsheet (`.xlsx`) and maps to `Client`/`AnamneseBase`. | Legacy dental migration |
| `import_legacy_podology_json` | Imports nested podology JSON into `Client`, `AnamneseBase`, `AnamnesePodologia` with explicit tenant/professional IDs. | Podology import pipeline |
| `link_professional_telegram_chat` | Creates/updates Telegram link for a professional. | Clinic reminder operations |
| `migrate_legacy_anamnesis_fields` | Migrates old anamnesis values from legacy client fields to `AnamnesisResponse`. | Legacy model transition |
| `normalize_legacy_dental_encoding` | Fixes mojibake/encoding issues in odonto procedure names. | Odonto cleanup |
| `reset_clinic_test_data_preserve_professional` | Resets test clients/odonto data while preserving user/professional login records. | Local testing and QA |
| `seed_anamnesis` | Seeds anamnesis field definitions from modules in `apps/clinic/seeds/`. | Setup per professional |
| `send_clinic_appointment_reminders` | Dispatches Telegram reminders for upcoming appointments. | Clinic reminder operations |
| `send_telegram_test_message` | Sends a Telegram test message for a professional. | Clinic reminder operations |

## Legacy Names Removed

Legacy command names (such as `import_bruninha`, `send_reminders`, `telegram_send_test`, `migrate_anamnesis_legacy`) were removed during command deduplication.
Use only the canonical names listed above.

## Execution Examples

### 1) Import legacy dental arcade data

```bash
python manage.py import_legacy_dental_arcade_data \
  --csv-dir backup_database/Bruna_Carvalho \
  --professional-email brunadentista@mail.com
```

### 2) Generate and approve reconciliation suggestions

```bash
python manage.py generate_legacy_dental_reconciliation_suggestions \
  --csv-dir backup_database/Bruna_Carvalho \
  --professional-email brunadentista@mail.com

python manage.py approve_legacy_dental_reconciliation \
  --input info/migration/odonto_reconciliation_assisted.csv
```

### 3) Import podology JSON to explicit tenant/professional

```bash
python manage.py import_legacy_podology_json \
  --file .temp/carga_podologa.json \
  --tenant <tenant_id> \
  --professional <professional_id>
```

### 4) Send reminders (dry run)

```bash
python manage.py send_clinic_appointment_reminders --dry-run
```

Para usar o token global configurado em `TELEGRAM_BOT_TOKEN`, crie um vínculo
ativo sem token privado:

```bash
python manage.py link_professional_telegram_chat \
  --email <email-da-profissional> \
  --chat-id <chat-id-do-telegram>
```

### 5) Generate admin TOTP QR code

```bash
scripts/create_admin_totp_qrcode.sh admin@example.com
```

Optional custom PNG output:

```bash
scripts/create_admin_totp_qrcode.sh admin@example.com .temp/totp-admin-1.png
```

## Podology Dynamic Fields (Canonical Seed)

```bash
python manage.py seed_anamnesis --professional-email=rezinha.bas@icloud.com --seed=podologia_unhas
```

To prune stale/non-canonical podology fields for a professional, use:

```bash
python manage.py seed_anamnesis --professional-email=rezinha.bas@icloud.com --seed=podologia_unhas --deactivate-missing
```
