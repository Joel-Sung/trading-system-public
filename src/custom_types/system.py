from datetime import datetime

from custom_types.market import Action, OrderType


class SystemOrder:
    def __init__(
        self,
        ticker: str,
        action: Action,
        order_type: OrderType,
        quantity: float,
        submitted_dt: datetime,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ):
        self.ticker = ticker
        self.action = action
        self.order_type = order_type
        self.quantity = quantity
        self.submitted_dt = submitted_dt

        if order_type == OrderType.LMT and limit_price is None:
            raise ValueError("Limit price must be provided for limit orders.")

        if order_type == OrderType.STP and stop_price is None:
            raise ValueError("Stop price must be provided for stop orders.")

        if order_type == OrderType.LMT_STP:
            if limit_price is None:
                raise ValueError(
                    "Limit price must be provided for limit orders with stop loss."
                )
            if stop_price is None:
                raise ValueError(
                    "Stop price must be provided for limit orders with stop loss."
                )

        self.limit_price = limit_price
        self.stop_price = stop_price

    def __str__(self) -> str:
        return (
            "SystemOrder("
            f"ticker={self.ticker}, "
            f"action={self.action}, "
            f"order_type={self.order_type}, "
            f"quantity={self.quantity}, "
            f"submitted_dt={self.submitted_dt}, "
            f"limit_price={round(self.limit_price, 3) if self.limit_price is not None else 'None'}, "
            f"stop_price={round(self.stop_price, 3) if self.stop_price is not None else 'None'}"
            ")"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SystemOrder):
            return NotImplemented

        return (
            self.ticker == other.ticker
            and self.action == other.action
            and self.order_type == other.order_type
            and self.quantity == other.quantity
            and self.submitted_dt == other.submitted_dt
            and self.limit_price == other.limit_price
            and self.stop_price == other.stop_price
        )
