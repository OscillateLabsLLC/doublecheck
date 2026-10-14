"""Doublecheck: ask before running a high-risk request that Switchboard held.

With ``high_risk: "confirm"``, Switchboard dispatches a high-risk request ("unlock the front door") here instead of
to its skill. Doublecheck repeats the request back in the user's own words and asks whether to go ahead. On a clear
yes it replays exactly the held intent, as ovos-core would have dispatched it; anything else runs nothing.

Doublecheck registers no intents, so no matcher can route to it by accident; the only way in is a dispatch to
``<skill_id>:confirm``. The held request lives only in the handler, for one question.

In a language it has no dialogs for, Doublecheck asks nothing and runs nothing: Switchboard's silent hold.
"""

import copy
import inspect
from pathlib import Path

from ovos_bus_client.message import Message
from ovos_workshop.skills.ovos import OVOSSkill


class DoublecheckSkill(OVOSSkill):
    """Receives Switchboard's held high-risk requests: asks, and replays the request only on yes."""
    # Interface contract with Switchboard, not user settings: changing either on one side alone breaks routing.
    CONFIRM_INTENT = "confirm"
    HELD_KEYS = frozenset({"held_intent", "held_label", "held_match_data"})
    CONFIRMED_EVENT = "doublecheck.confirmed"
    CANCELLED_EVENT = "doublecheck.cancelled"
    LOCALE = Path(__file__).parent / "locale"

    def initialize(self):
        # ovos-workshop >= 8 reports intent_name in the done-signal; Neon Hub's 0.1.7 has no such parameter.
        extra = {"intent_name": self.CONFIRM_INTENT} \
            if "intent_name" in inspect.signature(self.add_event).parameters else {}
        self.add_event(f"{self.skill_id}:{self.CONFIRM_INTENT}", self.handle_confirm,
                       handler_info="mycroft.skill.handler", activation=False, speak_errors=False, **extra)

    @classmethod
    def held_dispatch(cls, message: Message) -> Message:
        """The message ovos-core would have dispatched for the held intent: the original utterance's data and
        context (both arrive with Switchboard's dispatch here), the held match data, and the held skill's id."""
        label = message.data["held_label"]
        data = {k: v for k, v in message.data.items() if k not in cls.HELD_KEYS}
        data.update(message.data.get("held_match_data") or {})
        context = copy.deepcopy(message.context)
        context["skill_id"] = label.split(":", 1)[0]
        return Message(label, data, context)

    @classmethod
    def speaks(cls, lang: str) -> bool:
        """Whether Doublecheck has the question in this language. Checked against its own locale directory, not
        ovos-workshop's lookup: workshop 0.x and 8 fall back to English for any language, 9 to nothing."""
        primary = lang.split("-")[0].lower()
        return any(d.name.split("-")[0].lower() == primary and (d / "dialog" / "confirm.dialog").is_file()
                   for d in cls.LOCALE.iterdir())

    def handle_confirm(self, message: Message):
        """Ask once; replay the held request on yes, otherwise say so and run nothing."""
        if not message.data.get("held_label"):
            self.log.error("no held_label in %s: nothing to confirm", message.data)
            return
        dispatch = self.held_dispatch(message)  # fixed before asking: the answer can't change what runs
        utterance = message.data.get("utterance", "")
        lang = message.data.get("lang") or self.lang
        if not self.speaks(lang):
            self.log.warning("no %s dialogs: holding %r -> %s without asking", lang, utterance, dispatch.msg_type)
            self.bus.emit(message.forward(self.CANCELLED_EVENT, {"utterance": utterance, "held_label":
                                                                 dispatch.msg_type, "answer": None, "lang": lang}))
            return
        answer = self.ask_yesno("confirm", {"utterance": utterance})
        record = {"utterance": utterance, "held_label": dispatch.msg_type, "answer": answer, "lang": lang}
        if answer == "yes":
            self.log.info("confirmed: %r -> %s", utterance, dispatch.msg_type)
            self.bus.emit(message.forward(self.CONFIRMED_EVENT, record))
            self.bus.emit(dispatch)
            return
        self.log.info("not confirmed (%r): %r -> %s", answer, utterance, dispatch.msg_type)
        self.speak_dialog("cancelled")
        self.bus.emit(message.forward(self.CANCELLED_EVENT, record))
