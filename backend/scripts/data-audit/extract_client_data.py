#!/usr/bin/env python3
"""
Extract complete client arcade data and generate audit report.

Usage: python scripts/data-audit/extract_client_data.py <client_id>
Example: python scripts/data-audit/extract_client_data.py 51
"""

import os
import sys
import django
import json
from datetime import datetime
from collections import defaultdict


def configure_django() -> None:
    """Resolve a raiz do backend e inicializa o Django."""
    script_dir = os.path.abspath(os.path.dirname(__file__))
    backend_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    settings_module = os.path.join(backend_root, "core", "settings", "__init__.py")
    if not os.path.exists(settings_module):
        raise RuntimeError(
            "Could not locate core/settings. "
            "Run this script from a folder where the Django backend is available."
        )

    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    django.setup()


configure_django()

from apps.clients.models import Client
from apps.odonto.models import DentalArcade, Tooth, Surface, Procedure


def get_client_full_name(client):
    full_name = getattr(client, "full_name", None)
    if full_name:
        return full_name

    first_name = getattr(client, "first_name", "") or ""
    last_name = getattr(client, "last_name", "") or ""
    composed = f"{first_name} {last_name}".strip()
    return composed or "(sem nome)"


def serialize_date(dt):
    """Serialize datetime to ISO format or None."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def extract_client_data(client_id):
    """Extract all arcade data for a client."""
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        print(json.dumps({"error": f"Client ID {client_id} not found"}, indent=2))
        sys.exit(1)

    arcades = DentalArcade.objects.filter(client=client)

    # Build arcade data
    arcades_data = []
    total_procedures = 0
    status_count = defaultdict(int)
    started_at_filled = 0
    completed_at_filled = 0
    overall_teeth_with_procedures = set()
    general_procedures_count = 0
    date_formats = set()
    anomalies = []

    for arcade in arcades:
        procedures = Procedure.objects.filter(arcade=arcade).order_by(
            "tooth__international_number", "code"
        )
        teeth = Tooth.objects.filter(arcade=arcade).order_by("sequence")
        arcade_teeth_with_procedures = set()

        procedures_data = []
        for proc in procedures:
            total_procedures += 1
            status_count[proc.status] += 1

            proc_data = {
                "id": proc.id,
                "code": proc.code,
                "name": proc.name,
                "status": proc.status,
                "tooth": proc.tooth.international_number if proc.tooth else None,
                "surface": proc.surface.code if proc.surface else None,
                "surface_label": proc.surface.label if proc.surface else None,
                "started_at": serialize_date(proc.started_at),
                "completed_at": serialize_date(proc.completed_at),
                "duration_minutes": proc.duration_minutes,
                "patient_amount": float(proc.patient_amount) if proc.patient_amount else None,
                "paid_amount": float(proc.paid_amount) if proc.paid_amount else None,
                "is_active": proc.is_active,
                "notes": proc.notes,
                "created_at": serialize_date(proc.created_at),
            }
            procedures_data.append(proc_data)

            # Data quality checks
            if proc.started_at:
                started_at_filled += 1
                date_formats.add(type(proc.started_at).__name__)
            if proc.completed_at:
                completed_at_filled += 1
            if proc.tooth:
                arcade_teeth_with_procedures.add(proc.tooth.international_number)
                overall_teeth_with_procedures.add(proc.tooth.international_number)
            else:
                general_procedures_count += 1

            # Detect anomalies
            if proc.started_at and proc.completed_at and proc.started_at > proc.completed_at:
                anomalies.append(
                    {
                        "type": "timeline_error",
                        "procedure_id": proc.id,
                        "procedure_name": proc.name,
                        "detail": "started_at after completed_at",
                    }
                )

            if proc.status == "completed" and not proc.completed_at:
                anomalies.append(
                    {
                        "type": "missing_completed_date",
                        "procedure_id": proc.id,
                        "procedure_name": proc.name,
                    }
                )

            if proc.status == "pending" and proc.completed_at:
                anomalies.append(
                    {
                        "type": "inconsistent_status",
                        "procedure_id": proc.id,
                        "procedure_name": proc.name,
                        "detail": "status=pending but has completed_at",
                    }
                )

        teeth_empty = [
            t.international_number for t in teeth if not procedures.filter(tooth=t).exists()
        ]
        teeth_coverage = len(arcade_teeth_with_procedures) * 100 / 32 if arcade_teeth_with_procedures else 0

        arcades_data.append(
            {
                "arcade_id": arcade.id,
                "created_at": serialize_date(arcade.created_at),
                "updated_at": serialize_date(arcade.updated_at),
                "procedures_count": procedures.count(),
                "teeth_total": teeth.count(),
                "teeth_with_procedures": sorted(list(arcade_teeth_with_procedures)),
                "teeth_empty": sorted(teeth_empty),
                "coverage_percentage": round(teeth_coverage, 1),
                "procedures": procedures_data,
            }
        )

    # Compile report
    report = {
        "audit_timestamp": datetime.now().isoformat(),
        "client": {
            "id": client.id,
            "full_name": get_client_full_name(client),
            "cpf": getattr(client, "cpf", None) or getattr(client, "document_number", None),
            "email": client.email,
            "phone": client.phone,
            "date_of_birth": serialize_date(client.date_of_birth) if hasattr(client, "date_of_birth") else None,
            "created_at": serialize_date(client.created_at),
            "updated_at": serialize_date(client.updated_at),
        },
        "data_quality": {
            "total_procedures": total_procedures,
            "status_distribution": dict(status_count),
            "started_at_filled": started_at_filled,
            "started_at_null": total_procedures - started_at_filled,
            "completed_at_filled": completed_at_filled,
            "completed_at_null": total_procedures - completed_at_filled,
            "general_procedures": general_procedures_count,
            "date_formats_detected": list(date_formats),
            "anomalies_count": len(anomalies),
        },
        "anomalies": anomalies,
        "arcades": arcades_data,
        "summary": {
            "teeth_with_data": len(overall_teeth_with_procedures),
            "teeth_empty": 32 - len(overall_teeth_with_procedures),
            "coverage_percentage": round(len(overall_teeth_with_procedures) * 100 / 32, 1),
        },
    }

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/data-audit/extract_client_data.py <client_id>")
        print("Example: python scripts/data-audit/extract_client_data.py 51")
        sys.exit(1)

    client_id = int(sys.argv[1])
    report = extract_client_data(client_id)
    print(json.dumps(report, indent=2, ensure_ascii=False))
