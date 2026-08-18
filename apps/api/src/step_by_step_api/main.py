from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from step_by_step_api.envelope import master_key


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """What the backend proves before it serves a request.

    The master key is read here rather than at the first vault write: an
    instance that cannot open its own vault must fail while an operator is
    still watching the boot, not hours later on someone's password.
    """
    master_key()
    yield


app = FastAPI(title="step-by-step-api", lifespan=lifespan)


class Health(BaseModel):
    status: str


class Greeting(BaseModel):
    message: str


@app.get("/api/health", operation_id="getHealth")
def get_health() -> Health:
    return Health(status="ok")


@app.get("/api/hello/{name}", operation_id="getGreeting")
def get_greeting(name: str) -> Greeting:
    return Greeting(message=f"Hello, {name}!")
