"""The moonLedRemote moon lamp integration.

Pure YAML light platform -- see light.py. No component-level setup is
needed; this file only needs to exist for Home Assistant to recognize
`moonled_ir` as an integration domain. Depends on HA core's `infrared`
domain (declared in manifest.json) for the emitter entity this light
sends commands through -- see light.py and README.md.
"""
