"""Compatibilidade para o comando Clinic movido para apps.clinic."""

from apps.clinic.management.commands.import_clients_csv import Command, normalize_phone_digits

__all__ = ["Command", "normalize_phone_digits"]
