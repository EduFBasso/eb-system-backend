"""Compatibilidade para o comando Clinic movido para apps.clinic."""

from apps.clinic.management.commands.seed_demo_professional import Command

__all__ = ["Command"]
