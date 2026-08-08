from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .cep import normalize_cep


@dataclass(frozen=True)
class CepLookupResult:
    street: str
    neighborhood: str
    city: str
    state: str
    zip_code: str


def lookup_via_cep(zip_code: str, *, timeout: int = 10) -> CepLookupResult | None:
    digits = normalize_cep(zip_code)
    if len(digits) != 8:
        return None

    response = requests.get(
        f'https://viacep.com.br/ws/{digits}/json/',
        timeout=timeout,
    )
    response.raise_for_status()

    data: dict[str, Any] = response.json()
    if data.get('erro'):
        return None

    return CepLookupResult(
        street=str(data.get('logradouro') or ''),
        neighborhood=str(data.get('bairro') or ''),
        city=str(data.get('localidade') or ''),
        state=str(data.get('uf') or ''),
        zip_code=digits,
    )