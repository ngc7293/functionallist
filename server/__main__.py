import asyncio
import logging
from typing import cast

from hypercorn.asyncio import serve
from hypercorn.config import Config
from hypercorn.typing import Framework

from .app import app
from .logging import configure_logging
from .settings import settings


def main():
    configure_logging(settings.log_level)
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    config.accesslog = logging.getLogger("hypercorn.access")
    config.errorlog = logging.getLogger("hypercorn.error")
    asyncio.run(serve(cast(Framework, app), config))


main()
