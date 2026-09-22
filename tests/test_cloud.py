"""Regression tests for VIVAX EcoLink cloud authentication."""

from __future__ import annotations

import pytest
from aiohttp import ClientResponseError

from custom_components.vivax_ecolink.cloud import (
    AuthenticationError,
    VivaxCloudClient,
)
from custom_components.vivax_ecolink.models import ApplicationCredentials


class UnauthorizedResponse:
    """Minimal aiohttp response returning the vendor's expired-token status."""

    async def __aenter__(self) -> UnauthorizedResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        raise ClientResponseError(None, (), status=401)


class UnauthorizedSession:
    """Minimal session that always rejects the bearer token."""

    def post(self, *_args: object, **_kwargs: object) -> UnauthorizedResponse:
        return UnauthorizedResponse()


@pytest.mark.asyncio
async def test_http_401_expires_cached_access_token() -> None:
    """An HTTP 401 must trigger the coordinator's login-and-retry path."""
    application = ApplicationCredentials("secret", "client", "signing", "key")
    client = VivaxCloudClient(
        UnauthorizedSession(),  # type: ignore[arg-type]
        "https://example.test",
        application,
    )
    client._access_token = "expired"

    with pytest.raises(AuthenticationError, match="expired"):
        await client._post("/endpoint", {}, {})

    assert client.authenticated is False
