import os
import sys
import time
import json
import math
import copy
import logging
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

# BEGIN RESEARCH MODIFICATION: macOS native-runtime stability.
# CharacterBox loads both PyTorch (through sentence-transformers) and FAISS.
# Their separate LLVM OpenMP runtimes crashed on Apple Silicon during the first
# retrieval. Single-threaded OpenMP avoids that native race; setdefault keeps an
# explicit user setting. Tokenizer workers are disabled to avoid leaked workers
# after abnormal exits. These settings must precede the native imports below.
if sys.platform == "darwin":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# END RESEARCH MODIFICATION: macOS native-runtime stability.

import faiss
import argparse
import threading
from tqdm import tqdm
import concurrent.futures
from yacs.config import CfgNode
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.docstore import InMemoryDocstore
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import TimeWeightedVectorStoreRetriever
from langchain_experimental.generative_agents import GenerativeAgentMemory
from langchain_community.embeddings import HuggingFaceEmbeddings


from dataloader.data import Data
from dataloader.context_priorities import load_validated_priority_config
from dataloader.research_sidecar import (
    load_validated_sidecar,
    load_validated_pilot_config,
    resolve_source_dataset_path,
)
from utils import utils
from utils.message import Message
from utils.character import SceneInfo
from agents import Character, HumanPlayer, Narrator, NoScoreGenerativeAgentMemory
from langchain.globals import set_debug


# set_debug(True)


logging.basicConfig(level=logging.ERROR)
lock = threading.Lock()


