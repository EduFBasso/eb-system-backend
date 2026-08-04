"""Endpoints de sessões de dispositivos (fase 1)

Fornece três endpoints não versionados (por enquanto):
    GET /sessions/summary  -> { count: int, has_others: bool }
    GET /sessions/active   -> lista de sessões ativas (inclui sessão atual primeiro)
    POST /sessions/revoke  -> { revoked: n }

Características:
 - Identifica sessão pelo header 'X-Device-Id' (case-insensitive).
 - Se inexistente, cria automaticamente (lazy create) enquanto o usuário estiver autenticado.
 - Atualiza last_seen_at (auto_now no modelo) a cada requisição.
 - 'Revoke others' encerra todas as outras sessões ativas marcando terminate(reason='revoke').
 - Respostas sempre em JSON; erros simples em formato {'detail': '...'}.

Futuras extensões possíveis:
 - Heartbeat dedicado (PATCH /sessions/heartbeat)
 - Expiração automática por inatividade (cron/management command)
 - Paginação se volume crescer
 - Campo de plataforma / device_info adicional
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from .models import DeviceSession
import logging
import re

logger = logging.getLogger(__name__)


def _extract_device_id(request) -> str:
    # Frontend envia header 'X-Device-Id'; normalizamos aqui
    raw = request.META.get("HTTP_X_DEVICE_ID") or ""
    return raw.strip()[:64] or "unknown"


def _get_or_create_session(request):
    """Localiza ou cria a sessão do dispositivo atual para o usuário autenticado.
    Retorna (session, created:Boolean). Se usuário anônimo, retorna (None, False).
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None, False
    device_id = _extract_device_id(request)
    ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:255]
    ip = request.META.get('REMOTE_ADDR')
    session, created = DeviceSession.objects.get_or_create(
        professional=user,
        device_id=device_id,
        defaults={
            'user_agent': ua,
            'ip_address': ip,
            'is_active': True,
        }
    )
    if not created:
        # Tocar last_seen_at (auto_now) e reativar se necessário
        update_fields = []
        changed = False
        if not session.is_active:
            session.is_active = True
            changed = True
        if session.user_agent != ua:
            session.user_agent = ua
            changed = True
        if session.ip_address != ip:
            session.ip_address = ip
            changed = True
        if changed:
            update_fields = ['is_active', 'user_agent', 'ip_address']
            session.save(update_fields=update_fields)
    return session, created


_BROWSER_REGEXES = [
    (re.compile(r'Chrome/(?P<ver>[0-9.]+)'), 'Chrome'),
    (re.compile(r'Firefox/(?P<ver>[0-9.]+)'), 'Firefox'),
    (re.compile(r'Edg/(?P<ver>[0-9.]+)'), 'Edge'),
    (re.compile(r'OPR/(?P<ver>[0-9.]+)'), 'Opera'),
    (re.compile(r'Safari/(?P<ver>[0-9.]+)'), 'Safari'),
]

def _parse_ua(ua: str):
    ua = ua or ''
    # OS simples
    if 'Windows NT 10' in ua:
        os = 'Windows 10+'
    elif 'Windows' in ua:
        os = 'Windows'
    elif 'Android' in ua:
        os = 'Android'
    elif 'iPhone' in ua or 'iOS' in ua:
        os = 'iOS'
    elif 'Mac OS X' in ua or 'Macintosh' in ua:
        os = 'macOS'
    elif 'Linux' in ua:
        os = 'Linux'
    else:
        os = 'Other'

    # Device type heurística
    lowered = ua.lower()
    if 'mobile' in lowered or 'iphone' in lowered or 'android' in lowered and 'mobile' in lowered:
        device_type = 'mobile'
    elif 'ipad' in lowered or 'tablet' in lowered:
        device_type = 'tablet'
    else:
        device_type = 'desktop'

    browser = 'Unknown'
    browser_version = ''
    for rx, name in _BROWSER_REGEXES:
        m = rx.search(ua)
        if m:
            browser = name
            browser_version = m.group('ver')
            break
    if browser == 'Safari' and 'Chrome/' in ua:
        browser = 'Chrome'
    return device_type, os, f"{browser} {browser_version}".strip()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sessions_summary(request):
    """Resumo simples: total de sessões ativas e se existem outras além da atual."""
    session, _ = _get_or_create_session(request)
    qs = DeviceSession.objects.filter(professional=request.user, is_active=True)
    total = qs.count()
    has_others = False
    if session:
        has_others = qs.exclude(pk=session.pk).exists()
    body = { 'count': total, 'has_others': has_others }
    return Response(body)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sessions_active(request):
    """Lista de sessões ativas ordenadas com a atual primeiro e depois por last_seen_at desc."""
    session, _ = _get_or_create_session(request)
    qs = DeviceSession.objects.filter(professional=request.user, is_active=True)

    # Construir lista; evitar N+1 (sem relações extras aqui)
    items = []
    now_iso = timezone.now().isoformat()
    for s in qs.order_by('-last_seen_at'):
        device_type, os_name, browser_name = _parse_ua(s.user_agent)
        items.append({
            'id': str(s.id), # type: ignore
            'device_id': s.device_id,
            'created_at': s.created_at.isoformat(),
            'last_seen': s.last_seen_at.isoformat() if s.last_seen_at else now_iso,
            'is_current': session is not None and s.pk == session.pk,
            'ua': s.user_agent,
            'device_type': device_type,
            'os': os_name,
            'browser': browser_name,
        })
    # Garantir que sessão atual venha primeiro
    if session:
        items.sort(key=lambda x: 0 if x.get('is_current') else 1)
    return Response(items)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def sessions_revoke(request):
    """Revoga sessões.

    Modos:
      - Revogação individual: body { "session_id": "<uuid>" }
        -> Se pertence ao usuário e estiver ativa (e não for a atual), termina e retorna { revoked: 1 }.
      - Bulk (manter atual): body { "mode": "all_except_current" }
        -> Termina todas as outras; retorna { revoked: N }.
      - Sem body ou body vazio => mesmo comportamento de all_except_current (compat).
    """
    session, _ = _get_or_create_session(request)
    data = request.data if isinstance(request.data, dict) else {}
    target_id = (data.get('session_id') or '').strip()
    mode = (data.get('mode') or '').strip()

    if target_id:
        # Revogação individual
        try:
            target = DeviceSession.objects.get(professional=request.user, pk=target_id, is_active=True)
        except DeviceSession.DoesNotExist:
            return Response({'detail': 'Sessão não encontrada ou já inativa.'}, status=status.HTTP_404_NOT_FOUND)
        if session and target.pk == session.pk:
            return Response({'detail': 'Não é possível revogar a sessão atual.'}, status=status.HTTP_400_BAD_REQUEST)
        target.terminate(reason='revoke_one')
        return Response({'revoked': 1, 'mode': 'single'})

    # Bulk
    if mode not in ('', 'all_except_current'):
        return Response({'detail': 'Modo inválido.'}, status=status.HTTP_400_BAD_REQUEST)
    qs = DeviceSession.objects.filter(professional=request.user, is_active=True)
    if session:
        qs = qs.exclude(pk=session.pk)
    revoked = 0
    for s in qs.order_by('-last_seen_at'):
        s.terminate(reason='revoke')
        revoked += 1
    return Response({'revoked': revoked, 'mode': 'bulk'})


__all__ = [
    'sessions_summary',
    'sessions_active',
    'sessions_revoke',
]
