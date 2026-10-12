"""Regression tests for vendor-derived, single-field Zone-1 power actions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.vivax_ecolink.cloud import CloudError
from custom_components.vivax_ecolink.control import (
    PowerControlError,
    async_set_zone1_power,
)
from custom_components.vivax_ecolink.protocol import (
    ProtocolError,
    validate_power_ack,
    zone1_power_command,
)

# Synthetic basic settings. No credentials, device identifiers or serial data.
ON = bytes([1, 1, 0, 5, 35, 30, 48, 40, 1, 0])
OFF = bytes([0]) + ON[1:]


def ack(command: str, *, kind: int = 0x02) -> str:
    """Construct an independently checksummed synthetic C3 control response."""
    frame = bytes([0xAA, 15, 0xC3, 0, 0, 0, 0, 0, 0, kind])
    frame += bytes.fromhex(command)
    return (frame + bytes([-sum(frame[1:]) & 0xFF])).hex()


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [(False, "00000100ff"), (True, "00000101ff")],
)
def test_power_matches_exact_vendor_codec_output(enabled: bool, expected: str) -> None:
    """Field 0 changes Zone 1, not field 2 (DHW) or field 8 (curve)."""
    assert zone1_power_command(enabled) == expected
    validate_power_ack(ack(expected), enabled)


@pytest.mark.parametrize("value", [None, 0, 1, "on", "off", [], {}])
def test_power_builder_rejects_non_boolean_values(value: object) -> None:
    with pytest.raises(ValueError, match="boolean"):
        zone1_power_command(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "response",
    [
        "not hexadecimal",
        "",
        "aa",
        ack("00000100ff"),
        ack("00020101ff"),
        ack("00080101ff"),
        ack("00000101ff", kind=0x03),
        ack("00000101ff")[:-2] + "00",
        ack("00000101ff") + "00",
    ],
)
def test_wrong_power_acknowledgements_fail_closed(response: str) -> None:
    with pytest.raises(ProtocolError):
        validate_power_ack(response, True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("before", "after", "enabled"), [(ON, OFF, False), (OFF, ON, True)]
)
async def test_power_reads_before_and_after_without_other_writes(
    before: bytes, after: bytes, enabled: bool
) -> None:
    read = AsyncMock(side_effect=[before, after])
    write = AsyncMock()
    sleep = AsyncMock()
    assert await async_set_zone1_power(read, write, enabled, sleep=sleep) == after
    assert read.await_count == 2
    write.assert_awaited_once_with(enabled)
    sleep.assert_not_awaited()
    assert before[1:] == after[1:]


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "enabled"), [(ON, True), (OFF, False)])
async def test_already_requested_power_is_a_fresh_read_only_noop(
    status: bytes, enabled: bool
) -> None:
    read = AsyncMock(return_value=status)
    write = AsyncMock()
    assert await async_set_zone1_power(read, write, enabled) == status
    read.assert_awaited_once_with()
    write.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [b"", ON[:5], bytes([0xFF]) + ON[1:]])
async def test_unknown_preflight_state_sends_nothing(status: bytes) -> None:
    write = AsyncMock()
    with pytest.raises(ProtocolError, match="not available"):
        await async_set_zone1_power(AsyncMock(return_value=status), write, False)
    write.assert_not_awaited()


@pytest.mark.asyncio
async def test_cloud_lag_retries_reads_not_the_power_write() -> None:
    read = AsyncMock(side_effect=[ON, ON, ON, OFF])
    write = AsyncMock()
    sleep = AsyncMock()
    assert await async_set_zone1_power(read, write, False, sleep=sleep) == OFF
    write.assert_awaited_once_with(False)
    assert sleep.await_count == 2


@pytest.mark.asyncio
async def test_ack_without_confirmed_state_is_not_success() -> None:
    write = AsyncMock()
    with pytest.raises(PowerControlError, match="not confirmed"):
        await async_set_zone1_power(
            AsyncMock(return_value=ON), write, False, sleep=AsyncMock()
        )
    write.assert_awaited_once_with(False)


@pytest.mark.asyncio
@pytest.mark.parametrize("setting", range(1, 10))
async def test_changed_targets_modes_curves_or_other_zones_are_not_accepted(
    setting: int,
) -> None:
    changed = bytearray(OFF)
    changed[setting] ^= 1
    write = AsyncMock()
    with pytest.raises(PowerControlError, match="settings changed"):
        await async_set_zone1_power(
            AsyncMock(side_effect=[ON, bytes(changed)]), write, False
        )
    write.assert_awaited_once_with(False)


@pytest.mark.asyncio
async def test_ambiguous_write_failure_is_not_retried() -> None:
    read = AsyncMock(return_value=ON)
    write = AsyncMock(side_effect=CloudError("timeout"))
    with pytest.raises(CloudError, match="timeout"):
        await async_set_zone1_power(read, write, False)
    read.assert_awaited_once_with()
    write.assert_awaited_once_with(False)
