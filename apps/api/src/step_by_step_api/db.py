"""The backend's view of the database seam.

The engine, the declarative base, and the session scope live in
`step_by_step_core.db`, which the Workers write through as well. What is
FastAPI's alone stays here: the dependency a route handler declares.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session
from step_by_step_core.db import Base, get_engine, get_session

__all__ = ["Base", "SessionDep", "get_engine", "get_session"]

SessionDep = Annotated[Session, Depends(get_session)]
"""The dependency route handlers declare to receive their request's session."""
