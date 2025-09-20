from fastapi import FastAPI
from pydantic import BaseModel
from src.gtd_poc.agents import graph
from src.gtd_poc.db import init_database, get_next_action_list
from dotenv import load_dotenv
import logging

app = FastAPI()

load_dotenv()
init_database()

class Stuff(BaseModel):
    description: str

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/add")
async def collect(stuff: Stuff):
    logging.info("adding new task")
    response = await graph.ainvoke({"messages": stuff.description})
    return {
        "descritipn": stuff.description,
        "response": response
    }
    
@app.get("/next-action-list")
def next_action_list():
    logging.info("getting next action list")
    return get_next_action_list()
    
