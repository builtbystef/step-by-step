from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from step_by_step_api.accounts.routes import router as accounts_router
from step_by_step_api.accounts.service import signup_mode
from step_by_step_api.envelope import master_key
from step_by_step_api.errors import install_error_handler
from step_by_step_api.extension.routes import router as extension_router
from step_by_step_api.logs import configure as configure_logging
from step_by_step_api.mail import mailer
from step_by_step_api.runs.routes import router as runs_router
from step_by_step_api.secrets.routes import router as secrets_router
from step_by_step_api.workflows.catalog import router as workflow_catalog_router
from step_by_step_api.workflows.recording import router as recording_router
from step_by_step_api.workflows.routes import router as workflows_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """What the backend proves before it serves a request.

    Logging first, so that everything after it is said somewhere an operator
    can read it: uvicorn gives its own loggers a handler and the application's
    none, and a record written to a logger with no handler is dropped.

    Then all three are read here rather than at first use: an instance that
    cannot open its own vault, cannot send the Sign-in Code that is the only
    way in, or cannot say who may sign up, must fail while an operator is
    still watching the boot — not hours later on someone's secret or
    someone's sign-in.
    """
    configure_logging()
    master_key()
    mailer()
    signup_mode()
    yield


app = FastAPI(title="step-by-step-api", lifespan=lifespan)
install_error_handler(app)
app.include_router(accounts_router)
app.include_router(extension_router)
app.include_router(secrets_router)
app.include_router(workflows_router)
app.include_router(recording_router)
app.include_router(workflow_catalog_router)
app.include_router(runs_router)


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
