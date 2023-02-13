import logging
import platform
from rich.logging import RichHandler


def emojis(str=''):
    # Return platform-dependent emoji-safe version of string
    return str.encode().decode('ascii', 'ignore') if platform.system() == 'Windows' else str


def getLogger(name=None, level=logging.INFO):
    logger = logging.getLogger("Main" if name is None else name)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = RichHandler()
        handler.setFormatter(logging.Formatter(
            "[%(name)s]: %(message)s"))
        handler.setLevel(level)
        logger.addHandler(handler)

    return logger
