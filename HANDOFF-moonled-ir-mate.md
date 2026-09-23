# Handoff: Moon Lamp IR (moonLedRemote) via LIV IR Mate

Status as of 2026-09-22 (session 3). **The "trailing edge" / one-behind problem is
SOLVED.** There is now a confirmed send format that works immediately, every
time, leaving nothing pending. Read "The working send format" and you can skip
most of the history.

## TL;DR

- The lamp **never commits an isolated NEC frame.** It commits only after it sees
  the *repeat sequence* that a real button press produces.
- Working format: **canonical NEC frame + 41095 us gap + 3 repeat bursts at
  108 ms spacing.** Confirmed working (Green, verified end-state).
- The old "one-behind command queue" was never a queue. Each new transmission
  supplied the trailing structure the *previous* frame was missing, so the
  previous command finally committed. Same observable, completely different
  cause.
- **The session-2 Broadlink decoder was wrong.** Its 32.84 us tick constant
  inflates every timing by ~7-11%. The real remote, measured directly, is plain
  canonical NEC. Do not trust any timing derived from the base64 codes.

## Devices involved

- **LIV IR Mate** (`xiao-ir-mate-7c8798`, "LIV IR Mate ") - Seeed XIAO ESP32C3
  in the living room next to the moon lamp. Control via the custom service
  **`esphome.xiao_ir_mate_7c8798_send_raw_command`**:
  - `command: int[]` - signed us timings (positive = mark, negative = space)
  - `carrier_frequency: int` - **in Hz, use `38000`** (the field's "42" example
    misleadingly implies kHz)
  - No repeat/gap logic of its own; the array you pass is exactly what is sent.
- **Broadlink RM4 Pro** (`remote.broadlink_rm4_remote`, bedroom) - where the 15
  `moonLedRemote` base64 codes were originally learned. Out of range of the lamp.
  Now only of historical interest; its captures are timing-unreliable (see below).
- **"LIV moonLight" `led_infrared` integration** - deleted by the user in
  session 2. Its command *names* never matched this lamp's actual functions.

## The working send format

```python
L_H, L_L, B_H, Z_L, O_L = 9000, 4500, 562, 562, 1687   # canonical NEC
RPT = [9000, -2250, 562]                                # canonical NEC repeat burst

def nec_frame(command, address=0xEF00):
    t = [L_H, -L_L]
    v = (address & 0xFF) | (((address >> 8) & 0xFF) << 8) \
        | ((command & 0xFF) << 16) | (((~command) & 0xFF) << 24)
    for _ in range(32):
        t.append(B_H)
        t.append(-(O_L if v & 1 else Z_L))
        v >>= 1
    t.append(B_H)                       # stop mark
    return t

def gap(us, lim=30000):                 # keep each space under the RMT 15-bit field
    o = []
    while us > 0:
        s = min(us, lim); o.append(-s); us -= s
    return o

def send_array(command):
    f = nec_frame(command)
    g1 = 108000 - sum(abs(x) for x in f)          # -> first repeat at the 108 ms mark
    g2 = 108000 - sum(abs(x) for x in RPT)        # -> 108 ms between repeats
    return f + gap(g1) + RPT + gap(g2) + RPT + gap(g2) + RPT

# send_array(0x05) -> 86 values, call with carrier_frequency=38000
```

Three repeats is what a real press was measured to emit. Fewer has not been
tested; **one repeat is confirmed NOT enough** (see the failure log below).

### Also-works fallback: double frame

`nec_frame(cmd) + [-20000, -20000] + nec_frame(cmd)` works too (confirmed 3/3:
Red, Green, Yellow). It is inferior: the second frame stays pending and commits
on the *next* send, so it leaves a dangling duplicate. Harmless for colours,
dangerous for power/toggle codes. Prefer the repeat format.

## Ground truth table

Confidence resets this session: **any earlier "no visible effect" result is
suspect**, because it was produced with a frame format this lamp ignores.

