from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routes import aliases, canonical, embeddings, resolve, review, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Attribute AI Resolver",
    version="1.0.0",
    description="Local attribute aliasing, semantic matching, and review queue service.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(canonical.router)
app.include_router(aliases.router)
app.include_router(resolve.router)
app.include_router(review.router)
app.include_router(embeddings.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"ok": True}