class Simulator:
    """
    Simulator class for running the simulation.
    """
    def __init__(self, config: CfgNode, logger: logging.Logger):
        self.config = config
        self.logger = logger
        # BEGIN RESEARCH EXTENSION: controlled/dynamic simulation switch.
        # Default True preserves CharacterBox behavior for original configs.
        # Later functions will consult this flag; this step only stores it.
        self.dynamic_play = self.config.get("dynamic_play", True)
        # END RESEARCH EXTENSION: controlled/dynamic simulation switch.
        # BEGIN RESEARCH EXTENSION: resolved controlled-trial selectors.
        # These remain empty in CharacterBox-compatible dynamic mode.
        self.controlled_trial = None
        self.controlled_target_id = None
        self.controlled_action_reference = None
        self.controlled_turns = []
        self.dataset_source = None
        self.pilot_conditions = []
        self.context_condition = None
        self.priority_policy = None
        # END RESEARCH EXTENSION: resolved controlled-trial selectors.
        self.round_cnt = 0
        self.file_name_path: list[str] = []
        self.play_event = threading.Event()
        self.now = datetime.now().replace(hour=8, minute=0, second=0)
        self.round_message:list[Message] = []
        self.round_obs = {}
        self.acting = OrderedDict()
        self.acted = OrderedDict()
        self.last_round = ""
        self.character_record = {}
        self.round_record = []
        self.plot_record = {}
        self.narrator_record=[]
        self.records = []
        self.duration=0.

    def load_simulator(self):
        """Load and initiate the simulator."""
        self.round_cnt = 0
        self.data = Data(self.config, self.logger)

        # BEGIN RESEARCH EXTENSION: resolve controlled play from source.
        # A pilot sidecar is present only when the CLI explicitly receives
        # --pilot. Ordinary simulator runs resolve their editable selectors from
        # play.yaml and remain interactive. Both paths resolve Action Reference
        # from Data.init_actions rather than copying its value into configuration.
        if not self.dynamic_play:
            sidecar_path_value = self.config.get("research_sidecar_path")
            pilot = None
            trial = None
            run_config = None
            target_character_id = self.config.get("target_character_id")
            action_id = self.config.get("action_id")

            if sidecar_path_value:
                sidecar_path = Path(sidecar_path_value).resolve()
                pilot = load_validated_sidecar(sidecar_path)
                configured_dataset = Path(self.config["scene_path"]).resolve()
                pilot_dataset = (
                    sidecar_path.parent / pilot["source_dataset"]
                ).resolve()
                if configured_dataset != pilot_dataset:
                    raise ValueError(
                        "Controlled pilot source_dataset must match scene_path"
                    )
                if pilot["scene_id"] != self.config["scene_id"]:
                    raise ValueError(
                        "Controlled pilot scene_id must match configured scene_id"
                    )
                if pilot["player_character_id"] != self.config["play_role"]:
                    raise ValueError(
                        "Controlled pilot player_character_id must match play_role"
                    )
                matching_trials = [
                    candidate
                    for candidate in pilot["trials"]
                    if candidate["trial_id"] == self.config["trial_id"]
                ]
                if len(matching_trials) != 1:
                    raise ValueError("trial_id must identify one trial in the pilot")
                trial = matching_trials[0]
                # Action Reference is pilot-level (same scene, same target NPC
                # for every trial), not chosen per trial.
                target_character_id = pilot["target_character_id"]
                action_id = pilot["action_id"]

                pilot_config_path = self.config.get("pilot_config_path")
                if not pilot_config_path:
                    raise ValueError(
                        "pilot_config_path is required to resolve pilot conditions"
                    )
                run_config = load_validated_pilot_config(pilot_config_path)

            if target_character_id not in self.data.characters:
                raise ValueError("Controlled target character is not in the scene")

            matching_actions = [
                action
                for action in self.data.init_actions
                if action["action_id"] == action_id
            ]
            if len(matching_actions) != 1:
                raise ValueError(
                    "Controlled action_id must identify one source action"
                )

            condition = self.config["context_condition"]
            if condition not in {"U", "S", "P"}:
                raise ValueError("context_condition must be U, S, or P")

            # Pilot runs resolve their priority policy from the auto-loaded
            # run-config; YAML-only ad hoc controlled runs keep using the
            # editable play.yaml field.
            priority_policy_id = (
                run_config["priority_policy_id"]
                if run_config is not None
                else self.config.get("priority_policy_id")
            )
            priority_policy = None
            if condition == "P":
                priority_config = load_validated_priority_config(
                    self.config["priority_config_path"]
                )
                matching_policies = [
                    policy
                    for policy in priority_config["policies"]
                    if policy["policy_id"] == priority_policy_id
                ]
                if len(matching_policies) != 1:
                    raise ValueError(
                        "priority_policy_id must identify one priority policy"
                    )
                priority_policy = matching_policies[0]

            self.controlled_trial = (
                {
                    "trial_id": trial["trial_id"],
                    "pilot_id": pilot["pilot_id"],
                    "source_dataset": pilot["source_dataset"],
                }
                if trial is not None
                else None
            )
            self.controlled_target_id = target_character_id
            self.controlled_action_reference = matching_actions[0]["action"]
            if trial is not None:
                self.controlled_turns = copy.deepcopy(trial["turns"])
                self.dataset_source = pilot["dataset_source"]
                self.pilot_conditions = list(run_config["conditions"])
            else:
                self.controlled_turns = []
                self.dataset_source = self.config.get("dataset_source")
                self.pilot_conditions = []
            self.context_condition = condition
            self.priority_policy = priority_policy
        # END RESEARCH EXTENSION: resolve controlled play from source.

        # self.round_obs = {i:[] for i in self.data.characters.keys()}
        self.narrator, self.characters = self.agents_creation()
        
        self.character_record = {i:[] for i in self.characters.keys()}
        utils.ensure_dir(self.config["record_dir"])
        title = self.config['scene_path'].split("/")[-1].split(".")[0]
        utils.ensure_dir(os.path.join(self.config["record_dir"], title))
        self.plot_record = self.data.scenes[self.config['scene_id']]
        self.plot_record['generated_plot'] = []
        self.plot_record['synopsis'] = []
        for i in self.characters.keys():
            self.acting[i] = True
        self.logger.info("Simulator loaded.")



    def relevance_score_fn(self, score: float) -> float:
        """Return a similarity score on a scale [0, 1]."""

        return 1.0 - score / math.sqrt(2)

    def create_new_memory_retriever(self):
        """Create a new vector store retriever unique to the agent."""
        model_name = "sentence-transformers/all-mpnet-base-v2"
        model_kwargs = {'device': 'cpu'}
        embeddings_model = HuggingFaceEmbeddings(model_name=model_name, model_kwargs=model_kwargs)
        embedding_size=768
        #embeddings_model=OpenAIEmbeddings()
        #embedding_size = 1536
        # Initialize the vectorstore as empty
        
        index = faiss.IndexFlatL2(embedding_size)
        vectorstore = FAISS(
            embeddings_model.embed_query,
            index,
            InMemoryDocstore({}),
            {},
            relevance_score_fn=self.relevance_score_fn,
        )


        return TimeWeightedVectorStoreRetriever(vectorstore=vectorstore, other_score_keys=["importance"], k=5)

    def pause(self):
        self.play_event.clear()

    def play(self):
        self.play_event.set()

    def get_round_info(self):
        history=""
        for i in range(len(self.round_record)):
            history += self.round_record[i]['character_name']+":"+self.round_record[i]['detail']['text']+'\n'
        return history
    
    def get_character_obs(self, agent_id):
        return ". ".join(self.round_obs[agent_id])

    def _build_controlled_trajectory_record(self, research_metadata):
        """Return one evaluation-ready dialogue trajectory for a controlled run."""
        if self.dynamic_play:
            raise ValueError("Trajectory export is supported only for controlled play")

        player_id = self.config["play_role"]
        target_id = self.controlled_target_id
        source_scene = copy.deepcopy(self.data.scenes[self.config["scene_id"]])

        turns = []
        for expected_round, round_events in enumerate(self.records, start=1):
            player_dialogues = [
                event
                for event in round_events
                if event.get("round") == expected_round
                and event.get("character_id") == player_id
                and event.get("type") == "dialogue"
            ]
            target_dialogues = [
                event
                for event in round_events
                if event.get("round") == expected_round
                and event.get("character_id") == target_id
                and event.get("type") == "dialogue"
            ]
            if len(player_dialogues) != 1 or len(target_dialogues) != 1:
                raise ValueError(
                    "Controlled trajectory requires exactly one player and "
                    "one target dialogue per round"
                )
            player_detail = player_dialogues[0]["detail"]
            target_detail = target_dialogues[0]["detail"]
            turns.append(
                {
                    "round": expected_round,
                    "player_dialogue": player_detail["text"].strip(),
                    "npc_dialogue": target_detail["text"].strip(),
                    "npc_observation": target_detail.get("observation", ""),
                }
            )

        player_info = self.data.characters[player_id]
        target_info = self.data.characters[target_id]
        return {
            "schema_version": 1,
            "record_type": "controlled_dialogue_trajectory",
            "title": Path(self.config["scene_path"]).stem,
            "scene_id": self.config["scene_id"],
            **research_metadata,
            "generation": {
                "character_model": self.config["character_llm"],
                "temperature": self.config.get("temperature"),
                "max_token": self.config.get("max_token"),
                "duration_seconds": self.duration,
            },
            "source_dataset": (
                self.controlled_trial.get("source_dataset")
                if self.controlled_trial is not None
                else self.config.get("scene_path")
            ),
            "scene": {
                key: source_scene.get(key)
                for key in ("id", "event", "time", "location", "description")
            },
            "player": player_info.dict(),
            "target": {
                **target_info.dict(),
                "self_belief": self.characters[target_id].self_belief,
                "environment_belief": self.characters[target_id].env_belief,
            },
            "action_reference": self.controlled_action_reference,
            "turns": turns,
        }
    
    def save_record(self):
        title = self.config['scene_path'].split("/")[-1].split(".")[0]

        # BEGIN RESEARCH EXTENSION: identify controlled experimental records.
        # These selectors distinguish U/S/P outputs without duplicating any
        # world, scene, character, action, or dialogue value.
        research_metadata = {}
        if not self.dynamic_play:
            research_metadata = {
                "dynamic_play": False,
                "trial_id": (
                    self.controlled_trial["trial_id"]
                    if self.controlled_trial is not None
                    else self.config.get("trial_id")
                ),
                "pilot_id": (
                    self.controlled_trial["pilot_id"]
                    if self.controlled_trial is not None
                    else None
                ),
                "dataset_source": self.dataset_source,
                "player_character_id": self.config["play_role"],
                "target_character_id": self.controlled_target_id,
                "configured_rounds": (
                    len(self.controlled_turns)
                    if self.controlled_turns
                    else self.config["round"]
                ),
                "pilot_conditions": self.pilot_conditions,
                "context_condition": self.context_condition,
                "generation_run_id": self.config.get("generation_run_id"),
                "priority_policy_id": (
                    self.priority_policy["policy_id"]
                    if self.priority_policy is not None
                    else None
                ),
            }
        # END RESEARCH EXTENSION: identify controlled experimental records.

        # 记录结果
        if self.config['save_record']:
            utils.ensure_dir(os.path.join(self.config["record_dir"], title,"plot"))
            with open(os.path.join(self.config["record_dir"], title,"plot", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["plot_record_path"]), "a", encoding='utf8') as f:
                data={"title":title,"scene_id":self.config['scene_id'],"scene":self.data.init_scene,"characters":self.data.init_characters,"record":self.plot_record,**research_metadata}
                json.dump(data, f, default=lambda o: o.__dict__,  ensure_ascii=False)
                f.write("\n")

            print("Plot record saved in:",os.path.join(self.config["record_dir"], title,"plot", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["plot_record_path"]))

            utils.ensure_dir(os.path.join(self.config["record_dir"], title,"character"))
            with open(os.path.join(self.config["record_dir"], title,"character", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["character_record_path"]), "a", encoding='utf8') as f:
                data={"title":title,"scene_id":self.config['scene_id'],"scene":self.data.init_scene,"characters":self.data.init_characters,"record":self.character_record,**research_metadata}
                json.dump(data, f, default=lambda o: o.__dict__,  ensure_ascii=False)
                f.write("\n")

            print("Character record saved in:",os.path.join(self.config["record_dir"], title,"character", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["character_record_path"]))

            # BEGIN RESEARCH EXTENSION: canonical controlled trajectory export.
            # CharacterBox's separate record categories remain untouched. This
            # compact JSONL record is the stable input contract shared by the
            # CharacterBox-compatible and future turn-wise evaluators.
            if not self.dynamic_play:
                trajectory_dir = os.path.join(
                    self.config["record_dir"], title, "trajectory"
                )
                utils.ensure_dir(trajectory_dir)
                trajectory_path = os.path.join(
                    trajectory_dir,
                    self.config["narrator_llm"]
                    + "_"
                    + self.config["character_llm"]
                    + "_"
                    + self.config.get("trajectory_record_path", "trajectory.jsonl"),
                )
                trajectory = self._build_controlled_trajectory_record(
                    research_metadata
                )
                with open(trajectory_path, "a", encoding="utf8") as file:
                    json.dump(trajectory, file, ensure_ascii=False)
                    file.write("\n")
                print("Evaluation trajectory saved in:", trajectory_path)
            # END RESEARCH EXTENSION: canonical controlled trajectory export.

            utils.ensure_dir(os.path.join(self.config["record_dir"], title,"round"))
            with open(os.path.join(self.config["record_dir"], title,"round", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["round_record_path"]), "a", encoding='utf8') as f:
                data={"title":title,"scene_id":self.config['scene_id'],"scene":self.data.init_scene,"characters":self.data.init_characters,"record":self.records,**research_metadata}
                json.dump(data, f, default=lambda o: o.__dict__,  ensure_ascii=False)
                f.write("\n")
                
            print("Round record saved in:",os.path.join(self.config["record_dir"], title,"round", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["round_record_path"]))

            utils.ensure_dir(os.path.join(self.config["record_dir"], title,"narrator"))
            with open(os.path.join(self.config["record_dir"], title,"narrator", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["narrator_record_path"]), "a", encoding='utf8') as f:
                data={"title":title,"scene_id":self.config['scene_id'],"scene":self.data.init_scene,"characters":self.data.init_characters,"record":self.narrator_record,**research_metadata}
                json.dump(data, f, default=lambda o: o.__dict__, ensure_ascii=False)
                f.write("\n")
            print("Narrator record saved in:",os.path.join(self.config["record_dir"], title,"narrator", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["narrator_record_path"]))


            utils.ensure_dir(os.path.join(self.config["record_dir"], title,"all"))
            with open(os.path.join(self.config["record_dir"], title,"all", self.config['narrator_llm']+"_"+self.config['character_llm']+"_"+self.config["all_record_path"]), "a", encoding='utf8') as f:
                # BEGIN RESEARCH EXTENSION: controlled model-call collection.
                # Dynamic play retains CharacterBox's original Narrator-plus-all-
                # agents collection. Controlled play has no Narrator and only the
                # target NPC makes a model call; human terminal input is recorded
                # in character/round files rather than fabricated as an LLM trace.
                if self.dynamic_play:
                    all_record=self.narrator.all_actions
                    for id,agent in self.characters.items():
                        all_record+=agent.all_actions
                else:
                    all_record=list(
                        self.characters[self.controlled_target_id].all_actions
                    )
                # END RESEARCH EXTENSION: controlled model-call collection.
                # BEGIN RESEARCH EXTENSION: optional inherited cost estimate.
                # CharacterBox counts with GPT-2 and hard-codes legacy GPT-4
                # prices, producing warnings and inaccurate gpt-4o-mini costs.
                # Default True preserves original configurations; disabling it
                # still retains measured per-call and whole-run durations.
                if self.config.get("calculate_cost", True):
                    total_cost,duration=utils.calc_cost(self.config['narrator_llm'],self.config['character_llm'],all_record)
                    self.logger.info(f"Total Cost:{total_cost}, Duration:{duration}")
                else:
                    total_cost = None
                    duration = sum(
                        action.get("duration", 0.0) for action in all_record
                    )
                    self.logger.info(
                        f"Cost calculation disabled. Model-call Duration:{duration}"
                    )
                # END RESEARCH EXTENSION: optional inherited cost estimate.
                data={"title":title,"scene_id":self.config['scene_id'],"scene":self.data.init_scene,"characters":self.data.init_characters,"total_cost":total_cost,"duration":self.duration,"record":all_record,**research_metadata}
                json.dump(data, f, default=lambda o: o.__dict__,  ensure_ascii=False)
                f.write("\n")
    # Run one step of an agent.
    def one_step(self, agent_id):
        self.play_event.wait()
        agent = self.characters[agent_id]
        name = agent.name
        message = []

        action, detail = agent.take_action(self.get_character_obs(agent_id),self.synopsis[name], self.now)
        action_info = {"round":self.round_cnt, "character_id":agent_id, "character_name":name, "type":"action", "detail":detail}
        self.round_record.append(action_info)
        self.character_record[agent_id].append(action_info)
        action_message = Message(
                agent_id=0,
                action="POST",
                content=f"{name}: {action}."
            )
        message.append(action_message)
        self.round_message.append(action_message)
        # target, operation = self.narrator.analyze_action(action)
        self.logger.info(f"{name}: {action}")
        
        response, detail = agent.generate_dialogue( action,self.synopsis[name], self.now)
        self.logger.info(f"{name}: \"{response}\" ")
        response_message = Message(
                agent_id=agent_id,
                action="POST",
                content=f"{name}: \"{response}\""
            )
        message.append(response_message)
        self.round_message.append(response_message)
        self.round_obs[agent_id].clear() 
        action_info={"round":self.round_cnt, "character_id":agent_id, "character_name":name, "type":"dialogue", "detail":detail}   
        self.character_record[agent_id].append(action_info)
        self.round_record.append(action_info)

        # 分析行为对其他角色的影响并记录
        influence_id, inf_action,detail = self.narrator.analyze_action_influence(agent.name, action, self.now,verbose=True)
        action_info={"round":self.round_cnt, "character_id":-1, "character_name":"Narrator", "type":"Action Influence", "detail":detail}   
        self.narrator_record.append(action_info)
        print(f"influence_id:{influence_id}, inf_action:{inf_action}")
        
        reactions=[]
        if influence_id is not agent.id and influence_id is not None:
            
            inf_agent=self.characters[influence_id]
            reactions.append({"Actor:":name,"Action:":action})
            self.logger.info(f"{name} influenced {inf_agent.name}: {inf_action}")
           
            self.round_obs[influence_id].append(f"{name}:{action}")
            self.round_obs[influence_id].append(f"{name}: {response}")
            self.round_obs[influence_id].append(f"{inf_action}")
            reaction, detail = inf_agent.take_reaction(self.get_character_obs(influence_id),"", self.now)
            inf_agent.memory.add_memory(f"{name}: {action}", now=self.now)
            inf_agent.memory.add_memory(f"{name}: {inf_action}", now=self.now)
            inf_agent.memory.add_memory(f"{name}: {response}", now=self.now)

            # BEGIN RESEARCH MODIFICATION: blank HumanPlayer reaction means skip.
            # CharacterBox has no human reaction interface. A blank terminal
            # response now records an explicit skip, is not fed to Narrator as a
            # fabricated action, and does not consume the human's normal turn.
            skipped_human_reaction = (
                isinstance(inf_agent, HumanPlayer) and not reaction.strip()
            )
            if skipped_human_reaction:
                action_info = {
                    "round": self.round_cnt,
                    "character_id": influence_id,
                    "character_name": inf_agent.name,
                    "type": "reaction_skipped",
                    "detail": detail,
                }
                self.character_record[influence_id].append(action_info)
                self.round_record.append(action_info)
                self.logger.info(
                    f"{inf_agent.name} skipped reaction to {name}"
                )
            else:
                inf_agent.memory.add_memory(
                    f"{inf_agent.name}: {reaction}", now=self.now
                )
                if influence_id not in self.acted:
                    self.acted[influence_id] = True
                    self.acting.pop(influence_id)
                action_info = {"round":self.round_cnt, "character_id":influence_id, "character_name":inf_agent.name, "type":"reaction", "detail":detail}
                self.character_record[influence_id].append(action_info)
                self.round_record.append(action_info)
                self.logger.info(f"{inf_agent.name} react to {name}: {reaction}")
            # END RESEARCH MODIFICATION: blank HumanPlayer reaction means skip.
            
            # Narrator analyzes the result of the interaction
            if not skipped_human_reaction:
                reactions.append({"Actor:":inf_agent.name,"Action:":reaction})
            reactions_info=";".join([f"{r['Actor:']}:{r['Action:']}" for r in reactions])
            result,detail = self.narrator.analyze_result(reactions_info,self.now,verbose=True)
            action_info = {"round":self.round_cnt, "character_id":-1, "character_name":"Narrator", "type":"Analyze Result", "detail":detail}
            
            self.round_record.append(action_info)
            self.narrator_record.append(action_info)
            self.logger.info(f"Interaction Result:{result}")
            
           
            agent.memory.add_memory(result, now=self.now)
            inf_agent.memory.add_memory(result, now=self.now)

             # Update Characters
            inf_position, inf_states,detail = self.narrator.update_character(self.characters[influence_id].name,reactions_info+";"+result,self.now,verbose=True)
            self.round_obs[influence_id].clear()
            action_info={"round":self.round_cnt, "character_id":-1, "character_name":"Narrator", "type":"Update Character", "detail":detail}   
            self.narrator_record.append(action_info)
            self.logger.info(f"update_character: name:{self.characters[influence_id].name}\n position:{inf_position}\n states:{inf_states}\n")
            
           
            
            position, states,detail = self.narrator.update_character(self.characters[agent_id].name, reactions_info+";"+result, self.now,verbose=True)
            action_info={"round":self.round_cnt, "character_id":-1, "character_name":"Narrator", "type":"Update Character", "detail":detail}   
            self.narrator_record.append(action_info)
            self.logger.info(f"update_character: name:{self.characters[agent_id].name}\n position:{position}\n states:{states}\n")
            if position is not None and states is not None:
                for char_obj in [self.characters[influence_id], self.narrator.characters[influence_id], self.data.characters[influence_id], self.data.characters_list[influence_id]]:
                    char_obj.position = inf_position
                    char_obj.states = inf_states
                for char_obj in [self.characters[agent_id], self.narrator.characters[agent_id], self.data.characters[agent_id], self.data.characters_list[agent_id]]:
                    char_obj.position = position
                    char_obj.states = states
       
        else:
            position, states,detail = self.narrator.update_character(self.characters[agent_id].name,action ,self.now,verbose=True)
            action_info={"round":self.round_cnt, "character_id":-1, "character_name":"Narrator", "type":"Update Character", "detail":detail}   
            self.narrator_record.append(action_info)
            self.logger.info(f"update_character: name:{self.characters[agent_id].name}\n position:{position}\n states:{states}\n")
            for char_obj in [self.characters[agent_id], self.narrator.characters[agent_id], self.data.characters[agent_id], self.data.characters_list[agent_id]]:
                    char_obj.position = position
                    char_obj.states = states
       
        return message
    
    # Run many steps
    def round(self):
        """
        Run one step for all agents.
        """
        # BEGIN RESEARCH EXTENSION: controlled one-human/one-NPC round.
        # Return before CharacterBox's autonomous dynamic pipeline so controlled
        # U/S/P trials contain one human input and one generated NPC dialogue,
        # with no generated beliefs, actions, synopsis, narration, or state/scene
        # updates. The original dynamic body remains unchanged below this branch.
        if not self.dynamic_play:
            self.play_event.wait()
            player_id = self.config["play_role"]
            target_id = self.controlled_target_id
            if player_id not in self.characters:
                raise ValueError("Controlled player is not a created character")
            if target_id not in self.characters:
                raise ValueError("Controlled target is not a created character")

            player = self.characters[player_id]
            target = self.characters[target_id]

            # BEGIN RESEARCH MODIFICATION: dialogue-only controlled input.
            # Controlled trials intentionally exclude player actions and NPC
            # action generation. The source Action Reference remains fixed
            # context for the target NPC's existing dialogue path.
            if self.controlled_turns:
                if self.round_cnt > len(self.controlled_turns):
                    raise ValueError("Controlled round exceeds pilot turns")
                scripted_turn = self.controlled_turns[self.round_cnt - 1]
                player_dialogue = scripted_turn["player_dialogue"]
                dialogue_detail = {
                    "text": player_dialogue,
                    "source": "pilot_manifest",
                }
            else:
                while True:
                    player_dialogue, dialogue_detail = player.generate_dialogue(
                        self.get_character_obs(player_id),
                        "",
                        self.now,
                    )
                    if player_dialogue.strip():
                        break
                    print("Please enter dialogue.")

            player_messages = []
            observation_parts = []
            dialogue_info = {
                "round": self.round_cnt,
                "character_id": player_id,
                "character_name": player.name,
                "type": "dialogue",
                "detail": dialogue_detail,
            }
            self.round_record.append(dialogue_info)
            self.character_record[player_id].append(dialogue_info)
            dialogue_message = Message(
                agent_id=player_id,
                action="POST",
                content=f'{player.name}: "{player_dialogue.strip()}"',
            )
            player_messages.append(dialogue_message)
            observation_parts.append(dialogue_message.content)
            self.logger.info(dialogue_message.content)

            current_observation = " ".join(observation_parts)
            # Reuse CharacterBox's existing previous-round transcript instead
            # of generating a controlled synopsis or Narrator summary. The
            # first round receives the source initial actions, as dynamic play
            # does; later rounds receive the immediately preceding transcript.
            previous_round = self.last_round.strip()
            if previous_round:
                observation = (
                    f"Previous interaction:\n{previous_round}\n"
                    f"Current input:\n{current_observation}"
                )
            else:
                observation = current_observation
            # END RESEARCH MODIFICATION: dialogue-only controlled input.
            self.round_obs[target_id].clear()
            self.round_obs[target_id].append(observation)
            response, response_detail = target.generate_dialogue(
                self.get_character_obs(target_id),
                self.controlled_action_reference,
                self.now,
                context_condition=self.context_condition,
                priority_policy=self.priority_policy,
            )
            stored_response_detail = dict(response_detail)
            raw_response = stored_response_detail.get("text", "")
            if raw_response != response:
                stored_response_detail["raw_text"] = raw_response
            stored_response_detail["text"] = response
            response_info = {
                "round": self.round_cnt,
                "character_id": target_id,
                "character_name": target.name,
                "type": "dialogue",
                "detail": stored_response_detail,
            }
            self.round_record.append(response_info)
            self.character_record[target_id].append(response_info)
            response_message = Message(
                agent_id=target_id,
                action="POST",
                content=f'{target.name}: "{response}"',
            )

            controlled_messages = [
                player_messages,
                [response_message],
            ]
            self.round_message.extend(player_messages + [response_message])
            self.logger.info(f'{target.name}: "{response}"')

            self.last_round = self.get_round_info()
            self.records.append(copy.copy(self.round_record))
            self.round_message.clear()
            self.round_record.clear()
            return controlled_messages
        # END RESEARCH EXTENSION: controlled one-human/one-NPC round.

        messages = []
        futures = []
        self.logger.info("Round {} start.".format(self.round_cnt))
        for i in self.characters.keys():
            #self.characters[i].scene = new_scene
            # BEGIN RESEARCH MODIFICATION: human-aware dynamic belief updates.
            # HumanPlayer supplies terminal input and has no LLM belief methods.
            if i == self.data.role_id:
                continue
            # END RESEARCH MODIFICATION: human-aware dynamic belief updates.
            self_belief = self.characters[i].update_self_belief(self.last_round, self.now)
            other_character = self.get_other_agents(self.data.characters_list, i)
            env_belief = self.characters[i].update_env_belief(self.last_round, other_character, self.now)

        sequence=[self.characters[i].name for i in self.acting.keys()]
        #self.synopsis=self.narrator.generate_synopsis(self.last_round,sequence,self.now)
        # BEGIN RESEARCH MODIFICATION: human-aware dynamic synopsis source.
        # CharacterBox hard-codes character 0, which fails when play_role is 0.
        # Keep character 0 for the original path; otherwise choose the first NPC.
        synopsis_agent_id = 0
        if self.data.role_id == 0:
            npc_ids = [
                character_id
                for character_id in self.characters
                if character_id != self.data.role_id
            ]
            if not npc_ids:
                raise ValueError("Dynamic play requires an NPC synopsis generator")
            synopsis_agent_id = npc_ids[0]
        self.synopsis=self.characters[synopsis_agent_id].generate_synopsis(self.last_round,sequence,self.plot_record['synopsis'],self.now)
        # END RESEARCH MODIFICATION: human-aware dynamic synopsis source.
        for i in self.characters.keys():
            if self.characters[i].name not in self.synopsis:
                self.synopsis[self.characters[i].name]=""
        self.plot_record["synopsis"].append({"round":self.round_cnt, "synopsis":self.synopsis})
        self.logger.info(f"Round Synopsis:{self.synopsis}")
        while len(self.acted)<len(self.characters):
            actor = self.acting.popitem(last=False)[0]           
            msgs = self.one_step(actor)
            messages.append(msgs)
            self.acted[actor] = True


        
        self.last_round = self.get_round_info()
        new_scene,detail = self.narrator.update_scene(self.last_round,verbose=True)
        action_info={"round":self.round_cnt, "character_id":-1, "character_name":"Narrator", "type":"Update Scene", "detail":detail}   
        self.narrator_record.append(action_info)
        self.logger.info(f"Scene:{new_scene}")
        round_plot = self.narrator.summary_plot(self.last_round)
        self.plot_record["generated_plot"].append({"round":self.round_cnt, "plot":round_plot})
        self.logger.info(f"Round Plot:{round_plot}")
        

        for i in self.characters.keys():
            self.characters[i].scene = new_scene

        self.records.append(copy.copy(self.round_record))
        self.round_message.clear()
        self.round_record.clear()
        self.acting, self.acted = self.acted, self.acting
        
        return messages

    def create_character(self, i, api_key, api_base="", score_memories=True) -> Character:
        """
        Create an agent with the given id.
        """

        LLM = utils.get_llm(self.config['character_llm'], config=self.config, logger=self.logger, api_key=api_key,api_base=api_base)
        # BEGIN RESEARCH EXTENSION: skip wasted importance scoring in controlled
        # trials. See agents/character.py:NoScoreGenerativeAgentMemory. Dynamic
        # play keeps the unmodified CharacterBox memory class unconditionally.
        MemoryClass = GenerativeAgentMemory if score_memories else NoScoreGenerativeAgentMemory
        agent_memory = MemoryClass(
            llm=LLM,
            memory_retriever = self.create_new_memory_retriever(),
            verbose = False,
            reflection_threshold = 10,
            max_tokens_limit=2500,
            importance_weight=0.1
        )
        # END RESEARCH EXTENSION: skip wasted importance scoring in controlled trials.

        agent = Character(
                id = self.data.characters[i].id,
                name = self.data.characters[i].name,
                scene = SceneInfo(**self.data.scenes[self.config['scene_id']]),
                position = self.data.characters[i].position,
                states = self.data.characters[i].states,
                traits = self.data.characters[i].description,
                llm = LLM,
                memory = agent_memory,
                status="",
        )
        
        return agent

    def create_human_player(self, id, api_key, api_base=None):

        LLM = utils.get_llm(self.config['character_llm'],config=self.config, logger=self.logger, api_key=api_key, api_base=api_base)
        
      
        MemoryClass = GenerativeAgentMemory
        agent_memory = MemoryClass(
            llm=LLM,
            memory_retriever = self.create_new_memory_retriever(),
            verbose = False,
            reflection_threshold = 15,
        )
        
        agent = HumanPlayer(
            id=id,
            name=self.data.characters[id].name,
            gender=self.data.characters[id].gender,
            scene=SceneInfo(**self.data.scenes[self.config['scene_id']]),
            position=self.data.characters[id].position,
            states=self.data.characters[id].states,
            traits=self.data.characters[id].description,
            llm=LLM,
            memory=agent_memory,
            status="",
        )

        return agent

    def create_narrator(self, config, logger, api_key, api_base=None):

        LLM = utils.get_llm(self.config['narrator_llm'],config=self.config, logger=self.logger, api_key=api_key, api_base=api_base)
        
      
        MemoryClass = GenerativeAgentMemory
        agent_memory = MemoryClass(
            llm=LLM,
            memory_retriever = self.create_new_memory_retriever(),
            verbose = False,
            reflection_threshold = 15,
        )

        sid=config['scene_id']
        narrator = Narrator(
            id=0,
            name="Narrator",
            traits="",
            status="",
            llm=LLM,
            memory=agent_memory,
            scene=SceneInfo(**self.data.scenes[self.config['scene_id']]),
            characters=self.data.characters_list,
            
        )

        return narrator

    # 用于agents_creation的工具函数
    def get_other_agents(self, characters, agent_id):
        return [characters[i] for i in range(len(characters)) if characters[i].id != agent_id]

    def agents_creation(self):
        """
        Create agents in parallel
        """
        characters = {}
        character_api_key= self.config.get("character_api_key","")
        character_api_base = self.config.get("character_api_base","")
        # Add ONE human controllable role into the simulator if the flag is true.
        # We block the main thread when the user is creating the role.
        self.last_round=""
        for action in self.data.init_actions:
            self.last_round += action["character"] + ":" + action['action'] + ";" + action["character"] + ":" + action['dialogue'] + '\n'
        

        for i in tqdm(self.data.characters.keys()):
            if self.config["play_role"] is not None and i==self.config["play_role"]:
                role_id = self.config["play_role"]
                agent = self.create_human_player(role_id, character_api_key, character_api_base)
                characters[role_id] = agent
                self.data.role_id = role_id
                # BEGIN RESEARCH MODIFICATION: initialise HumanPlayer observation.
                # CharacterBox continues before creating this buffer, although
                # one_step() later reads and clears it for every acting agent.
                self.round_obs[role_id]=[]
                self.round_obs[role_id].append(self.last_round)
                # END RESEARCH MODIFICATION: initialise HumanPlayer observation.
                continue
            agent = self.create_character(
                i, character_api_key, character_api_base,
                score_memories=self.dynamic_play,
            )
            characters[agent.id] = agent
            self.round_obs[agent.id]=[]
            self.round_obs[agent.id].append(self.last_round)
                
        # BEGIN RESEARCH EXTENSION: controlled/dynamic Narrator routing.
        # Preserve CharacterBox's original Narrator creation verbatim in dynamic
        # play. Controlled U/S/P trials omit the generated world adjudicator so
        # every condition receives the same fixed source scene state.
        if self.dynamic_play:
            narrator_api_key= self.config.get("narrator_api_key","")
            narrator_api_base = self.config.get("narrator_api_base","")
            narrator = self.create_narrator(self.config, self.logger, narrator_api_key, narrator_api_base)
        else:
            narrator = None
        # END RESEARCH EXTENSION: controlled/dynamic Narrator routing.

        return narrator, characters

    def reset(self):
        # Reset the system
        self.pause()
        self.round_cnt = 0
        log_string = ""
        self.load_simulator()
        log_string = "The system is reset, and the historic records are removed."
        return log_string


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
         "--character_llm", type=str,default=None, help="Path to config file"
    )
    parser.add_argument(
         "--scene_path", type=str,default=None, help="Path to config file"
    )
    parser.add_argument(
        "-c", "--config_file", type=str, required=True, help="Path to config file"
    )
    # BEGIN RESEARCH EXTENSION: explicit pilot activation.
    # Omitting this option guarantees that simulator.py reads no pilot manifest.
    parser.add_argument(
        "--pilot",
        type=str,
        default=None,
        help="Optional fixed-input pilot manifest; omitted for YAML-only play",
    )
    # END RESEARCH EXTENSION: explicit pilot activation.
    parser.add_argument(
        "-i", "--scene_id", type=int, default=None, help="Path to config file"
    )
    parser.add_argument(
        "-l", "--log_file", type=str, default="", help="Path to log file"
    )
    parser.add_argument(
        "-n", "--log_name", type=str, default=str(os.getpid()), help="Name of logger"
    )
    parser.add_argument(
        "-p",
        "--play_role",
        type=int,
        default=-1,
        help="Add a user controllable role",
    )
    args = parser.parse_args()
    return args


