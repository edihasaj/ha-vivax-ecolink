# VIVAX EcoLink for Home Assistant

Cloud monitoring and Zone-1 power control for the VIVAX EcoLink `KJRH-120L`
heating and cooling controller. The integration uses the same EcoLink account
as the official Android application and refreshes expired login tokens
automatically.

## Supported data

- Zone 1 target and controller power state
- heating/cooling operating mode and compressor frequency
- outdoor, water inlet, and water outlet temperatures
- current electrical power
- total, heating, and cooling electricity and thermal energy
- lifetime and heating coefficient of performance (COP)

The cumulative electricity sensors use Home Assistant's `total_increasing`
state class and can be selected in the Energy dashboard.

## Current limitations

- Tested hardware: `KJRH-120L`, C3 model code `17100003`.
- The **Zone 1 power** switch controls house heating/cooling, not DHW or the
  controller's electrical supply. It uses the exact model's vendor codec,
  preserves the target/mode/curve settings and confirms changes with fresh
  read-back. It does not optimistically report a requested state.
- On a controller that explicitly reports Zone 2 disabled, its inactive Zone-2
  power flag may mirror Zone 1. This is accepted only with fresh single-zone
  evidence and matching power flags before and after; all other settings remain
  protected. No Zone-2 command is sent.
- Mode, target-temperature, DHW, Zone-2 and curve writes remain unavailable.
  See [control protocol and verification](docs/control-protocol.md).
- Cooling totals are derived as total minus heating. This is valid only on an
  installation without domestic-hot-water hardware.
- The integration includes the static application identity used by the official
  EcoLink client. These shared values are not user or device credentials.

## Install with HACS

1. Open **HACS**, then its top-right menu.
2. Select **Custom repositories**.
3. Add `https://github.com/edihasaj/ha-vivax-ecolink` as an **Integration**.
4. Download **VIVAX EcoLink** and restart Home Assistant.
5. Open **Settings → Devices & services → Add integration** and search for
   **VIVAX EcoLink**.

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=edihasaj&repository=ha-vivax-ecolink&category=integration)

## Setup

Prepare your EcoLink account email/password and account region, normally Europe
for VIVAX. Use a dedicated EcoLink account shared with the heat pump rather than
your primary account. The first setup page authenticates the account and the
second lets you select the device.

Your email and password remain in Home Assistant's private `.storage`
configuration. They are redacted from diagnostics and never written by this
integration to logs or files.

## Token expiry

Access tokens exist only in Home Assistant memory. On startup, or whenever the
cloud rejects an expired token, the integration logs in again with the stored
EcoLink account password and retries the update. Manual reauthentication is
needed only after an account password or vendor API change.

## Troubleshooting

- **Invalid email or password:** confirm the account works in the official app.
- **Unable to authenticate:** verify the account region and that EcoLink's cloud
  is available.
- **Unavailable entities:** confirm the controller is online in EcoLink. The
  vendor cloud can briefly delay responses.
- Never post diagnostics together with raw `.storage` files. Diagnostics from
  this integration redact all configured secrets.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

CI also runs the action tests inside the pinned Home Assistant container, with
networking disabled and a mocked cloud client. This checks native coordinator
and switch behavior without operating any real appliance.

## License

MIT. This is an independent community integration, not an official VIVAX
product and not affiliated with VIVAX.
