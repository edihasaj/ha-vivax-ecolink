"""Async client for the VIVAX EcoLink cloud service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import time
import uuid
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import APP_ID, APP_KEY, APP_VERSION
from .models import ApplicationCredentials, VivaxDevice
from .protocol import (
    decode_cloud_payload,
    short_query,
    validate_power_ack,
    zone1_power_command,
)


class CloudError(Exception):
    """Base cloud communication error."""


class AuthenticationError(CloudError):
    """Authentication failed or the access token expired."""


def _response_code(result: dict[str, Any]) -> int | str:
    """Expose only numeric vendor codes, never arbitrary response content."""
    code = result.get("code")
    return code if type(code) is int else "unknown"


class VivaxCloudClient:
    """Minimal client for the endpoints used by VIVAX EcoLink."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        application: ApplicationCredentials,
        *,
        timeout: int = 20,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._application = application
        self._timeout = ClientTimeout(total=timeout)
        self._access_token: str | None = None
        self._device_id = uuid.uuid4().hex.upper()

    @property
    def authenticated(self) -> bool:
        """Return whether a token is loaded in this runtime."""
        return self._access_token is not None

    def _v1_signature(self, body: str, random_value: str) -> str:
        message = APP_KEY + body + random_value
        return hmac.new(
            self._application.app_secret.encode("ascii"),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _v2_signature(self, path: str, body: str) -> str:
        digest = hmac.new(
            self._application.client_secret.encode(),
            f"POST{path}{body}".encode(),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode()

    def _encrypt_password(self, password: str) -> str:
        password_digest = hashlib.sha256(password.encode()).hexdigest().encode()
        key_digest = hashlib.sha256(
            self._application.encryption_key.encode()
        ).hexdigest()
        key = key_digest[:16].encode("ascii")
        iv = key_digest[16:32].encode("ascii")
        padder = padding.PKCS7(128).padder()
        padded = padder.update(password_digest) + padder.finalize()
        encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return (encryptor.update(padded) + encryptor.finalize()).hex()

    async def _post(
        self, path: str, body_data: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        body = json.dumps(body_data, separators=(",", ":"))
        try:
            async with self._session.post(
                self._base_url + path,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "VIVAX EcoLink Home Assistant",
                    "language": "en_US",
                    **headers,
                },
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                result = await response.json(content_type=None)
        except ClientResponseError as err:
            if err.status == 401:
                self._access_token = None
                raise AuthenticationError("EcoLink access token expired") from err
            raise CloudError(
                f"EcoLink HTTP request failed (status {err.status})"
            ) from err
        except TimeoutError as err:
            raise CloudError("EcoLink request timed out") from err
        except (ClientError, ValueError) as err:
            raise CloudError("Unable to communicate with VIVAX EcoLink") from err
        if not isinstance(result, dict):
            raise CloudError("VIVAX EcoLink returned an invalid response")
        return result

    async def login(self, account: str, password: str) -> None:
        """Authenticate using an EcoLink account password."""
        body_data = {
            "loginAccount": account,
            "password": self._encrypt_password(password),
            "encryptVersion": "1",
        }
        body = json.dumps(body_data, separators=(",", ":"))
        stamp = time.strftime("%Y%m%d%H%M%S")
        random_value = stamp + str(random.randint(0, 65535))
        result = await self._post(
            "/v1/user/login",
            body_data,
            {
                "random": random_value,
                "src": "20",
                "appid": APP_ID,
                "clienttype": "2",
                "appvnum": APP_VERSION,
                "stamp": stamp,
                "deviceid": self._device_id,
                "sign": self._v1_signature(body, random_value),
                "reqid": uuid.uuid4().hex,
            },
        )
        if result.get("code") == 0 and isinstance(result.get("data"), dict):
            token = result["data"].get("accessToken")
            if isinstance(token, str) and token:
                self._access_token = token
                return
        code = result.get("code")
        if isinstance(code, int) and 14000 <= code < 15000:
            raise AuthenticationError("EcoLink rejected the account credentials")
        raise CloudError(f"EcoLink login failed with code {_response_code(result)}")

    async def _business_request(
        self, path: str, body_data: dict[str, Any]
    ) -> dict[str, Any]:
        if not self._access_token:
            raise AuthenticationError("EcoLink login is required")
        body = json.dumps(body_data, separators=(",", ":"))
        result = await self._post(
            path,
            body_data,
            {
                "authorization": f"Bearer {self._access_token}",
                "clientId": self._application.client_id,
                "signature": self._v2_signature(path, body),
                "signatureversion": "2.0",
                "reqid": uuid.uuid4().hex,
            },
        )
        if result.get("code") in (12001, 14005, 3114016):
            self._access_token = None
            raise AuthenticationError("EcoLink access token expired")
        return result

    async def devices(self) -> list[VivaxDevice]:
        """List appliances on the authenticated account."""
        result = await self._business_request(
            "/midea/open/business/v1/appliance/list", {"queryAuth": True}
        )
        if result.get("code") != 0 or not isinstance(result.get("data"), list):
            raise CloudError(
                f"EcoLink device discovery failed with code {_response_code(result)}"
            )
        return [VivaxDevice.from_cloud(item) for item in result["data"]]

    async def payload(self, appliance_code: str, subtype: int) -> bytes:
        """Query and decode one short C3 cloud frame."""
        result = await self._business_request(
            "/midea/open/business/v1/appliance/control/hexadecimal",
            {
                "applianceCode": appliance_code,
                "command": short_query(subtype),
            },
        )
        if result.get("code") != 0 or not isinstance(result.get("data"), str):
            raise CloudError(
                f"EcoLink device query failed with code {_response_code(result)}"
            )
        return decode_cloud_payload(result["data"], subtype)

    async def set_zone1_power(self, appliance_code: str, enabled: bool) -> None:
        """Write only the exact-model vendor codec's Zone-1 power field."""
        command = zone1_power_command(enabled)
        result = await self._business_request(
            "/midea/open/business/v1/appliance/control/hexadecimal",
            {"applianceCode": appliance_code, "command": command},
        )
        if result.get("code") != 0:
            raise CloudError(
                f"EcoLink rejected the power command (code {_response_code(result)})"
            )
        if not isinstance(result.get("data"), str):
            raise CloudError("EcoLink power command returned no acknowledgement")
        validate_power_ack(result["data"], enabled)
