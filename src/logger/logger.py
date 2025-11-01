import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
   "{asctime} - {levelname} - {message} | {funcName}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

