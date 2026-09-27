"""Real-data compatibility test for CharacterBox's character-side round flow."""

from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from agents.character import Character
from dataloader.context_priorities import load_validated_priority_config
from dataloader.data import Data
from dataloader.research_sidecar import load_validated_sidecar
from utils.character import SceneInfo


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HARRY_POTTER_DATA = (
    REPOSITORY_ROOT / "data" / "generated_data" / "Harry_Potter.json"
)
PILOT_SIDECAR = (
    REPOSITORY_ROOT
    / "data"
    / "research_annotations"
    / "characterbox_pilot.json"
)
PRIORITY_CONFIG = REPOSITORY_ROOT / "config" / "context_priorities.json"


class FakeLLM:
    """Provides CharacterBox's prompt-token count without a model call."""

    def get_num_tokens(self, prompt):
        return len(prompt.split())


class FakeMemory:
    """Provides CharacterBox's memory keys and records saved actions."""

    most_recent_memories_token_key = "recent_memories_token"
    add_memory_key = "add_memory"
    now_key = "now"

    def __init__(self):
        self.saved_contexts = []

    def save_context(self, inputs, outputs):
        self.saved_contexts.append((inputs, outputs))


class SequentialFakeChain:
    """Returns deterministic responses in CharacterBox simulator call order."""

    def __init__(self, responses, most_recent_memories=""):
        self.responses = iter(responses)
        self.most_recent_memories = most_recent_memories
        self.inputs = []

    def invoke(self, input):
        self.inputs.append(input)
        return {
            "most_recent_memories": self.most_recent_memories,
            "text": next(self.responses),
        }


