"""Decoder for verified VIVAX KJRH-120L C3 cloud frames."""

from __future__ import annotations

from .models import VivaxTelemetry

DEVICE_TYPE_C3 = 0xC3
IDENTITY_TRAILER = b"\x19\x21W"


class ProtocolError(ValueError):
    """Raised when a response is not a supported VIVAX C3 frame."""


def short_query(subtype: int) -> str:
    """Build the short query accepted by the KJRH-120L cloud bridge."""
    if not 0 <= subtype <= 0xFF:
        raise ValueError("subtype must fit in one byte")
    return f"ffff{subtype:02x}{subtype:02x}{subtype:02x}ff"


def decode_cloud_payload(response_hex: str, expected_subtype: int) -> bytes:
    """Remove the outer C3 frame and VIVAX declared-length envelope."""
    try:
        raw = bytes.fromhex(response_hex.replace(",", " "))
    except ValueError as err:
        raise ProtocolError("Cloud response is not hexadecimal") from err

    if len(raw) < 20:
        raise ProtocolError("Cloud response is truncated")
    if raw[0] != 0xAA or raw[2] != DEVICE_TYPE_C3:
        raise ProtocolError("Cloud response is not a C3 frame")

    body = raw[10:-1]
    if len(body) < 9 or body[0] != expected_subtype or body[1] != 0xFE:
        raise ProtocolError("Cloud response has an unexpected subtype")

    declared_length = int.from_bytes(body[6:8], "big")
    payload = body[8:-1]
    if len(payload) != declared_length:
        raise ProtocolError(
            f"Payload length {len(payload)} does not match {declared_length}"
        )
    return payload


def decode_temperature(value: int) -> float | None:
    """Decode the controller's negative-capable temperature byte."""
    if value == 0x7F:
        return None
    return float(value - 200 if value >= 200 else value)


def _u32(payload: bytes, offset: int) -> int:
    if offset < 0 or len(payload) < offset + 4:
        raise ProtocolError("Energy data is truncated")
    return int.from_bytes(payload[offset : offset + 4], "big")


def _cop(consumed: int, produced: int) -> float | None:
    return round(produced / consumed, 2) if consumed else None


def decode_telemetry(status: bytes, unit: bytes) -> VivaxTelemetry:
    """Decode fields verified against the official VIVAX EcoLink app."""
    if len(status) < 5 or len(unit) < 18:
        raise ProtocolError("Required telemetry payload is truncated")

    trailer = unit.find(IDENTITY_TRAILER)
    energy_offset = trailer - 24
    if energy_offset < 0:
        raise ProtocolError("Unit identity trailer or energy block is missing")

    total_electricity = _u32(unit, energy_offset)
    total_thermal = _u32(unit, energy_offset + 4)
    heating_electricity = _u32(unit, energy_offset + 8)
    heating_thermal = _u32(unit, energy_offset + 12)

    if total_electricity < heating_electricity or total_thermal < heating_thermal:
        raise ProtocolError("Cumulative energy counters are inconsistent")

    mode_code = unit[1]
    operating_mode = {0: "Off", 2: "Cool", 3: "Heat"}.get(
        mode_code, f"Unknown ({mode_code})"
    )
    current_power = int.from_bytes(unit[energy_offset + 16 : energy_offset + 18], "big")

    return VivaxTelemetry(
        controller_power=bool(status[0] & 0x01),
        operating_mode=operating_mode,
        zone1_target=float(status[4]),
        compressor_frequency=unit[0],
        outdoor_temperature=decode_temperature(unit[6]),
        water_inlet_temperature=decode_temperature(unit[8]),
        water_outlet_temperature=decode_temperature(unit[9]),
        current_power=current_power,
        total_electricity=total_electricity,
        total_thermal_energy=total_thermal,
        heating_electricity=heating_electricity,
        heating_thermal_energy=heating_thermal,
        cooling_electricity=total_electricity - heating_electricity,
        cooling_thermal_energy=total_thermal - heating_thermal,
        lifetime_cop=_cop(total_electricity, total_thermal),
        heating_cop=_cop(heating_electricity, heating_thermal),
    )
