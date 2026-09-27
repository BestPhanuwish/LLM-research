from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from agents.character import Character
from dataloader.context_priorities import load_validated_priority_config
from utils.character import SceneInfo


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PRIORITY_CONFIG = REPOSITORY_ROOT / "config" / "context_priorities.json"


class FakeLLM:
    """Provides only the token-count method used by CharacterBox here."""

    def __init__(self):
        self.counted_prompt = None

    def get_num_tokens(self, prompt):
        self.counted_prompt = prompt
        return 137


class FakeMemory:
    """Uses CharacterBox's memory keys without retrieval or an API call."""

    most_recent_memories_token_key = "recent_memories_token"
    add_memory_key = "add_memory"
    now_key = "now"

    def __init__(self):
        self.saved_contexts = []

    def save_context(self, inputs, outputs):
        self.saved_contexts.append((inputs, outputs))


class FakeChain:
    """Returns a fixed memory value and model response."""

    def __init__(self, text="Mira: I have not seen him today.\nIgnored second line."):
        self.inputs = []
        self.text = text

    def invoke(self, input):
        self.inputs.append(input)
        return {
            "most_recent_memories": (
                "Yesterday, Mira saw Rowan leave through the eastern gate."
            ),
            "text": self.text,
        }


class CharacterBoxStructuredResponseTests(TestCase):
    def _make_character(self):
        scene = SceneInfo(
            id=0,
            event="A visitor questions the gatekeeper",
            time="Early evening",
            location="The eastern gate",
            description="Rain falls while the city gates are closing.",
            plot="Mira remains at her assigned post.",
        )
        llm = FakeLLM()
        memory = FakeMemory()
        chain = FakeChain()
        character = Character.construct(
            id=0,
            name="Mira",
            traits="Mira is a cautious and observant city guard.",
            position="Beside the eastern gate lever.",
            status="",
            states="Alert but tired.",
            scene=scene,
            self_belief="I must keep the gate secure until nightfall.",
            env_belief="The visitor appears worried but not dangerous.",
            llm=llm,
            memory=memory,
            all_actions=[],
        )
        return character, llm, memory, chain

    def _generate_for_condition(self, condition, priority_policy=None):
        character, llm, memory, chain = self._make_character()
        now = datetime(2026, 8, 8, 18, 0, 0)
        with patch.object(Character, "chain", return_value=chain):
            response, detail = character.generate_dialogue(
                observation='Player says: "Have you seen Rowan?"',
                plot="Mira should answer while continuing to guard the gate.",
                now=now,
                context_condition=condition,
                priority_policy=priority_policy,
            )
        return character, llm, memory, chain, response, detail

    def test_generate_dialogue_preserves_characterbox_english_prompt(self):
        scene = SceneInfo(
            id=0,
            event="A visitor questions the gatekeeper",
            time="Early evening",
            location="The eastern gate",
            description="Rain falls while the city gates are closing.",
            plot="Mira remains at her assigned post.",
        )
        llm = FakeLLM()
        memory = FakeMemory()
        chain = FakeChain()
        character = Character.construct(
            id=0,
            name="Mira",
            traits="Mira is a cautious and observant city guard.",
            position="Beside the eastern gate lever.",
            status="",
            states="Alert but tired.",
            scene=scene,
            self_belief="I must keep the gate secure until nightfall.",
            env_belief="The visitor appears worried but not dangerous.",
            llm=llm,
            memory=memory,
            all_actions=[],
        )
        observation = 'Player says: "Have you seen Rowan?"'
        action_reference = "Mira should answer while continuing to guard the gate."
        now = datetime(2026, 8, 8, 18, 0, 0)

        with patch.object(Character, "chain", return_value=chain):
            response, detail = character.generate_dialogue(
                observation=observation,
                plot=action_reference,
                now=now,
            )

        expected_prompt = (
            "Please act as Mira  and respond using the tone, manner and vocabulary "
            "Mira would use.\n The context and Mira's information is as follows:\n"
            "Event: A visitor questions the gatekeeper\n"
            "Time: Early evening\n"
            "Location: The eastern gate\n"
            "Description: Rain falls while the city gates are closing.\n"
            "Character Profile:\n"
            "Name: Mira\n"
            "Character Description: Mira is a cautious and observant city guard.\n"
            "Position: Beside the eastern gate lever.\n"
            "Current State: Alert but tired.\n"
            "Self Belief: I must keep the gate secure until nightfall.\n"
            "Environment Belief: The visitor appears worried but not dangerous.\n"
            "Recent Memory(Ordered in reverse chronological order): "
            "Yesterday, Mira saw Rowan leave through the eastern gate.\n"
            'Observation: Player says: "Have you seen Rowan?"\n'
            "Action Reference: Mira should answer while continuing to guard the gate.\n"
            "Based on the provided character profile, current action reference, and "
            "observation, describe a line Mira might say at this moment. Consider "
            "Mira's personality, observation, the characters in the story, and recent "
            "memories to determine the tone and content of the dialogue. The line Mira "
            "says at this moment should align with the character profile and behavioral "
            "traits, ensuring it is closely related to the current environment and "
            "observation, and distinct from the content in recent memories.\n"
        )

        self.assertEqual(character.all_actions[0]["prompt"], expected_prompt)
        self.assertEqual(response, "I have not seen him today.")
        self.assertEqual(detail["text"], "Mira: I have not seen him today.\nIgnored second line.")
        self.assertEqual(chain.inputs[0]["recent_memories_token"], 137)
        self.assertEqual(
            memory.saved_contexts,
            [
                (
                    {},
                    {
                        "add_memory": "Mira: I have not seen him today.",
                        "now": now,
                    },
                )
            ],
        )
        self.assertNotIn(
            "Yesterday, Mira saw Rowan leave through the eastern gate.",
            llm.counted_prompt,
        )

    def test_dialogue_cleanup_extracts_speech_after_stage_direction(self):
        character, _, memory, _ = self._make_character()
        chain = FakeChain(
            "*Mira watches the gate, then answers:*\n\n"
            "\u201cRowan left before sunset.\u201d\n\n"
            "*She lowers her voice.* \"He used the eastern road.\""
        )
        now = datetime(2026, 8, 8, 18, 0, 0)

        with patch.object(Character, "chain", return_value=chain):
            response, detail = character.generate_dialogue(
                observation="The visitor asks again.",
                plot="Mira should answer the visitor.",
                now=now,
            )

        self.assertEqual(
            "Rowan left before sunset. He used the eastern road.",
            response,
        )
        self.assertEqual(chain.text, detail["text"])
        self.assertEqual(
            "Mira: Rowan left before sunset. He used the eastern road.",
            memory.saved_contexts[0][1]["add_memory"],
        )

    def test_unstructured_condition_changes_only_prompt_rendering(self):
        character, _, memory, chain, response, detail = (
            self._generate_for_condition("U")
        )
        prompt = character.all_actions[0]["prompt"]

        self.assertNotIn("Event:", prompt)
        self.assertNotIn("Character Profile:", prompt)
        self.assertNotIn("Action Reference:", prompt)
        self.assertNotIn("Priority 1", prompt)
        for value in (
            "A visitor questions the gatekeeper",
            "Early evening",
            "The eastern gate",
            "Rain falls while the city gates are closing.",
            "Mira is a cautious and observant city guard.",
            "Beside the eastern gate lever.",
            "Alert but tired.",
            "I must keep the gate secure until nightfall.",
            "The visitor appears worried but not dangerous.",
            "Yesterday, Mira saw Rowan leave through the eastern gate.",
            'Player says: "Have you seen Rowan?"',
            "Mira should answer while continuing to guard the gate.",
        ):
            self.assertIn(value, prompt)
        self.assertEqual(response, "I have not seen him today.")
        self.assertEqual(
            detail["text"],
            "Mira: I have not seen him today.\nIgnored second line.",
        )
        self.assertEqual(1, len(chain.inputs))
        self.assertEqual(
            memory.saved_contexts[0][1]["add_memory"],
            "Mira: I have not seen him today.",
        )

    def test_prioritised_condition_uses_validated_four_level_policy(self):
        config = load_validated_priority_config(PRIORITY_CONFIG)
        policy = config["policies"][0]
        character, _, memory, _, response, _ = self._generate_for_condition(
            "P",
            priority_policy=policy,
        )
        prompt = character.all_actions[0]["prompt"]

        headings = [
            "Priority 1 — current_world_constraints",
            "Priority 2 — world_background",
            "Priority 3 — character_guidance",
            "Priority 4 — conditional_memory",
        ]
        heading_positions = [prompt.index(item) for item in headings]
        self.assertEqual(sorted(heading_positions), heading_positions)
        self.assertIn(
            "Use all relevant context when it is compatible. If context conflicts, "
            "follow the lower priority number.",
            prompt,
        )
        self.assertIn("Location: The eastern gate", prompt)
        self.assertIn("Description: Rain falls while the city gates are closing.", prompt)
        self.assertIn("Character Description: Mira is a cautious", prompt)
        self.assertIn(
            "Recent Memory: Yesterday, Mira saw Rowan leave through the eastern gate.",
            prompt,
        )
        self.assertIn(
            "Action Reference: Mira should answer while continuing to guard the gate.",
            prompt,
        )
        action_position = prompt.index("Action Reference:")
        self.assertGreater(action_position, heading_positions[2])
        self.assertLess(action_position, heading_positions[3])
        self.assertEqual(response, "I have not seen him today.")
        self.assertEqual(memory.saved_contexts[0][1]["add_memory"], "Mira: I have not seen him today.")

    def test_unknown_context_condition_is_rejected(self):
        character, _, _, _ = self._make_character()

        with self.assertRaisesRegex(ValueError, "expected U, S, or P"):
            character.generate_dialogue(
                observation="Player says hello.",
                plot="Mira remains at the gate.",
                now=datetime(2026, 8, 8, 18, 0, 0),
                context_condition="X",
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
