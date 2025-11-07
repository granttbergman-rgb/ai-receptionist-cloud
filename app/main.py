from fastapi import FastAPI

app = FastAPI(title="Cloud Test")

@app.get("/")
def root():
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "ok"}

