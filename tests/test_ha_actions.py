"""Exercise coordinator and switch behavior in an isolated real HA instance."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.vivax_ecolink.cloud import AuthenticationError, CloudError
    from custom_components.vivax_ecolink.coordinator import VivaxCoordinator
    from custom_components.vivax_ecolink.models import VivaxDevice
    from custom_components.vivax_ecolink.protocol import ProtocolError
    from custom_components.vivax_ecolink.switch import (
        VivaxZone1PowerSwitch,
        async_setup_entry,
    )
except ImportError:
    HomeAssistant = None

ON = bytes([1, 1, 0, 5, 35, 30, 48, 40, 1, 0])
OFF = bytes([0]) + ON[1:]
UNIT = bytes([0, 3]) + bytes(40) + b"\x19\x21W"


@unittest.skipIf(HomeAssistant is None, "Run these tests in the HA container")
class HaPowerActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.entry = ConfigEntry(
            version=4,
            minor_version=1,
            domain="vivax_ecolink",
            title="Synthetic VIVAX",
            data={
                "appliance_code": "synthetic-device",
                "email": "test@example.invalid",
                "password": "test-only",
                "region": "eu",
                "sn8": "17100003",
            },
            options={},
            source="user",
            unique_id="synthetic-vivax",
            discovery_keys={},
            subentries_data=None,
        )
        self.client = AsyncMock()
        self.client.authenticated = True
        self.client.payload.side_effect = self.payload
        self.status = ON
        self.write_started = asyncio.Event()
        self.write_resume = asyncio.Event()
        self.client.set_zone1_power.side_effect = self.write
        with (
            patch(
                "custom_components.vivax_ecolink.coordinator.VivaxCloudClient",
                return_value=self.client,
            ),
            patch(
                "custom_components.vivax_ecolink.coordinator.async_get_clientsession",
                return_value=object(),
            ),
        ):
            self.coordinator = VivaxCoordinator(self.hass, self.entry)
        # This isolated instance is not loading a real config entry.
        await self.coordinator.async_refresh()
        self.assertTrue(self.coordinator.last_update_success)
        self.hass.data["vivax_ecolink"] = {self.entry.entry_id: self.coordinator}

    async def asyncTearDown(self) -> None:
        await self.hass.async_stop(force=True)
        self.directory.cleanup()

    async def payload(self, device: str, subtype: int) -> bytes:
        self.assertEqual(device, "synthetic-device")
        return self.status if subtype == 1 else UNIT

    async def write(self, device: str, enabled: bool) -> None:
        self.assertEqual(device, "synthetic-device")
        self.status = ON if enabled else OFF

    async def test_switch_actions_follow_fresh_readback(self) -> None:
        switch = VivaxZone1PowerSwitch(self.coordinator)
        self.assertTrue(switch.is_on)
        await switch.async_turn_off()
        self.assertFalse(switch.is_on)
        self.assertEqual(self.coordinator.data.zone1_target, 35)
        await switch.async_turn_on()
        self.assertTrue(switch.is_on)
        self.assertEqual(self.coordinator.data.zone1_target, 35)
        self.assertEqual(self.client.set_zone1_power.await_count, 2)

    async def test_single_zone_switch_accepts_only_the_disabled_power_mirror(
        self,
    ) -> None:
        self.status = ON + bytes(8)

        async def single_zone_write(_device: str, enabled: bool) -> None:
            self.status = bytes([int(enabled), int(enabled)]) + self.status[2:]

        self.client.set_zone1_power.side_effect = single_zone_write
        await self.coordinator.async_refresh()
        switch = VivaxZone1PowerSwitch(self.coordinator)
        await switch.async_turn_off()
        self.assertFalse(switch.is_on)
        self.assertEqual(self.coordinator.data.zone1_target, 35)
        await switch.async_turn_on()
        self.assertTrue(switch.is_on)
        self.assertEqual(self.coordinator.data.zone1_target, 35)
        self.assertEqual(self.client.set_zone1_power.await_count, 2)

    async def test_stale_cached_state_does_not_trigger_an_unnecessary_write(
        self,
    ) -> None:
        # Cached HA state is On, but the official app already turned Zone 1 Off.
        self.status = OFF
        await self.coordinator.async_set_zone1_power(False)
        self.client.set_zone1_power.assert_not_awaited()
        self.assertFalse(self.coordinator.data.controller_power)

    async def test_unknown_model_does_not_create_a_switch_or_send_writes(self) -> None:
        object.__setattr__(
            self.entry, "data", {**self.entry.data, "sn8": "different-model"}
        )
        added = []
        await async_setup_entry(self.hass, self.entry, added.extend)
        self.assertEqual(added, [])
        with self.assertRaises(HomeAssistantError):
            await self.coordinator.async_set_zone1_power(False)
        self.client.set_zone1_power.assert_not_awaited()

    async def test_action_is_not_optimistic_and_polling_waits_for_it(self) -> None:
        async def delayed_write(device: str, enabled: bool) -> None:
            self.write_started.set()
            await self.write_resume.wait()
            await self.write(device, enabled)

        self.client.set_zone1_power.side_effect = delayed_write
        action = asyncio.create_task(self.coordinator.async_set_zone1_power(False))
        await self.write_started.wait()
        self.assertTrue(self.coordinator.data.controller_power)
        polling = asyncio.create_task(self.coordinator._async_update_data())
        await asyncio.sleep(0)
        self.assertFalse(polling.done())
        self.write_resume.set()
        await action
        result = await polling
        self.assertFalse(result.controller_power)
        self.assertFalse(self.coordinator.data.controller_power)

    async def test_settings_change_fails_and_refreshes_observed_state(self) -> None:
        async def changed_target(_device: str, _enabled: bool) -> None:
            self.status = OFF[:4] + bytes([36]) + OFF[5:]

        self.client.set_zone1_power.side_effect = changed_target
        with self.assertRaises(HomeAssistantError):
            await self.coordinator.async_set_zone1_power(False)
        self.client.set_zone1_power.assert_awaited_once_with("synthetic-device", False)
        self.assertEqual(self.coordinator.data.zone1_target, 36)
        self.assertFalse(self.coordinator.data.controller_power)

    async def test_missing_model_is_discovered_only_from_the_owned_device(self) -> None:
        object.__setattr__(
            self.entry,
            "data",
            {key: value for key, value in self.entry.data.items() if key != "sn8"},
        )
        self.assertFalse(self.coordinator.supports_power_control)
        self.client.devices.return_value = [
            VivaxDevice("unrelated-device", "Other unit", "Other", "17100003"),
            VivaxDevice("synthetic-device", "Test unit", "KJRH-120L", "17100003"),
        ]

        def update_entry(entry: ConfigEntry, *, data: dict[str, str]) -> None:
            self.assertIs(entry, self.entry)
            object.__setattr__(entry, "data", data)

        update = Mock(side_effect=update_entry)
        self.hass.config_entries = SimpleNamespace(async_update_entry=update)
        await self.coordinator.async_discover_model()
        update.assert_called_once()
        self.assertTrue(self.coordinator.supports_power_control)
        self.assertEqual(self.entry.data["model"], "KJRH-120L")
        self.assertEqual(self.entry.data["appliance_code"], "synthetic-device")
        await self.coordinator.async_discover_model()
        self.client.devices.assert_awaited_once()

    async def test_discovery_failure_or_unrelated_device_keeps_writes_disabled(
        self,
    ) -> None:
        object.__setattr__(
            self.entry,
            "data",
            {key: value for key, value in self.entry.data.items() if key != "sn8"},
        )
        self.client.devices.side_effect = CloudError("offline")
        await self.coordinator.async_discover_model()
        self.assertFalse(self.coordinator.supports_power_control)
        self.client.devices.side_effect = None
        self.client.devices.return_value = [
            VivaxDevice("unrelated-device", "Other unit", "KJRH-120L", "17100003")
        ]
        await self.coordinator.async_discover_model()
        self.assertFalse(self.coordinator.supports_power_control)
        self.client.set_zone1_power.assert_not_awaited()

    async def test_explicit_auth_rejection_reauthenticates_once(self) -> None:
        rejected = True

        async def expire_once(device: str, enabled: bool) -> None:
            nonlocal rejected
            if rejected:
                rejected = False
                raise AuthenticationError("expired")
            await self.write(device, enabled)

        self.client.set_zone1_power.side_effect = expire_once
        await self.coordinator.async_set_zone1_power(False)
        self.client.login.assert_awaited_once_with("test@example.invalid", "test-only")
        self.assertEqual(self.client.set_zone1_power.await_count, 2)
        self.assertFalse(self.coordinator.data.controller_power)

    async def test_ambiguous_cloud_error_does_not_repeat_the_write(self) -> None:
        async def applied_but_timed_out(device: str, enabled: bool) -> None:
            await self.write(device, enabled)
            raise CloudError("timeout")

        self.client.set_zone1_power.side_effect = applied_but_timed_out
        with self.assertRaises(HomeAssistantError):
            await self.coordinator.async_set_zone1_power(False)
        self.client.set_zone1_power.assert_awaited_once_with("synthetic-device", False)
        self.client.login.assert_not_awaited()
        self.assertFalse(self.coordinator.data.controller_power)

    async def test_invalid_polled_power_makes_the_switch_unavailable(self) -> None:
        switch = VivaxZone1PowerSwitch(self.coordinator)
        self.assertTrue(switch.available)
        self.status = bytes([0xFF]) + ON[1:]
        await self.coordinator.async_refresh()
        self.assertFalse(switch.available)
        self.client.set_zone1_power.assert_not_awaited()

    async def test_action_preserves_cloud_and_protocol_failure_reasons(self) -> None:
        for error in (
            CloudError("EcoLink rejected the power command (code 1214)"),
            CloudError("EcoLink request timed out"),
            ProtocolError("Power acknowledgement has an unexpected length (20 bytes)"),
        ):
            with self.subTest(reason=str(error)):
                self.client.set_zone1_power.reset_mock()
                self.client.set_zone1_power.side_effect = error
                with (
                    self.assertLogs(
                        "custom_components.vivax_ecolink.coordinator", level="WARNING"
                    ) as logs,
                    self.assertRaises(HomeAssistantError) as raised,
                ):
                    await self.coordinator.async_set_zone1_power(False)
                self.assertIn(str(error), str(raised.exception))
                self.assertIs(raised.exception.__cause__, error)
                self.assertIn(str(error), logs.output[0])
                self.client.set_zone1_power.assert_awaited_once_with(
                    "synthetic-device", False
                )
                self.client.login.assert_not_awaited()
                self.assertTrue(self.coordinator.data.controller_power)


if __name__ == "__main__":
    unittest.main()