| Label | cmd | Confirmed function | Confidence |
|---|---|---|---|
| Red1 | 0x04 | **Red** | **Certain** - decoded directly from a physical Red button press captured by the IR Mate receiver |
| Green1 | 0x05 | **Green** | **Certain** - confirmed twice this session with two different working formats |
| Yellow | 0x14 | **Yellow** | **Certain** - confirmed this session via double-frame |
| - | 0x06 | **Blue** | **Certain** - confirmed session 3; not in the learned 15-code set |
| False | 0x07 | **Turns lamp OFF** | **Certain** - confirmed session 3, lamp visibly went off |
| 60m | 0x00 | Turns lamp ON, defaults to red | Low - indirect inference only |
| Fade | 0x01 | Fade effect | Low - via the deleted led_infrared integration |
| Red2 | 0x08 | Turns lamp OFF | Low - via the deleted led_infrared integration |
| True | 0x02 | **Turns lamp ON** | **Certain** - confirmed session 3: no effect while already on, turns the lamp on from off. True/False are a genuine on/off pair, which is why every earlier test of 0x02 looked dead |
| Up | 0x03 | ? | Retest |
| Down | 0x0B | ? | Retest |
| White | 0x13 | ? | Retest |
| 30m | 0x0F | ? | Retest |
| Orange1 | 0x0C | ? | Untested |
| Orange2 | 0x10 | ? | Untested |
| Flash | 0x17 | ? | Untested |

Address is **0xEF00** for all codes, confirmed by direct measurement.

## The colour grid matches the standard 24-key table (big finding)

Compared against `home-assistant-libs/infrared-protocols`,
`infrared_protocols/codes/generic/led/generic_24_key.py`:

| Code | Table says | We measured | |
|---|---|---|---|
| 0x04 | RED | Red | match |
| 0x05 | GREEN | Green | match |
| 0x14 | YELLOW | Yellow | match |
| 0x06 | BLUE | Blue | match (confirmed session 3) |
| 0x07 | WHITE | **OFF** | MISMATCH |
| 0x02 | OFF | **ON** | MISMATCH |

**The colour codes match the standard table exactly. Only the function /
top-row keys are remapped on this lamp.** The session-2 blanket warning that
"the mapping does not match this lamp" was too pessimistic - it is specifically
the function keys that differ, and the colour grid can be trusted.

### Nine extra colours your remote cannot send

The protocol defines 24 keys; only 15 were ever learned onto the Broadlink. These
command bytes were never in the `moonLedRemote` set at all, and `0x06` (BLUE) is
confirmed working, so the rest are very likely good:

| Code | Table name |
|---|---|
| 0x06 | BLUE - **confirmed** |
| 0x09 | LIGHT_GREEN |
| 0x0A | SKY_BLUE |
| 0x0D | CYAN |
| 0x0E | REBECCA_PURPLE |
| 0x11 | TURQUOISE |
| 0x12 | PURPLE |
| 0x15 | DARK_CYAN |
| 0x16 | PLUM |

All were transmitted in session 3; per-colour visual confirmation is incomplete.

### Predictions still to confirm for the effect keys

The table also predicts the effect keys, which would explain why session 2
recorded them as "no visible effect" - nobody waited to watch for motion:

| Code | Old label | Table predicts |
|---|---|---|
| 0x0B | Down | FLASH |
| 0x0F | 30m | STROBE |
| 0x13 | White | FADE |
| 0x17 | Flash | SMOOTH |
| 0x00 | 60m | BRIGHTNESS_UP |
| 0x01 | Fade | BRIGHTNESS_DOWN |
| 0x03 | Up | ON |
| 0x0C | Orange1 | ORANGE_RED |
| 0x10 | Orange2 | ORANGE |
| 0x08 | Red2 | TOMATO |

Note 0x00 = BRIGHTNESS_UP would explain the session-2 "turns lamp ON, defaults
to red" inference: brightness-up on an off lamp may well wake it.

## The measurement rig (the thing that cracked this)

**The IR Mate's own receiver picks up its own transmitter.** That turns the
device into an oscilloscope. A temporary automation
`automation.tmp_ir_rx_capture_debug` mirrors every `esphome.ir_received` event
into the HA system log:

- trigger: event `esphome.ir_received`
- action: `system_log.write`, level `warning`, logger `irdebug`,
  message `IRRX {{ trigger.event.event_type }} :: {{ trigger.event.data | tojson }}`

Read it back with `ha_get_logs(source="system", search="IRRX")`. The event
payload carries a full `raw` timing list and a `size`. This verifies what
actually went out on the wire, and it also captures the **physical remote**
when pressed - which is how the canonical timings were established.

Delete the automation when no longer wanted; it is debug-only and writes a
WARNING line per IR reception.

## Measured ground truth: a real Red button press

