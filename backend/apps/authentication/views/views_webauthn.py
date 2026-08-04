"""WebAuthn / Passkey endpoints.

Endpoints:
    POST /register/auth/webauthn/register-begin/    — IsAuthenticated
    POST /register/auth/webauthn/register-complete/ — IsAuthenticated
    POST /register/auth/webauthn/login-begin/       — AllowAny
    POST /register/auth/webauthn/login-complete/    — AllowAny

Flow:
    1. After successful TOTP login the frontend calls register-begin, receives
       PublicKeyCredentialCreationOptions, prompts the user for biometrics and
       sends the attestation to register-complete.
    2. On subsequent logins the frontend calls login-begin with the email,
       receives PublicKeyCredentialRequestOptions, prompts the user for
       biometrics and sends the assertion to login-complete which returns a
       JWT just like totp_verify does.
"""

import base64
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

import webauthn
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import DeviceSession, Professional, WebAuthnCredential
from .serializers_professionals import ProfessionalSerializer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registration (caller must already have a valid JWT from TOTP login)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webauthn_register_begin(request):
    """Return PublicKeyCredentialCreationOptions so the browser can prompt
    the user for biometrics.

    POST /register/auth/webauthn/register-begin/
    Response: PublicKeyCredentialCreationOptions (JSON)
    """
    professional = request.user

    options = webauthn.generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(professional.pk).encode(),
        user_name=professional.email,
        user_display_name=f"{professional.first_name} {professional.last_name}",
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
    )

    # Challenge stored as bytes in cache (key = professional PK)
    cache.set(f"wa_reg_{professional.pk}", options.challenge, timeout=300)

    logger.info("[WebAuthn] register-begin for user=%s", professional.email)
    return Response(json.loads(webauthn.options_to_json(options)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webauthn_register_complete(request):
    """Verify attestation and persist the WebAuthn credential.

    POST /register/auth/webauthn/register-complete/
    Body: { credential: <RegistrationResponseJSON>, device_name?: string }
    Response: { ok: true }
    """
    professional = request.user
    credential_data = request.data.get("credential")
    device_name = (request.data.get("device_name") or "")[:120]

    if not credential_data:
        return Response({"error": "Dados de credencial ausentes."}, status=400)

    stored_challenge = cache.get(f"wa_reg_{professional.pk}")
    if not stored_challenge:
        return Response({"error": "Sessão de registro expirada. Tente novamente."}, status=400)

    try:
        credential = RegistrationCredential(
            id=credential_data["id"],
            raw_id=base64url_to_bytes(credential_data["rawId"]),
            response=AuthenticatorAttestationResponse(
                client_data_json=base64url_to_bytes(
                    credential_data["response"]["clientDataJSON"]
                ),
                attestation_object=base64url_to_bytes(
                    credential_data["response"]["attestationObject"]
                ),
            ),
            type=credential_data.get("type", "public-key"),
        )

        verification = webauthn.verify_registration_response(
            credential=credential,
            expected_challenge=stored_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGINS,
        )
    except Exception as exc:
        logger.warning(
            "[WebAuthn] register-complete failed for user=%s: %s",
            professional.email,
            exc,
        )
        return Response({"error": str(exc)}, status=400)

    cache.delete(f"wa_reg_{professional.pk}")

    # Persist — credential_id stored as base64url (the "id" from the frontend)
    WebAuthnCredential.objects.update_or_create(
        credential_id=credential_data["id"],
        defaults={
            "professional": professional,
            "public_key": base64.b64encode(verification.credential_public_key).decode(),
            "sign_count": verification.sign_count,
            "device_name": device_name,
        },
    )

    logger.info(
        "[WebAuthn] register-complete OK for user=%s device=%s",
        professional.email,
        device_name,
    )
    return Response({"ok": True})


# ---------------------------------------------------------------------------
# Authentication (public — no JWT required)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([AllowAny])
def webauthn_login_begin(request):
    """Return PublicKeyCredentialRequestOptions for the given email.

    POST /register/auth/webauthn/login-begin/
    Body: { email: string }
    Response: PublicKeyCredentialRequestOptions (JSON)
    """
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response({"error": "E-mail obrigatório."}, status=400)

    try:
        professional = Professional.objects.get(email__iexact=email, is_active=True)
    except Professional.DoesNotExist:
        return Response({"error": "Usuário não encontrado."}, status=404)

    credentials = professional.webauthn_credentials.all() # type: ignore
    if not credentials.exists():
        return Response({"error": "Nenhuma biometria registrada para este usuário."}, status=404)

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
        for c in credentials
    ]

    options = webauthn.generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    cache.set(f"wa_login_{professional.pk}", options.challenge, timeout=300)

    logger.info("[WebAuthn] login-begin for user=%s", email)
    return Response(json.loads(webauthn.options_to_json(options)))


@api_view(["POST"])
@permission_classes([AllowAny])
def webauthn_login_complete(request):
    """Verify authentication assertion and return JWT.

    POST /register/auth/webauthn/login-complete/
    Body: { email: string, assertion: <AuthenticationResponseJSON>, device_id?: string }
    Response: { access, refresh, professional, active_sessions_count, device_id }
    """
    email = (request.data.get("email") or "").strip().lower()
    assertion_data = request.data.get("assertion")
    device_id = (request.data.get("device_id") or "").strip()[:64]

    if not email or not assertion_data:
        return Response({"error": "E-mail e credencial são obrigatórios."}, status=400)

    try:
        professional = Professional.objects.get(email__iexact=email, is_active=True)
    except Professional.DoesNotExist:
        return Response({"error": "Usuário não encontrado."}, status=404)

    stored_challenge = cache.get(f"wa_login_{professional.pk}")
    if not stored_challenge:
        return Response({"error": "Sessão expirada. Tente novamente."}, status=400)

    credential_id_b64url = assertion_data.get("id", "")
    try:
        stored_cred = professional.webauthn_credentials.get(credential_id=credential_id_b64url) # type: ignore
    except WebAuthnCredential.DoesNotExist:
        return Response({"error": "Credencial não encontrada."}, status=400)

    try:
        assertion = AuthenticationCredential(
            id=assertion_data["id"],
            raw_id=base64url_to_bytes(assertion_data["rawId"]),
            response=AuthenticatorAssertionResponse(
                client_data_json=base64url_to_bytes(
                    assertion_data["response"]["clientDataJSON"]
                ),
                authenticator_data=base64url_to_bytes(
                    assertion_data["response"]["authenticatorData"]
                ),
                signature=base64url_to_bytes(assertion_data["response"]["signature"]),
                user_handle=(
                    base64url_to_bytes(assertion_data["response"]["userHandle"])
                    if assertion_data["response"].get("userHandle")
                    else None
                ),
            ),
            type=assertion_data.get("type", "public-key"),
        )

        verification = webauthn.verify_authentication_response(
            credential=assertion,
            expected_challenge=stored_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGINS,
            credential_public_key=base64.b64decode(stored_cred.public_key),
            credential_current_sign_count=stored_cred.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        logger.warning(
            "[WebAuthn] login-complete failed for user=%s: %s", email, exc
        )
        return Response({"error": str(exc)}, status=401)

    cache.delete(f"wa_login_{professional.pk}")

    # Update sign count and last used timestamp
    stored_cred.sign_count = verification.new_sign_count
    stored_cred.last_used_at = timezone.now()
    stored_cred.save(update_fields=["sign_count", "last_used_at"])

    # Register / update device session (same logic as totp_verify)
    if not device_id:
        device_id = f"wa-{professional.pk}"
    ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]
    ip = request.META.get("REMOTE_ADDR")

    session, created = DeviceSession.objects.get_or_create(
        professional=professional,
        device_id=device_id,
        defaults={"user_agent": ua, "ip_address": ip, "is_active": True},
    )
    if not created:
        session.is_active = True
        session.user_agent = ua
        session.ip_address = ip
        session.save()

    max_sessions = getattr(settings, "MAX_ACTIVE_DEVICE_SESSIONS", 2)
    active_qs = DeviceSession.objects.filter(professional=professional, is_active=True)
    active_count = active_qs.count()
    if active_count > max_sessions:
        overflow = active_count - max_sessions
        to_close = (
            DeviceSession.objects.filter(professional=professional, is_active=True)
            .exclude(device_id=device_id)
            .order_by("last_seen_at")[:overflow]
        )
        for s in to_close:
            s.terminate(reason="limit")
        active_count = max_sessions

    refresh = RefreshToken.for_user(professional)
    logger.info("[WebAuthn] login-complete OK for user=%s", email)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "professional": ProfessionalSerializer(professional).data,
            "active_sessions_count": active_count,
            "device_id": device_id,
        },
        status=status.HTTP_200_OK,
    )
