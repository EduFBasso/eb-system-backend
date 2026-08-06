import csv
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import unicodedata
from difflib import SequenceMatcher

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clinic.models.clients import Client
from apps.clinic.models.odonto import DentalArcade, Tooth, Surface, Procedure


class Command(BaseCommand):
    help = 'Import dental arcade data from Bruna CSV exports into odonto models.'
    LEGACY_CHAR_MAP = {
        '\x87': 'á',
        '\x8d': 'ç',
        '\x8b': 'ã',
        '\x99': 'ô',
        '\x97': 'ó',
        '\x8e': 'é',
    }
    INTERNATIONAL_NUMBER_BY_SEQUENCE = {
        1: 18, 2: 17, 3: 16, 4: 15, 5: 14, 6: 13, 7: 12, 8: 11,
        9: 21, 10: 22, 11: 23, 12: 24, 13: 25, 14: 26, 15: 27, 16: 28,
        17: 48, 18: 47, 19: 46, 20: 45, 21: 44, 22: 43, 23: 42, 24: 41,
        25: 31, 26: 32, 27: 33, 28: 34, 29: 35, 30: 36, 31: 37, 32: 38,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-dir',
            type=str,
            default='backup_database/Bruna_Carvalho',
            help='Directory containing CSV exports (PACIENTE_DADOS, TRATAMENTO, TRATAMENTO_ARCADA, TRATAMENTO_ITEM)',
        )
        parser.add_argument(
            '--professional-email',
            type=str,
            default='brunadentista@mail.com',
            help='Email of the professional (Bruna) in the local database.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be done without saving to database.',
        )
        parser.add_argument(
            '--alias-csv',
            type=str,
            default='',
            help='Optional CSV mapping legacy_name -> client_id/client_name for approved reconciliations.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_dir = Path(options['csv_dir'])
        professional_email = options['professional_email']
        dry_run = options['dry_run']
        alias_csv = (options.get('alias_csv') or '').strip()

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

        self.stdout.write(f'📋 Starting import for professional: {professional.first_name} {professional.last_name}')
        self.stdout.write(f'📁 CSV directory: {csv_dir}')

        # Load CSV files
        patients = self._load_patients_csv(csv_dir / 'PACIENTE_DADOS.csv')
        treatments = self._load_treatments_csv(csv_dir / 'TRATAMENTO.csv')
        arcade_rows = self._load_arcade_csv(csv_dir / 'TRATAMENTO_ARCADA.csv')
        procedures = self._load_procedures_csv(csv_dir / 'TRATAMENTO_ITEM.csv')

        self.stdout.write(f'✓ Loaded {len(patients)} patients')
        self.stdout.write(f'✓ Loaded {len(treatments)} treatments')
        self.stdout.write(f'✓ Loaded {len(arcade_rows)} arcade rows')
        self.stdout.write(f'✓ Loaded {len(procedures)} procedures')

        # Build client lookup map (by name)
        client_map = self._build_client_lookup(professional)
        alias_lookup = self._load_alias_lookup(alias_csv, professional) if alias_csv else {}
        self.stdout.write(
            f"✓ Found {len(client_map['exact'])} existing clients for professional "
            f"({len(client_map['relaxed'])} relaxed keys)"
        )
        if alias_csv:
            self.stdout.write(f"✓ Loaded {len(alias_lookup)} approved alias mappings")

        # Process data
        stats = {
            'arcades_created': 0,
            'arcades_updated': 0,
            'teeth_created': 0,
            'surfaces_created': 0,
            'procedures_created': 0,
            'procedures_updated': 0,
            'patients_not_found': 0,
            'clients_matched_fuzzy': 0,
            'clients_matched_alias': 0,
            'treatments_skipped': 0,
        }

        # Group arcade rows by treatment
        arcade_by_treatment = {}
        for row in arcade_rows:
            treat_id = row['ID_PT_HEADER']
            if treat_id not in arcade_by_treatment:
                arcade_by_treatment[treat_id] = []
            arcade_by_treatment[treat_id].append(row)

        # Group procedures by treatment
        procedures_by_treatment = {}
        for proc in procedures:
            treat_id = proc['ID_PT_HEADER']
            if treat_id not in procedures_by_treatment:
                procedures_by_treatment[treat_id] = []
            procedures_by_treatment[treat_id].append(proc)

        # Process each treatment
        for treatment in treatments:
            treat_id = treatment['ID_PT_HEADER']
            patient_id = treatment['ID_PACIENTE']

            # Find patient
            patient = next((p for p in patients if p['ID_PACIENTE'] == patient_id), None)
            if not patient:
                stats['patients_not_found'] += 1
                self.stdout.write(f'  ⚠️  Patient ID {patient_id} not found in export (skipping treatment {treat_id})')
                continue

            # Find client in local DB by name
            patient_name = patient.get('TX_NOME', '').strip()
            client, matched_mode = self._match_client(patient_name, client_map, alias_lookup)
            if matched_mode == 'fuzzy':
                stats['clients_matched_fuzzy'] += 1
            elif matched_mode == 'alias':
                stats['clients_matched_alias'] += 1

            if not patient_name or client is None:
                stats['patients_not_found'] += 1
                self.stdout.write(f'  ⚠️  Client "{patient_name}" not found locally (skipping treatment {treat_id})')
                continue

            # Create or get DentalArcade
            if dry_run:
                self.stdout.write(f'  [DRY] Would create arcade for {client.first_name} {client.last_name}')
            else:
                arcade, created = DentalArcade.objects.update_or_create(
                    professional=professional,
                    external_treatment_id=treat_id,
                    defaults={
                        'client': client,
                        'status': 'completed' if treatment.get('TX_STATUS') == 'Finalizado' else 'pending',
                        'started_at': self._parse_date(treatment.get('DT_INICIO')),
                        'completed_at': self._parse_date(treatment.get('DT_FINALIZACAO')),
                    },
                )
                if created:
                    stats['arcades_created'] += 1
                    self.stdout.write(f'  ✓ Created arcade #{arcade.id} for {client.first_name}')
                else:
                    stats['arcades_updated'] += 1

            # Create teeth and surfaces
            teeth_for_arcade = arcade_by_treatment.get(treat_id, [])
            if not dry_run and teeth_for_arcade:
                for arcade_row in teeth_for_arcade:
                    sequence = self._parse_int(arcade_row.get('NR_DENTE'))
                    if sequence is None:
                        continue

                    international_number = self._resolve_international_number(
                        arcade_row.get('NR_ODONTO'),
                        sequence,
                    )
                    if international_number is None:
                        continue

                    tooth, tooth_created = Tooth.objects.get_or_create(
                        arcade=arcade,
                        sequence=sequence,
                        defaults={
                            'international_number': international_number,
                        },
                    )
                    if tooth_created:
                        stats['teeth_created'] += 1

                        # Create 5 surfaces for each tooth
                        for code in ['O', 'PO', 'MO', 'VO', 'LDI']:
                            surface, surf_created = Surface.objects.get_or_create(
                                tooth=tooth,
                                code=code,
                            )
                            if surf_created:
                                stats['surfaces_created'] += 1

            # Create procedures
            procs_for_arcade = procedures_by_treatment.get(treat_id, [])
            if not dry_run and procs_for_arcade:
                for proc_row in procs_for_arcade:
                    region = proc_row.get('TX_REGIAO', '').strip()
                    faces = proc_row.get('TX_FACES', '').strip()

                    # Find matching tooth/surface
                    tooth = None
                    surface = None
                    if region and arcade_by_treatment.get(treat_id):
                        for arcade_row in arcade_by_treatment[treat_id]:
                            if str(arcade_row['NR_ODONTO']) == region:
                                tooth = Tooth.objects.filter(
                                    arcade=arcade,
                                    international_number=int(region),
                                ).first()
                                break

                    if tooth and faces:
                        surface = Surface.objects.filter(
                            tooth=tooth,
                            code=faces,
                        ).first()

                    procedure, proc_created = Procedure.objects.update_or_create(
                        arcade=arcade,
                        external_item_id=proc_row.get('ID_PT_ITEM'),
                        defaults={
                            'tooth': tooth,
                            'surface': surface,
                            # code (CD_TAB_PRC_ITEM), paid_amount (VL_PAG) e duration_minutes
                            # (VL_TEMPO) são dados financeiros do ERP legado — não usados no
                            # sistema atual e ignorados para reduzir custo de armazenamento.
                            'name': self._normalize_legacy_text(
                                proc_row.get('TX_NOME_PRC_ITEM', 'Procedimento')
                            ),
                            'status': 'completed' if proc_row.get('CD_STATUS') == 'FI' else 'pending',
                            'region_raw': region,
                            'faces_raw': faces,
                            'started_at': self._parse_date(proc_row.get('DT_INICIO')),
                            'completed_at': self._parse_date(proc_row.get('DT_FINALIZACAO')),
                            'patient_amount': self._parse_decimal(proc_row.get('VL_PAC')),
                        },
                    )
                    if proc_created:
                        stats['procedures_created'] += 1
                    else:
                        stats['procedures_updated'] += 1

        self.stdout.write(self.style.SUCCESS('\n✅ Import completed!\n'))
        self.stdout.write(f"  Arcades created: {stats['arcades_created']}")
        self.stdout.write(f"  Arcades updated: {stats['arcades_updated']}")
        self.stdout.write(f"  Teeth created: {stats['teeth_created']}")
        self.stdout.write(f"  Surfaces created: {stats['surfaces_created']}")
        self.stdout.write(f"  Procedures created: {stats['procedures_created']}")
        self.stdout.write(f"  Procedures updated: {stats['procedures_updated']}")
        self.stdout.write(f"  Patients not found: {stats['patients_not_found']}")
        self.stdout.write(f"  Clients alias-matched: {stats['clients_matched_alias']}")
        self.stdout.write(f"  Clients fuzzy-matched: {stats['clients_matched_fuzzy']}")

    def _load_patients_csv(self, filepath):
        return self._read_csv_rows(filepath)

    def _load_treatments_csv(self, filepath):
        return self._read_csv_rows(filepath)

    def _load_arcade_csv(self, filepath):
        return self._read_csv_rows(filepath)

    def _load_procedures_csv(self, filepath):
        return self._read_csv_rows(filepath)

    def _read_csv_rows(self, filepath):
        if not filepath.exists():
            raise CommandError(f'CSV file not found: {filepath}')

        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']
        last_error = None

        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding, newline='') as f:
                    sample = f.read(4096)
                    f.seek(0)

                    delimiter = ';'
                    if sample.count(',') > sample.count(';'):
                        delimiter = ','

                    reader = csv.DictReader(f, delimiter=delimiter)
                    rows = [row for row in reader if row]
                    self.stdout.write(f'  ✓ Loaded {filepath.name} with encoding={encoding} delimiter={delimiter}')
                    return rows
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

        raise CommandError(f'Could not decode CSV file {filepath}. Last error: {last_error}')

    def _build_client_lookup(self, professional):
        """Build lookup maps for exact and relaxed normalized patient names."""
        exact_lookup = {}
        relaxed_lookup = {}
        relaxed_lookup_multi = {}
        clients = Client.objects.filter(professional=professional)
        for client in clients:
            full_name = f'{client.first_name} {client.last_name}'.strip()
            exact_key = self._normalize_name(full_name)
            relaxed_key = self._normalize_name_relaxed(full_name)
            exact_lookup[exact_key] = client
            if relaxed_key and relaxed_key not in relaxed_lookup:
                relaxed_lookup[relaxed_key] = client
            if relaxed_key:
                relaxed_lookup_multi.setdefault(relaxed_key, []).append(client)
        return {
            'exact': exact_lookup,
            'relaxed': relaxed_lookup,
            'relaxed_multi': relaxed_lookup_multi,
        }

    def _match_client(self, patient_name, client_map, alias_lookup=None):
        patient_name = (patient_name or '').strip()
        if not patient_name:
            return None, 'none'

        # Try direct/relaxed matching first using both raw and repaired text.
        variants = [patient_name]
        repaired = self._fix_mojibake(patient_name)
        if repaired and repaired != patient_name:
            variants.append(repaired)

        alias_lookup = alias_lookup or {}
        for variant in variants:
            for key in {
                variant,
                self._normalize_name(variant),
                self._normalize_name_relaxed(variant),
            }:
                if key and key in alias_lookup:
                    return alias_lookup[key], 'alias'

        for variant in variants:
            exact_key = self._normalize_name(variant)
            if exact_key in client_map['exact']:
                return client_map['exact'][exact_key], 'exact'

            relaxed_key = self._normalize_name_relaxed(variant)
            if relaxed_key in client_map['relaxed']:
                return client_map['relaxed'][relaxed_key], 'relaxed'

        # Conservative fuzzy fallback to reduce false positives.
        best_client = None
        best_score = 0.0
        second_score = 0.0
        for variant in variants:
            relaxed_key = self._normalize_name_relaxed(variant)
            if not relaxed_key or len(relaxed_key) < 6:
                continue
            for key, candidates in client_map['relaxed_multi'].items():
                if len(candidates) != 1:
                    continue
                if abs(len(key) - len(relaxed_key)) > 8:
                    continue
                score = SequenceMatcher(None, relaxed_key, key).ratio()
                if score > best_score:
                    second_score = best_score
                    best_score = score
                    best_client = candidates[0]
                elif score > second_score:
                    second_score = score

        if best_client and best_score >= 0.93 and (best_score - second_score) >= 0.03:
            return best_client, 'fuzzy'

        return None, 'none'

    def _load_alias_lookup(self, alias_csv, professional):
        alias_path = Path(alias_csv)
        if not alias_path.exists():
            raise CommandError(f'Alias CSV file not found: {alias_path}')

        clients = {
            client.id: client
            for client in Client.objects.filter(professional=professional)
        }
        alias_lookup = {}
        with open(alias_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                client_id_raw = (row.get('client_id') or row.get('candidate_client_id') or '').strip()
                if not client_id_raw:
                    continue
                try:
                    client_id = int(client_id_raw)
                except ValueError:
                    continue
                client = clients.get(client_id)
                if client is None:
                    continue
                names = [
                    (row.get('legacy_name') or '').strip(),
                    (row.get('legacy_name_repaired') or '').strip(),
                ]
                for name in names:
                    if not name:
                        continue
                    alias_lookup[name] = client
                    alias_lookup[self._normalize_name(name)] = client
                    alias_lookup[self._normalize_name_relaxed(name)] = client
        return alias_lookup

    def _fix_mojibake(self, value):
        """Best-effort recovery for UTF-8 text read as latin-1/cp1252."""
        text = (value or '').strip()
        if not text:
            return text

        if not self._looks_like_mojibake(text):
            return text

        try:
            for source_encoding in ('cp1252', 'latin-1'):
                try:
                    repaired = text.encode(source_encoding).decode('utf-8').strip()
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue

                if repaired and any(ch.isalpha() for ch in repaired):
                    return repaired
        except Exception:
            return text
        return text

    def _looks_like_mojibake(self, value):
        text = (value or '')
        markers = (
            'Ã',
            'Â',
            '',
            '',
            '',
            '',
            '',
            '�',
        )
        return any(marker in text for marker in markers)

    def _normalize_legacy_text(self, value):
        text = (value or '').strip()
        if not text:
            return text

        # First normalize known legacy control-byte substitutions.
        for bad_char, good_char in self.LEGACY_CHAR_MAP.items():
            text = text.replace(bad_char, good_char)

        fixed = self._fix_mojibake(text)
        # Keep text canonically composed for stable display/search.
        return unicodedata.normalize('NFC', fixed)

    def _normalize_name(self, value):
        normalized = unicodedata.normalize('NFKD', (value or '').strip().lower())
        no_accents = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
        return ' '.join(no_accents.split())

    def _normalize_name_relaxed(self, value):
        normalized = self._normalize_name(value)
        tokens = [t for t in normalized.split(' ') if t]
        noise_tokens = {
            'uniodonto',
            'uniodonto-',
            'endo',
            '-',
            'paciente',
        }
        clean_tokens = []
        for token in tokens:
            raw = ''.join(ch for ch in token if ch.isalnum())
            if not raw:
                continue
            if raw.isdigit():
                continue
            if raw in noise_tokens:
                continue
            clean_tokens.append(raw)
        return ' '.join(clean_tokens)

    def _parse_date(self, value):
        if not value or value.strip() == '':
            return None
        try:
            # Try common Brazilian date formats
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d/%m/%Y %H:%M']:
                try:
                    return datetime.strptime(value.strip(), fmt).date()
                except ValueError:
                    continue
        except (ValueError, AttributeError):
            pass
        return None

    def _parse_decimal(self, value):
        if not value or value.strip() == '':
            return None
        try:
            # Replace comma with dot for Brazilian format
            return Decimal(str(value).replace(',', '.'))
        except (ValueError, AttributeError):
            return None

    def _parse_int(self, value):
        if not value or value.strip() == '':
            return None
        try:
            return int(float(str(value).replace(',', '.')))
        except (ValueError, AttributeError):
            return None

    def _resolve_international_number(self, raw_number, sequence):
        parsed = self._parse_int(raw_number)
        if parsed and parsed in self.INTERNATIONAL_NUMBER_BY_SEQUENCE.values():
            return parsed
        return self.INTERNATIONAL_NUMBER_BY_SEQUENCE.get(sequence)
