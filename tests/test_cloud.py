"""Regression tests for VIVAX EcoLink cloud authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import ClientResponseError

from custom_components.vivax_ecolink.cloud import (
    AuthenticationError,
    CloudError,
    VivaxCloudClient,
)
from custom_components.vivax_ecolink.models import ApplicationCredentials
from custom_components.vivax_ecolink.protocol import ProtocolError
from tests.test_power_control import ack


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            ClientResponseError(None, (), status=403),
            "EcoLink HTTP request failed (status 403)",
        ),
        (TimeoutError("private-request-content"), "EcoLink request timed out"),
    ],
)
async def test_transport_errors_are_specific_and_do_not_expose_request_content(
    error: Exception, message: str
) -> None:
    response = UnauthorizedResponse()
    response.raise_for_status = Mock(side_effect=error)
    session = Mock()
    session.post.return_value = response
    client = VivaxCloudClient(
        session,
        "https://example.test",
        ApplicationCredentials("secret", "client", "signing", "key"),
    )
    client._access_token = "private-token"
    with pytest.raises(CloudError) as raised:
        await client._post("/endpoint", {}, {})
    assert str(raised.value) == message
    assert client.authenticated is True


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_power_transport_sends_only_the_verified_zone1_field(
    enabled: bool,
) -> None:
    client = VivaxCloudClient(
        UnauthorizedSession(),  # type: ignore[arg-type]
        "https://example.test",
        ApplicationCredentials("secret", "client", "signing", "key"),
    )
    command = "00000101ff" if enabled else "00000100ff"
    client._business_request = AsyncMock(return_value={"code": 0, "data": ack(command)})
    await client.set_zone1_power("test-appliance", enabled)
    client._business_request.assert_awaited_once_with(
        "/midea/open/business/v1/appliance/control/hexadecimal",
        {"applianceCode": "test-appliance", "command": command},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"code": 1214, "data": None}, CloudError),
        ({"code": 0, "data": None}, CloudError),
        ({"code": 0, "data": ack("00020101ff")}, ProtocolError),
    ],
)
async def test_power_transport_rejects_errors_and_dhw_ack(
    response: dict[str, object], error: type[Exception]
) -> None:
    client = VivaxCloudClient(
        UnauthorizedSession(),  # type: ignore[arg-type]
        "https://example.test",
        ApplicationCredentials("secret", "client", "signing", "key"),
    )
    client._business_request = AsyncMock(return_value=response)
    with pytest.raises(error):
        await client.set_zone1_power("test-appliance", True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({"code": 1214}, "rejected the power command (code 1214)"),
        (
            {"code": "private-response-content"},
            "rejected the power command (code unknown)",
        ),
        ({"code": 0, "data": None}, "returned no acknowledgement"),
        ({"code": 0, "data": "aa"}, "unexpected length (1 bytes)"),
    ],
)
async def test_power_errors_explain_the_failure_without_raw_response_content(
    response: dict[str, object], message: str
) -> None:
    client = VivaxCloudClient(
        UnauthorizedSession(),  # type: ignore[arg-type]
        "https://example.test",
        ApplicationCredentials("secret", "client", "signing", "key"),
    )
    client._business_request = AsyncMock(return_value=response)
    with pytest.raises((CloudError, ProtocolError)) as error:
        await client.set_zone1_power("private-appliance", False)
    assert message in str(error.value)
    assert "private-" not in str(error.value)
    client._business_request.assert_awaited_once()
