"""Compatibilidade para o comando Clinic movido para apps.clinic."""

from apps.clinic.management.commands.export_clients_csv import Command

__all__ = ["Command"]
