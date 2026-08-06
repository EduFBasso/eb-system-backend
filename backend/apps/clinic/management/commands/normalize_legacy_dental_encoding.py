import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.clinic.models.odonto import Procedure


class Command(BaseCommand):
    help = 'Normalize mojibake/encoding issues in odonto text fields.'
    LEGACY_CHAR_MAP = {
        '\x87': 'á',
        '\x8d': 'ç',
        '\x8b': 'ã',
        '\x99': 'ô',
        '\x97': 'ó',
        '\x8e': 'é',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=int,
            default=None,
            help='Optional client id to normalize only one client first.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        client_id = options.get('client_id')
        dry_run = options.get('dry_run', False)

        queryset = Procedure.objects.select_related('arcade', 'arcade__client').all()
        if client_id is not None:
            queryset = queryset.filter(arcade__client_id=client_id)

        checked = 0
        changed = 0

        for proc in queryset.iterator():
            checked += 1
            original_name = proc.name or ''
            normalized_name = self._normalize_legacy_text(original_name)

            if normalized_name != original_name:
                changed += 1
                self.stdout.write(
                    f"Procedure {proc.id} | Client {proc.arcade.client_id} | "
                    f"{original_name} -> {normalized_name}"
                )
                if not dry_run:
                    proc.name = normalized_name
                    proc.save(update_fields=['name'])

        mode = 'DRY-RUN' if dry_run else 'APPLY'
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] checked={checked} changed={changed}"
        ))

        if dry_run:
            transaction.set_rollback(True)

    def _looks_like_mojibake(self, value):
        text = value or ''
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

    def _fix_mojibake(self, value):
        text = (value or '').strip()
        if not text:
            return text

        if not self._looks_like_mojibake(text):
            return text

        for source_encoding in ('cp1252', 'latin-1'):
            try:
                repaired = text.encode(source_encoding).decode('utf-8').strip()
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

            if repaired and any(ch.isalpha() for ch in repaired):
                return repaired

        return text

    def _normalize_legacy_text(self, value):
        text = (value or '').strip()
        if not text:
            return text

        for bad_char, good_char in self.LEGACY_CHAR_MAP.items():
            text = text.replace(bad_char, good_char)

        fixed = self._fix_mojibake(text)
        return unicodedata.normalize('NFC', fixed)
