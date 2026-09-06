"""Frontend application registry for trusted origins and multi-RP WebAuthn.

Gate Zero placeholder: implementation will be added in the Multi-RP phase.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FrontendApplication:
    application_key: str
    origin: str
    rp_id: str
    rp_name: str
