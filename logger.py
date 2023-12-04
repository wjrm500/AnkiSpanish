import logging

from consts import PrintColour as PC

class CustomFormatter(logging.Formatter):
    FORMAT = "%(asctime)s %(levelname)s %(message)s"

    FORMATS = {
        logging.DEBUG: FORMAT,
        logging.INFO: FORMAT,
        logging.WARNING: PC.YELLOW.value + FORMAT + PC.RESET.value,
        logging.ERROR: PC.RED.value + FORMAT + PC.RESET.value,
        logging.CRITICAL: PC.RED.value + FORMAT + PC.RESET.value
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

logging.basicConfig(level=logging.DEBUG)
formatter = CustomFormatter()
logger = logging.getLogger()
for handler in logger.handlers:
    handler.setFormatter(formatter)