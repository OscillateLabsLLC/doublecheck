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


def test_the_question_quotes_the_user(skill):
    assert skill.dialog_renderer.render("confirm", {"utterance": "unlock the front door"}) == \
        "I think you said: unlock the front door. Should I do that?"


def test_a_dispatch_without_a_held_label_asks_nothing(skill):
    asked = answer_with(skill, "yes")
    seen = collect(skill.bus, "mycroft.skill.handler.complete")
    switchboard_dispatch(skill, held_label=None)
    wait_for(seen, "mycroft.skill.handler.complete")
    assert asked == []


def test_registers_no_intents(skill):
    assert not skill.intent_service.registered_intents
