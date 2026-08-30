import logging
import sys

HANDLER_NAME = "step-by-step"

LEVEL = logging.INFO

FORMAT = "%(asctime)s %(levelname)-5s %(name)s %(message)s"


def configure() -> None:
    root = logging.getLogger()
    root.setLevel(LEVEL)
    if any(handler.get_name() == HANDLER_NAME for handler in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(handler)
