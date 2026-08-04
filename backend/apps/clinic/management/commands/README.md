# Clinic Management Commands

This folder contains operational and migration commands for the Clinic domain.

## Naming Policy

- Use English, action-first names.
- Do not use personal names in command filenames.
- Prefix legacy data workflows with `import_legacy_` or `reconcile_legacy_`.

## Command Inventory

| Current command | Purpose | Tenant/client context | Proposed standardized name |
|---|---|---|---|
| `import_bruna_arcada` | Imports dental arcade/procedure CSV exports into odonto models (`DentalArcade`, `Tooth`, `Surface`, `Procedure`). | Dental professional **Dra. Bruna Carvalho** (`brunadentista@mail.com`) | `import_legacy_dental_arcade_data` |
| `assist_bruna_reconciliation` | Generates assisted matching suggestions between legacy patient names and local clients. | Same legacy dental migration for **Dra. Bruna Carvalho** | `generate_legacy_dental_reconciliation_suggestions` |
| `approve_bruna_reconciliation` | Promotes high-confidence reconciliation suggestions and creates review queues. | Same legacy dental migration for **Dra. Bruna Carvalho** | `approve_legacy_dental_reconciliation` |
| `import_bruninha` | Imports patients from legacy ERP spreadsheet (`.xlsx`) and maps to `Client`/`AnamneseBase`. | Same dental migration for **Dra. Bruna Carvalho** (“Bruninha” source file naming) | `import_legacy_dental_patients_xlsx` |
| `normalize_odonto_encoding` | Fixes mojibake/encoding issues in odonto procedure names. | General odonto cleanup (initially used during Bruna migration) | `normalize_legacy_dental_encoding` |
| `export_podologia_json` | Exports legacy SQLite client + podology anamnesis columns to nested JSON payload. | Podology legacy extraction (commonly used for **Regiane** dataset) | `export_legacy_podology_json` |
| `import_podologia_json` | Imports nested podology JSON into `Client`, `AnamneseBase`, `AnamnesePodologia` with explicit tenant/professional IDs. | Podology import pipeline (commonly **Regiane**) | `import_legacy_podology_json` |
| `import_production_basic_data` | Purifies podology JSON and optionally imports basic personal/address data into target tenant/professional. | Production-safe basic data import (commonly **Regiane**) | `import_legacy_basic_clinic_data` |
| `migrate_anamnesis_legacy` | Migrates old anamnesis values from legacy client fields to `AnamnesisResponse`. | Clinic-wide legacy model transition | `migrate_legacy_anamnesis_fields` |
| `seed_anamnesis` | Seeds anamnesis field definitions from seed modules. | Clinic-wide setup per professional | `seed_clinic_anamnesis_fields` |
| `reset_test_data_preserve_professional` | Resets test clients/odonto data while preserving user/professional login records. | Local testing and QA | `reset_clinic_test_data_preserve_professional` |
| `send_reminders` | Dispatches Telegram reminders for upcoming appointments. | Clinic reminder operations | `send_clinic_appointment_reminders` |
| `telegram_link_professional` | Creates/updates Telegram link for a professional. | Clinic reminder operations | `link_professional_telegram_chat` |
| `telegram_send_test` | Sends a Telegram test message for a professional. | Clinic reminder operations | `send_telegram_test_message` |

## Notes About "Bruna/Bruninha"

The commands with `bruna` / `bruninha` in the filename are tied to the **legacy dental migration for Dra. Bruna Carvalho** and should be renamed to neutral, domain-oriented names.

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

### 5) Generate admin TOTP QR code

```bash
scripts/create_admin_totp_qrcode.sh admin@example.com
```

Optional custom PNG output:

```bash
scripts/create_admin_totp_qrcode.sh admin@example.com .temp/totp-admin-1.png
```

## Migration Plan for Command Renaming

1. Add aliases keeping old names for one transition cycle.
2. Update scripts/automation and docs to new names.
3. Deprecate old names with warning output.
4. Remove old name modules after team sign-off.
