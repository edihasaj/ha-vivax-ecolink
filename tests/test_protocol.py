"""Regression tests for the verified KJRH-120L frame decoder."""

from __future__ import annotations

import pytest

from custom_components.vivax_ecolink.protocol import (
    ProtocolError,
    decode_cloud_payload,
    decode_telemetry,
    short_query,
)

STATUS = bytes.fromhex(
    "01 01 00 05 12 0c 30 28 01 00 00 00 00 00 01 01 01 00 00 00 "
    "00 00 00 00 00 00 00 00 01 50 23 19 05 37 19 19 05 3c 22 46 "
    "14 7f 00 01 01 04 04 01 01 d9 2f ff ff ff ff ff ff ff ff ff ff "
    "ff 30 ff ff ff ff 00 00 00 01 00 01 00 00 00 1a 08 0e 00 22 00 "
    "30 00 01"
)

UNIT = bytes.fromhex(
    "00 02 00 06 00 d9 d9 db da db 7f 04 00 00 00 00 00 e2 00 3c "
    "0a 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 00 00 00 00 00 00 00 00 01 00 00 00 00 01 01 00 00 00 "
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "db dd da da 7f 7f 7f 7f 00 03 98 03 70 da 07 00 00 1f df ff ff "
    "00 00 00 00 00 00 15 00 ff 00 ff 63 00 00 32 72 00 00 d4 0e "
    "00 00 2c 86 00 00 b4 e9 00 01 00 00 00 00 b2 6d 19 21 57 38 "
    "33 35 33 35 30 37 33 39 32 47 41 41 31 37 30 31 30 30 30 30 "
    "39"
)


def test_short_query() -> None:
    """Queries use the controller's confirmed short command shape."""
    assert short_query(0x10) == "ffff101010ff"


def test_decode_telemetry() -> None:
    """Decode the known live sample without confusing metadata for energy."""
    data = decode_telemetry(STATUS, UNIT)
    assert data.controller_power is True
    assert data.operating_mode == "Cool"
    assert data.zone1_target == 18
    assert data.compressor_frequency == 0
    assert data.outdoor_temperature == 17
    assert data.water_inlet_temperature == 18
    assert data.water_outlet_temperature == 19
    assert data.current_power == 1
    assert data.total_electricity == 12914
    assert data.total_thermal_energy == 54286
    assert data.heating_electricity == 11398
    assert data.heating_thermal_energy == 46313
    assert data.cooling_electricity == 1516
    assert data.cooling_thermal_energy == 7973
    assert data.lifetime_cop == 4.2
    assert data.heating_cop == 4.06


def test_decode_variable_length_unit_frame() -> None:
    """Energy is located from the identity trailer, not an outer fixed offset."""
    data = decode_telemetry(STATUS, b"\x00\x00\x00" + UNIT)
    assert data.total_electricity == 12914
    assert data.current_power == 1


def test_reject_inconsistent_energy() -> None:
    """Never publish negative derived counters into Home Assistant."""
    unit = bytearray(UNIT)
    base = unit.find(b"\x19\x21W") - 24
    unit[base : base + 4] = (1).to_bytes(4, "big")
    with pytest.raises(ProtocolError, match="inconsistent"):
        decode_telemetry(STATUS, bytes(unit))


def test_decode_cloud_payload() -> None:
    """Validate and strip both response envelopes."""
    payload = b"\x01\x02\x03"
    body = bytes([0x01, 0xFE, 0, 0, 0, 0, 0, len(payload)]) + payload + b"\xff"
    frame = bytes([0xAA, 0, 0xC3, 0, 0, 0, 0, 0, 0, 0]) + body + b"\x00"
    assert decode_cloud_payload(frame.hex(), 0x01) == payload


def test_reject_wrong_declared_length() -> None:
    """Malformed cloud frames fail closed."""
    body = bytes([0x01, 0xFE, 0, 0, 0, 0, 0, 5, 1, 2, 0xFF])
    frame = bytes([0xAA, 0, 0xC3, 0, 0, 0, 0, 0, 0, 0]) + body + b"\x00"
    with pytest.raises(ProtocolError, match="Payload length"):
        decode_cloud_payload(frame.hex(), 0x01)
