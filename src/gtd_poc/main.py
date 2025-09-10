from fastapi import FastAPI
from pydantic import BaseModel
import logging

app = FastAPI()

class Stuff(BaseModel):
    description: str

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/add")
def collect(stuff: Stuff):
    logging.info(f"Adding thread of thoughts: {stuff.description}")
    return {
        "descritipn": stuff.description,
        "category": "Next Action"
    }
