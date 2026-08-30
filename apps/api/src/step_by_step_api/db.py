from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session
from step_by_step_core.db import Base, get_engine, get_session

__all__ = ["Base", "SessionDep", "get_engine", "get_session"]

SessionDep = Annotated[Session, Depends(get_session)]
