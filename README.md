# Doublecheck

An OVOS skill that asks before running a high-risk request [Switchboard](https://github.com/OscillateLabsLLC/switchboard) held.

Some requests shouldn't run on a misheard word: unlocking a door, opening the garage, shutting down, clearing data.
Switchboard never acts on these directly, and no confidence threshold makes them safe: wrong high-risk picks have
reached 0.994 confidence. With Switchboard's `high_risk: "confirm"`, a held request is dispatched to Doublecheck,
which:

- **repeats it back in the user's own words** and asks: "You said: unlock the front door. Should I go ahead?",
- **on a clear yes**, runs exactly the held intent, with the same message ovos-core would have dispatched to its
  skill (the original utterance's data and context, the matched slots, the skill's id), so the skill can't tell
  the difference,
- **on anything else** (no, silence, an unclear answer) says "OK, I won't" and runs nothing.

Quoting the user needs no per-intent wording and is honest about speech recognition: the user hears what was
actually understood, so a misheard request is caught before it runs.

The yes/no answer is read by ovos-workshop's `ask_yesno`, which handles each language's ways of saying yes and no.
If nothing is heard, it asks once more before giving up. The held request lives only in the handler, for that one
question; a "yes" said later is an ordinary utterance and runs nothing.

Doublecheck registers no intents, so no matcher can route to it by accident. The only way in is a dispatch to
`ovos-skill-doublecheck.oscillatelabsllc:confirm`. It emits `doublecheck.confirmed` or `doublecheck.cancelled` on
the bus for anything that wants to observe.

## Install

```sh
pip install git+https://github.com/OscillateLabsLLC/doublecheck
```

Then set `high_risk` to `"confirm"` in Switchboard's `intents.switchboard` config section.

Python 3.11-3.14. Works with ovos-workshop 0.x and current OVOS (9.x).

## Languages

English (`en-us`). Another language needs two dialog files in `ovos_skill_doublecheck/locale/<lang>/dialog/`:
`confirm.dialog` (with `{utterance}`) and `cancelled.dialog`.

## License

Apache-2.0
