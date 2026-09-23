"""NEC command builder for the moonLedRemote lamp, via HA core's own encoder.

Earlier versions of this hack hand-rolled the NEC frame + repeat-burst
timings directly (see git history) because at the time there was no other
way to reach this ESPHome node from HA except a bespoke raw-send service.
That hand-rolled encoder was verified against
infrared_protocols.commands.nec.NECCommand (the encoder HA core's own
`infrared` integration uses) and found to produce byte-for-byte identical
constants:

  leader 9000/-4500, bit mark 562, zero -562, one -1687,
  repeat burst [9000, -2250, 562], ~108 ms frame period

`NECCommand(address, command, repeat_count=N).get_raw_timings()` embeds N
repeat bursts directly into the returned array -- this is what makes a
repeat_count=3 NECCommand equivalent to the handoff's confirmed-working
"frame + 3 repeat bursts at 108 ms spacing" format. There's no reason to
maintain a second implementation, so this module now just wraps it.
"""

from __future__ import annotations

from infrared_protocols.commands.nec import NECCommand


def build_command(
    command: int, address: int, repeat_count: int, modulation: int
) -> NECCommand:
    """Build the NEC command for one button press."""
    return NECCommand(
        address=address,
        command=command,
        repeat_count=repeat_count,
        modulation=modulation,
    )
