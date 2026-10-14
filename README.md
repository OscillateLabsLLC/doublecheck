# Doublecheck

An OVOS skill that asks before a risky request runs. It works with
[Switchboard](https://github.com/OscillateLabsLLC/switchboard).

Some requests shouldn't run on a misheard word: unlocking a door, opening the garage, shutting down, clearing data.
Switchboard never runs these directly. With Doublecheck installed and Switchboard's `high_risk` set to `"confirm"`,
it hands them to Doublecheck, which:

- **repeats what it heard** and asks: "I think you said: unlock the front door. Should I do that?"
- **on a clear yes**, runs exactly that request, as if it had gone straight to the skill;
- **on anything else** (no, silence, an unclear answer) says "OK, I won't" and runs nothing.

Repeating the user's own words means no special wording is needed for each request, and if the assistant misheard,
the user hears the mistake before anything happens.

The request is kept only for that one question. A "yes" said later runs nothing.

## Install

```sh
pip install ovos-skill-doublecheck
```

Then set `"high_risk": "confirm"` under `intents.switchboard` in `mycroft.conf`.

Python 3.11-3.14. Works with ovos-workshop 0.x (Neon) and current OVOS.

## Languages

Basque, Catalan, Danish, Dutch, English, French, Galician, German, Italian, Persian, Polish, Portuguese (European
and Brazilian), Russian, Spanish and Swedish: the languages most OVOS skills ship. Regional variants use their
language's version (`en-GB` uses `en-US`).

Doublecheck only asks a question that can be answered. If it has no question in the user's language, or OVOS
can't understand a "yes" in it, Doublecheck asks nothing and runs nothing (the request is simply held) and logs a
warning. Today that applies to Galician and Italian, until fixes to OVOS's yes/no parser are released
([#8](https://github.com/OpenVoiceOS/ovos-YesNo-plugin/pull/8),
[#9](https://github.com/OpenVoiceOS/ovos-YesNo-plugin/pull/9)); then they start asking on their own.

The translations were written by a non-native speaker, so corrections are welcome. Kabyle is missing and needs a
native speaker. A language is three short files in `ovos_skill_doublecheck/locale/<lang>/`: `dialog/confirm.dialog`
(with `{utterance}`), `dialog/cancelled.dialog` and `vocab/yes.voc`.

## For developers

Doublecheck registers no intents; only Switchboard sends to it (`ovos-skill-doublecheck.oscillatelabsllc:confirm`).
It announces `doublecheck.confirmed` or `doublecheck.cancelled` on the bus.

## License

Apache-2.0
