import time

import pytest
from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from ovos_skill_doublecheck import DoublecheckSkill


SKILL_ID = "ovos-skill-doublecheck.oscillatelabsllc"
CONFIRM_TOPIC = f"{SKILL_ID}:{DoublecheckSkill.CONFIRM_INTENT}"
HA = "skill-homeassistant.oscillatelabsllc"
HELD_LABEL = f"{HA}:unlock"
SESSION = {"session_id": "default", "lang": "en-us"}


@pytest.fixture(name="skill")
def skill_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    s = DoublecheckSkill(skill_id=SKILL_ID, bus=FakeBus())
    yield s
    s.shutdown()


def answer_with(skill, answer):
    """Stand in for the spoken answer; ask_yesno itself is ovos-workshop's."""
    asked = []
    skill.ask_yesno = lambda prompt, data=None: asked.append((prompt, data)) or answer
    return asked


def collect(bus, *topics):
    seen = {t: [] for t in topics}
    for t in topics:
        bus.on(t, lambda m, t=t: seen[t].append(m))
    return seen


def wait_for(seen, topic, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline and not seen[topic]:
        time.sleep(0.05)


def switchboard_dispatch(skill, **held):
    """What ovos-core sends Doublecheck for Switchboard's match: the original utterance message's data and context,
    merged with the match data."""
    data = {"utterances": ["unlock the front door"], "lang": "en-us", "utterance": "unlock the front door",
            "held_intent": "lock.unlock", "held_label": HELD_LABEL, "held_match_data": {"entity": "front door"},
            **held}
    context = {"session": SESSION, "source": "audio", "destination": "skills", "skill_id": SKILL_ID,
               "pipeline_id": "ovos-switchboard-exact-pipeline-plugin"}
    skill.bus.emit(Message(CONFIRM_TOPIC, data, context))


def test_yes_replays_exactly_the_held_dispatch(skill):
    asked = answer_with(skill, "yes")
    seen = collect(skill.bus, HELD_LABEL, "speak", DoublecheckSkill.CONFIRMED_EVENT, "mycroft.skill.handler.complete")
    switchboard_dispatch(skill)
    wait_for(seen, "mycroft.skill.handler.complete")
    assert asked == [("confirm", {"utterance": "unlock the front door"})]
    replay = seen[HELD_LABEL][0]
    assert replay.data == {"utterances": ["unlock the front door"], "lang": "en-us",
                           "utterance": "unlock the front door", "entity": "front door"}
    assert replay.context == {"session": SESSION, "source": "audio", "destination": "skills", "skill_id": HA,
                              "pipeline_id": "ovos-switchboard-exact-pipeline-plugin"}
    assert seen[DoublecheckSkill.CONFIRMED_EVENT][0].data["held_label"] == HELD_LABEL
    assert not seen["speak"], "on yes the held skill does the talking"


@pytest.mark.parametrize("answer", ["no", None, "maybe later"])
def test_anything_but_yes_runs_nothing(skill, answer):
    answer_with(skill, answer)
    seen = collect(skill.bus, HELD_LABEL, "speak", DoublecheckSkill.CANCELLED_EVENT, "mycroft.skill.handler.complete")
    switchboard_dispatch(skill)
    wait_for(seen, "mycroft.skill.handler.complete")
    assert not seen[HELD_LABEL]
    assert [m.data["utterance"] for m in seen["speak"]] == ["OK, I won't."]
    assert seen[DoublecheckSkill.CANCELLED_EVENT][0].data["answer"] == answer


def held_silently(skill, lang):
    asked = answer_with(skill, "yes")
    seen = collect(skill.bus, HELD_LABEL, "speak", DoublecheckSkill.CANCELLED_EVENT, "mycroft.skill.handler.complete")
    switchboard_dispatch(skill, lang=lang)
    wait_for(seen, "mycroft.skill.handler.complete")
    return asked == [] and not seen[HELD_LABEL] and not seen["speak"] and \
        seen[DoublecheckSkill.CANCELLED_EVENT][0].data["lang"] == lang


def test_a_language_without_dialogs_holds_silently(skill):
    """Workshop would speak the English question to a Japanese speaker (0.x, 8) or nothing usable (9)."""
    assert held_silently(skill, "ja-JP")


class StubEngine:
    """Stands in for OVOS's configured yes/no engine (ovos-workshop 9's _get_yesno_engine)."""
    def __init__(self, reads):
        self.reads = reads

    def yes_or_no(self, question, response, lang):  # pylint: disable=unused-argument
        if isinstance(self.reads, Exception):
            raise self.reads
        return self.reads


@pytest.mark.parametrize("reads", [None, False, ValueError("Unsupported language: 'gl-ES'")])
def test_a_language_ovos_cant_read_a_yes_in_holds_silently(skill, reads):
    """Live: OVOS's parser has no Galician, and never matches an Italian yes (capitalized word list)."""
    skill._get_yesno_engine = lambda: StubEngine(reads)  # pylint: disable=protected-access
    assert held_silently(skill, "gl-ES")


def test_understands_asks_the_engine_with_the_languages_own_yes(skill):
    heard = []
    engine = StubEngine(True)
    engine.yes_or_no = lambda question, response, lang: heard.append((response, lang)) or True
    skill._get_yesno_engine = lambda: engine  # pylint: disable=protected-access
    assert skill.understands("pt-BR") and heard == [("sim", "pt-BR")]


def test_without_an_engine_to_ask_every_spoken_language_is_trusted(skill):
    if hasattr(skill, "_get_yesno_engine"):
        pytest.skip("this ovos-workshop has the engine")
    assert skill.understands("gl-ES")


def test_a_regional_variant_uses_its_languages_dialogs(skill):
    asked = answer_with(skill, "no")
    seen = collect(skill.bus, "mycroft.skill.handler.complete")
    switchboard_dispatch(skill, lang="en-GB")
    wait_for(seen, "mycroft.skill.handler.complete")
    assert asked == [("confirm", {"utterance": "unlock the front door"})]


@pytest.mark.parametrize("lang, speaks", [("en-us", True), ("en-US", True), ("en-gb", True), ("ca-es", True),
                                          ("fr-FR", True), ("fr-ca", True), ("gl-es", True), ("de-de", True),
                                          ("de-at", True), ("ja-jp", False), ("kab-dz", False)])
def test_speaks_checks_its_own_locale(lang, speaks):
    assert DoublecheckSkill.speaks(lang) is speaks


@pytest.mark.parametrize("lang, folder", [("pt-PT", "pt-PT"), ("pt-br", "pt-BR"), ("pt-AO", "pt-BR"),
                                          ("en-GB", "en-US")])
def test_the_exact_tag_wins_then_the_language(lang, folder):
    assert DoublecheckSkill.locale_for(lang).name in ({folder} if lang != "pt-AO" else {"pt-PT", "pt-BR"})


LOCALES = sorted(d.name for d in DoublecheckSkill.LOCALE.iterdir())


def test_every_language_ships_both_lines_and_a_yes():
    for name in LOCALES:
        for f in ("dialog/confirm.dialog", "dialog/cancelled.dialog", "vocab/yes.voc"):
            assert (DoublecheckSkill.LOCALE / name / f).read_text(encoding="utf-8").strip(), f"{name}/{f}"


@pytest.mark.parametrize("lang", LOCALES)
def test_the_question_quotes_the_user(skill, lang):
    renderer = skill.load_lang(lang=lang).dialog_renderer
    question = renderer.render("confirm", {"utterance": "unlock the front door"})
    assert "unlock the front door" in question and "{" not in question
    assert renderer.render("cancelled", {}) not in ("", "cancelled")


def test_the_english_wording():
    english = DoublecheckSkill.LOCALE / "en-US" / "dialog"
    assert (english / "confirm.dialog").read_text().strip() == "I think you said: {utterance}. Should I do that?"
    assert (english / "cancelled.dialog").read_text().strip() == "OK, I won't."


def test_a_dispatch_without_a_held_label_asks_nothing(skill):
    asked = answer_with(skill, "yes")
    seen = collect(skill.bus, "mycroft.skill.handler.complete")
    switchboard_dispatch(skill, held_label=None)
    wait_for(seen, "mycroft.skill.handler.complete")
    assert asked == []


def test_registers_no_intents(skill):
    assert not skill.intent_service.registered_intents