class CharacterBoxRealSceneFlowTests(TestCase):
    def test_characterbox_pilot_renders_same_source_values_for_u_s_and_p(self):
        pilot = load_validated_sidecar(PILOT_SIDECAR)
        trial = pilot["trials"][0]
        data = Data(
            {
                "scene_path": str(HARRY_POTTER_DATA),
                "scene_id": pilot["scene_id"],
            },
            logger=None,
        )
        scene = data.scenes[pilot["scene_id"]]
        player_info = data.characters[pilot["player_character_id"]]
        character_info = data.characters[pilot["target_character_id"]]
        selected_action = next(
            action
            for action in data.init_actions
            if action["action_id"] == pilot["action_id"]
        )
        # Controlled trials seed no memory: every character starts with a
        # fresh, empty memory store, so Recent Memory is empty in every
        # condition (still equal across U/S/P, just not a non-empty value).
        recent_memory = ""
        priority_policy = load_validated_priority_config(PRIORITY_CONFIG)[
            "policies"
        ][0]
        player_observation = (
            f"{player_info.name}:{trial['turns'][0]['player_dialogue']}"
        )
        prompts = {}

        for condition in ("U", "S", "P"):
            chain = SequentialFakeChain(
                ["Neville Longbottom: We should still speak quietly."],
                most_recent_memories=recent_memory,
            )
            character = Character.construct(
                id=character_info.id,
                name=character_info.name,
                traits=character_info.description,
                position=character_info.position,
                status="",
                states=character_info.states,
                scene=SceneInfo(**scene),
                self_belief="",
                env_belief="",
                llm=FakeLLM(),
                memory=FakeMemory(),
                all_actions=[],
            )
            with patch.object(Character, "chain", return_value=chain):
                character.generate_dialogue(
                    observation=player_observation,
                    plot=selected_action["action"],
                    now=datetime(2026, 8, 8, 12, 0, 0),
                    context_condition=condition,
                    priority_policy=(priority_policy if condition == "P" else None),
                )
            prompts[condition] = character.all_actions[0]["prompt"]

        source_values = (
            scene["event"],
            scene["time"],
            scene["location"],
            scene["description"],
            character_info.name,
            character_info.description,
            character_info.position,
            character_info.states,
            player_observation,
            selected_action["action"],
        )
        for prompt in prompts.values():
            for source_value in source_values:
                self.assertIn(source_value, prompt)

        self.assertNotIn("Event:", prompts["U"])
        self.assertIn("Event: " + scene["event"], prompts["S"])
        self.assertIn("Priority 1 — current_world_constraints", prompts["P"])
        self.assertIn("Priority 3 — character_guidance", prompts["P"])
        self.assertLess(
            prompts["P"].index("Priority 3 — character_guidance"),
            prompts["P"].index("Action Reference: " + selected_action["action"]),
        )

    def test_real_scene_follows_characterbox_character_side_round_flow(self):
        data = Data(
            {"scene_path": str(HARRY_POTTER_DATA), "scene_id": 0},
            logger=None,
        )
        initial_history = "".join(
            action["character"]
            + ":"
            + action["action"]
            + ";"
            + action["character"]
            + ":"
            + action["dialogue"]
            + "\n"
            for action in data.init_actions
        )
        mr_dursley = data.characters[0]
        memory = FakeMemory()
        chain = SequentialFakeChain(
            [
                "I value normality and want these strange events to stop.",
                "The street feels increasingly unusual and unsettling.",
                (
                    "Mr. Dursley: Inspect the garden wall for the strange cat.\n"
                    "The Cat: Remain still and observe Mr. Dursley.\n"
                    "The Cloaked Man: Approach the corner of Privet Drive."
                ),
                "Mr. Dursley: He cautiously approaches the garden wall.",
                "Mr. Dursley: Shoo! Get away from there!\nIgnored second line.",
            ]
        )
        character = Character.construct(
            id=mr_dursley.id,
            name=mr_dursley.name,
            traits=mr_dursley.description,
            position=mr_dursley.position,
            status="",
            states=mr_dursley.states,
            scene=SceneInfo(**data.scenes[0]),
            self_belief="",
            env_belief="",
            llm=FakeLLM(),
            memory=memory,
            all_actions=[],
        )
        now = datetime(2026, 8, 8, 8, 0, 0)
        character_names = [item.name for item in data.characters_list]
        other_characters = [
            item for item in data.characters_list if item.id != character.id
        ]

        with patch.object(Character, "chain", return_value=chain), patch(
            "builtins.print"
        ):
            self_belief = character.update_self_belief(initial_history, now)
            env_belief = character.update_env_belief(
                initial_history,
                other_characters,
                now,
            )
            synopsis = character.generate_synopsis(
                initial_history,
                character_names,
                [],
                now,
            )
            action_reference = synopsis[character.name]
            action, action_detail = character.take_action(
                initial_history,
                action_reference,
                now,
            )
            dialogue, dialogue_detail = character.generate_dialogue(
                action,
                action_reference,
                now,
            )

        self.assertTrue(
            initial_history.startswith(
                "Mr. Dursley:Notices the cat reading a map and tries to shoo "
                "it away;Mr. Dursley:None\n"
            )
        )
        self.assertEqual(
            self_belief,
            "I value normality and want these strange events to stop.",
        )
        self.assertEqual(
            env_belief,
            "The street feels increasingly unusual and unsettling.",
        )
        self.assertEqual(
            action_reference,
            "Inspect the garden wall for the strange cat.",
        )
        self.assertEqual(action, " He cautiously approaches the garden wall.")
        self.assertEqual(dialogue, "Shoo! Get away from there!")

        synopsis_input = chain.inputs[2]
        self.assertEqual(synopsis_input["actions"], initial_history)
        self.assertEqual(synopsis_input["sequence"], character_names)
        self.assertEqual(synopsis_input["history"], [])

        action_prompt = character.all_actions[2]["prompt"]
        dialogue_prompt = character.all_actions[3]["prompt"]
        for prompt in (action_prompt, dialogue_prompt):
            self.assertIn("Event: An Unusual Encounter on Privet Drive", prompt)
            self.assertIn("Name: Mr. Dursley", prompt)
            self.assertIn(
                "Character Description: A robust man with a minimal neck",
                prompt,
            )
            self.assertIn(
                "Action Reference: Inspect the garden wall for the strange cat.",
                prompt,
            )

        self.assertIn("Observation: " + initial_history, action_prompt)
        self.assertIn(
            "Observation:  He cautiously approaches the garden wall.",
            dialogue_prompt,
        )
        self.assertEqual(
            action_detail["text"],
            "Mr. Dursley: He cautiously approaches the garden wall.",
        )
        self.assertEqual(
            dialogue_detail["text"],
            "Mr. Dursley: Shoo! Get away from there!\nIgnored second line.",
        )
        self.assertEqual(
            [saved[1]["add_memory"] for saved in memory.saved_contexts],
            [
                "Mr. Dursley: He cautiously approaches the garden wall.",
                "Mr. Dursley: Shoo! Get away from there!",
            ],
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
