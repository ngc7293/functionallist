import logging
import sys


class ColoredLogFormatter(logging.Formatter):
    """Use ANSI color codes to colorize log messages for TTY output"""

    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        log_fmt = f"%(asctime)s.%(msecs)03d %(name)28s: {color}%(levelname)7s{self.RESET}: %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(ColoredLogFormatter())
    root.addHandler(console)
