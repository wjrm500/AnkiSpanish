import logging
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING

from constant import PrintColour as PC


class CustomFormatter(logging.Formatter):
    FORMAT = "%(asctime)s %(levelname)s %(message)s"

    FORMATS = {
        DEBUG: FORMAT,
        INFO: FORMAT,
        WARNING: PC.YELLOW.value + FORMAT + PC.RESET.value,
        ERROR: PC.RED.value + FORMAT + PC.RESET.value,
        CRITICAL: PC.RED.value + FORMAT + PC.RESET.value,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno, self.FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logging.basicConfig(level=INFO)
formatter = CustomFormatter()
logger = logging.getLogger()
for handler in logger.handlers:
    handler.setFormatter(formatter)

__all__ = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "logger"]
