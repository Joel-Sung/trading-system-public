from enum import StrEnum


class Indicator(StrEnum):
    TICKER = "ticker"
    SECTOR = "sector"
    DATETIME = "datetime"

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"

    ROLLING_HIGH = "rolling_high"
    ROLLING_LOW = "rolling_low"
    ATR = "atr"
    RS = "rs"
    RS_WITH_SECTOR = "rs_with_sector"
    RS_WITH_MARKET = "rs_with_market"

    ENTRY_TIME = "entry_time"
    ENTRY_PRICE = "entry_price"
    EXIT_TIME = "exit_datetime"
    EXIT_PRICE = "exit_price"
    PROFIT_IN_R = "profit_in_r"