def apply_pilot_overrides(config, pilot_path):
    """Apply an explicitly selected pilot over runtime/provider defaults."""
    # BEGIN RESEARCH EXTENSION: reproducible pilot configuration layer.
    if not pilot_path:
        # Ignore/remove the former YAML activation key so only --pilot can
        # attach fixed input, including for older local configuration files.
        if "research_sidecar_path" in config:
            del config["research_sidecar_path"]
        return None
    pilot = load_validated_sidecar(pilot_path)
    config["research_sidecar_path"] = str(Path(pilot_path).resolve())
    config["scene_path"] = str(resolve_source_dataset_path(pilot_path, pilot))
    config["scene_id"] = pilot["scene_id"]
    config["play_role"] = pilot["player_character_id"]
    config["dynamic_play"] = False
    config["target_character_id"] = pilot["target_character_id"]
    config["action_id"] = pilot["action_id"]
    pilot_config_path = config.get("pilot_config_path")
    if not pilot_config_path:
        raise ValueError("play.yaml must set pilot_config_path to run --pilot")
    config["pilot_config_path"] = str(Path(pilot_config_path).resolve())
    # trial_id and round are resolved per trial in run_pilot_conditions().
    return pilot
    # END RESEARCH EXTENSION: reproducible pilot configuration layer.


