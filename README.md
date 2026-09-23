# Moon Lamp IR (moonLedRemote)

A Home Assistant custom `light` integration for one specific unlabelled
24-key RGB LED remote (product name `moonLedRemote`, an IR-controlled moon
lamp), controlled through a Seeed XIAO ESP32C3 running ESPHome's native
`infrared` platform (`ir_rf_proxy`) — the same core `infrared`/NEC stack
HA's own `led_infrared` uses.

This is a **hack repo for one device**, not a general-purpose IR light
integration. Every command byte below came from directly capturing this
lamp's own physical remote with the ESPHome node's IR receiver — see
`HANDOFF-moonled-ir-mate.md` in the parent directory for the full
investigation log.

## Why a custom integration instead of HA core's `led_infrared`

HA core's [`led_infrared`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/led_infrared)
integration is built for exactly this class of remote (it even uses the
same 24-key protocol table this lamp matches) and this repo now sits on
top of the same `infrared` domain and `infrared_protocols.NECCommand`
encoder it uses. The one thing it doesn't do is fit this specific lamp's
remote:

- `led_infrared` deliberately models the light as `ColorMode.ONOFF` + an
  effect list (colours are effects, not real colour) — a reasonable
  protocol-agnostic choice, but this lamp's remote has genuine colour
  buttons *and* two relative brightness buttons with 4 physical steps. So
  this hack models it as a real `ColorMode.RGB` light with a 4-level
  brightness attribute instead (see below).
- This lamp's top-row function keys (power, brightness, effects) don't
  match the standard 24-key layout `led_infrared` assumes, and several are
  still unconfirmed predictions (see the tables below) — not something a
  general-purpose integration could hardcode.

The architecture (`const.py` protocol table + `light.py` entity) is
deliberately modelled on `led_infrared`'s `entity.py`/`light.py` split.

## Requires: `ir_rf_proxy` on the IR Mate node

This integration sends commands through an `infrared.*` **emitter**
entity via `InfraredEmitterConsumerEntity` (same base class
`led_infrared` uses) — it does **not** call any bespoke ESPHome service.
The XIAO IR Mate node needs ESPHome's
[`ir_rf_proxy`](https://esphome.io/components/infrared.html) platform
added under `infrared:`, wrapping its existing `remote_transmitter`:

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
entity in HA — that's what `infrared_entity_id` in this light's config
points at. (The living-room XIAO IR Mate's own `xiao-ir-mate-7c8798.yaml`
already has this block added; it just needs reflashing.)

## How sending works

The lamp **never commits an isolated NEC frame** — it only commits after
seeing the repeat sequence a real button press produces. The confirmed
working format is:

```
canonical NEC frame + 3 repeat bursts at ~108 ms spacing
```

This was reverse-engineered by making the IR Mate's own receiver capture
its own transmissions (and real remote presses) — see the handoff's
"measurement rig" section. One repeat burst is confirmed **not** enough;
three is what a real button press measured, and is the default here.

`protocol.py` builds this via `infrared_protocols.commands.nec.NECCommand`
(HA core's own NEC encoder — the same one `led_infrared` uses), passing
`repeat_count=3`. Its `get_raw_timings()` embeds 3 repeat bursts directly
into the returned array; verified byte-for-byte equivalent to this repo's
original hand-rolled encoder (see `protocol.py`'s docstring). There's no
reason to maintain a second NEC implementation once the real one is
reachable.

Each send takes ~330 ms to fully clear the transmitter; the entity awaits
that before the next command, so rapid successive calls (e.g. several
brightness steps) don't collide on the ESPHome RMT peripheral — the
underlying `remote_transmitter` is `non_blocking: true`.

## Installation

1. Add the `ir_rf_proxy` block above to the IR Mate node's ESPHome YAML
   (already done for `xiao-ir-mate-7c8798.yaml`) and flash it. Confirm the
   new `infrared.*_ir_proxy_transmitter` entity appears in HA.
2. Copy `custom_components/moonled_ir/` into your Home Assistant
   `config/custom_components/` directory (or add this repo as a HACS
   custom repository — category "Integration").
3. Restart Home Assistant.
4. Set the light up either way — both produce the same entity, and you can
   mix them across multiple lamps if you ever add a second one:

   **GUI:** Settings → Devices & Services → Add Integration → "Moon Lamp
   IR (moonLedRemote)". Pick the infrared emitter entity from a dropdown
   (only entities under the `infrared` domain are offered); address,
   carrier frequency and repeat count are pre-filled with the confirmed
   defaults and rarely need changing. Settings can be edited later via the
   integration's "Reconfigure" option, no YAML edits or restart needed.

   **YAML**, see `example_configuration.yaml`:

   ```yaml
   light:
     - platform: moonled_ir
       name: Moon Lamp
       infrared_entity_id: infrared.living_room_liv_ir_mate_ir_proxy_transmitter
   ```

   Either way, check Developer Tools → States for the exact
   `infrared.*_ir_proxy_transmitter` entity_id once the node's been
   reflashed — HA generates it from the device + entity name.

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
- `HANDOFF-moonled-ir-mate.md` — the full reverse-engineering log,
  measurement rig, and ground-truth table this repo's constants come from.
