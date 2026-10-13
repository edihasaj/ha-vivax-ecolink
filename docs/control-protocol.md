---
summary: "Vendor-derived Zone-1 power encoding and hardware verification boundary."
read_when:
  - Adding or changing VIVAX actions.
  - Reviewing a KJRH-120L power or temperature command.
---

# KJRH-120L Zone-1 control

Only model code `17100003` is supported for writes. Existing telemetry sensors
and their unique IDs remain unchanged. Prototype entries without a model code
discover it from their own authenticated appliance metadata before exposing a
switch; unknown models remain monitoring-only.

## Source of the command

The vendor codec is `T_0000_C3_17100003_2024011601.lua`, published in
[midea-local](https://github.com/midea-lan/midea-local/blob/804eac178ae587979709b2f312257ee24e64ebf8/lua/c3/T_0000_C3_17100003_2024011601.lua).
Its SHA-256 is
`101585e5c8a8a69ce539bbb41bccaacfd0dda14c0b4ea53d8c11aab941b04c11`.
The vendor source is not redistributed or executed by this integration.

The codec's `jsonToData` was executed offline with just
`{"control":{"zone1_power_state":"off"}}` or the corresponding `"on"` value.
The resulting commands are:

| Action | Command |
| --- | --- |
| Zone-1 off | `00000100ff` |
| Zone-1 on | `00000101ff` |

This is a single TLV field: two-byte field index `0`, one-byte length `1`,
one-byte power value, and `ff` terminator. The cloud adds the C3 envelope.
There is no setpoint, operating-mode, DHW or curve field in a power command.

The same codec independently produces the existing status queries
`ffff010101ff` and `ffff101010ff`. Its first ten decoded settings match the
controller's fresh status payload layout.

## Do not confuse the fields

- Field `0`: Zone-1 power.
- Field `2`: DHW power. It must not be used to switch house heating.
- Field `4`: Zone-1 water target, not field `8`.
- Field `8`: Zone-1 weather-curve enable. The previously guessed temperature
  write targeted this field and must never be restored.

Temperature, mode, curve, Zone-2 and DHW writes are not exposed in this release.
Vendor encoding is not, by itself, a completed hardware test for those actions.

## Action verification

Each action serializes with normal polling, reads fresh basic settings before
writing, and skips a write if power is already in the requested state. It
requires a checksummed C3 control acknowledgement echoing exactly field `0`
and then up to three fresh status queries confirming the requested power.

DHW power, mode, all basic targets and curve-enable values must remain unchanged.
Zone-2 power must also remain unchanged except for the narrowly verified
inactive-zone mirror below. A changed setting or an unconfirmed response fails
visibly.
No optimistic state, blind write retries, or automatic inverse/repair commands
are used. Only an explicit authentication rejection permits a login and retry.

Version 0.2.1 preserves the specific failure in the Home Assistant action error
and a warning log. It distinguishes numeric cloud rejection codes, HTTP errors,
timeouts, missing acknowledgements, invalid frame length/header/checksum, and
read-back failures. Raw replies, account credentials and device identifiers
are not logged. This diagnostic change does not relax validation or change the
wire command. A failed action may already have reached the controller; check
EcoLink before retrying and do not repeatedly cycle power.

Version 0.2.2 identifies each changed basic setting by its vendor-defined name
and before/after byte value, alongside the observed Zone-1 power. Only positions
1–9 are reported, never an entire payload or identity block. The settings guard
still fails closed; a valid acknowledgement followed by this error is not a
cloud rejection, and may mean the requested power did change. Do not ignore
coupled-zone, mode or target differences without captured evidence of their
meaning.

## Single-zone inactive power flag

Version 0.2.3 handles the observed single-zone controller behavior: a field-0
power action changes both Zone-1 and the inactive Zone-2 power flags. The
installation owner confirmed there is no Zone 2, and a read-only status query
reported `double_zone_enable = 0`. The vendor codec defines that capability at
basic byte 17. No Zone-2 field is added to the outgoing command.

The exception applies only when both fresh snapshots explicitly show byte 17
as zero, and Zone-2 power matches Zone-1 power in both snapshots. Requested
Zone-1 power must still be confirmed. Every other protected basic value must
remain unchanged, including the unused Zone-2 target and curve. A changed or
missing previously observed capability fails the action. Enabled, unknown or
truncated Zone-2 capability never permits the mirror exception. There are no
repair writes or blind retries.

Protocol and isolated tests do not establish a live hardware power cycle.
Before claiming hardware verification, obtain approval for one supervised
Off/On cycle, record fresh before/after settings, and confirm the controller
and official app agree. Do not repeatedly cycle the compressor.
