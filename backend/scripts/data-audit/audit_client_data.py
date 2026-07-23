#!/usr/bin/env python3
"""
Script para auditar dados completos de um cliente com arcada.

Uso:
  python scripts/data-audit/audit_client_data.py
"""

import os
import sys
import django
from collections import defaultdict


def configure_django() -> None:
    """Resolve a raiz do backend e inicializa o Django."""
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
    django.setup()


configure_django()

from apps.clients.models import Client
from apps.odonto.models import DentalArcade, Procedure, Tooth


def safe_tooth_number(proc: Procedure) -> str:
    tooth = getattr(proc, "tooth", None)
    if tooth is None:
        return "GENERAL"
    return str(getattr(tooth, "international_number", getattr(tooth, "number", "N/A")))


# Encontrar clientes com arcadas e procedures
print("\n" + "=" * 80)
print("BUSCANDO CLIENTES COM DADOS DE ARCADA")
print("=" * 80 + "\n")

clients_with_arcade = Client.objects.filter(dentalarcade__isnull=False).distinct().order_by("id")

# Contar procedures por cliente
client_stats = []
for client in clients_with_arcade:
    arcades = DentalArcade.objects.filter(client=client)
    total_procedures = Procedure.objects.filter(arcade__in=arcades).count()
    total_teeth = Tooth.objects.filter(arcade__in=arcades).count()

    if total_procedures > 0:  # Apenas clientes com procedures
        client_stats.append(
            {
                "id": client.id,
                "name": client.full_name,
                "arcades": arcades.count(),
                "teeth": total_teeth,
                "procedures": total_procedures,
            }
        )

# Ordenar por numero de procedures
client_stats.sort(key=lambda x: x["procedures"], reverse=True)

print("TOP 10 CLIENTES COM MAIS PROCEDURES:")
print("-" * 80)
for i, stat in enumerate(client_stats[:10], 1):
    print(f"{i}. Client ID={stat['id']}: {stat['name']}")
    print(
        f"   Arcadas: {stat['arcades']}, Dentes: {stat['teeth']}, Procedures: {stat['procedures']}\n"
    )

# Pegar o cliente com mais procedures para analise completa
if client_stats:
    reference_client_id = client_stats[0]["id"]
    print("\n" + "=" * 80)
    print(f"ANALISE COMPLETA - CLIENT ID: {reference_client_id}")
    print("=" * 80 + "\n")

    client = Client.objects.get(id=reference_client_id)
    arcades = DentalArcade.objects.filter(client=client)

    print(f"Cliente: {client.full_name} (ID={client.id})")
    print(f"CPF: {client.cpf}")
    print(f"Email: {client.email}")
    print(f"Telefone: {client.phone}")
    print(f"Data de criacao no sistema: {client.created_at}\n")

    # Por cada arcade
    for arcade in arcades:
        print(f"\n--- ARCADE ID: {arcade.id} ---")
        print(f"Teeth count: {arcade.teeth.count()}")

        # Procedures nesta arcade
        procedures = Procedure.objects.filter(arcade=arcade).order_by("tooth__international_number")

        # Agrupar por status
        by_status = defaultdict(list)
        has_null_dates = 0

        for proc in procedures:
            by_status[proc.status].append(proc)
            if proc.status == "pending" and not proc.started_at:
                has_null_dates += 1

        print("\nStatistics:")
        print(f"  Total procedures: {procedures.count()}")
        print(f"  - Pending: {len(by_status['pending'])} (sem started_at: {has_null_dates})")
        print(f"  - Completed: {len(by_status['completed'])}")
        print(f"  - Canceled: {len(by_status['canceled'])}")

        # General procedures (tooth=null)
        general = procedures.filter(tooth__isnull=True).count()
        tooth_specific = procedures.filter(tooth__isnull=False).count()
        print(f"  - General procedures (tooth=null): {general}")
        print(f"  - Tooth-specific procedures: {tooth_specific}")

        print("\nPROCEDURES SAMPLE (primeiras 5):")
        print("-" * 80)
        for i, proc in enumerate(procedures[:5], 1):
            print(f"\n{i}. {proc.name} (Code: {proc.code})")
            print(f"   Status: {proc.status}")
            print(f"   Tooth: {safe_tooth_number(proc)}")
            print(f"   Started: {proc.started_at if proc.started_at else 'NULL'}")
            print(f"   Completed: {proc.completed_at if proc.completed_at else 'NULL'}")
            print(
                f"   Duration: {proc.duration_minutes} min"
                if proc.duration_minutes
                else "   Duration: not set"
            )
            print(
                f"   Patient Amount: R$ {proc.patient_amount}"
                if proc.patient_amount
                else "   Patient Amount: not set"
            )

        if procedures.count() > 5:
            print(f"\n... e mais {procedures.count() - 5} procedures")

    print("\n" + "=" * 80)
    print("SUGESTAO: Use CLIENT_ID = " + str(reference_client_id))
    print("=" * 80)
