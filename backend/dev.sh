#!/usr/bin/env bash
# dev.sh — Sobe o servidor Django e o loop de lembretes de push em paralelo.
#
# Uso:
#   cd backend
#   bash dev.sh
#
# O loop de lembretes roda send_clinic_appointment_reminders a cada 60 segundos por
# padrão. Ajuste REMINDERS_LOOP_INTERVAL_SECONDS se necessário.
# Em produção NÃO use este script — configure o cron job no Render.

set -euo pipefail

# Garante que estamos na pasta backend
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

REMINDERS_LOOP_INTERVAL_SECONDS="${REMINDERS_LOOP_INTERVAL_SECONDS:-60}"
PYTHON_BIN="${PYTHON_BIN:-$SCRIPT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python"
fi

# ── Loop de lembretes em background ────────────────────────────────────────
reminder_loop() {
    echo "[reminders] Loop iniciado — rodando send_clinic_appointment_reminders a cada ${REMINDERS_LOOP_INTERVAL_SECONDS} s"
    while true; do
        "$PYTHON_BIN" manage.py send_clinic_appointment_reminders 2>&1 | sed 's/^/[reminders] /'
        sleep "$REMINDERS_LOOP_INTERVAL_SECONDS"
    done
}

reminder_loop &
REMINDER_PID=$!

# Garante que o loop morre quando este script for encerrado (Ctrl+C)
trap "echo ''; echo '[dev.sh] Encerrando...'; kill $REMINDER_PID 2>/dev/null; exit 0" INT TERM

# ── Servidor Django (foreground) ────────────────────────────────────────────
echo "[server] Iniciando Django em 0.0.0.0:8000"
"$PYTHON_BIN" manage.py runserver 0.0.0.0:8000

# Se o servidor sair, encerra o loop também
kill "$REMINDER_PID" 2>/dev/null
