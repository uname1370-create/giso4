from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Giso Beauty Vision Engine", version="1.0.0")
app.include_router(router, prefix="/v1")

@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "vision-engine", "version": "1.0.0"}
