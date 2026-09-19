from __future__ import annotations


def normalize_cep(value: str) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())[:8]