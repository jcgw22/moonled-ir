# 🌙 Moon Lamp IR (moonLedRemote)

[![hacs_custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/jcgw22/moonled-ir?include_prereleases)](https://github.com/jcgw22/moonled-ir/releases)
[![License](https://img.shields.io/github/license/jcgw22/moonled-ir)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/jcgw22/moonled-ir)](https://github.com/jcgw22/moonled-ir/commits/main)

A Home Assistant custom `light` integration for one specific unlabelled
24-key RGB LED remote (product name `moonLedRemote`, an IR-controlled moon
lamp) — a real `ColorMode.RGB` light with 4 brightness steps and effects,
not just an on/off switch with colour "effects" bolted on.

> [!WARNING]
> **This is a hack repo for one device, not a general-purpose IR light
> integration.** Every command byte below came from directly capturing
> this exact lamp's physical remote with an ESPHome IR receiver. If your
> remote *looks* the same, some buttons will probably work (the colour
> grid follows a documented standard) but the power/brightness/effect
> keys are very likely wired differently — see
> [Confidence levels](#confidence-levels) before trusting anything here.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [Command reference](#command-reference)
- [Confidence levels](#confidence-levels)
- [Contributing / help wanted](#contributing--help-wanted)
- [Credits](#credits)

## Features

- 🎨 **Real RGB colour**, not an effect list — `light.turn_on` with
  `rgb_color` snaps to the nearest of 14 confirmed/likely preset colours.
- 💡 **4-level brightness**, synthesized from the remote's relative
  up/down buttons via a calibrate-then-step routine (no feedback hardware
  needed).
- ✨ 4 lighting effects (flash/strobe/fade/smooth).
- 🖥️ **Configurable via the GUI** (Settings → Devices & Services) or YAML
  — your choice, both produce the same entity.
- 📡 Built on Home Assistant core's own `infrared` domain and NEC encoder
  (`infrared_protocols.commands.nec.NECCommand`) — the same stack core's
  `led_infrared` integration uses. No bespoke ESPHome service calls.
- 📝 Every command byte's confidence level is documented and traceable
  back to the original reverse-engineering session.

## Requirements

- A Home Assistant instance running a version with the core `infrared`
  domain (confirmed present on `2026.9.3`).
- An ESP32-based IR blaster running [ESPHome](https://esphome.io) with the
  [`ir_rf_proxy`](https://esphome.io/components/infrared.html) platform
  configured (wraps `remote_transmitter`/`remote_receiver` — see
  [below](#requirements-1)). This repo was built against a Seeed XIAO
  ESP32C3 "IR Mate" node, but any ESPHome device with `ir_rf_proxy` works.
- This exact lamp/remote (or one confirmed to share its protocol —
  see [Confidence levels](#confidence-levels)).

## Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jcgw22&repository=moonled-ir&category=integration)

Or manually: HACS → ⋮ → Custom repositories → add
`https://github.com/jcgw22/moonled-ir` as category **Integration** → install
**Moon Lamp IR (moonLedRemote)** → restart Home Assistant.

### Manual

1. Copy `custom_components/moonled_ir/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

### Requirements: the ESPHome side

This integration sends commands through an `infrared.*` **emitter**
entity via `InfraredEmitterConsumerEntity` (the same base class
`led_infrared` uses) — it does **not** call any bespoke ESPHome service.
Your IR blaster node needs ESPHome's `ir_rf_proxy` platform added under
`infrared:`, wrapping its existing `remote_transmitter`:

```yaml
remote_transmitter:
  id: my_transmitter
  pin: GPIO3
  carrier_duty_percent: 50%   # must NOT be 0% or 100%
  non_blocking: true

infrared:
  - platform: ir_rf_proxy
    name: IR Proxy Transmitter
    id: ir_proxy_tx
    remote_transmitter_id: my_transmitter
  # optional, if the node also has a remote_receiver:
  - platform: ir_rf_proxy
    name: IR Proxy Receiver
    id: ir_proxy_rx
    remote_receiver_id: rcvr
```

Once flashed, this creates an `infrared.<device>_ir_proxy_transmitter`
entity in HA — check Developer Tools → States for the exact id (HA
generates it from the device + entity name).

## Configuration

Both paths produce the same entity; use whichever you prefer, and mix
freely if you ever add a second lamp.

### GUI

Settings → Devices & Services → **Add Integration** → "Moon Lamp IR
(moonLedRemote)". Pick the infrared emitter entity from a dropdown (only
entities under the `infrared` domain are offered); address, carrier
frequency and repeat count are pre-filled with the confirmed defaults and
rarely need changing. Edit settings later via the integration's
**Reconfigure** option — no YAML edits or restart needed.

### YAML

See [`example_configuration.yaml`](example_configuration.yaml):

```yaml
light:
  - platform: moonled_ir
    name: Moon Lamp
    infrared_entity_id: infrared.living_room_liv_ir_mate_ir_proxy_transmitter
    # optional, these are the defaults:
    address: 0xEF00
    carrier_frequency: 38000
    repeat_count: 3
```

## How it works

The lamp **never commits an isolated NEC frame** — it only commits after
seeing the repeat sequence a real button press produces. The confirmed
working format is:

```
canonical NEC frame + 3 repeat bursts at ~108 ms spacing
```

This was reverse-engineered by making the IR Mate's own receiver capture
its own transmissions (and real remote presses) — see
[`HANDOFF-moonled-ir-mate.md`](HANDOFF-moonled-ir-mate.md) for the full
"measurement rig" writeup. One repeat burst is confirmed **not** enough;
three is what a real button press measured, and is the default here.

[`protocol.py`](custom_components/moonled_ir/protocol.py) builds this via
`infrared_protocols.commands.nec.NECCommand` (HA core's own NEC encoder —
the same one `led_infrared` uses), passing `repeat_count=3`. Its
`get_raw_timings()` embeds 3 repeat bursts directly into the returned
array; verified byte-for-byte equivalent to this repo's original
hand-rolled encoder. There's no reason to maintain a second NEC
implementation once the real one is reachable.

Each send takes ~330 ms to fully clear the transmitter; the entity awaits
that before the next command, so rapid successive calls (e.g. several
brightness steps) don't collide on the ESPHome RMT peripheral — the
underlying `remote_transmitter` is `non_blocking: true`.

## Command reference

The light is `assumed_state` (no feedback path exists — the lamp is a
bare IR receiver), so all state shown in HA is Home Assistant's best
guess based on what it has sent. Using the physical remote in parallel
will desync it until the next command.

<details>
<summary><strong>Power</strong> — certain</summary>

| Button | Command | Function |
|---|---|---|
| True | `0x02` | Turn on |
| False | `0x07` | Turn off |

Note these are swapped relative to the standard 24-key table (`ON=0x03`,
`OFF=0x02`) — only this lamp's top-row function keys are remapped; the
colour grid matches the standard table exactly.

</details>

<details>
<summary><strong>Colours</strong> — <code>ColorMode.RGB</code>, nearest-match</summary>

Calling `light.turn_on` with `rgb_color` snaps to the nearest of these 14
preset colours and sends that button:

| Colour | Command | Confidence |
|---|---|---|
| Red | `0x04` | Certain |
| Green | `0x05` | Certain |
| Blue | `0x06` | Certain |
| Yellow | `0x14` | Certain |
| Light green | `0x09` | Likely (untested, matches table) |
| Sky blue | `0x0A` | Likely |
| Cyan | `0x0D` | Likely |
| Rebecca purple | `0x0E` | Likely |
| Turquoise | `0x11` | Likely |
| Purple | `0x12` | Likely |
| Dark cyan | `0x15` | Likely |
| Plum | `0x16` | Likely |
| Orange red | `0x0C` | Untested prediction |
| Orange | `0x10` | Untested prediction |

Deliberately **excluded**: `0x07` (WHITE in the standard table) is
hijacked for OFF on this lamp, and `0x08` (TOMATO) was once observed to
turn the lamp off via an earlier config — a colour that might silently
kill the lamp isn't worth including.

</details>

<details>
<summary><strong>Effects</strong> — unconfirmed predictions</summary>

`light.turn_on` with `effect` sends one of these. None of the four has
been visually confirmed yet (nobody's watched for motion after sending
them) — if one turns out wrong, only `EFFECTS` in `const.py` needs to
change.

| Effect | Command |
|---|---|
| `flash` | `0x0B` |
| `strobe` | `0x0F` |
| `fade` | `0x13` |
| `smooth` | `0x17` |

</details>

<details>
<summary><strong>Brightness</strong> — 4 levels, relative-step hack</summary>

The remote only has BRIGHTNESS_UP (`0x00`) / BRIGHTNESS_DOWN (`0x01`)
buttons — no absolute-level command exists, and there's no feedback. HA's
`brightness` (0–255) is exposed as 4 discrete steps (64/128/191/255).

On the *first* brightness change each HA restart, the entity first sends
3 DOWN presses to force the lamp to its bottom step (a "calibration"),
then steps UP to the requested level. After that it trusts its own
tracked step count and only sends the delta. If the physical remote is
used in between, the tracked level — and therefore the next calibration —
can drift; there's no way to detect that without feedback hardware.

</details>

## Confidence levels

| Level | Meaning |
|---|---|
| **Certain** | Directly confirmed by capturing a real button press, or by observed effect on the physical lamp. |
| **Likely** | Matches the documented standard 24-key table exactly, but this specific byte was never sent to *this* lamp and visually confirmed. |
| **Untested prediction** | Table-predicted only; genuinely might be wrong or remapped, same as this lamp's power/brightness/effect keys turned out to be. |

## Contributing / help wanted

If you have this lamp (or one that responds to the same remote) and want
to help tighten up the confidence table:

1. Send an "Untested prediction" or "Likely" colour/effect and watch what
   actually happens.
2. Update the comment next to that entry in
   [`custom_components/moonled_ir/const.py`](custom_components/moonled_ir/const.py)
   and open a PR.

No code changes needed for most of this — it's all in one dict per
category.

## Credits

- [`home-assistant/core` `led_infrared`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/led_infrared) —
  architecture this hack is modelled on, and the integration this device
  would use if its function keys matched the standard layout.
- [`home-assistant/core` `infrared`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/infrared) —
  the core domain/entity base classes (`InfraredEmitterConsumerEntity`,
  `async_send_command`) this light sends through.
- [`esphome/esphome` `ir_rf_proxy`](https://github.com/esphome/esphome/tree/dev/esphome/components/ir_rf_proxy) —
  the ESPHome platform that exposes a native `infrared.*` emitter/receiver
  entity backed by `remote_transmitter`/`remote_receiver`, no bespoke
  service needed.
- [`home-assistant-libs/infrared-protocols`](https://github.com/home-assistant-libs/infrared-protocols)
  `infrared_protocols/commands/nec.py` (the NEC encoder this light's
  commands are built with) and
  `infrared_protocols/codes/generic/led/generic_24_key.py` (the standard
  24-key command table this lamp's colour grid matches).
- [`HANDOFF-moonled-ir-mate.md`](HANDOFF-moonled-ir-mate.md) — the full
  reverse-engineering log, measurement rig, and ground-truth table this
  repo's constants come from.

## License

[MIT](LICENSE)
