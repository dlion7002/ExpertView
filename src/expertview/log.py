"""Structlog configuration for ExpertView.

Configures structlog once on import with an ISO 8601 timestamper and a JSON
renderer so investigator-node timing events (``investigator.start`` /
``investigator.finish``) land as interleaved, timestamped JSON lines — the
application-side complement to the LangSmith trace described in
[architecture.md §5](../../ProjectDocs/architecture.md).

Module-import configuration is idempotent: ``structlog.configure`` replaces
any prior configuration in process, so callers (CLI, tests, integration
fixtures) need only import :func:`get_logger` to get a configured logger.
"""

from __future__ import annotations

import logging
import sys

import structlog

_LOG_LEVEL = logging.INFO


def _configure_structlog() -> None:
    # stdlib logging is the sink structlog writes through; without a configured
    # handler at INFO the start/finish events would be filtered before reaching
    # stdout.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=_LOG_LEVEL,
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_LOG_LEVEL),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name) if name is not None else structlog.get_logger()


_configure_structlog()
