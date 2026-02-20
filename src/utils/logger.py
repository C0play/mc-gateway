import logging
import os

lvl = None
match os.getenv("LOG_LEVEL"):
    case "DEBUG":
        lvl = logging.DEBUG
    case "INFO":
        lvl = logging.INFO
    case "WARN":
        lvl = logging.WARN
    case "ERROR":
        lvl = logging.ERROR
    case "CRIT":
        lvl = logging.CRITICAL
    case _:
        lvl = logging.INFO

logger = logging.getLogger(__name__)
logger.setLevel(lvl)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
   "{asctime} - {levelname} - {message} | {funcName}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
)

console_handler.setFormatter(formatter)

logger.addHandler(console_handler)