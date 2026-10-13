"""Read-before-write and read-back verification for Zone-1 power only."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .cloud import CloudError
from .protocol import ProtocolError

ReadStatus = Callable[[], Awaitable[bytes]]
WritePower = Callable[[bool], Awaitable[None]]
Sleep = Callable[[float], Awaitable[None]]

# Byte positions verified against the exact 17100003 vendor codec. These nine
# basic values contain no credentials, serial numbers or appliance identifiers.
PROTECTED_SETTINGS = (
    "Zone-2 power",
    "DHW power",
    "commanded mode",
    "Zone-1 target",
    "Zone-2 target",
    "room target",
    "DHW target",
    "Zone-1 curve",
    "Zone-2 curve",
)


class PowerControlError(CloudError):
    """An action could not be verified against fresh controller state."""


def validate_power_status(status: bytes) -> None:
    """Reject unknown/truncated state rather than writing against cached data."""
    if len(status) < 10 or status[0] not in (0, 1):
        raise ProtocolError("Zone-1 power state is not available")


async def async_set_zone1_power(
    read_status: ReadStatus,
    write_power: WritePower,
    enabled: bool,
    *,
    sleep: Sleep = asyncio.sleep,
) -> bytes:
    """Set one power field, preserving the other basic settings.

    Callers serialize this operation with polling. A successful acknowledgement
    alone is insufficient: a fresh query must show the requested power and the
    unchanged zone/DHW/mode/target/curve settings. Never retry an ambiguous write
    or roll unrelated settings back over a possible official-app change.
    """
    if type(enabled) is not bool:
        raise ValueError("Zone-1 power must be a boolean")
    before = await read_status()
    validate_power_status(before)
    if bool(before[0]) == enabled:
        return before

    await write_power(enabled)
    for attempt in range(3):
        after = await read_status()
        validate_power_status(after)
        if after[1:10] != before[1:10]:
            changed = ", ".join(
                f"{name} {before[index]} -> {after[index]}"
                for index, name in enumerate(PROTECTED_SETTINGS, start=1)
                if before[index] != after[index]
            )
            raise PowerControlError(
                f"Controller settings changed during the power action: {changed}. "
                f"Observed Zone-1 power: {'On' if after[0] else 'Off'}"
            )
        if bool(after[0]) == enabled:
            return after
        if attempt < 2:
            await sleep(2)
    raise PowerControlError("EcoLink has not confirmed the requested Zone-1 power")
