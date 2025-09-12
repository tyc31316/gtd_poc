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
    prompt = SystemMessage(
        content="""
            You are a Organzaier agent.
            Given a task, classify it into one of: "do", "calendar", "defer", or "delegate".
            - "do": if it can be done in under 2 minutes.
            - "calendar": if the task must be done by themselves at a specific time.
            - "defer": if the task must be done by themselves, but not at a specific time.
            - "delegate": if someone else should do it.
            Respond ONLY with the single word.
        """
    )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini"
    )
    try:
        import json
        actions = []
        content = state.get("messages")[-1].content
        decision: str
        try:
            actions = json.loads(content.strip("```json").strip("```"))
            if(len(actions) > 0):
                decision = llm.invoke([prompt] + [AIMessage(content=actions[0])]).content
                
            if len(actions) == 1:
                cursor.execute("INSERT INTO next_actions (description) VALUES (?)", [actions[0]])
                
            elif len(actions) > 1:
                project_name= next(msg.content for msg in state["messages"] if isinstance(msg, HumanMessage))
                cursor.execute("INSERT INTO projects (description) VALUES (?)", [project_name])
                project_id = cursor.lastrowid
                for action in actions:
                    cursor.execute("INSERT INTO next_actions (description, project_id) VALUES (?, ?)", (action, project_id))

                
            if(decision == "do"):
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Do it now: {actions[0]}")]}
                )
            elif(decision == "calendar"):
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Put it on calendar: {actions[0]}")]}
                )
            elif(decision == "defer"):
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Added to next action list: {actions[0]}")]}
                )
            elif(decision == "delegate"):
                return Command(
                    goto=END,
                    update={"messages": [AIMessage(content=f"Someone else needs to to it: {actions[0]}")]}
                )
            
                
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