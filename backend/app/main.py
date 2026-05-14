from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, fields, missions, analytics

app = FastAPI(
    title="Precision Agriculture Drone Analytics Platform",
    version="2.0.0",
    description="PostGIS-backed drone anomaly detection and field intelligence API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(fields.router)
app.include_router(missions.router)
app.include_router(analytics.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
