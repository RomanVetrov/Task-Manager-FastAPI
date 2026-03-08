import logging

import structlog


def setup_logging() -> None:
    """Настраивает structlog для всего приложения. Вызывается один раз при старте."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
