from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

    # clarifier = create_react_agent(
    #     model="openai:gpt-4o-mini",
    #     prompt=(
    #     "You are a task clarifier agent.\n"
    #     "Given an input, or \"stuff\", you need to determine whether it is actionable or not."
    #     "If it is, hand it off to the action list generator agent."
    #     "If not, END."
    #     ),
    #     name="clarifier_agent",
    #     tools=[]
    # )


async def clarifier_agent(state: MessagesState) -> Command[Literal["actions_generator_agent"]]:
    logging.info(f"[clarifying]: {state.messages}")
    message = HumanMessage(
        content=state.messages
    )
    llm = ChatOpenAI(
        model="openai:gpt-4o-mini",
        prompt=(
            f"Your are a task classifier. User will enter an idea OR task OR todos. You need to determine whether this \"stuff\" is an actionalble item or not.")
    )
    response = await model.ainvoke(message)
    return Command(
        goto="actions_generator_agent",
        update={"messages": response}
    )

def actions_generator_agent(state: MessagesState) -> Command[Literal[END]]:
    return Command(
        goto=END,
        update={"messages": f"actions generator: {state.messages}"}
    )
    
builder = StateGraph(MessagesState)
builder.add_node(clarifier_agent)
builder.add_node(actions_generator_agent)
builder.add_edge(START, "clarifier_agent")
builder.add_edge("clarifier_agent", "actions_generator_agent")
graph = builder.compile()