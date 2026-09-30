"""Tests for the controlled/dynamic Simulator mode switch."""

import json
import logging
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from yacs.config import CfgNode

from agents import NoScoreGenerativeAgentMemory
from agents.human_player import HumanPlayer
from langchain.retrievers import TimeWeightedVectorStoreRetriever
from langchain_core.language_models import BaseLanguageModel
from langchain_experimental.generative_agents import GenerativeAgentMemory
from simulator import (
    Simulator,
    apply_pilot_overrides,
    config_for_logging,
    run_pilot_conditions,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SimulatorModeTests(TestCase):
    def test_config_logging_redacts_provider_credentials(self):
        config = CfgNode(
            {
                "character_api_key": "character-secret",
                "narrator_api_key": "narrator-secret",
                "character_llm": "test-model",
            },
            new_allowed=True,
        )

        safe_config = config_for_logging(config)

        self.assertEqual("[REDACTED]", safe_config["character_api_key"])
        self.assertEqual("[REDACTED]", safe_config["narrator_api_key"])
        self.assertEqual("test-model", safe_config["character_llm"])
        self.assertEqual("character-secret", config["character_api_key"])

    def test_pilot_manifest_overrides_play_experiment_selectors(self):
        pilot_path = (
            REPOSITORY_ROOT
            / "data"
            / "research_annotations"
            / "characterbox_pilot.json"
        )
        pilot_config_path = REPOSITORY_ROOT / "config" / "pilot_run_config.json"
        config = CfgNode(
            {
                "scene_path": "wrong.json",
                "scene_id": 0,
                "play_role": 99,
                "dynamic_play": True,
                "target_character_id": 99,
                "action_id": 99,
                "pilot_config_path": str(pilot_config_path),
                "round": 99,
            },
            new_allowed=True,
        )

        pilot = apply_pilot_overrides(config, pilot_path)

        self.assertEqual(19, config["scene_id"])
        self.assertEqual(0, config["play_role"])
        self.assertIs(False, config["dynamic_play"])
        self.assertEqual(1, config["target_character_id"])
        self.assertEqual(1, config["action_id"])
        self.assertEqual(
            str(pilot_config_path.resolve()), config["pilot_config_path"]
        )
        self.assertTrue(config["scene_path"].endswith("Harry_Potter.json"))
        self.assertEqual(str(pilot_path.resolve()), config["research_sidecar_path"])
        self.assertEqual("cb_hp_019_luna_neville", pilot["pilot_id"])
        self.assertGreaterEqual(len(pilot["trials"]), 1)

    def test_omitted_pilot_does_not_modify_yaml_config(self):
        config = CfgNode(
            {
                "scene_path": "editable-scene.json",
                "scene_id": 7,
                "round": 4,
                "context_condition": "S",
                "research_sidecar_path": "legacy-implicit-pilot.json",
            },
            new_allowed=True,
        )

        pilot = apply_pilot_overrides(config, None)

        self.assertIsNone(pilot)
        self.assertEqual("editable-scene.json", config["scene_path"])
        self.assertEqual(7, config["scene_id"])
        self.assertEqual(4, config["round"])
        self.assertNotIn("research_sidecar_path", config)

    def test_paired_conditions_use_fresh_condition_configs(self):
        pilot_config_path = REPOSITORY_ROOT / "config" / "pilot_run_config.json"
        config = CfgNode(
            {
                "context_condition": "S",
                "marker": "unchanged",
                "pilot_config_path": str(pilot_config_path),
            },
            new_allowed=True,
        )
        pilot = {
            "pilot_id": "cb_hp_019_luna_neville",
            "trials": [
                {"trial_id": "cb_hp_019_luna_neville_t01", "turns": [{}]},
                {"trial_id": "cb_hp_019_luna_neville_t02", "turns": [{}, {}]},
            ],
        }
        created = [object() for _ in range(6)]

        with (
            patch("simulator.run_simulation", side_effect=created) as run_mock,
            patch("builtins.print") as print_mock,
        ):
            completed = run_pilot_conditions(
                config,
                logging.getLogger("paired-condition-test"),
                pilot,
            )

        self.assertEqual(created, completed)
        self.assertEqual(
            ["U", "S", "P"] * 2,
            [call.args[0]["context_condition"] for call in run_mock.call_args_list],
        )
        self.assertEqual(
            ["cb_hp_019_luna_neville_t01"] * 3 + ["cb_hp_019_luna_neville_t02"] * 3,
            [call.args[0]["trial_id"] for call in run_mock.call_args_list],
        )
        self.assertEqual(
            [1, 1, 1, 2, 2, 2],
            [call.args[0]["round"] for call in run_mock.call_args_list],
        )
        generation_run_ids = {
            call.args[0]["generation_run_id"]
            for call in run_mock.call_args_list
        }
        self.assertEqual(1, len(generation_run_ids))
        generation_run_id = generation_run_ids.pop()
        print_mock.assert_any_call(
            f"Pilot generation_run_id: {generation_run_id}"
        )
        print_mock.assert_any_call(
            f"Pilot complete. generation_run_id: {generation_run_id}"
        )
        self.assertEqual("S", config["context_condition"])
        self.assertEqual(
            6,
            len({id(call.args[0]) for call in run_mock.call_args_list}),
        )

    def test_original_config_defaults_to_dynamic_play(self):
        simulator = Simulator({}, logging.getLogger("dynamic-default-test"))

        self.assertIs(True, simulator.dynamic_play)

    def test_macos_native_runtime_guard_precedes_faiss_import(self):
        source = (REPOSITORY_ROOT / "simulator.py").read_text(encoding="utf-8")

        guard_position = source.index(
            'os.environ.setdefault("OMP_NUM_THREADS", "1")'
        )
        faiss_position = source.index("import faiss")
        self.assertLess(guard_position, faiss_position)
        self.assertIn(
            'os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")',
            source,
        )

    def test_config_can_select_controlled_play(self):
        simulator = Simulator(
            {"dynamic_play": False},
            logging.getLogger("controlled-mode-test"),
        )

        self.assertIs(False, simulator.dynamic_play)

    def _create_character_with_fake_collaborators(self, score_memories):
        simulator = Simulator(
            {"character_llm": "test-model", "scene_id": 19},
            logging.getLogger("create-character-memory-test"),
        )
        simulator.data = SimpleNamespace(
            characters={
                1: SimpleNamespace(
                    id=1,
                    name="Neville Longbottom",
                    position="Hiding behind a rock.",
                    states="Nervous.",
                    description="Brave and loyal.",
                )
            },
            scenes={
                19: {
                    "id": 19,
                    "event": "The Secret Meeting",
                    "time": "Late evening",
                    "location": "The Shrieking Shack",
                    "description": "Eerie atmosphere.",
                }
            },
        )
        fake_llm = Mock(spec=BaseLanguageModel)
        fake_retriever = Mock(spec=TimeWeightedVectorStoreRetriever)
        with (
            patch("simulator.utils.get_llm", return_value=fake_llm),
            patch.object(
                simulator, "create_new_memory_retriever", return_value=fake_retriever
            ),
        ):
            agent = simulator.create_character(
                1, "", score_memories=score_memories
            )
        return agent

    def test_controlled_character_uses_no_score_memory(self):
        agent = self._create_character_with_fake_collaborators(score_memories=False)

        self.assertIsInstance(agent.memory, NoScoreGenerativeAgentMemory)

    def test_dynamic_character_keeps_original_generative_agent_memory(self):
        agent = self._create_character_with_fake_collaborators(score_memories=True)

        self.assertIsInstance(agent.memory, GenerativeAgentMemory)
        self.assertNotIsInstance(agent.memory, NoScoreGenerativeAgentMemory)

    def _simulator_with_fake_data(self, dynamic_play):
        config = {
            "dynamic_play": dynamic_play,
            "play_role": 0,
            "character_api_key": "",
            "character_api_base": "https://example.invalid/v1",
            "narrator_api_key": "",
            "narrator_api_base": "https://example.invalid/v1",
        }
        simulator = Simulator(config, logging.getLogger("agent-routing-test"))
        simulator.data = SimpleNamespace(
            characters={
                0: SimpleNamespace(id=0, name="Luna Lovegood"),
                1: SimpleNamespace(id=1, name="Neville Longbottom"),
            },
            init_actions=[],
            role_id=-1,
        )
        simulator.create_human_player = Mock(
            return_value=SimpleNamespace(id=0, name="Luna Lovegood")
        )
        simulator.create_character = Mock(
            return_value=SimpleNamespace(id=1, name="Neville Longbottom")
        )
        simulator.create_narrator = Mock(return_value=object())
        return simulator

    def test_controlled_agents_creation_omits_narrator(self):
        simulator = self._simulator_with_fake_data(dynamic_play=False)

        with patch("simulator.tqdm", side_effect=lambda values: values):
            narrator, characters = simulator.agents_creation()

        self.assertIsNone(narrator)
        self.assertEqual([0, 1], list(characters))
        self.assertEqual({0: [""], 1: [""]}, simulator.round_obs)
        simulator.create_human_player.assert_called_once()
        simulator.create_character.assert_called_once()
        self.assertIs(False, simulator.create_character.call_args.kwargs["score_memories"])
        simulator.create_narrator.assert_not_called()

    def test_dynamic_agents_creation_preserves_narrator(self):
        simulator = self._simulator_with_fake_data(dynamic_play=True)

        with patch("simulator.tqdm", side_effect=lambda values: values):
            narrator, characters = simulator.agents_creation()

        self.assertIsNotNone(narrator)
        self.assertEqual([0, 1], list(characters))
        self.assertEqual({0: [""], 1: [""]}, simulator.round_obs)
        self.assertIs(True, simulator.create_character.call_args.kwargs["score_memories"])
        simulator.create_narrator.assert_called_once_with(
            simulator.config,
            simulator.logger,
            "",
            "https://example.invalid/v1",
        )

    def test_dynamic_round_skips_human_beliefs_and_uses_npc_synopsis(self):
        simulator = Simulator(
            {"dynamic_play": True},
            logging.getLogger("dynamic-human-round-test"),
        )
        human = SimpleNamespace(id=0, name="Luna Lovegood", scene=None)
        npc = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            scene=None,
            update_self_belief=Mock(return_value="NPC self belief"),
            update_env_belief=Mock(return_value="NPC environment belief"),
            generate_synopsis=Mock(
                return_value={
                    "Luna Lovegood": "Human turn",
                    "Neville Longbottom": "NPC turn",
                }
            ),
        )
        new_scene = SimpleNamespace(description="Updated scene")
        narrator = SimpleNamespace(
            update_scene=Mock(return_value=(new_scene, {"text": "scene"})),
            summary_plot=Mock(return_value="Round summary"),
        )
        simulator.characters = {0: human, 1: npc}
        simulator.data = SimpleNamespace(
            role_id=0,
            characters_list=[human, npc],
        )
        simulator.narrator = narrator
        simulator.plot_record = {"synopsis": [], "generated_plot": []}
        simulator.acting = OrderedDict(((0, True), (1, True)))
        simulator.acted = OrderedDict()
        simulator.one_step = Mock(return_value=[])

        messages = simulator.round()

        npc.update_self_belief.assert_called_once_with("", simulator.now)
        npc.update_env_belief.assert_called_once()
        synopsis_args = npc.generate_synopsis.call_args.args
        self.assertEqual("", synopsis_args[0])
        self.assertEqual(
            ["Luna Lovegood", "Neville Longbottom"],
            synopsis_args[1],
        )
        self.assertIs(simulator.plot_record["synopsis"], synopsis_args[2])
        self.assertEqual(simulator.now, synopsis_args[3])
        self.assertEqual(2, simulator.one_step.call_count)
        narrator.update_scene.assert_called_once_with("", verbose=True)
        narrator.summary_plot.assert_called_once_with("")
        self.assertIs(new_scene, human.scene)
        self.assertIs(new_scene, npc.scene)
        self.assertEqual([[], []], messages)

    def _load_controlled_pilot(self, condition):
        config = {
            "dynamic_play": False,
            "scene_path": str(
                REPOSITORY_ROOT / "data" / "generated_data" / "Harry_Potter.json"
            ),
            "scene_id": 19,
            "play_role": 0,
            "research_sidecar_path": str(
                REPOSITORY_ROOT
                / "data"
                / "research_annotations"
                / "characterbox_pilot.json"
            ),
            "trial_id": "cb_hp_019_luna_neville_t01",
            "context_condition": condition,
            "priority_config_path": str(
                REPOSITORY_ROOT / "config" / "context_priorities.json"
            ),
            "pilot_config_path": str(
                REPOSITORY_ROOT / "config" / "pilot_run_config.json"
            ),
            "record_dir": "unused-test-record-dir",
        }
        simulator = Simulator(config, logging.getLogger("controlled-load-test"))
        fake_characters = {
            0: SimpleNamespace(id=0, name="Luna Lovegood"),
            1: SimpleNamespace(id=1, name="Neville Longbottom"),
        }
        with patch.object(
            simulator,
            "agents_creation",
            return_value=(None, fake_characters),
        ), patch("simulator.utils.ensure_dir"):
            simulator.load_simulator()
        return simulator

    def test_controlled_load_resolves_trial_and_action_from_source(self):
        simulator = self._load_controlled_pilot("S")

        self.assertEqual(
            "cb_hp_019_luna_neville_t01",
            simulator.controlled_trial["trial_id"],
        )
        self.assertEqual(1, simulator.controlled_trial["trial_type"])
        self.assertEqual(1, simulator.controlled_target_id)
        self.assertEqual(
            "Neville whispers to Luna, reminding her to keep her voice down so "
            "as not to attract unwanted attention.",
            simulator.controlled_action_reference,
        )
        self.assertEqual("S", simulator.context_condition)
        self.assertIsNone(simulator.priority_policy)

    def test_controlled_load_resolves_priority_policy_only_for_p(self):
        simulator = self._load_controlled_pilot("P")

        self.assertEqual("P", simulator.context_condition)
        self.assertEqual(
            "primary_five_level",
            simulator.priority_policy["policy_id"],
        )

    def test_yaml_only_controlled_load_is_interactive_and_has_no_pilot(self):
        config = {
            "dynamic_play": False,
            "scene_path": str(
                REPOSITORY_ROOT / "data" / "generated_data" / "Harry_Potter.json"
            ),
            "scene_id": 19,
            "play_role": 0,
            "target_character_id": 1,
            "action_id": 1,
            "dataset_source": "characterbox_generated",
            "trial_id": None,
            "context_condition": "S",
            "priority_config_path": str(
                REPOSITORY_ROOT / "config" / "context_priorities.json"
            ),
            "priority_policy_id": "primary_four_level",
            "round": 2,
            "record_dir": "unused-test-record-dir",
        }
        simulator = Simulator(config, logging.getLogger("yaml-controlled-test"))
        fake_characters = {
            0: SimpleNamespace(id=0, name="Luna Lovegood"),
            1: SimpleNamespace(id=1, name="Neville Longbottom"),
        }

        with patch.object(
            simulator,
            "agents_creation",
            return_value=(None, fake_characters),
        ), patch("simulator.utils.ensure_dir"):
            simulator.load_simulator()

        self.assertIsNone(simulator.controlled_trial)
        self.assertEqual([], simulator.controlled_turns)
        self.assertEqual([], simulator.pilot_conditions)
        self.assertEqual(1, simulator.controlled_target_id)
        self.assertEqual("S", simulator.context_condition)
        self.assertEqual(
            "Neville whispers to Luna, reminding her to keep her voice down so "
            "as not to attract unwanted attention.",
            simulator.controlled_action_reference,
        )

    def test_controlled_round_generates_only_target_dialogue(self):
        simulator = Simulator(
            {"dynamic_play": False, "play_role": 0},
            logging.getLogger("controlled-round-test"),
        )
        player = SimpleNamespace(
            id=0,
            name="Luna Lovegood",
            take_action=Mock(
                return_value=(
                    "Luna lowers her wand",
                    {"text": "Luna lowers her wand", "source": "human"},
                )
            ),
            generate_dialogue=Mock(
                return_value=(
                    "What did you want to tell me?",
                    {
                        "text": "What did you want to tell me?",
                        "source": "human",
                    },
                )
            ),
        )
        target = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            memory=SimpleNamespace(add_memory=Mock()),
            generate_dialogue=Mock(
                return_value=(
                    "Keep your voice down.",
                    {"text": "Keep your voice down."},
                )
            ),
        )
        policy = {"policy_id": "primary_four_level", "priorities": []}
        simulator.characters = {0: player, 1: target}
        simulator.character_record = {0: [], 1: []}
        simulator.round_obs = {0: ["Initial history"], 1: ["Initial history"]}
        simulator.controlled_target_id = 1
        simulator.controlled_action_reference = "Neville should answer quietly."
        simulator.context_condition = "P"
        simulator.priority_policy = policy
        simulator.round_cnt = 1
        simulator.play()

        messages = simulator.round()

        player.take_action.assert_not_called()
        player.generate_dialogue.assert_called_once_with(
            "Initial history",
            "",
            simulator.now,
        )
        target.generate_dialogue.assert_called_once_with(
            'Luna Lovegood: "What did you want to tell me?"',
            "Neville should answer quietly.",
            simulator.now,
            context_condition="P",
            priority_policy=policy,
            remember=False,
        )
        self.assertEqual(2, len(messages))
        self.assertEqual(1, len(messages[0]))
        self.assertEqual(1, len(messages[1]))
        self.assertEqual(
            'Neville Longbottom: "Keep your voice down."',
            messages[1][0].content,
        )
        self.assertEqual(["dialogue", "dialogue"], [
            item["type"] for item in simulator.records[0]
        ])
        self.assertEqual([], simulator.round_record)
        self.assertIn("Neville Longbottom:Keep your voice down.", simulator.last_round)

    def test_controlled_round_uses_scripted_pilot_turn_without_terminal_input(self):
        simulator = Simulator(
            {"dynamic_play": False, "play_role": 0},
            logging.getLogger("controlled-scripted-turn-test"),
        )
        player = SimpleNamespace(
            id=0,
            name="Luna Lovegood",
            take_action=Mock(),
            generate_dialogue=Mock(),
        )
        target = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            memory=SimpleNamespace(add_memory=Mock()),
            generate_dialogue=Mock(
                return_value=("Keep your voice down.", {"text": "raw reply"})
            ),
        )
        simulator.characters = {0: player, 1: target}
        simulator.character_record = {0: [], 1: []}
        simulator.round_obs = {0: [], 1: []}
        simulator.controlled_target_id = 1
        simulator.controlled_action_reference = "Neville should answer quietly."
        simulator.controlled_turns = [
            {
                "round": 1,
                "player_dialogue": "What did you want to tell me?",
            }
        ]
        simulator.context_condition = "S"
        simulator.priority_policy = None
        simulator.round_cnt = 1
        simulator.play()

        simulator.round()

        player.take_action.assert_not_called()
        player.generate_dialogue.assert_not_called()
        target.generate_dialogue.assert_called_once_with(
            'Luna Lovegood: "What did you want to tell me?"',
            "Neville should answer quietly.",
            simulator.now,
            context_condition="S",
            priority_policy=None,
            remember=False,
        )
        self.assertEqual(
            ["pilot_manifest"],
            [item["detail"]["source"] for item in simulator.records[0][:1]],
        )

    def test_controlled_round_never_requests_player_action(self):
        simulator = Simulator(
            {"dynamic_play": False, "play_role": 0},
            logging.getLogger("controlled-blank-action-test"),
        )
        player = SimpleNamespace(
            id=0,
            name="Luna Lovegood",
            take_action=Mock(return_value=("", {"text": "", "source": "human"})),
            generate_dialogue=Mock(
                return_value=(
                    "What did you want to tell me?",
                    {"text": "What did you want to tell me?", "source": "human"},
                )
            ),
        )
        target = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            memory=SimpleNamespace(add_memory=Mock()),
            generate_dialogue=Mock(
                return_value=("Keep your voice down.", {"text": "reply"})
            ),
        )
        simulator.characters = {0: player, 1: target}
        simulator.character_record = {0: [], 1: []}
        simulator.round_obs = {0: [], 1: []}
        simulator.controlled_target_id = 1
        simulator.controlled_action_reference = "Neville should answer quietly."
        simulator.context_condition = "S"
        simulator.priority_policy = None
        simulator.round_cnt = 1
        simulator.play()

        messages = simulator.round()

        player.take_action.assert_not_called()
        target.generate_dialogue.assert_called_once_with(
            'Luna Lovegood: "What did you want to tell me?"',
            "Neville should answer quietly.",
            simulator.now,
            context_condition="S",
            priority_policy=None,
            remember=False,
        )
        self.assertEqual(1, len(messages[0]))
        self.assertEqual(
            ["dialogue", "dialogue"],
            [item["type"] for item in simulator.records[0]],
        )

    def test_controlled_round_reprompts_when_dialogue_is_blank(self):
        simulator = Simulator(
            {"dynamic_play": False, "play_role": 0},
            logging.getLogger("controlled-all-blank-test"),
        )
        player = SimpleNamespace(
            id=0,
            name="Luna Lovegood",
            take_action=Mock(),
            generate_dialogue=Mock(
                side_effect=[
                    ("", {"text": "", "source": "human"}),
                    ("Hello?", {"text": "Hello?", "source": "human"}),
                ]
            ),
        )
        target = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            memory=SimpleNamespace(add_memory=Mock()),
            generate_dialogue=Mock(return_value=("Hello.", {"text": "reply"})),
        )
        simulator.characters = {0: player, 1: target}
        simulator.character_record = {0: [], 1: []}
        simulator.round_obs = {0: [], 1: []}
        simulator.controlled_target_id = 1
        simulator.controlled_action_reference = "Neville should answer quietly."
        simulator.context_condition = "U"
        simulator.priority_policy = None
        simulator.round_cnt = 1
        simulator.play()

        with patch("builtins.print") as print_mock:
            messages = simulator.round()

        print_mock.assert_called_once_with("Please enter dialogue.")
        player.take_action.assert_not_called()
        self.assertEqual(2, player.generate_dialogue.call_count)
        target.generate_dialogue.assert_called_once_with(
            'Luna Lovegood: "Hello?"',
            "Neville should answer quietly.",
            simulator.now,
            context_condition="U",
            priority_policy=None,
            remember=False,
        )
        self.assertEqual(1, len(messages[0]))
        self.assertEqual(
            ["dialogue", "dialogue"],
            [item["type"] for item in simulator.records[0]],
        )

    def test_controlled_rounds_store_player_then_npc_lines_in_npc_memory(self):
        simulator = Simulator(
            {"dynamic_play": False, "play_role": 0},
            logging.getLogger("controlled-memory-order-test"),
        )
        player = SimpleNamespace(
            id=0,
            name="Luna Lovegood",
            take_action=Mock(),
            generate_dialogue=Mock(
                side_effect=[
                    ("Harry meets us at midnight.", {"text": "", "source": "human"}),
                    ("When is Harry coming?", {"text": "", "source": "human"}),
                ]
            ),
        )
        target = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            memory=SimpleNamespace(add_memory=Mock()),
            generate_dialogue=Mock(
                side_effect=[
                    ("Midnight, got it.", {"text": "Midnight, got it."}),
                    ("At midnight.", {"text": "At midnight."}),
                ]
            ),
        )
        simulator.characters = {0: player, 1: target}
        simulator.character_record = {0: [], 1: []}
        simulator.round_obs = {0: [], 1: []}
        simulator.controlled_target_id = 1
        simulator.controlled_action_reference = "Neville should answer quietly."
        simulator.context_condition = "S"
        simulator.priority_policy = None
        simulator.round_cnt = 1
        simulator.play()

        simulator.round()
        simulator.round_cnt = 2
        simulator.round()

        self.assertEqual(
            [
                "Luna Lovegood: Harry meets us at midnight.",
                "Neville Longbottom: Midnight, got it.",
                "Luna Lovegood: When is Harry coming?",
                "Neville Longbottom: At midnight.",
            ],
            [call.args[0] for call in target.memory.add_memory.call_args_list],
        )
        for call in target.generate_dialogue.call_args_list:
            self.assertFalse(call.kwargs["remember"])

    def test_controlled_second_round_reuses_previous_transcript(self):
        simulator = Simulator(
            {"dynamic_play": False, "play_role": 0},
            logging.getLogger("controlled-history-test"),
        )
        player = SimpleNamespace(
            id=0,
            name="Luna Lovegood",
            take_action=Mock(),
            generate_dialogue=Mock(
                side_effect=[
                    (
                        "Is anyone there?",
                        {"text": "Is anyone there?", "source": "human"},
                    ),
                    (
                        "What did you hear?",
                        {"text": "What did you hear?", "source": "human"},
                    ),
                ]
            ),
        )
        target = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            memory=SimpleNamespace(add_memory=Mock()),
            generate_dialogue=Mock(
                side_effect=[
                    ("First reply.", {"text": "Raw first reply."}),
                    ("Second reply.", {"text": "Raw second reply."}),
                ]
            ),
        )
        simulator.characters = {0: player, 1: target}
        simulator.character_record = {0: [], 1: []}
        simulator.round_obs = {0: [], 1: []}
        simulator.controlled_target_id = 1
        simulator.controlled_action_reference = "Neville should answer quietly."
        simulator.context_condition = "S"
        simulator.priority_policy = None
        simulator.round_cnt = 1
        simulator.play()

        simulator.round()
        simulator.round_cnt = 2
        simulator.round()

        first_observation = target.generate_dialogue.call_args_list[0].args[0]
        second_observation = target.generate_dialogue.call_args_list[1].args[0]
        self.assertEqual(
            'Luna Lovegood: "Is anyone there?"',
            first_observation,
        )
        self.assertEqual(
            "Previous interaction:\n"
            "Luna Lovegood:Is anyone there?\n"
            "Neville Longbottom:First reply.\n"
            "Current input:\n"
            'Luna Lovegood: "What did you hear?"',
            second_observation,
        )
        player.take_action.assert_not_called()

    def test_controlled_save_records_target_trace_and_condition_metadata(self):
        with TemporaryDirectory() as record_dir:
            config = {
                "dynamic_play": False,
                "scene_path": "data/generated_data/Harry_Potter.json",
                "scene_id": 19,
                "play_role": 0,
                "save_record": True,
                "record_dir": record_dir,
                "narrator_llm": "unused-narrator",
                "character_llm": "test-character",
                "plot_record_path": "plot.jsonl",
                "character_record_path": "character.jsonl",
                "round_record_path": "round.jsonl",
                "narrator_record_path": "narrator.jsonl",
                "all_record_path": "all.jsonl",
            }
            simulator = Simulator(config, logging.getLogger("controlled-save-test"))
            target_trace = {
                "character": "Neville Longbottom",
                "prompt": "Fixed prompt",
                "response": "Fixed response",
                "duration": 0.25,
            }
            simulator.data = SimpleNamespace(
                init_scene="Fixed source scene",
                init_characters="Fixed source characters",
                scenes={
                    19: {
                        "id": 19,
                        "event": "Fixed event",
                        "time": "Fixed time",
                        "location": "Fixed location",
                        "description": "Fixed description",
                    }
                },
                characters={
                    0: SimpleNamespace(
                        dict=Mock(
                            return_value={
                                "id": 0,
                                "name": "Luna Lovegood",
                                "description": "Player profile",
                            }
                        )
                    ),
                    1: SimpleNamespace(
                        dict=Mock(
                            return_value={
                                "id": 1,
                                "name": "Neville Longbottom",
                                "description": "Target profile",
                            }
                        )
                    ),
                },
                init_actions=[
                    {
                        "action_id": 0,
                        "character_id": 0,
                        "action": "Earlier action",
                        "dialogue": "Earlier dialogue",
                    }
                ],
            )
            simulator.plot_record = {"generated_plot": [], "synopsis": []}
            player_event = {
                "round": 1,
                "character_id": 0,
                "character_name": "Luna Lovegood",
                "type": "dialogue",
                "detail": {"text": "Fixed player dialogue", "source": "pilot_manifest"},
            }
            target_event = {
                "round": 1,
                "character_id": 1,
                "character_name": "Neville Longbottom",
                "type": "dialogue",
                "detail": {
                    "text": "Fixed NPC dialogue",
                    "observation": "Fixed observation",
                },
            }
            simulator.character_record = {
                0: [player_event],
                1: [target_event],
            }
            simulator.records = [[player_event, target_event]]
            simulator.narrator_record = []
            simulator.characters = {
                0: SimpleNamespace(id=0, name="Luna Lovegood"),
                1: SimpleNamespace(
                    id=1,
                    name="Neville Longbottom",
                    all_actions=[target_trace],
                    self_belief="Fixed self belief",
                    env_belief="Fixed environment belief",
                ),
            }
            simulator.controlled_target_id = 1
            simulator.controlled_trial = {
                "trial_id": "cb_hp_019_luna_neville_t01",
                "pilot_id": "cb_hp_019_luna_neville",
                "source_dataset": "../generated_data/Harry_Potter.json",
            }
            simulator.controlled_action_reference = "Fixed Action Reference"
            simulator.dataset_source = "characterbox_generated"
            simulator.pilot_conditions = ["U", "S", "P"]
            simulator.controlled_turns = [
                {"round": 1, "player_dialogue": "Fixed"}
            ]
            simulator.context_condition = "P"
            simulator.priority_policy = {
                "policy_id": "primary_four_level"
            }

            config["calculate_cost"] = False
            config["generation_run_id"] = "fixed-run-001"
            with patch("simulator.utils.calc_cost") as calc_cost:
                simulator.save_record()

            calc_cost.assert_not_called()

            base = Path(record_dir) / "Harry_Potter"
            output_name = "unused-narrator_test-character_"
            records = {}
            for folder, filename in (
                ("plot", "plot.jsonl"),
                ("character", "character.jsonl"),
                ("round", "round.jsonl"),
                ("narrator", "narrator.jsonl"),
                ("all", "all.jsonl"),
                ("trajectory", "trajectory.jsonl"),
            ):
                path = base / folder / f"{output_name}{filename}"
                records[folder] = json.loads(path.read_text(encoding="utf-8"))

            for record in records.values():
                self.assertIs(False, record["dynamic_play"])
                self.assertEqual(
                    "cb_hp_019_luna_neville_t01",
                    record["trial_id"],
                )
                self.assertEqual(
                    "cb_hp_019_luna_neville",
                    record["pilot_id"],
                )
                self.assertEqual("P", record["context_condition"])
                self.assertEqual("fixed-run-001", record["generation_run_id"])
                self.assertEqual(
                    "primary_four_level",
                    record["priority_policy_id"],
                )
                self.assertEqual("characterbox_generated", record["dataset_source"])
                self.assertEqual(0, record["player_character_id"])
                self.assertEqual(1, record["target_character_id"])
                self.assertEqual(1, record["configured_rounds"])
                self.assertEqual(["U", "S", "P"], record["pilot_conditions"])
            self.assertEqual([], records["narrator"]["record"])
            self.assertEqual([target_trace], records["all"]["record"])
            self.assertIsNone(records["all"]["total_cost"])
            trajectory = records["trajectory"]
            self.assertEqual("controlled_dialogue_trajectory", trajectory["record_type"])
            self.assertEqual("Fixed Action Reference", trajectory["action_reference"])
            self.assertEqual("Fixed player dialogue", trajectory["turns"][0]["player_dialogue"])
            self.assertEqual("Fixed NPC dialogue", trajectory["turns"][0]["npc_dialogue"])
            self.assertEqual("Fixed observation", trajectory["turns"][0]["npc_observation"])
            self.assertNotIn("recent_memory", trajectory)
            self.assertNotIn("evaluation_cases", trajectory)

    def test_blank_human_reaction_does_not_consume_dynamic_turn(self):
        simulator = Simulator(
            {"dynamic_play": True},
            logging.getLogger("blank-human-reaction-test"),
        )
        actor_memory = SimpleNamespace(add_memory=Mock())
        human_memory = SimpleNamespace(add_memory=Mock())
        actor = SimpleNamespace(
            id=1,
            name="Neville Longbottom",
            take_action=Mock(
                return_value=("Neville reveals a parchment", {"text": "action"})
            ),
            generate_dialogue=Mock(
                return_value=("Look at this.", {"text": "dialogue"})
            ),
            memory=actor_memory,
            position="By Luna",
            states="Determined",
        )
        human = HumanPlayer.construct(
            id=0,
            name="Luna Lovegood",
            memory=human_memory,
            position="At the entrance",
            states="Curious",
        )
        data_human = SimpleNamespace(position="At the entrance", states="Curious")
        data_actor = SimpleNamespace(position="By Luna", states="Determined")
        narrator_human = SimpleNamespace(position="At the entrance", states="Curious")
        narrator_actor = SimpleNamespace(position="By Luna", states="Determined")
        narrator = SimpleNamespace(
            analyze_action_influence=Mock(
                return_value=(0, "Neville moves beside Luna", {"text": "influence"})
            ),
            analyze_result=Mock(
                return_value=("Neville waits.", {"text": "result"})
            ),
            update_character=Mock(
                side_effect=[
                    ("At the entrance", "Curious", {"text": "human update"}),
                    ("By Luna", "Determined", {"text": "actor update"}),
                ]
            ),
            characters=[narrator_human, narrator_actor],
        )
        simulator.characters = {0: human, 1: actor}
        simulator.data = SimpleNamespace(
            characters={0: data_human, 1: data_actor},
            characters_list=[data_human, data_actor],
        )
        simulator.narrator = narrator
        simulator.synopsis = {"Neville Longbottom": ""}
        simulator.round_obs = {0: [], 1: ["Current observation"]}
        simulator.character_record = {0: [], 1: []}
        simulator.acting = OrderedDict(((0, True),))
        simulator.acted = OrderedDict()
        simulator.round_cnt = 2
        simulator.play()

        with patch.object(
            HumanPlayer,
            "take_reaction",
            return_value=("", {"text": "", "source": "human"}),
        ):
            simulator.one_step(1)

        self.assertIn(0, simulator.acting)
        self.assertNotIn(0, simulator.acted)
        self.assertEqual(
            ["reaction_skipped"],
            [item["type"] for item in simulator.character_record[0]],
        )
        narrator.analyze_result.assert_called_once_with(
            "Neville Longbottom:Neville reveals a parchment",
            simulator.now,
            verbose=True,
        )
        self.assertFalse(
            any(
                call.args[0] == "Luna Lovegood: "
                for call in human_memory.add_memory.call_args_list
            )
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