```
9038,-4530, <32 bits>, 584, -40774, 9054,-2258,584   (one event)
9046,-2258,584                                        (separate event, ~108 ms later)
9042,-2256,582                                        (separate event, ~108 ms later)
```

- Leader **9038 / -4530**, bit mark **584**, zero-space **-550**, one-space **-1684**
- Frame + gap = **108228 us**, i.e. the textbook NEC 108 ms period
- Repeat burst **9054, -2258, 584** = canonical NEC repeat
- Decodes as `addr=0xEF00 cmd=0x04`

Compare the session-2 Broadlink-derived values for the same button: leader
9622/-4893, one-space -1872, zero-space -624, repeat 9655/-2463. Uniformly
~7-11% long. **The 32.84 us tick constant in the old decoder is wrong** (the
other common Broadlink tick, 1/32768 s = 30.52 us, lands on canonical). Use the
base64 codes only to recover *command bytes*, never timings.

## What was tried and failed (don't repeat these)

| Attempt | Result |
|---|---|
| Bare 67-value frame | Never commits. Waits indefinitely. |
| Frame + trailing gap (`-20000` / `-40000`) | No effect - a gap adds no new leader edge. |
| Frame + **one** canonical repeat burst | **Fails.** Tested 5 times (Green, Orange1, Orange2, Yellow, White) - all 5 verified correct on the wire, lamp ignored every one. |
| "Verbatim" replay of the Broadlink capture (stretched timings, 1-2 repeats) | **Fails** - the ~7% stretch puts it outside the lamp's decode tolerance. |
| Frame + 40 ms + frame (double frame) | **Works**, but leaves a pending duplicate. |
| Frame + 41 ms + 3 repeats at 108 ms | **Works. Use this.** |

## ESPHome facts established from source (2026.9.0)

Read from `esphome/components/remote_transmitter/remote_transmitter_rmt.cpp`
and `__init__.py`:

- **The >32767 us gap / "flooding" bug is structurally handled.** ESPHome
  already splits any duration longer than `RMT_SYMBOL_DURATION_MAX` (0x7FFF)
  into multiple RMT symbols. Long gaps were sent repeatedly this session with
  no flooding. Manual chunking to <=30000 is still used as belt-and-braces.
- Adjacent spaces merge on the wire (`-20000, -20000` was received as `-39990`),
  so chunking is transparent to the receiver.
- `carrier.flags.always_on = 1` is set, but `eot_level` defaults to **low** for
  a normal non-inverted pin, so nothing is emitted after transmission. Confirmed
  by capture: frames end in a space, never a runaway mark. The "carrier stuck
  on" theory is dead.
- The final stop mark **is** transmitted. Confirmed by capture (532-588 us mark
  present at the end of every frame). The "ESPHome drops the last odd timing"
  theory is dead.
- `non_blocking` defaults to **true** since ESPHome 2025.11.0, and
  `trans_queue_depth = 1`. Transmissions nonetheless fire immediately - the
  capture timestamps prove it. The "transmitter queues one behind" theory is dead.

## Next steps

1. [ ] Finish the ground truth table using the working format - the six
   "Retest" and three "Untested" rows. Every send is now immediate and
   self-contained, so no chain-test bookkeeping is needed; just send one code
   and read the result. Keep the lamp **on** so colour/effect codes are visible.
2. [ ] Test the power codes (0x07, 0x08, 0x00) last, since they change power
   state and will mask subsequent colour tests.
3. [ ] Check whether fewer than 3 repeat bursts suffice (2? 1 is known to fail)
   - purely an optimisation, the 86-value array is already fine.
4. [ ] Build the control surface: a script/dashboard calling
   `esphome.xiao_ir_mate_7c8798_send_raw_command` with the verified arrays.
   Re-learning the Broadlink codes under corrected names is no longer needed -
   the lamp is out of the RM4's range anyway.
5. [ ] Delete `automation.tmp_ir_rx_capture_debug` when debugging is finished.

## Appendix: original base64 codes (command bytes only - timings unreliable)

