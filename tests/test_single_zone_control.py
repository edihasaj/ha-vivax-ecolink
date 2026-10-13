"""Accept the observed inactive Zone-2 mirror, never unrelated changes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.vivax_ecolink.control import (
    PowerControlError,
    async_set_zone1_power,
)

# Independent synthetic schema: byte 17 is double_zone_enable, not a power bit.
ON = bytes([1, 1, 0, 3, 35, 30, 48, 40, 0, 0]) + bytes(8)
OFF = bytes([0, 0]) + ON[2:]


def replace(status: bytes, index: int, value: int) -> bytes:
    data = bytearray(status)
    data[index] = value
    return bytes(data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("before", "after", "enabled"), [(ON, OFF, False), (OFF, ON, True)]
)
async def test_disabled_zone2_may_mirror_confirmed_zone1_power(
    before: bytes, after: bytes, enabled: bool
) -> None:
    read = AsyncMock(side_effect=[before, after])
    write = AsyncMock()
    assert await async_set_zone1_power(read, write, enabled) == after
    write.assert_awaited_once_with(enabled)
    assert read.await_count == 2
    assert before[2:] == after[2:]


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", [1, 2, 255])
@pytest.mark.parametrize("enabled", [False, True])
async def test_enabled_or_unknown_zone2_never_gets_the_mirror_exception(
    capability: int, enabled: bool
) -> None:
    before, after = (OFF, ON) if enabled else (ON, OFF)
    write = AsyncMock()
    with pytest.raises(PowerControlError, match="Zone-2 power"):
        await async_set_zone1_power(
            AsyncMock(
                side_effect=[
                    replace(before, 17, capability),
                    replace(after, 17, capability),
                ]
            ),
            write,
            enabled,
        )
    write.assert_awaited_once_with(enabled)


@pytest.mark.asyncio
@pytest.mark.parametrize(("before_size", "after_size"), [(10, 18), (17, 18), (18, 17)])
async def test_missing_capability_evidence_fails_closed(
    before_size: int, after_size: int
) -> None:
    with pytest.raises(PowerControlError):
        await async_set_zone1_power(
            AsyncMock(side_effect=[ON[:before_size], OFF[:after_size]]),
            AsyncMock(),
            False,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("setting", range(2, 10))
@pytest.mark.parametrize("enabled", [False, True])
async def test_inactive_mirror_does_not_hide_target_mode_curve_or_dhw_changes(
    setting: int, enabled: bool
) -> None:
    before, after = (OFF, ON) if enabled else (ON, OFF)
    after = replace(after, setting, after[setting] ^ 1)
    write = AsyncMock()
    with pytest.raises(PowerControlError, match="settings changed"):
        await async_set_zone1_power(
            AsyncMock(side_effect=[before, after]), write, enabled
        )
    write.assert_awaited_once_with(enabled)


@pytest.mark.asyncio
@pytest.mark.parametrize(("before_cap", "after_cap"), [(0, 1), (1, 0), (0, 255)])
async def test_zone_configuration_changes_are_not_accepted(
    before_cap: int, after_cap: int
) -> None:
    with pytest.raises(PowerControlError, match="enable configuration"):
        await async_set_zone1_power(
            AsyncMock(
                side_effect=[
                    replace(ON, 17, before_cap),
                    replace(OFF, 17, after_cap),
                ]
            ),
            AsyncMock(),
            False,
        )


@pytest.mark.asyncio
async def test_zone2_change_without_matching_zone1_power_is_not_a_mirror() -> None:
    with pytest.raises(PowerControlError, match="Zone-2 power"):
        await async_set_zone1_power(
            AsyncMock(side_effect=[ON, replace(ON, 1, 0)]), AsyncMock(), False
        )


@pytest.mark.asyncio
async def test_unmatched_initial_flags_do_not_get_the_exception() -> None:
    with pytest.raises(PowerControlError, match="Zone-2 power"):
        await async_set_zone1_power(
            AsyncMock(side_effect=[replace(ON, 1, 0), replace(OFF, 1, 1)]),
            AsyncMock(),
            False,
        )
