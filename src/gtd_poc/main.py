from fastapi import FastAPI
from pydantic import BaseModel
from src.gtd_poc.agents import graph
import logging

app = FastAPI()

class Stuff(BaseModel):
    description: str

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/add")
def collect(stuff: Stuff):
    response = graph.invoke({"messages": stuff.description})
    return {
        "descritipn": stuff.description,
        "response": response
    }
