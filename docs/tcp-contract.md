# PAMG TCP Contract

The TCP server accepts newline-delimited JSON objects. This contract separates
music-generation inputs from compatibility telemetry and lifecycle commands.

## Generation-affecting fields

- `x`, `y`: normalized XY preset coordinates in `[0, 1]`.
- `tempo`: positive BPM.
- `loop_size`: positive loop length.
- `grain`: positive subdivision factor.
- `time_signature`: supported meter; updates loop structure and grain.
- `seed` or `base_seed`: base phrase seed; `0` enables improvisation.

Only these fields may change generated musical state.

## Diagnostic compatibility fields

`health`, `enemies`, `valence`, `arousal`, and `key_center` may be accepted and
reported for integration compatibility, but they do not directly alter PAMG
generation state. XY coordinates must be supplied explicitly for preset
movement.

## Lifecycle actions

The server may receive `handshake`, `pause`, `resume`, `stop`, `reset`,
`status`/`query`, and `shutdown`. Telemetry does not implicitly resume
playback; playback state changes require an explicit lifecycle action.
