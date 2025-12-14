from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import app as flask_app

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Flask app under FastAPI
@app.get("/")
async def root():
    return {"message": "Geraldine AI Agent API"}

# Import all routes from Flask app
for rule in flask_app.url_map.iter_rules():
    endpoint = flask_app.view_functions[rule.endpoint]
    methods = list(rule.methods - {"OPTIONS", "HEAD"})
    path = str(rule)
    
    if path == "/":
        continue
        
    @app.route(path, methods=methods)
    async def wrapper(*args, **kwargs):
        return await endpoint(*args, **kwargs)