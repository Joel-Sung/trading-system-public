import math
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import (
    Action,
    MarketAssets,
    MarketBarPeriod,
    MarketOrder,
    MarketPosition,
    OrderType,
    TradeType,
)
from custom_types.ticker import Ticker
from system.indicator.indicator_types import Indicator
from util.df_util import does_df_contain_cols

REQUIRED_MARKET_DATA_COLS = [
    Indicator.TICKER,
    Indicator.DATETIME,
    Indicator.OPEN,
    Indicator.HIGH,
    Indicator.LOW,
    Indicator.CLOSE,
]

ORDER_STATUS_SUBMITTED = "SUBMITTED"


@dataclass
class _TickerBars:
    frame: pd.DataFrame
    times: pd.DatetimeIndex


@dataclass
class _PendingOrder:
    order_id: str
    ticker: str
    action: Action
    order_type: OrderType
    quantity: float
    submitted_at: datetime
    limit_price: float | None = None
    stop_price: float | None = None


@dataclass
class _Position:
    ticker: str
    trade_type: TradeType
    quantity: float
    average_cost: float
    realized_pnl: float = 0.0


class StubBrokerClient(BrokerClient):
    """
    In-memory BrokerClient for backtests, holding an account that trades against
    the given historical daily bars.

    Time only moves when advance_to() is called, which is what a backtest does once
    per day. Orders are day orders, matching BrokerClient's contract: the ones placed
    on a day are matched against the next bar the clock moves to, and are dropped if
    they do not fill. Fills follow the same rules as OrderHandler: a limit order fills
    at its limit price if the bar traded through it, a stop order fills at its stop
    price if the bar traded through it.

    Shorting locks the sale proceeds and consumes the same amount of available cash
    again, so a short uses as much buying power as a long of the same size.
    Fees are delegated to fee_broker, so the backtest uses the fees of a real broker.
    """

    def __init__(
        self,
        market_data: pd.DataFrame,
        initial_cash: float,
        fee_broker: BrokerClient,
    ) -> None:
        if not does_df_contain_cols(market_data, REQUIRED_MARKET_DATA_COLS):
            raise MyValueError(
                "Market data does not have the required columns",
                required_cols=[str(col) for col in REQUIRED_MARKET_DATA_COLS],
                columns=list(market_data.columns),
            )

        data = market_data.copy()
        data[Indicator.DATETIME] = pd.to_datetime(data[Indicator.DATETIME])

        self._bars: dict[str, _TickerBars] = {}
        for ticker, ticker_df in data.groupby(Indicator.TICKER):
            ticker_df = ticker_df.sort_values(Indicator.DATETIME).reset_index(drop=True)
            self._bars[str(ticker)] = _TickerBars(
                frame=ticker_df,
                times=pd.DatetimeIndex(ticker_df[Indicator.DATETIME]),
            )

        self._fee_broker = fee_broker
        self._cash_balance = float(initial_cash)
        self._realized_pnl = 0.0
        self._positions: dict[str, _Position] = {}
        self._pending_orders: list[_PendingOrder] = []
        self._next_order_number = 1
        self._current_datetime: pd.Timestamp | None = None

    # --- Time ---

    @property
    def current_datetime(self) -> pd.Timestamp | None:
        return self._current_datetime

    def get_now(self) -> pd.Timestamp:
        if self._current_datetime is None:
            raise MyValueError(
                "StubBrokerClient has no current datetime yet, call advance_to first."
            )
        return self._current_datetime

    def advance_to(self, new_datetime: datetime) -> None:
        """
        Moves the clock to the next bar datetime, charges the day's margin
        interest on open shorts, then matches the orders placed on previous days
        against the bars of new_datetime.
        """
        new_datetime = pd.Timestamp(new_datetime)
        if (
            self._current_datetime is not None
            and new_datetime <= self._current_datetime
        ):
            raise MyValueError(
                "StubBrokerClient can only move forward in time.",
                current_datetime=self._current_datetime,
                new_datetime=new_datetime,
            )

        self._current_datetime = new_datetime
        self._charge_margin_interest()
        self._match_pending_orders()

    # --- BrokerClient ---

    def get_name(self) -> str:
        return f"stub({self._fee_broker.get_name()})"

    def calculate_fees(
        self, shares: float, price: float, trade_type: TradeType
    ) -> float:
        return self._fee_broker.calculate_fees(
            shares=shares, price=price, trade_type=trade_type
        )

    def calculate_margin_interest(
        self, margin_amount: float, duration_days: int
    ) -> float:
        return self._fee_broker.calculate_margin_interest(
            margin_amount=margin_amount, duration_days=duration_days
        )

    def get_assets(self) -> MarketAssets:
        long_value = 0.0
        short_value = 0.0
        unrealized_pnl = 0.0

        for position in self._positions.values():
            price = self._get_mark_price(position)
            value = position.quantity * price
            if position.trade_type == TradeType.LONG:
                long_value += value
                unrealized_pnl += (price - position.average_cost) * position.quantity
            else:
                short_value += value
                unrealized_pnl += (position.average_cost - price) * position.quantity

        cash_available = self._get_cash_available()

        return MarketAssets(
            net_liquidation=self._cash_balance + long_value - short_value,
            cash_balance=self._cash_balance,
            cash_available_for_trading=cash_available,
            buying_power=max(cash_available, 0.0),
            gross_position_value=long_value + short_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self._realized_pnl,
        )

    def get_positions(self) -> list[MarketPosition]:
        """Shorts have a negative quantity and market value, like the real brokers."""
        positions: list[MarketPosition] = []

        for position in self._positions.values():
            price = self._get_mark_price(position)
            sign = 1 if position.trade_type == TradeType.LONG else -1
            positions.append(
                MarketPosition(
                    ticker=position.ticker,
                    trade_type=position.trade_type,
                    quantity=sign * position.quantity,
                    average_cost=position.average_cost,
                    market_value=sign * position.quantity * price,
                    unrealized_pnl=sign
                    * (price - position.average_cost)
                    * position.quantity,
                    realized_pnl=position.realized_pnl,
                )
            )

        return positions

    def get_orders(self) -> list[MarketOrder]:
        """Orders that have been placed and not matched yet."""
        return [
            MarketOrder(
                order_id=order.order_id,
                ticker=order.ticker,
                action=order.action,
                order_type=order.order_type,
                quantity=order.quantity,
                filled_quantity=0.0,
                avg_fill_price=0.0,
                fees=0.0,
                submitted_at=order.submitted_at,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
                status=ORDER_STATUS_SUBMITTED,
            )
            for order in self._pending_orders
        ]

    def place_limit_order(
        self, ticker: Ticker, quantity: int, action: Action, limit_price: float
    ) -> str:
        return self._place_order(
            ticker=ticker,
            action=action,
            order_type=OrderType.LMT,
            quantity=quantity,
            limit_price=limit_price,
        )

    def place_stop_order(
        self, ticker: Ticker, quantity: int, action: Action, stop_price: float
    ) -> str:
        return self._place_order(
            ticker=ticker,
            action=action,
            order_type=OrderType.STP,
            quantity=quantity,
            stop_price=stop_price,
        )

    def get_market_data(
        self,
        ticker: Ticker,
        begin_time: datetime,
        end_time: datetime,
        period: MarketBarPeriod = MarketBarPeriod.DAY,
    ) -> pd.DataFrame:
        """Returns the bars between begin_time and end_time, never later than the current datetime."""
        if period != MarketBarPeriod.DAY:
            raise MyValueError(
                "StubBrokerClient only has daily bars.", period=period, ticker=ticker
            )

        bars = self._bars.get(str(ticker))
        if bars is None or self._current_datetime is None:
            return pd.DataFrame()

        last_time = min(pd.Timestamp(end_time), self._current_datetime)
        start = bars.times.searchsorted(pd.Timestamp(begin_time), side="left")
        stop = bars.times.searchsorted(last_time, side="right")
        return bars.frame.iloc[start:stop].copy()

    # --- Orders ---

    def _place_order(
        self,
        ticker: Ticker,
        action: Action,
        order_type: OrderType,
        quantity: float,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> str:
        if quantity <= 0:
            raise MyValueError(
                "Order quantity must be positive.", ticker=ticker, quantity=quantity
            )

        order = _PendingOrder(
            order_id=f"stub-{self._next_order_number}",
            ticker=str(ticker),
            action=action,
            order_type=order_type,
            quantity=quantity,
            submitted_at=self.get_now(),
            limit_price=limit_price,
            stop_price=stop_price,
        )
        self._next_order_number += 1
        self._pending_orders.append(order)

        return order.order_id

    def _match_pending_orders(self) -> None:
        orders, self._pending_orders = self._pending_orders, []

        for order in orders:
            bar = self._get_current_bar(order.ticker)
            if bar is None:
                continue

            fill_price = self._get_fill_price(order, bar)
            if fill_price is None:
                continue

            self._fill_order(order, fill_price)

    @staticmethod
    def _get_fill_price(order: _PendingOrder, bar: pd.Series) -> float | None:
        high = bar[Indicator.HIGH]
        low = bar[Indicator.LOW]

        if order.order_type == OrderType.LMT:
            traded_through = (
                low <= order.limit_price
                if order.action == Action.BUY
                else high >= order.limit_price
            )
            return order.limit_price if traded_through else None

        if order.order_type == OrderType.STP:
            traded_through = (
                high >= order.stop_price
                if order.action == Action.BUY
                else low <= order.stop_price
            )
            return order.stop_price if traded_through else None

        raise MyValueError("Unsupported order type", order=order)

    def _fill_order(self, order: _PendingOrder, price: float) -> None:
        position = self._positions.get(order.ticker)
        order_trade_type = (
            TradeType.LONG if order.action == Action.BUY else TradeType.SHORT
        )
        is_closing = position is not None and position.trade_type != order_trade_type

        if is_closing:
            self._close_position(position, order.quantity, price)
        elif order.order_type == OrderType.LMT:
            self._open_position(order, order_trade_type, price)
        # A stop order is only there to close a position, otherwise it is rejected

    def _open_position(
        self, order: _PendingOrder, trade_type: TradeType, price: float
    ) -> None:
        qty = order.quantity
        fees = self.calculate_fees(shares=qty, price=price, trade_type=trade_type)

        if price * qty + fees > self._get_cash_available():
            return  # Rejected for insufficient buying power

        position = self._positions.get(order.ticker)
        if position is None:
            position = _Position(
                ticker=order.ticker,
                trade_type=trade_type,
                quantity=qty,
                average_cost=price,
            )
            self._positions[order.ticker] = position
        else:
            total_qty = position.quantity + qty
            position.average_cost = (
                position.average_cost * position.quantity + price * qty
            ) / total_qty
            position.quantity = total_qty

        if trade_type == TradeType.LONG:
            self._cash_balance -= price * qty + fees
        else:
            self._cash_balance += price * qty - fees

        position.realized_pnl -= fees
        self._realized_pnl -= fees

    def _close_position(self, position: _Position, quantity: float, price: float):
        qty = min(quantity, position.quantity)
        fees = self.calculate_fees(
            shares=qty, price=price, trade_type=position.trade_type
        )

        if position.trade_type == TradeType.LONG:
            gross_pnl = (price - position.average_cost) * qty
            self._cash_balance += price * qty - fees
        else:
            gross_pnl = (position.average_cost - price) * qty
            self._cash_balance -= price * qty + fees

        position.realized_pnl += gross_pnl - fees
        self._realized_pnl += gross_pnl - fees

        position.quantity -= qty
        if math.isclose(position.quantity, 0, abs_tol=1e-9):
            del self._positions[position.ticker]

    # --- Account ---

    def _get_short_proceeds(self) -> float:
        return sum(
            position.average_cost * position.quantity
            for position in self._positions.values()
            if position.trade_type == TradeType.SHORT
        )

    def _get_cash_available(self) -> float:
        # The proceeds of shorts are locked, and the short consumes as much again
        return self._cash_balance - 2 * self._get_short_proceeds()

    def _charge_margin_interest(self) -> None:
        for position in self._positions.values():
            if position.trade_type != TradeType.SHORT:
                continue

            interest = self.calculate_margin_interest(
                margin_amount=position.average_cost * position.quantity,
                duration_days=1,
            )
            self._cash_balance -= interest
            position.realized_pnl -= interest
            self._realized_pnl -= interest

    # --- Market data ---

    def _get_current_bar(self, ticker: str) -> pd.Series | None:
        bars = self._bars.get(ticker)
        if bars is None:
            return None

        index = bars.times.searchsorted(self._current_datetime, side="left")
        if index >= len(bars.times) or bars.times[index] != self._current_datetime:
            return None

        return bars.frame.iloc[index]

    def _get_mark_price(self, position: _Position) -> float:
        """Latest close up to the current datetime, or the average cost if there is none."""
        bars = self._bars.get(position.ticker)
        if bars is None:
            return position.average_cost

        index = bars.times.searchsorted(self._current_datetime, side="right") - 1
        if index < 0:
            return position.average_cost

        return float(bars.frame[Indicator.CLOSE].iloc[index])

    def __str__(self) -> str:
        return (
            f"StubBrokerClient ({self.get_name()}, "
            f"tickers={len(self._bars)}, "
            f"current_datetime={self._current_datetime})"
        )
