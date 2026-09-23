# Moon Lamp IR (moonLedRemote)

A Home Assistant custom `light` integration for one specific unlabelled
24-key RGB LED remote (product name `moonLedRemote`, an IR-controlled moon
lamp), built entirely around a Seeed XIAO ESP32C3 running ESPHome as a
raw IR blaster (no HA core `remote`/`infrared` platform involved).

This is a **hack repo for one device**, not a general-purpose IR light
integration. Every command byte below came from directly capturing this
lamp's own physical remote with the ESPHome node's IR receiver — see
`HANDOFF-moonled-ir-mate.md` in the parent directory for the full
investigation log.

## Why a custom integration instead of HA core's `led_infrared`

HA core's [`led_infrared`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/led_infrared)
integration is built for exactly this class of remote (it even uses the
same 24-key protocol table this lamp matches), but it doesn't fit here for
two reasons:

1. It depends on HA core's new `infrared` integration/domain (emitter and
   receiver entities), which this setup doesn't have — IR is sent via a
   plain ESPHome custom service (`esphome.xiao_ir_mate_7c8798_send_raw_command`)
   on the XIAO IR Mate, not a `remote.*`/`infrared.*` entity.
2. It deliberately models the light as `ColorMode.ONOFF` + an effect list
   (colours are effects, not real colour). That's a reasonable choice for
   a protocol-agnostic integration, but this lamp's remote has genuine
   colour buttons *and* two relative brightness buttons with 4 physical
   steps, so this hack models it as a real `ColorMode.RGB` light with a
   4-level brightness attribute instead.

The architecture (`const.py` protocol table + entity split) is deliberately
modelled on `led_infrared`'s `entity.py`/`light.py` split, just swapped to
talk to an ESPHome service and to expose real colour + brightness.

## How sending works

The lamp **never commits an isolated NEC frame** — it only commits after
seeing the repeat sequence a real button press produces. The confirmed
working format (`protocol.py`) is:

```
canonical NEC frame + 41095 us gap + 3 repeat bursts at 108 ms spacing
```

This was reverse-engineered by making the IR Mate's own receiver capture
its own transmissions (and real remote presses) — see the handoff's
"measurement rig" section. One repeat burst is confirmed **not** enough;
three is what a real button press measured, and is the default here.

Each send takes ~330 ms to fully clear the transmitter
(`repeat_count * 108 ms`); the entity awaits that before the next command,
so rapid successive calls (e.g. several brightness steps) don't collide on
the ESPHome RMT peripheral.

## Installation

1. Copy `custom_components/moonled_ir/` into your Home Assistant
   `config/custom_components/` directory (or add this repo as a HACS
   custom repository — category "Integration").
2. Add a `light:` entry, see `example_configuration.yaml`:

   ```yaml
   light:
     - platform: moonled_ir
       name: Moon Lamp
       send_service: esphome.xiao_ir_mate_7c8798_send_raw_command
   ```

   `send_service` is the ESPHome raw-send service exposed by your IR
   blaster node, as `domain.service`.
3. Restart Home Assistant.

No config flow / UI setup — this is YAML-only by design, so tweaking a
command byte in `const.py` doesn't require re-adding a config entry.

## What each control does

The light is `assumed_state` (no feedback path exists — the lamp is a bare
IR receiver), so all state shown in HA is Home Assistant's best guess
based on what it has sent. Using the physical remote in parallel will
desync it until the next command.

### Power — certain

| Button | Command | Function |
|---|---|---|
| True | `0x02` | Turn on |
| False | `0x07` | Turn off |

Note these are swapped relative to the standard 24-key table (`ON=0x03`,
`OFF=0x02`) — only this lamp's top-row function keys are remapped; the
colour grid matches the standard table exactly.

### Colours — `ColorMode.RGB`, nearest-match

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
turn the lamp off via the old deleted `led_infrared` config — a colour
that might silently kill the lamp isn't worth including.

### Effects — unconfirmed predictions

`light.turn_on` with `effect` sends one of these. None of the four has
been visually confirmed yet (handoff: "nobody waited to watch for
motion") — if one turns out wrong, only `EFFECTS` in `const.py` needs to
change.

| Effect | Command |
|---|---|
| `flash` | `0x0B` |
| `strobe` | `0x0F` |
| `fade` | `0x13` |
| `smooth` | `0x17` |

### Brightness — 4 levels, relative-step hack

The remote only has BRIGHTNESS_UP (`0x00`) / BRIGHTNESS_DOWN (`0x01`)
buttons — no absolute-level command exists, and there's no feedback. HA's
`brightness` (0–255) is exposed as 4 discrete steps (64/128/191/255).

On the *first* brightness change each HA restart, the entity first sends
3 DOWN presses to force the lamp to its bottom step (a "calibration"),
then steps UP to the requested level. After that it trusts its own
tracked step count and only sends the delta. If the physical remote is
used in between, the tracked level — and therefore the next calibration —
can drift; there's no way to detect that without feedback hardware.

## Credit / references

- [`home-assistant/core` `led_infrared`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/led_infrared) —
  architecture this hack is modelled on.
- [`home-assistant-libs/infrared-protocols`](https://github.com/home-assistant-libs/infrared-protocols)
  `infrared_protocols/codes/generic/led/generic_24_key.py` — the standard
  24-key command table this lamp's colour grid matches.
- `HANDOFF-moonled-ir-mate.md` — the full reverse-engineering log,
  measurement rig, and ground-truth table this repo's constants come from.
