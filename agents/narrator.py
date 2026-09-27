from __future__ import annotations

# Adapted from CharacterBox agents/narrator.py at commit 5c19141e.
# Original copyright (c) 2023 Lei Wang; MIT licensed.
# See docs/characterbox-provenance.md for modifications.

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import json

from langchain.schema import BaseMemory
from langchain.prompts import PromptTemplate
from langchain_experimental.generative_agents import GenerativeAgent,GenerativeAgentMemory


from utils.character import CharacterInfo,SceneInfo
import time

class Narrator(GenerativeAgent):
    id: int
    """The agent's unique identifier"""
  
    BUFFERSIZE = 10
    """The size of the agent's history buffer"""

    max_dialogue_token_limit: int = 600
    """The maximum number of tokens to use in a dialogue"""

    synopsis:List[str]=[]

    plots:List[str]=[]

    history: List[str] = []


    characters:List[CharacterInfo]


    scene: SceneInfo

    memory: GenerativeAgentMemory

    all_actions:list=[]
    
    round_plot_actions:List[Dict]=[]

    """The memory module in Narrator."""

    def update_from_dict(self, data_dict: dict):
        for key, value in data_dict.items():
            setattr(self, key, value)

    def _generate_reaction(self, suffix: str, now: Optional[datetime] = None,verbose=False, **extra_kwargs) -> str:
        """React to a given observation."""

        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        # Preserve CharacterBox's original English prompt exactly while removing
        # runtime language detection and the unused Chinese prompt branch.
        prompt = PromptTemplate.from_template(
            "Please act as a screenwriter for a key scene in an art novel that highlights the characters' unique traits and drives the plot forward\n"
            +"Event: {event}\n"
            +"Time: {time}\n"
            +"Location: {location}\n"
            +"Description: {description}\n"
            +"Characters: {characters}\n"
            +"There is no one else in the scene other than the above characters.\n"
            +suffix
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        now = datetime.now() if now is None else now
        kwargs: Dict[str, Any] = dict(
            event=self.scene.event,
            time=self.scene.time,
            location=self.scene.location,
            description=self.scene.description,
            characters=self.characters,
            #synopsis=self.synopsis,
            **extra_kwargs
        )

        st=time.time()
        result = self.chain(prompt=prompt).invoke(input=kwargs)
        ed=time.time()
        duration=ed-st
        result['prompt']=prompt
        all_prompt=prompt.format(**kwargs)
        self.all_actions.append({'character':self.name,'prompt':all_prompt,'response':result['text'].strip(),'duration':duration})
        if verbose:
            return result['text'].strip(),result
        else:
            return result['text'].strip()

    def update_character(self, name, observation, now,verbose=False):

        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        call_to_action_template = (
            "Observation: {observation}\n"
            "Character Name: {name}\n"
            "Given the character's rich backstory and observation within the scene, distill this information into a succinct summary of their present location and condition. Focus on how their interactions, especially the dynamic interplay with other characters, shape their current circumstances. This interaction's effects should be evident in the nuanced portrayal of their condition and placement within the scene. Utilize this structured format for your depiction:\n\n"
            "Position: [Specify {name}'s exact position, incorporating environmental details or spatial context to enhance the scene's visuality.]\n"
            "State: [Describe {name}'s current state, weaving together emotional nuances, physical readiness, and the influence of recent encounters or developments.]"
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        response,detail = self._generate_reaction(call_to_action_template, now, observation=observation, name=name,verbose=True)
        
        # BEGIN RESEARCH MODIFICATION: English-only response parsing.
        robust_position_value_pattern = r"Position:\s*(.+)"
        robust_state_value_pattern = r"State:\s*(.+)"
        # END RESEARCH MODIFICATION: English-only response parsing.

        # Extracting location and state using the defined regular expressions
        position_value_match = re.search(robust_position_value_pattern, response, re.IGNORECASE)
        state_value_match = re.search(robust_state_value_pattern, response, re.IGNORECASE)
        
        position_value = position_value_match.group(1).strip() if position_value_match else None
        state_value = state_value_match.group(1).strip() if state_value_match else None
        if verbose:
            return position_value, state_value,detail
        return position_value, state_value,None


    def analyze_action(self, actor,action, now) -> Tuple[int,str]:

        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        call_to_action_template = (
            "Action: {action}\n"
            "Actor: {actor}\n"
            "Analyze the action and the actor within the given context to determine which character from the Characters is most likely to respond to the action. Assess and explain why this character would be affected and describe the potential reaction. If the action directly physically impacts a target character, identify and describe the specific action affecting them, along with the reason and its effect. Responses should be formatted as [Reacting Character Name]|[Affected Action]. If no character is likely to react, return the actor's name. Ensure the response is concise and clear."
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        response = self._generate_reaction(call_to_action_template, now, action=action,actor=actor)
        pattern = re.compile(r"\s*(.*)\|\s*(.*)")

        match = re.match(pattern, response)
        target_id = None
        action = ""
        reason=""
        if match:
            target_id, action = match.groups()
            #target_id = int(target_id)
            for character in self.characters:
                if character.name==target_id:
                    target_id = character.id
                    break
        return target_id,action

    def analyze_action_influence(self, actor,action, now,verbose=False) :

        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        call_to_action_template = (
    "Action: {action}\n"
        "Actor: {actor}\n"
        "Please analyze the physical actions and impacts detailed above, specifically focusing on the effects on ONLY one character listed in 'Characters'.\n"
        "Your analysis must:\n"
        "1. Identify the target character affected (must be from the 'Characters' list).\n"
        "2. Describe the specific physical action initiated by the actor.\n"
        "3. Explain the tangible impact of this action on the target character's physical state or circumstances.\n"
        "4. You must pick up ONLY ONE character from the 'Characters' list.\n"
        "5. Emphasize physical interactions or impacts. If an action does not physically affect any characters listed, return the actor's name as Target Name.\n"
        "6. Must format your response as follows: [Actor];;[Target Name];;[Detailed Physical Impact of {actor} on Target].\n"
        "Ensure responses are concise, precise, and adhere to the specified format.\n"
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        response,detail = self._generate_reaction(call_to_action_template, now, action=action,actor=actor,verbose=True)
        #print("influence response: ",response)
        pattern = r"\[?([^;\[\]]+)\]?\s*;;\s*\[?([^;\[\]]+)\]?\s*;;\s*\[?([^;\[\]]+)\]?"
        matches = re.search(pattern, response)
        target_id=None
        if matches:
            actor = matches.group(1)
            target_name = matches.group(2)
            action = matches.group(3)
            for character in self.characters:
                if character.name==target_name:
                    target_id = character.id
                    break
        else:
            print("No match found.")
        if verbose:
            return target_id,action,detail
        return target_id,action

    def analyze_result(self, actions, now,verbose=False):
        """Take one of the actions below.
        (1) Enter the Recommender.
        (2) Enter the Social Media.
        (3) Do Nothing.
        """

        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        call_to_action_template = (
            "Actions: {actions}\n"
            "Instruction: Serve as an instant event adjudicator, swiftly analyzing the interactions between specified characters and their actions. Narrate the immediate outcomes in a concise omniscient narrator's voice, focusing exclusively on the direct consequences of these interactions at this very moment. Your narration should clearly and directly elucidate the cause-and-effect relationship between actions, emphasizing the instant outcomes without delving into any future implications or extended storylines."

            "Very Important Guidelines:"

            "1. Narrate the outcomes with immediacy, centering on the direct results of the current actions' interactions."
            "2. Use a concise omniscient narrator’s voice to maintain a narrative style while ensuring the analysis is straightforward and to the point."
            "3. Your analysis should be grounded in the character descriptions and actions provided, avoiding any speculative or unnecessary detail."
            "4. Do not repeat the Actions in the result. The result is only the result of the current action interaction."
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        response,detail = self._generate_reaction(call_to_action_template, now, actions=actions,verbose=True)
        if verbose:
            return response,detail
        return response

    def update_scene(self, obs,verbose=False):

        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        prompt = PromptTemplate.from_template(
            """
    Given an initial scene description, examine the provided observations to identify any direct and significant physical impacts on the environment. Update the scene based on these observations, focusing solely on changes to the physical environment. If the observations do not reveal any significant physical changes to the environment, the original scene description should remain unchanged. Ensure the updated scene retains the structure of the initial scene description and does not introduce new properties that were not part of the original scene description.

    Note:
    1. The scene description should focus solely on the physical environment and should not contain character actions or interactions.
    2. The elements 'time', 'location', and 'description' in the scene should not be changed unless the observation specifically indicates a change.
    3. The output should consist of structured elements for 'time', 'location', and 'description' without adding any extra text or prefixes.
    4. The description refers to the physical description of the environment and should not include character actions or interactions.

    Input:
    - Time: {time}
    - Location: {location}
    - Description: {description}

    Observation: {observation}

    Output:
    - Time: 
    - Location: 
    - Description:
    """
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        st=time.time()
        result = self.chain(prompt=prompt).invoke(input={"time":self.scene.time,"location":self.scene.location,"description":self.scene.description,"observation":obs})
        result['prompt']=prompt
        response=result["text"].strip()
        ed=time.time()
        duration=ed-st
        all_prompt=prompt.format( **{"time":self.scene.time,"location":self.scene.location,"description":self.scene.description,"observation":obs})
        self.all_actions.append({'character':self.name,'prompt':all_prompt,'response':result['text'].strip(),'duration':duration})
        # BEGIN RESEARCH MODIFICATION: English-only response parsing.
        output_time_pattern = re.compile(r"- Time:\s*\[?(.+?)\]?\n", re.IGNORECASE)
        output_location_pattern = re.compile(r"- Location:\s*\[?(.+?)\]?\n", re.IGNORECASE)
        output_description_pattern = re.compile(r"- Description:\s*\[?(.+?)\]?(?:\n|$)", re.IGNORECASE | re.DOTALL)
        # END RESEARCH MODIFICATION: English-only response parsing.

        # Extract output information.
        updated_time = output_time_pattern.search(response)
        updated_location = output_location_pattern.search(response)
        updated_description = output_description_pattern.search(response)
        if updated_time:
            self.scene.time = updated_time.group(1)
            #print("updated_time: ",updated_time.group(1))
        if updated_location:
            self.scene.location = updated_location.group(1)
            #print("updated_location: ",updated_location.group(1))
        if updated_description:
            self.scene.description = updated_description.group(1)
            #print("updated_description: ",updated_description.group(1))
        
        if verbose:
            return self.scene,result
        else:
            return self.scene

    def summary_plot(self,actions) -> str:
        # BEGIN RESEARCH MODIFICATION: English-only study scope.
        prompt = PromptTemplate.from_template(
            """
            "Actions: {actions}\n"
            Given ths list of actions performed by characters as above, create a concise paragraph summarizing these actions. Detail each action in the order they occurred, focusing solely on what was done without interpreting the motivations or outcomes. Ensure the summary is clear and maintains the logical sequence of events.

            """
        )
        # END RESEARCH MODIFICATION: English-only study scope.
        st=time.time()
        result = self.chain(prompt=prompt).invoke(input={"actions":actions})
        result['prompt']=prompt
        response=result["text"].strip()
        ed=time.time()
        duration=ed-st
        all_prompt=prompt.format( **{"actions":actions})
        self.all_actions.append({'character':self.name,'prompt':all_prompt,'response':result['text'].strip(),'duration':duration})

        self.plots.append(response)
        return response
