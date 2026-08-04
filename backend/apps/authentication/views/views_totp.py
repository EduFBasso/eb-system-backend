import re
import io
import pyotp
import qrcode
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.core.mail import EmailMessage
from .models import Professional, DeviceSession
from .serializers import ProfessionalSerializer

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def totp_setup(request):
    """Generate (or regenerate) a TOTP secret for the authenticated professional.

    Returns the otpauth:// URI so the frontend can render a QR code.
    The secret is saved immediately — the professional must verify a code
    (via totp_confirm) before the secret is considered active. For simplicity
    in phase 1 we save it directly and rely on the verify endpoint.

    POST /register/auth/totp/setup/
    Response: { secret, otpauth_uri, issuer }
    """
    user = request.user
    secret = pyotp.random_base32()
    user.totp_secret = secret  # type: ignore[union-attr]
    user.save(update_fields=["totp_secret"])  # type: ignore[union-attr]

    issuer = getattr(settings, "TOTP_ISSUER", "ClinicSystem")
    email = user.email  # type: ignore[union-attr]
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name=issuer)

    logger.info("[TOTP Setup] New secret generated for user=%s", email)
    return Response({
        "secret": secret,
        "otpauth_uri": uri,
        "issuer": issuer,
    })


@api_view(["POST"])
def totp_verify(request):
    """Authenticate using email + TOTP code, return JWT.

    Replaces the OTP-email flow for professionals that have TOTP configured.

    POST /register/auth/totp/verify/
    Body: { email, code, device_id (optional) }
    Response: { access, refresh, professional, device_id }
    """
    email = (request.data.get("email") or "").strip()
    raw_code = (request.data.get("code") or "").strip()
    code = re.sub(r"\D", "", raw_code)[:6]
    device_id = (request.data.get("device_id") or "").strip()[:64]

    red_email = email.split("@")[0] + "@***" if "@" in email else "***"
    logger.info("[TOTP Verify] user=%s", red_email)

    if not email or not code or len(code) != 6:
        return Response(
            {"valid": False, "message": "E-mail e código de 6 dígitos são obrigatórios."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        professional = Professional.objects.get(email__iexact=email)
    except Professional.DoesNotExist:
        return Response(
            {"valid": False, "message": "Profissional não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not professional.is_active:
        return Response(
            {"valid": False, "message": "Conta desativada."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not professional.totp_secret:
        return Response(
            {"valid": False, "message": "TOTP não configurado para este profissional."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    totp = pyotp.TOTP(professional.totp_secret)
    valid_window = max(0, int(getattr(settings, "TOTP_VALID_WINDOW", 4)))
    # valid_window=4 accepts codes ±120s from server time.
    # On iOS the user must: see code in authenticator → switch app → type → submit.
    # That round-trip easily spans 20-40s; if the code is near end-of-window this
    # exceeds the ±60s tolerance of valid_window=2, causing silent rejections on iPhone.
    if not totp.verify(code, valid_window=valid_window):
        logger.warning("[TOTP Verify] Invalid code for user=%s", red_email)
        return Response(
            {"valid": False, "message": "Código inválido ou expirado."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Register device session
    if not device_id:
        device_id = f"totp-{professional.pk}"
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

    # Enforce session limit
    max_sessions = getattr(settings, "MAX_ACTIVE_DEVICE_SESSIONS", 2)
    active_qs = DeviceSession.objects.filter(professional=professional, is_active=True)
    active_count = active_qs.count()
    if active_count > max_sessions:
        overflow = active_count - max_sessions
        to_close = (
            DeviceSession.objects
            .filter(professional=professional, is_active=True)
            .exclude(device_id=device_id)
            .order_by("last_seen_at")[:overflow]
        )
        for s in to_close:
            s.terminate(reason="limit")
        active_count = max_sessions

    refresh = RefreshToken.for_user(professional)
    logger.info("[TOTP Verify] Success for user=%s", red_email)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "professional": ProfessionalSerializer(professional).data,
        "active_sessions_count": active_count,
        "device_id": device_id,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def professional_create(request):
    """Create a new Professional and immediately generate a TOTP secret.

    Requires superuser JWT. Returns the professional data plus the otpauth_uri
    so the frontend can show a QR code for the new user to scan right away.

    POST /register/auth/professional-create/
    Body: { email, first_name, last_name, password, specialty?, register_number?, phone?, city?, state? }
    Response: { professional, secret, otpauth_uri, issuer }
    """
    email = (request.data.get("email") or "").strip().lower()
    first_name = (request.data.get("first_name") or "").strip()
    last_name = (request.data.get("last_name") or "").strip()
    password = request.data.get("password") or ""
    display_name = (request.data.get("display_name") or "").strip()
    specialty = (request.data.get("specialty") or "").strip()
    register_number = (request.data.get("register_number") or "").strip() or None
    phone = (request.data.get("phone") or "").strip() or ""
    city = (request.data.get("city") or "").strip()
    state = (request.data.get("state") or "").strip()[:2].upper()

    if not email or not first_name or not last_name or not password:
        return Response(
            {"message": "email, first_name, last_name e password são obrigatórios."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if Professional.objects.filter(email__iexact=email).exists():
        return Response(
            {"message": "Já existe um profissional com este e-mail."},
            status=status.HTTP_409_CONFLICT,
        )

    secret = pyotp.random_base32()
    professional = Professional.objects.create_user( # type: ignore
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
        specialty=specialty,
        register_number=register_number,
        phone=phone,
        city=city,
        state=state,
        totp_secret=secret,
    )

    issuer = getattr(settings, "TOTP_ISSUER", "ClinicSystem")
    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)

    logger.info("[Professional Create] Created user=%s by superuser=%s", email, request.user.email)  # type: ignore[union-attr]
    return Response({
        "professional": ProfessionalSerializer(professional).data,
        "secret": secret,
        "otpauth_uri": uri,
        "issuer": issuer,
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def totp_admin_reset(request):
    """Reset the TOTP secret of any professional (e.g. lost phone).

    Requires superuser JWT. Generates a new secret and returns the otpauth_uri
    so the admin can show the QR code to the professional.

    POST /register/auth/totp/admin-reset/
    Body: { user_id }
    Response: { secret, otpauth_uri, issuer, professional }
    """
    user_id = request.data.get("user_id")
    if not user_id:
        return Response(
            {"message": "user_id é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        professional = Professional.objects.get(pk=user_id)
    except Professional.DoesNotExist:
        return Response(
            {"message": "Profissional não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    secret = pyotp.random_base32()
    professional.totp_secret = secret
    professional.save(update_fields=["totp_secret"])

    issuer = getattr(settings, "TOTP_ISSUER", "ClinicSystem")
    uri = pyotp.TOTP(secret).provisioning_uri(name=professional.email, issuer_name=issuer)

    logger.info(
        "[TOTP Admin Reset] secret reset for user=%s by superuser=%s",
        professional.email,
        request.user.email,  # type: ignore[union-attr]
    )

    # Send email to professional with new QR code attached
    try:
        qr_img = qrcode.make(uri)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        buf.seek(0)

        subject = f"[{issuer}] Seu novo código de autenticação"
        body = (
            f"Olá, {professional.first_name}!\n\n"
            "Seu autenticador foi redefinido por um administrador.\n"
            "Abra o Google Authenticator (ou app compatível) e escaneie\n"
            "o QR code em anexo para configurar o novo código de entrada.\n\n"
            "Se você não solicitou esta alteração, entre em contato com o administrador imediatamente.\n\n"
            f"— {issuer}"
        )
        email_msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@clinicsystem.app"),
            to=[professional.email],
        )
        email_msg.attach("authenticator-qrcode.png", buf.read(), "image/png")
        email_msg.send(fail_silently=True)
        logger.info("[TOTP Admin Reset] QR code email sent to %s", professional.email)
    except Exception as exc:
        logger.warning("[TOTP Admin Reset] Failed to send email to %s: %s", professional.email, exc)

    return Response({
        "secret": secret,
        "otpauth_uri": uri,
        "issuer": issuer,
        "professional": ProfessionalSerializer(professional).data,
    })
