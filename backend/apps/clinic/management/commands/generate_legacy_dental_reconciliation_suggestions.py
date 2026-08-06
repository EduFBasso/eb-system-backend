import csv
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.clinic.models.clients import Client
from apps.clinic.management.commands.import_bruna_arcada import Command as ImportCommand


class Command(BaseCommand):
    help = 'Generate assisted reconciliation suggestions for unmatched legacy patients.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-dir',
            type=str,
            default='backup_database/Bruna_Carvalho',
            help='Directory containing CSV exports (PACIENTE_DADOS and TRATAMENTO).',
        )
        parser.add_argument(
            '--professional-email',
            type=str,
            default='brunadentista@mail.com',
            help='Email of the professional in the local database.',
        )
        parser.add_argument(
            '--top-k',
            type=int,
            default=5,
            help='How many candidate clients to output for each unmatched name.',
        )
        parser.add_argument(
            '--min-score',
            type=float,
            default=0.70,
            help='Minimum similarity score to include a suggestion.',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='',
            help='Output CSV path. Defaults to info/migration/odonto_reconciliation_assisted_<timestamp>.csv',
        )

    def handle(self, *args, **options):
        csv_dir = Path(options['csv_dir'])
        professional_email = options['professional_email']
        top_k = max(1, int(options['top_k']))
        min_score = float(options['min_score'])
        output = options.get('output', '').strip()

        if not csv_dir.exists():
            raise CommandError(f'CSV directory not found: {csv_dir}')

        try:
            from apps.authentication.models import Professional
            professional = Professional.objects.get(email=professional_email)
        except Professional.DoesNotExist:
            raise CommandError(
                f'Professional not found with email {professional_email}. '
                f'Please create the professional first.'
            )

        importer = ImportCommand()

        self.stdout.write(f'📋 Assisted reconciliation for: {professional.first_name} {professional.last_name}')
        self.stdout.write(f'📁 CSV directory: {csv_dir}')

        patients = importer._load_patients_csv(csv_dir / 'PACIENTE_DADOS.csv')
        treatments = importer._load_treatments_csv(csv_dir / 'TRATAMENTO.csv')
        client_map = importer._build_client_lookup(professional)

        patients_by_id = {
            (row.get('ID_PACIENTE') or '').strip(): (row.get('TX_NOME') or '').strip()
            for row in patients
            if (row.get('ID_PACIENTE') or '').strip()
        }

        treatment_patient_ids = [
            (row.get('ID_PACIENTE') or '').strip()
            for row in treatments
            if (row.get('ID_PACIENTE') or '').strip()
        ]
        treatments_by_patient = Counter(treatment_patient_ids)

        unmatched_names = {}
        for patient_id, count in treatments_by_patient.items():
            patient_name = patients_by_id.get(patient_id, '').strip()
            if not patient_name:
                continue
            client, _mode = importer._match_client(patient_name, client_map)
            if client is None:
                unmatched_names[patient_name] = unmatched_names.get(patient_name, 0) + count

        if not output:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            output = f'info/migration/odonto_reconciliation_assisted_{ts}.csv'

        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        client_candidates = []
        for c in Client.objects.filter(professional=professional):
            full_name = f'{c.first_name} {c.last_name}'.strip()
            relaxed = importer._normalize_name_relaxed(full_name)
            if not relaxed:
                continue
            client_candidates.append((c.id, full_name, relaxed))

        rows = []
        for patient_name, treatment_count in sorted(
            unmatched_names.items(),
            key=lambda kv: (-kv[1], kv[0].lower()),
        ):
            repaired_name = importer._fix_mojibake(patient_name)
            target_relaxed = importer._normalize_name_relaxed(repaired_name)
            if not target_relaxed:
                continue

            scored = []
            for cid, cname, cname_relaxed in client_candidates:
                if abs(len(cname_relaxed) - len(target_relaxed)) > 14:
                    continue
                score = SequenceMatcher(None, target_relaxed, cname_relaxed).ratio()
                if score >= min_score:
                    scored.append((score, cid, cname))

            scored.sort(key=lambda x: (-x[0], x[2].lower()))
            top = scored[:top_k]

            if not top:
                rows.append({
                    'legacy_name': patient_name,
                    'legacy_name_repaired': repaired_name,
                    'legacy_relaxed': target_relaxed,
                    'treatment_count': treatment_count,
                    'candidate_rank': '',
                    'candidate_client_id': '',
                    'candidate_client_name': '',
                    'score': '',
                })
                continue

            for idx, (score, cid, cname) in enumerate(top, start=1):
                rows.append({
                    'legacy_name': patient_name,
                    'legacy_name_repaired': repaired_name,
                    'legacy_relaxed': target_relaxed,
                    'treatment_count': treatment_count,
                    'candidate_rank': idx,
                    'candidate_client_id': cid,
                    'candidate_client_name': cname,
                    'score': f'{score:.4f}',
                })

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    'legacy_name',
                    'legacy_name_repaired',
                    'legacy_relaxed',
                    'treatment_count',
                    'candidate_rank',
                    'candidate_client_id',
                    'candidate_client_name',
                    'score',
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        unique_unmatched = len(unmatched_names)
        total_unmatched_treatments = sum(unmatched_names.values())
        self.stdout.write(self.style.SUCCESS('\n✅ Assisted reconciliation file generated!'))
        self.stdout.write(f'  Unmatched unique names: {unique_unmatched}')
        self.stdout.write(f'  Unmatched treatments: {total_unmatched_treatments}')
        self.stdout.write(f'  Suggestion rows written: {len(rows)}')
        self.stdout.write(f'  Output: {output_path}')
