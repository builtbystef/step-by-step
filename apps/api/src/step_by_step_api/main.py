from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from step_by_step_api.accounts.routes import router as accounts_router
from step_by_step_api.accounts.service import signup_mode
from step_by_step_api.envelope import master_key
from step_by_step_api.errors import install_error_handler
from step_by_step_api.mail import mailer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """What the backend proves before it serves a request.

    All three are read here rather than at first use: an instance that cannot
    open its own vault, cannot send the Sign-in Code that is the only way in,
    or cannot say who may sign up, must fail while an operator is still
    watching the boot — not hours later on someone's secret or someone's
    sign-in.
    """
    master_key()
    mailer()
    signup_mode()
    yield


app = FastAPI(title="step-by-step-api", lifespan=lifespan)
install_error_handler(app)
app.include_router(accounts_router)


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
