### Build and Run
1. Create an virtual environment if you have not.
`python3 -m venv .venv`
2. Activate the virtual environment if you have not.
`source .venv/bin/activate`
3. Install dependencies
`poetry install`
4. Run the app
`uvicorn src.gtd_poc.main:app --reload`

### Debug with