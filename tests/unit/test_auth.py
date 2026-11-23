import asyncio
from types import SimpleNamespace

import jwt
import pytest

from app.core import auth


def test_decode_token_reports_unavailable_signing_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing crypto backend must not escape as a KeyError/500 response."""

    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"alg": "ES256", "kid": "k1"})
    monkeypatch.setattr(auth.jwt.algorithms, "get_default_algorithms", lambda: {})
    auth._jwks_cache["https://example.supabase.co/auth/v1/.well-known/jwks.json"] = [{"kid": "k1"}]

    with pytest.raises(jwt.InvalidAlgorithmError, match="not available"):
        asyncio.run(auth._decode_token("token", SimpleNamespace(supabase_url="https://example.supabase.co")))
