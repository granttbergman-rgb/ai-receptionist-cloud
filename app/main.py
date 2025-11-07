from fastapi import FastAPI
from app.routers import agent

app = FastAPI(title="AI Receptionist Cloud")

app.include_router(agent.router)

@app.get("/")
def root():
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "ok"}

