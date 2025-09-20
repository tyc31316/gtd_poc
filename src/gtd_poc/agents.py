from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.gtd_poc.db import get_connection
import logging

async def clarifier_agent(state: MessagesState) -> Command[Literal["actions_generator_agent", END]]:
    logging.info(f"[clarifying]: {state.get('messages')}")

    prompt = SystemMessage(
        content="""
            You are a Task Classifier.
            The user will enter an idea, task, or todo item.
            You must determine whether this "stuff" is actionable or non-actionable.
            Respond with a single word: either "actionable" or "non-actionable" — and nothing else.
        """
    )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
    )

    try:
        response = await llm.ainvoke([prompt] + state.get("messages"))
        if(response.content.strip().lower() == "actionable"):
            return Command(
                goto="actions_generator_agent"
                
            )
        else:
            return Command(
                goto=END
            )
    except Exception as e:
        logging.error(f"[clarifier] error calling llm: {e}")
        return Command(
            goto=END,
            update={"messages": [f"[clarifier] error calling llm: {e}"]}
        )

async def actions_generator_agent(state: MessagesState) -> Command[Literal["organizer_agent"]]:
    prompt = SystemMessage(
        content="""
            You are a Next Action Generator.
            Given a task, produce an ordered, step-by-step list of concrete next actions that will successfully conclude the task. 
            Each action should be small, specific, and directly executable.
            Respond in the format of a JSON array of strings.

            For example: ["Write down initial ideas and brainstorm", "Make an appointment with Kevin to discuss", "Create a proposal"]
        """
    )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini"
    )

    try:
        response = await llm.ainvoke([prompt] + [state.get("messages")[-1]])
        return Command(
            goto="organizer_agent",
            update={"messages": [response]}
        )
    except Exception as e:
        logging.error(f"[action generator] error calling llm: {e}")
        return Command(
            goto=END,
            update={"messages": f"[action generator] error calling llm: {e}"}
        )

def organizer_agent(state: MessagesState) -> Command[Literal[END]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        import json
        actions = []
        content = state.get("messages")[-1].content
        try:
            actions = json.loads(content.strip("```json").strip("```"))
            if len(actions) == 1:
                cursor.execute("INSERT INTO next_actions (description) VALUES (?)", [actions[0]])
                
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Added to Next Actions: {actions[0]}")]}
                )
            elif len(actions) > 1:
                project_name= next(msg.content for msg in state["messages"] if isinstance(msg, HumanMessage))
                cursor.execute("INSERT INTO projects (description) VALUES (?)", [project_name])
                project_id = cursor.lastrowid
                for action in actions:
                    cursor.execute("INSERT INTO next_actions (description, project_id) VALUES (?, ?)", (action, project_id))

                # how to store actions to some table and associate them with the project id? SQL question..
                
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Created Project '{project_name}' with {len(actions)} actions.")]}
                )
            else:
                cursor.execute("INSERT INTO items_pending_review (description) VALUES (?)", [actions])
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Added to Pending Review: {actions}")]}
                )
                
        except Exception:
            cursor.execute("INSERT INTO items_pending_review (description) VALUES (?)", [content])
            return Command(
                goto=END,
                update={"messages": [AIMessage(content=f"Added to Pending Review: {actions}")]}
            )
            
    finally:
        conn.commit()
        cursor.close()
        conn.close()


builder = StateGraph(MessagesState)
builder.add_node(clarifier_agent)
builder.add_node(actions_generator_agent)
builder.add_node(organizer_agent)
builder.add_edge(START, "clarifier_agent")
graph = builder.compile()