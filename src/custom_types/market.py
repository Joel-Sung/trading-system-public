from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from custom_types.exception import MyValueError


class Action(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TradeType(StrEnum):
    LONG = "long"
    SHORT = "short"


class OrderType(StrEnum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"
    LMT_STP = "LMT_STP"  # Limit order with stop loss


class MarketBarPeriod(StrEnum):
    HOUR = "HOUR"
    DAY = "DAY"
    MONTH = "MONTH"
    YEAR = "YEAR"


@dataclass
class MarketAssets:
    net_liquidation: (
        float  # Total value of the account if all positions were closed including cash
    )
    cash_balance: float  # Cash balance in the account
    cash_available_for_trading: (
        float  # Cash available for trading after accounting for margin requirements
    )
    buying_power: (
        float  # The maximum amount of money that can be used to buy securities
    )
    gross_position_value: (
        float  # The total value of all positions in the account excluding cash
    )
    unrealized_pnl: float  # The total profit or loss of all open positions
    realized_pnl: float  # The total profit or loss of all closed positions


@dataclass
class MarketPosition:
    ticker: str  # The ticker symbol of the security
    trade_type: TradeType
    quantity: float  # The number of shares or contracts held
    average_cost: float  # The average cost per share or contract
    market_value: float  # The current market value of the position
    unrealized_pnl: (
        float  # The profit or loss of the position that has not been realized
    )
    realized_pnl: float  # The profit or loss of the position that has been realized


class MarketOrder:
    def __init__(
        self,
        order_id: str,
        ticker: str,
        action: Action,
        order_type: OrderType,
        quantity: float,
        filled_quantity: float,
        avg_fill_price: float,
        fees: float,
        submitted_at: datetime,
        limit_price: float | None = None,
        stop_price: float | None = None,
        status: str | None = None,
    ):
        self.order_id = order_id
        self.ticker = ticker
        self.action = action
        self.order_type = order_type
        self.quantity = quantity
        self.filled_quantity = filled_quantity
        self.avg_fill_price = avg_fill_price
        self.fees = fees
        self.submitted_at = submitted_at

        if order_type == OrderType.LMT and limit_price is None:
            raise MyValueError(
                "Limit price must be provided for limit orders", order_id=order_id
            )

        if order_type == OrderType.STP and stop_price is None:
            raise MyValueError(
                "Stop price must be provided for stop orders", order_id=order_id
            )

        if order_type == OrderType.LMT_STP and (
            limit_price is None or stop_price is None
        ):
            raise MyValueError(
                "Both limit and stop prices must be provided for limit-stop orders",
                order_id=order_id,
                limit_price=limit_price,
                stop_price=stop_price,
            )

        self.limit_price = limit_price
        self.stop_price = stop_price
        self.status = status

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"order_id={self.order_id!r}, "
            f"ticker={self.ticker!r}, "
            f"action={self.action!r}, "
            f"order_type={self.order_type!r}, "
            f"quantity={self.quantity!r}, "
            f"filled_quantity={self.filled_quantity!r}, "
            f"avg_fill_price={self.avg_fill_price!r}, "
            f"fees={self.fees!r}, "
            f"submitted_at={self.submitted_at!r}, "
            f"limit_price={self.limit_price!r}, "
            f"stop_price={self.stop_price!r}, "
            f"status={self.status!r}"
            f")"
        )


class APIRateLimitExceededError(Exception):
    """Raised when a broker API rate limit has been exceeded."""

    def __init__(self, message: str = "Broker API rate limit exceeded."):
        super().__init__(message)
