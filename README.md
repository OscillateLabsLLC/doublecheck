# Doublecheck

An OVOS skill that asks before running a high-risk request [Switchboard](https://github.com/OscillateLabsLLC/switchboard) held.

Some requests shouldn't run on a misheard word: unlocking a door, opening the garage, shutting down, clearing data.
Switchboard never acts on these directly, and no confidence threshold makes them safe: wrong high-risk picks have
reached 0.994 confidence in benchmarks. With Switchboard's `high_risk: "confirm"`, a held request is dispatched to Doublecheck,
which:

- **repeats it back in the user's own words** and asks: "I think you said: unlock the front door. Should I do that?",
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

The languages most OVOS skills ship: Basque, Catalan, Danish, Dutch, English, French, Galician, German, Italian,
Persian, Polish, Portuguese (European and Brazilian), Russian, Spanish and Swedish. Regional variants use their
language's dialogs (`en-GB` uses `en-US`).

Doublecheck only asks when it can be answered. Before asking, it checks two things:

- it has the question in the user's language, and
- OVOS's yes/no engine reads that language's plain yes (`vocab/yes.voc`) as yes.

Otherwise it asks nothing and runs nothing, the same as Switchboard's silent hold, and logs a warning. As of
ovos-yes-no-plugin 0.4, that holds **Galician** (the parser has no Galician yet) and **Italian** (its yes words
are capitalized, so no lowercase answer ever matches). Both start asking as soon as the parser can read them. On
ovos-workshop 0.x and 8, which parse yes/no differently, the engine check is skipped.

Kabyle, also widely shipped in OVOS, is missing: it needs a native speaker. Adding a language means three files
in `ovos_skill_doublecheck/locale/<lang>/`: `dialog/confirm.dialog` (with `{utterance}`), `dialog/cancelled.dialog`
and `vocab/yes.voc`. The dialogs other than English were written by a non-native speaker; corrections are welcome.

## License

Apache-2.0
