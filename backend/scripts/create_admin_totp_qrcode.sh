#!/usr/bin/env zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
BACKEND_DIR=${SCRIPT_DIR:h}
PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"

if [[ ${1:-} == "-h" || ${1:-} == "--help" || ${1:-} == "" ]]; then
  echo "Usage: scripts/create_admin_totp_qrcode.sh <admin_email> [output_png]"
  echo "Example: scripts/create_admin_totp_qrcode.sh edu_fabric@outlook.com .temp/totp-admin.png"
  exit 0
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Virtualenv python not found at ${PYTHON_BIN}" >&2
  exit 1
fi

ADMIN_EMAIL=${1}
QR_OUTPUT=${2:-.temp/totp-admin.png}

cd "${BACKEND_DIR}"

ADMIN_EMAIL="${ADMIN_EMAIL}" QR_OUTPUT="${QR_OUTPUT}" "${PYTHON_BIN}" manage.py shell <<'PY'
from pathlib import Path
import os

import pyotp
import qrcode
from django.conf import settings
from django.contrib.auth import get_user_model

email = (os.environ.get('ADMIN_EMAIL') or '').strip().lower()
output = (os.environ.get('QR_OUTPUT') or '.temp/totp-admin.png').strip()

if not email:
    raise SystemExit('ADMIN_EMAIL is required.')

User = get_user_model()
user = User.objects.get(email__iexact=email)

secret = pyotp.random_base32()
user.totp_secret = secret
user.save(update_fields=['totp_secret'])

issuer = getattr(settings, 'TOTP_ISSUER', 'ClinicSystem')
uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)

output_path = Path(output)
if not output_path.is_absolute():
    output_path = Path.cwd() / output_path
output_path.parent.mkdir(parents=True, exist_ok=True)
qrcode.make(uri).save(output_path)

print(f'Admin: {user.email}')
print(f'Issuer: {issuer}')
print(f'QR generated at: {output_path}')
print(f'otpauth URI: {uri}')
PY