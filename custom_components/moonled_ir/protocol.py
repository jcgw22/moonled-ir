"""NEC IR frame builder for the moonLedRemote lamp.

Ported verbatim from the confirmed-working send format in
HANDOFF-moonled-ir-mate.md: a canonical NEC frame followed by three repeat
bursts at 108 ms spacing. The lamp never commits an isolated NEC frame --
it only commits after seeing the repeat sequence a real button press
produces. A single repeat burst is confirmed NOT enough (tested 5 times,
all verified correct on the wire, lamp ignored every one); three is what a
real press measured, so that's the default.
"""

from __future__ import annotations

from .const import (
    BIT_MARK,
    FRAME_PERIOD_US,
    LEADER_MARK,
    LEADER_SPACE,
    MAX_SPACE_US,
    ONE_SPACE,
    REPEAT_BURST,
    ZERO_SPACE,
)


def _nec_frame(command: int, address: int) -> list[int]:
    timings = [LEADER_MARK, LEADER_SPACE]
    value = (
        (address & 0xFF)
        | (((address >> 8) & 0xFF) << 8)
        | ((command & 0xFF) << 16)
        | ((~command & 0xFF) << 24)
    )
    for _ in range(32):
        timings.append(BIT_MARK)
        timings.append(ONE_SPACE if value & 1 else ZERO_SPACE)
        value >>= 1
    timings.append(BIT_MARK)  # stop mark
    return timings


def _gap(duration_us: int) -> list[int]:
    """Split a gap into chunks under MAX_SPACE_US.

    ESPHome's RMT transmitter already splits long spaces on its own, but
    this is kept as belt-and-braces per the handoff.
    """
    chunks: list[int] = []
    remaining = duration_us
    while remaining > 0:
        step = min(remaining, MAX_SPACE_US)
        chunks.append(-step)
        remaining -= step
    return chunks


def build_command(command: int, address: int, repeat_count: int) -> list[int]:
    """Build the full raw-timing array for one button press.

    Pass the result as the `command` field of
    esphome.<node>_send_raw_command with carrier_frequency in Hz (38000
    for this lamp).
    """
    frame = _nec_frame(command, address)
    frame_gap = FRAME_PERIOD_US - sum(abs(v) for v in frame)
    repeat_gap = FRAME_PERIOD_US - sum(abs(v) for v in REPEAT_BURST)

    result = list(frame)
    result += _gap(frame_gap)
    for i in range(repeat_count):
        result += REPEAT_BURST
        if i < repeat_count - 1:
            result += _gap(repeat_gap)
    return result
