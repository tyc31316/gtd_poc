import json
from langgraph.graph import StateGraph, START, END
from typing import  TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.gtd_poc.db import get_connection
from enum import StrEnum
from langgraph.graph import MessagesState

class GTDCategory(StrEnum):
    DO_NOW = 'DO_NOW'
    NEXT_ACTION_LIST = 'NEXT_ACTION_LIST'
    DELEGATE = 'DELEGATE'
    CALENDAR = 'CALENDAR'
    WAITING_FOR = 'WAITING_FOR'
    SOMEDAY_MAYBE = 'SOMEDAY_MAYBE'
    
class Action:
    id: int
    description: str
    context: list[str]
    time_minutes: list[int]
    category: GTDCategory

class GTDState(MessagesState):
    user_input: str
    is_project: bool
    project_name: str
    project_description: str
    next_action_list: list[Action]
    
llm = ChatOpenAI(
        model="gpt-4o-mini",
    )

async def is_project(state: GTDState):
    prompt = SystemMessage(
        content=
        """
            You are a GTD classifier that determines whether an input represents a "project" or a "single-step action".

            Definitions:
            - A **project** is any desired outcome that requires two or more physical, visible actions to complete.
            - A **non-project** (single action) is something that can be completed in one physical step.

            Instructions:
            1. Read the user's input (which may be an idea, task, or to-do item).
            2. Apply the GTD definition above.
            3. If the input represents a project:
                - Set "is_project" to true.
                - Generate a concise, outcome-oriented project name (e.g., "Launch new website", "Organize summer trip").
                - The project name should describe the *final desired result*, not the next action.
            4. If the input is a single-step action:
                - Set "is_project" to false.
            5. Respond **only** in valid JSON format using one of these exact schemas:
                - For projects:
                    ```json
                    {"is_project": true, "project_name": "some project name"}
                    ```
                - For non-projects:
                    ```json
                    {"is_project": false}
                    ```
            6. Use lowercase true/false (not strings).
            7. Do **not** include any explanations, comments, or text outside the JSON.
        """
    )

    response = await llm.ainvoke([prompt] + [HumanMessage(content = state.get("user_input"))])
    return json.loads(response.content)

async def actions_generator_agent(state: GTDState):
    
    prompt = SystemMessage(
        content=
        """
            You are a GTD Next Action Generator.

            Your task is to determine the *physical, concrete, and immediately executable next action(s)* for the given task or project, following the principles of Getting Things Done (GTD).

            Guidelines:
            1. Focus only on **actions that can be done directly** — not vague or planning tasks.
                - ✅ "Email Sarah to confirm the meeting time"
                - ❌ "Plan the meeting"
            2. Each action must describe a **visible physical behavior** that can typically be done in one sitting.
            3. If multiple next actions can be performed in parallel, list them all.
            4. For each action, provide:
                - `"description"` — a concise, physical next step
                - `"context"` — short tags describing the situation, tools, or environment needed (e.g. `"computer"`, `"phone"`, `"office"`, `"home"`, `"errand"`, `"anywhere"`)
                - `"time_minutes"` — approximate number of minutes required to complete (integer estimate)
            5. Respond **only** in valid JSON format: an array of objects with these three fields.
            6. Do **not** include any explanations, text, or comments outside the JSON.

            Example response:
            [
            {
                "description": "Contact Kevin to schedule a discussion time",
                "context": ["computer", "email"],
                "time_minutes": 5
            },
            {
                "description": "Brainstorm possible ideas for the proposal",
                "context": ["office", "thinking"],
                "time_minutes": 20
            }
            ]
        """
    )

    response = await llm.ainvoke([prompt] + [HumanMessage(content=state.get('user_input'))])
    # action_list = []
    
    # for index, action in json.loads(response.content):
    #     action_list.append(Action(index, action["description"], "project_id"))
    
    return {"next_action_list": json.loads(response.content)}

async def action_organizer(state: GTDState):
    prompt = SystemMessage(
        content="""
            You are a GTD Action Categorizer.
            Your task is to categorize each next action into the appropriate GTD list or bucket, based on its nature, urgency, and required context.

            You will receive one or more actions, each containing:
                - "description": what the action is
                - "context": where or how it can be done (e.g., ["computer", "phone", "office"])
                - "time_minutes": estimated time needed to complete it

            You must assign each action to exactly one of the following GTD categories:
            1. "DO_NOW" — Actions that take less than 2 minutes, or are so quick it’s better to do them immediately.
            2. "CALENDAR" — Actions that must be done at a specific time or date (e.g., meetings, appointments, deadlines).
            3. "DELEGATE" — Actions that should be handed off to someone else to complete.
            4. "WAITING_FOR" — Actions that are currently blocked because you’re waiting on someone or something.
            5. "NEXT_ACTION_LIST" — Actions that you will do soon, but not immediately; they remain available by context for future execution.
            6. "SOMEDAY_MAYBE" — Actions or ideas you might want to consider later but not commit to now.

            Rules:
            - Always output a valid JSON array.
            - Each item in the array must include the fields:
                - "description"
                - "context"
                - "time_minutes"
                - "category"
            - Preserve the original fields as given.
            - Do **not** include any explanation, reasoning, or text outside the JSON.

            Example input:
            [
                {"description": "Email Sarah to confirm meeting time", "context": ["computer", "email"], "time_minutes": 3},
                {"description": "Prepare slides for Monday’s client presentation", "context": ["computer", "office"], "time_minutes": 90}
            ]

            Example response:
            [
                {"description": "Email Sarah to confirm meeting time", "context": ["computer", "email"], "time_minutes": 3, "category": "DO_NOW"},
                {"description": "Prepare slides for Monday’s client presentation", "context": ["computer", "office"], "time_minutes": 90, "category": "CALENDAR"}
            ]
        """
    )
    
    response = await llm.ainvoke([prompt] + [AIMessage(content = json.dumps(state.get("next_action_list")))])
   
    return {"next_action_list": json.loads(response.content)}


builder = StateGraph(GTDState)
builder.add_node(is_project)
builder.add_node(actions_generator_agent)
builder.add_node(action_organizer)

builder.add_edge(START, "is_project")
builder.add_edge(START, "actions_generator_agent")
builder.add_edge('is_project', 'action_organizer')
builder.add_edge('actions_generator_agent', 'action_organizer')
builder.add_edge('action_organizer', END)
graph = builder.compile()