def run_simulation(config, logger):

    role_agent = Simulator(config, logger)
    role_agent.load_simulator()

    messages = []
    role_agent.play()
    st = time.time()
    for _ in range(role_agent.round_cnt + 1, config["round"] + 1):
        role_agent.round_cnt = role_agent.round_cnt + 1
        role_agent.logger.info(f"Round {role_agent.round_cnt}")

        message = role_agent.round()
        messages.append(message)

    role_agent.duration = time.time() - st
    role_agent.logger.info(f"Duration:{role_agent.duration}")
    print(f"Duration:{role_agent.duration}")
    role_agent.save_record()
    return role_agent


def run_pilot_conditions(config, logger, pilot=None):
    """Run every trial under every declared condition with a fresh Simulator
    instance, sharing one generation_run_id across the whole pilot."""
    if pilot is None:
        trials = [None]
        conditions = [config["context_condition"]]
        run_id_seed = config.get("trial_id") or "controlled"
    else:
        run_config = load_validated_pilot_config(config["pilot_config_path"])
        trials = pilot["trials"]
        conditions = run_config["conditions"]
        run_id_seed = pilot["pilot_id"]

    generation_run_id = config.get("generation_run_id") or (
        f"{run_id_seed}-{time.time_ns()}"
    )
    print(f"Pilot generation_run_id: {generation_run_id}")
    completed = []
    for trial in trials:
        for condition in conditions:
            run_config_for_call = config.clone()
            run_config_for_call["context_condition"] = condition
            run_config_for_call["generation_run_id"] = generation_run_id
            if trial is not None:
                run_config_for_call["trial_id"] = trial["trial_id"]
                run_config_for_call["round"] = len(trial["turns"])
            logger.info(
                "Paired pilot trial/condition: "
                f"{trial['trial_id'] if trial else None}/{condition}"
            )
            completed.append(run_simulation(run_config_for_call, logger))
    print(f"Pilot complete. generation_run_id: {generation_run_id}")
    return completed


