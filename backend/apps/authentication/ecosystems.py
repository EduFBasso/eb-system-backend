"""Registro central de ecossistemas (multi-tenant / multi-ecosystem).

Fonte única de verdade para tudo que varia por ecossistema: capabilities
permitidas, configuração de bot do Telegram, prefixo de URL e se o ecossistema
aceita auto-cadastro público de clientes.

Adicionar um novo ecossistema passa a ser registrar um ``EcosystemSpec`` aqui
(e um valor correspondente em ``Tenant.Ecosystem``), em vez de editar ``if/elif``
espalhados por autenticação, permissões, notificações e views.

Este módulo não importa modelos nem lê ``settings`` em tempo de import: ele
guarda apenas os *nomes* das variáveis de configuração, resolvidos no uso.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EcosystemSpec:
    slug: str
    label: str
    url_prefix: str
    allowed_capabilities: frozenset[str]
    telegram_token_setting: str
    telegram_api_base_setting: str
    telegram_timeout_setting: str
    public_self_registration: bool


_SPECS: tuple[EcosystemSpec, ...] = (
    EcosystemSpec(
        slug="clinic",
        label="Unidade Clínica (Saúde/Estética)",
        url_prefix="/",
        allowed_capabilities=frozenset({"clinic", "podologia", "odonto"}),
        telegram_token_setting="CLINIC_TELEGRAM_BOT_TOKEN",
        telegram_api_base_setting="CLINIC_TELEGRAM_BOT_API_BASE",
        telegram_timeout_setting="CLINIC_TELEGRAM_BOT_TIMEOUT_SECONDS",
        public_self_registration=False,
    ),
    EcosystemSpec(
        slug="bakery",
        label="Unidade Padaria (Alimentação/Varejo)",
        url_prefix="/api/v1/bakery/",
        allowed_capabilities=frozenset({"bakery"}),
        telegram_token_setting="BAKERY_TELEGRAM_BOT_TOKEN",
        telegram_api_base_setting="BAKERY_TELEGRAM_BOT_API_BASE",
        telegram_timeout_setting="BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS",
        public_self_registration=True,
    ),
)

REGISTRY: dict[str, EcosystemSpec] = {spec.slug: spec for spec in _SPECS}

#: Union de todas as capabilities que o sistema reconhece em qualquer ecossistema.
KNOWN_CAPABILITIES: frozenset[str] = frozenset().union(
    *(spec.allowed_capabilities for spec in _SPECS)
)


def ecosystem_slugs() -> tuple[str, ...]:
    return tuple(REGISTRY)


def get_ecosystem(slug: str) -> EcosystemSpec:
    try:
        return REGISTRY[slug]
    except KeyError:
        raise ValueError(f"Ecossistema não registrado: {slug!r}")


def allowed_capabilities(slug: str) -> frozenset[str]:
    return get_ecosystem(slug).allowed_capabilities
