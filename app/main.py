from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database.mongodb import connect, disconnect
from app.routes.analyze import router as analyze_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    yield
    await disconnect()


app = FastAPI(title="DPDP Guard AI", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(analyze_router, prefix="/api")