def config_for_logging(config):
    """Return a config copy with provider credentials removed."""
    safe_config = config.clone()
    for key in ("character_api_key", "narrator_api_key", "api_key"):
        if key in safe_config:
            safe_config[key] = "[REDACTED]"
    return safe_config

def main():
    args = parse_args()

    
    # create config
    config = CfgNode(new_allowed=True)
    config = utils.add_variable_to_config(config, "log_file", args.log_file)
    config = utils.add_variable_to_config(config, "log_name", args.log_name)
    config = utils.add_variable_to_config(config, "play_role", args.play_role)
    config.merge_from_file(args.config_file)
    # BEGIN RESEARCH SECURITY FIX: runtime-only provider credentials.
    # Environment values override placeholder YAML fields so secrets are not
    # committed to configuration or copied into experiment artefacts.
    shared_api_key = os.environ.get("OPENAI_API_KEY")
    character_api_key = os.environ.get("CHARACTER_API_KEY") or shared_api_key
    narrator_api_key = os.environ.get("NARRATOR_API_KEY") or shared_api_key
    if character_api_key:
        config["character_api_key"] = character_api_key
    if narrator_api_key:
        config["narrator_api_key"] = narrator_api_key
    # END RESEARCH SECURITY FIX: runtime-only provider credentials.
    # BEGIN RESEARCH EXTENSION: explicit pilot invocation.
    # play.yaml never activates a manifest by itself. --pilot deliberately
    # overlays fixed experiment selectors while retaining YAML provider/model
    # and output settings.
    pilot = apply_pilot_overrides(config, args.pilot)
    # END RESEARCH EXTENSION: explicit pilot invocation.
    if args.character_llm is not None:
        config['character_llm']=args.character_llm
    if args.scene_path is not None:
        config['scene_path']=args.scene_path
    if args.scene_id is not None:
        config['scene_id']=args.scene_id
    title=config['scene_path'].split("/")[-1].split(".")[0]
    if args.log_file=="":
        utils.ensure_dir("output/log/simulation/"+title)
        args.log_file=f"simulation/{title}/{config['narrator_llm']}_{config['character_llm']}_{config['scene_id']}_character_simulation.log"
    logger = utils.set_logger(args.log_file, args.log_name)
    logger.info(f"os.getpid()={os.getpid()}")
    logger.info(f"\n{config_for_logging(config)}")

    
    # BEGIN RESEARCH EXTENSION: explicit paired-pilot routing.
    # YAML-only execution runs once and remains interactive. An explicit pilot
    # runs each declared condition with a fresh Character and memory instance.
    if pilot is None:
        run_simulation(config, logger)
    else:
        run_pilot_conditions(config, logger, pilot)
    # END RESEARCH EXTENSION: explicit paired-pilot routing.

if __name__ == "__main__":
    main()
