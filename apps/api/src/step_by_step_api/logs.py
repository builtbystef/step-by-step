"""Where the backend's own log records get a handler.

uvicorn configures handlers for its `uvicorn*` loggers and none for the root,
so a record any application module writes — `log.info(...)` in the mailer, in
a route, anywhere — goes to a logger with nothing attached and is dropped.
The console mailer's message is such a record, and on a default dev instance
the Sign-in Code inside it is the only way in.

So this is the one place the backend configures logging, called from the
lifespan beside the other startup gates. No call site configures anything: a
module takes its logger and writes to it, and where the record ends up is
this module's business.
"""

import logging
import sys

HANDLER_NAME = "step-by-step"
"""The handler's name, which is how a second start finds the first one's."""

LEVEL = logging.INFO
"""What the backend says out loud. INFO carries the console mailer's message."""

FORMAT = "%(asctime)s %(levelname)-5s %(name)s %(message)s"
"""The Worker's format, so one stack's logs read the same however they arrive."""


def configure() -> None:
    """Put one handler on the root logger, on stdout, once.

    The root and nothing else: uvicorn's own loggers keep their handlers and
    do not propagate to it, so its access and error records are neither
    silenced nor written a second time. Calling this again — `--reload`
    restarts the app, and so does every test that starts it — finds the
    handler already there and leaves it alone.
    """
    root = logging.getLogger()
    root.setLevel(LEVEL)
    if any(handler.get_name() == HANDLER_NAME for handler in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(handler)
