import logging
from datetime import datetime

from util.logger import Logger, LogLevel


def test_formats_message_with_additional_info(caplog, logger: Logger):
    with caplog.at_level(logging.INFO, logger="test"):
        logger.log(
            source="AlignDataHandler",
            log_datetime=datetime(2026, 1, 6),
            log_level=LogLevel.INFO,
            message="Closed campaign",
            additional_info={"ticker": "AAPL", "qty": 10},
        )

    assert caplog.messages == [
        "[2026-01-06] [AlignDataHandler] Closed campaign. ticker: AAPL, qty: 10"
    ]


def test_omits_additional_info_when_empty(caplog, logger: Logger):
    with caplog.at_level(logging.INFO, logger="test"):
        logger.log("Engine", datetime(2026, 1, 6), LogLevel.INFO, "Started")

    assert caplog.messages == ["[2026-01-06] [Engine] Started."]


def test_uses_the_given_log_level(caplog, logger: Logger):
    with caplog.at_level(logging.DEBUG, logger="test"):
        logger.log("Engine", datetime(2026, 1, 6), LogLevel.WARNING, "Careful")

    assert caplog.records[0].levelno == logging.WARNING
