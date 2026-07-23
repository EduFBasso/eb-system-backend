#!/usr/bin/env python3
"""
Fix encoding of text fields imported from MacRoman-encoded CSV but
stored as if each byte were a Unicode code point (U+0000–U+00FF).

Run once:
  .venv/bin/python3 scripts/data-fix/fix_encoding.py [--dry-run]
"""

import os
import sys


def configure_django() -> None:
    script_dir = os.path.abspath(os.path.dirname(__file__))
    backend_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    settings_module = os.path.join(backend_root, "core", "settings", "__init__.py")
    if not os.path.exists(settings_module):
        raise RuntimeError(
            "Nao foi possivel localizar core/settings. "
            "Execute este script a partir do projeto backend."
        )

    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


configure_django()

import django

django.setup()

from apps.clients.models import Client
from apps.odonto.models import Procedure


def fix_text(value: str) -> str:
    """
    Re-encode a string that was mis-imported:
      original bytes (MacRoman) were stored as Unicode code points.
    Fix: encode back to Latin-1 bytes (identity for U+0000–U+00FF),
         then decode those bytes as Mac Roman.
    Only touches chars in U+0080–U+00FF range (control/extended).
    """
    if not value:
        return value
    try:
        # Only attempt fix if string contains chars that look like raw MacRoman bytes
        if not any(0x80 <= ord(c) <= 0xFF for c in value):
            return value
        return value.encode("latin-1", errors="replace").decode("mac_roman", errors="replace")
    except Exception:
        return value


def fix_procedures(dry_run: bool) -> int:
    qs = Procedure.objects.all()
    updated = 0
    for proc in qs.iterator():
        new_name = fix_text(proc.name)
        new_notes = fix_text(proc.notes)

        if new_name != proc.name or new_notes != proc.notes:
            if dry_run:
                if new_name != proc.name:
                    print(f"[{proc.id}] name: {repr(proc.name)} -> {repr(new_name)}")
                if new_notes != proc.notes:
                    print(f"[{proc.id}] notes: {repr(proc.notes[:80])} -> {repr(new_notes[:80])}")
            else:
                proc.name = new_name
                proc.notes = new_notes
                proc.save(update_fields=["name", "notes"])
            updated += 1
    return updated


def fix_clients(dry_run: bool) -> int:
    updated = 0
    for client in Client.objects.all().iterator():
        new_first = fix_text(client.first_name or "")
        new_last = fix_text(client.last_name or "")

        if new_first != (client.first_name or "") or new_last != (client.last_name or ""):
            if dry_run:
                if new_first != (client.first_name or ""):
                    print(
                        f"Client [{client.id}] first_name: {repr(client.first_name)} -> {repr(new_first)}"
                    )
                if new_last != (client.last_name or ""):
                    print(
                        f"Client [{client.id}] last_name: {repr(client.last_name)} -> {repr(new_last)}"
                    )
            else:
                client.first_name = new_first
                client.last_name = new_last
                client.save(update_fields=["first_name", "last_name"])
            updated += 1
    return updated


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN — no changes will be saved ===\n")

    print("--- Procedures ---")
    n = fix_procedures(dry_run)
    print(f"{'Would update' if dry_run else 'Updated'}: {n} procedures\n")

    print("--- Clients ---")
    n = fix_clients(dry_run)
    print(f"{'Would update' if dry_run else 'Updated'}: {n} clients\n")

    if dry_run:
        print("\nRun without --dry-run to apply changes.")
    else:
        print("Done.")
