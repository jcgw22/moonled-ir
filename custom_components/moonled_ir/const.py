"""Constants and IR protocol data for the moonLedRemote moon lamp.

Command bytes and confidence levels are lifted directly from
HANDOFF-moonled-ir-mate.md (session 3, 2026-09-22) and cross-checked
against home-assistant-libs/infrared-protocols'
infrared_protocols/codes/generic/led/generic_24_key.py, which is the
standard 24-key table this lamp's colour grid matches exactly. Only the
top-row function keys (ON/OFF/brightness/effects) are remapped on this
particular lamp -- see the per-entry comments below.
"""

DOMAIN = "moonled_ir"

CONF_SEND_SERVICE = "send_service"
CONF_ADDRESS = "address"
CONF_CARRIER_FREQUENCY = "carrier_frequency"
CONF_REPEAT_COUNT = "repeat_count"

DEFAULT_NAME = "Moon Lamp"
DEFAULT_ADDRESS = 0xEF00
DEFAULT_CARRIER_FREQUENCY = 38000
DEFAULT_REPEAT_COUNT = 3

# Canonical NEC timings measured directly off a real button press via the
# IR Mate's own receiver (handoff: "Measured ground truth: a real Red
# button press"). Do NOT substitute the Broadlink-derived timings from the
# learned base64 codes -- that decoder's tick constant is ~7-11% long and
# the lamp will silently ignore the result.
LEADER_MARK = 9000
LEADER_SPACE = -4500
BIT_MARK = 562
ZERO_SPACE = -562
ONE_SPACE = -1687
REPEAT_BURST = [9000, -2250, 562]
FRAME_PERIOD_US = 108000  # textbook NEC 108 ms leader-to-leader spacing
MAX_SPACE_US = 30000  # stay under the RMT 15-bit space field (belt-and-braces)

# --- Power ---------------------------------------------------------------
# Certain, confirmed session 3 by direct observation. Note these do NOT
# match the standard table (which has ON=0x03, OFF=0x02) -- this lamp's
# power keys are swapped/remapped relative to the generic layout.
CMD_ON = 0x02  # "True" button
CMD_OFF = 0x07  # "False" button -- NOT "white", despite matching the WHITE
                # slot (0x07) in the standard table.

# --- Brightness ------------------------------------------------------------
# Unconfirmed prediction from the standard table (handoff: "Predictions
# still to confirm for the effect keys"). Plausible: the "0x00 turns the
# lamp on and defaults to red" observation from session 2 is consistent
# with brightness-up also waking an off lamp. Re-verify against a real
# button capture before trusting this for anything beyond this hack.
CMD_BRIGHTNESS_UP = 0x00  # "60m" button
CMD_BRIGHTNESS_DOWN = 0x01  # "Fade" button
BRIGHTNESS_LEVELS = 4  # physical steps on the remote; no feedback path

# --- Colours ---------------------------------------------------------------
# High confidence: the handoff found the colour grid matches the standard
# 24-key table exactly. 0x04/0x05/0x06/0x14 are directly confirmed; the
# rest were never in the original learned set but follow the same table
# and 0x06 (BLUE), also not in the learned set, came back correct.
#
# Excluded from this map on purpose:
#   0x07 WHITE  -- hijacked for OFF on this lamp, sending it would turn
#                  the lamp off instead of setting a colour.
#   0x08 TOMATO -- session 2 recorded this as "turns the lamp off" via the
#                  old led_infrared integration. That conflicts with the
#                  table's TOMATO prediction and was never re-verified; a
#                  colour button that might silently kill the lamp is
#                  worse than one missing colour.
COLORS: dict[int, tuple[int, int, int]] = {
    0x04: (255, 0, 0),  # RED -- certain
    0x05: (0, 255, 0),  # GREEN -- certain
    0x06: (0, 0, 255),  # BLUE -- certain
    0x14: (255, 255, 0),  # YELLOW -- certain
    0x09: (144, 238, 144),  # LIGHT_GREEN -- likely, untested
    0x0A: (135, 206, 235),  # SKY_BLUE -- likely, untested
    0x0D: (0, 255, 255),  # CYAN -- likely, untested
    0x0E: (102, 51, 153),  # REBECCA_PURPLE -- likely, untested
    0x11: (64, 224, 208),  # TURQUOISE -- likely, untested
    0x12: (128, 0, 128),  # PURPLE -- likely, untested
    0x15: (0, 139, 139),  # DARK_CYAN -- likely, untested
    0x16: (221, 160, 221),  # PLUM -- likely, untested
    0x0C: (255, 69, 0),  # ORANGE_RED -- untested prediction
    0x10: (255, 165, 0),  # ORANGE -- untested prediction
}

# --- Effects -----------------------------------------------------------
# All unconfirmed predictions from the standard table (handoff: "would
# explain why session 2 recorded them as 'no visible effect' -- nobody
# waited to watch for motion"). Wire up under these names; if a code turns
# out wrong only this dict needs to change.
EFFECT_FLASH = "flash"
EFFECT_STROBE = "strobe"
EFFECT_FADE = "fade"
EFFECT_SMOOTH = "smooth"

EFFECTS: dict[str, int] = {
    EFFECT_FLASH: 0x0B,  # "Down" button
    EFFECT_STROBE: 0x0F,  # "30m" button
    EFFECT_FADE: 0x13,  # "White" button
    EFFECT_SMOOTH: 0x17,  # "Flash" button
}