```json
{
  "True": "JgBYAAABJpMTEhMSExIUERQRFBITEhEUEzcRORI4FDcTERQ3EzcRORMSEjgUEhETFBESFBEUERQROREUETkSOBI4EzgRORE5EQAFOAABJkwSAAxOAAEnSxIADQU=",
  "False": "JgBYAAABJJUUEhMSExIRFBMSExIRFBITEzcUNhQ3ETkTEhM3EzcRORM3EjgSOBMSEhMSExITEhMSExITEhQRORE5ETkRORI4EgAFNQABKEkUAAxKAAEoShMADQU=",
  "Up": "JgBYAAABJpMUERIUExITEhMSExITEhMSEzcTNxM3EzcTEhM3EzcTNxQ2FDYUERQREhMUERQSExITEhMSEzcTNxM3EzcTNxE5EgAFNgABJksSAAxLAAEmTBEADQU=",
  "Down": "JgBgAAABJZUUERQRExITEhQRExITEhQREjkRORE5ETkSExI4EjgSORE5ETkRFBI4EhMSExITEhQRFBMSEzcTEhM3FDYUNhQ3EwAFNQABKUcWAAxMAAEnShMADEwAASZLEgANBQ==",
  "White": "JgBYAAABJZQTExITERQRFBEUERQSExITEjgTNxI5ETkRFBE5ETkUNhQ2FDYUEhMSEzcSExEUERQRFBITEjgSOBIUETkRORE5EQAFNwABJ0sSAAxPAAEmTBEADQU=",
  "30m": "JgBYAAABJZUTEhEUEhMSExITEhMUERQSEzcRORE5ETkTEhM3EzcTNxQ2FDYUNxE5ERQTEhMSExIRFBMSExISExQ2FDcRORE5EQAFOAABKEoUAAxMAAEoShMADQU=",
  "60m": "JgBYAAABJ5MTEhMSExITEhMSExIUERQREzgSOBE5EjgSExI4EjkROREUERQRFBITEhMSExIUERQRORE5EjgUNhQ3EzcTNxQ2FAAFNgABKUkTAAxPAAEoSRQADQU=",
  "Flash": "JgBYAAABJJUSExEUExITEhMSFBEUERQRFDYUNhQ2FDcTEhE5ETkRORE5ETkSOBEUETkSExITEhMSExITExISOBITEjgSOBI4FAAFMwABKEoTAAxKAAEoSRIADQU=",
  "Fade": "JgBYAAABJJUSExQREhMSExQREhMUEhMSETkTNxM3EzcTEhM3ETkSOBI5ERMSExIaCxMSExITEhMSExI5EjgRORE5ETkRORE5EQAFNgABKEoTAAxIAAEoShMADQU=",
  "Red1": "JgBQAAABJZUSExEUERQRFBITEhMSExITEjkROBI5ETkRFBE5ETkSOBITEhMSOBITEhQRFBEUERQRORI4ERQRORE5ETkSOBI4EgAFNgABJksSAA0F",
  "Red2": "JgBYAAABJJUSExITEhMSExITEhMSExITEjkRORE5ETkRFBI4EjgSOBITEhQRFBE5ERQRFBEUEhMSOBI4EjgSFBE5ETkRORI4EgAFNQABJkwRAAxMAAEmSxMADQU=",
  "Orange1": "JgBQAAABJ5MTEhMSFBEUERQRFBEUERQREjkRORM3ETkRFBE5EjgSOBITEhQRORE5ERQRFBEUEhMSOBI4ExMRFBE5ETkRORI4EgAFNwABKEoTAA0F",
  "Orange2": "JgBYAAABJZUTEhEUERQRFBITEhMSExQREjgUNxM3EzcTEhM3EzcTNxQRFBEUERQRFDYUERQREhMUNhI4EjkSOBITETkSOBI4EgAFNgABJUwTAAxJAAEmTBEADQU=",
  "Yellow": "JgBYAAABJ5IUERQSExITEhMSExITEhMSEzcRORE5EzcUEhE5EzcTNxMSExITNxMSEjgUERITEhMSORE5ERQRORITETkSOBI4EgAFNgABJkwSAAxOAAEnSxIADQU=",
  "Green1": "JgBYAAABJZUSExITEhMSExITEhMSExIUETkRORE5EzcRFBM3EzcSOBQ2FBEUNhQSExITEhMSExITEhM3ERQSOBQ2EjgTOBE5EQAFNgABJkwSAAxMAAElTBEADQU="
}
```

Command bytes: True 0x02, False 0x07, Up 0x03, Down 0x0B, White 0x13, 30m 0x0F,
60m 0x00, Flash 0x17, Fade 0x01, Red1 0x04, Red2 0x08, Orange1 0x0C,
Orange2 0x10, Yellow 0x14, Green1 0x05.
