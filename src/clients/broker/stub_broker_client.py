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
from util.market_data_util import process_market_data

ORDER_STATUS_SUBMITTED = "SUBMITTED"


@dataclass
class TickerBars:
    frame: pd.DataFrame
    times: pd.DatetimeIndex


class StubBrokerClient(BrokerClient):
    def __init__(
        self,
        market_data: pd.DataFrame,
        initial_cash: float,
        fee_broker: BrokerClient,
        start_datetime: datetime | None = None,
    ) -> None:
        process_market_data(market_data)

        self.bars: dict[str, TickerBars] = {}
        for ticker, ticker_df in market_data.groupby(Indicator.TICKER):
            ticker_df = ticker_df.sort_values(Indicator.DATETIME).reset_index(drop=True)
            self.bars[str(ticker)] = TickerBars(
                frame=ticker_df,
                times=pd.DatetimeIndex(ticker_df[Indicator.DATETIME]),
            )

        self.datetimes = pd.DatetimeIndex(
            market_data[Indicator.DATETIME].drop_duplicates().sort_values()
        )
        first_index = (
            0
            if start_datetime is None
            else self.datetimes.searchsorted(pd.Timestamp(start_datetime), side="left")
        )
        if first_index >= len(self.datetimes):
            raise MyValueError(
                "Market data has no bars from the start datetime",
                start_datetime=start_datetime,
            )

        self.fee_broker = fee_broker
        self.assets = MarketAssets(
            net_liquidation=initial_cash,
            cash_balance=initial_cash,
            cash_available_for_trading=initial_cash,
            buying_power=initial_cash,
            gross_position_value=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )
        self.positions: dict[Ticker, MarketPosition] = {}
        self.pending_orders: list[MarketOrder] = []
        self.next_order_number = 1
        self.current_index = int(first_index)
        self.current_datetime: pd.Timestamp = self.datetimes[self.current_index]

    def get_name(self) -> str:
        return "stub broker client"

    def get_trading_fees(
        self, shares: float, price: float, trade_type: TradeType
    ) -> float:
        return self.fee_broker.get_trading_fees(
            shares=shares, price=price, trade_type=trade_type
        )

    def get_margin_interest(self, margin_amount: float, duration_days: int) -> float:
        return self.fee_broker.get_margin_interest(
            margin_amount=margin_amount, duration_days=duration_days
        )

    def get_assets(self) -> MarketAssets:
        return self.assets

    def get_positions(self) -> list[MarketPosition]:
        return list(self.positions.values())

    def get_orders(self) -> list[MarketOrder]:
        return self.pending_orders

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

        order = MarketOrder(
            order_id=f"stub-{self.next_order_number}",
            ticker=str(ticker),
            action=action,
            order_type=order_type,
            quantity=quantity,
            filled_quantity=0.0,
            avg_fill_price=0.0,
            fees=0.0,
            submitted_at=self.current_datetime,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        self.next_order_number += 1
        self.pending_orders.append(order)

        return order.order_id

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

        bars = self.bars.get(str(ticker))
        if bars is None:
            return pd.DataFrame()

        last_time = min(pd.Timestamp(end_time), self.current_datetime)
        start = bars.times.searchsorted(pd.Timestamp(begin_time), side="left")
        stop = bars.times.searchsorted(last_time, side="right")
        return bars.frame.iloc[start:stop].copy()

    def advance(self) -> None:
        if self.current_index + 1 >= len(self.datetimes):
            return

        self.current_index += 1
        self.current_datetime = self.datetimes[self.current_index]
        self._charge_margin_interest()
        self._process_pending_orders()
        self._update_positions()

    def _update_cash(self, cash_available: float, cash_balance: float) -> None:
        self.assets.cash_available_for_trading += cash_available
        self.assets.cash_balance += cash_balance
        self.assets.buying_power = max(self.assets.cash_available_for_trading, 0.0)

    def _charge_margin_interest(self) -> None:
        for position in self.positions.values():
            if position.trade_type != TradeType.SHORT:
                continue

            interest = self.get_margin_interest(
                margin_amount=position.average_cost * position.quantity,
                duration_days=1,
            )

            self._update_cash(cash_available=-interest, cash_balance=-interest)
            position.realized_pnl -= interest
            self.assets.realized_pnl -= interest

    def _process_pending_orders(self) -> None:
        for order in self.pending_orders:
            bar = self._get_current_bar(order.ticker)
            if bar is None:
                continue

            fill_price = self._get_fill_price(order, bar)
            if fill_price is None:
                continue

            self._fill_order(order, fill_price)

        self.pending_orders = []

    def _get_fill_price(self, order: MarketOrder, bar: pd.Series) -> float | None:
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

    def _fill_order(self, order: MarketOrder, price: float) -> None:
        position = self.positions.get(order.ticker)
        trade_type = TradeType.LONG if order.action == Action.BUY else TradeType.SHORT

        if position is not None and position.trade_type != trade_type:
            self._close_position(position, order.quantity, price)
        elif order.order_type == OrderType.LMT:
            # Opens a position, or adds to the one held in the same direction
            self._open_position(order, trade_type, price)
        # A stop order is only there to close a position, otherwise it is rejected

    def _open_position(
        self, order: MarketOrder, trade_type: TradeType, price: float
    ) -> None:
        trading_fees = self.get_trading_fees(
            shares=order.quantity,
            price=price,
            trade_type=trade_type,
        )
        market_value = price * order.quantity

        if market_value + trading_fees > self.assets.cash_available_for_trading:
            return  # Rejected for insufficient buying power

        position = self.positions.get(order.ticker)
        if position is None:
            self.positions[order.ticker] = MarketPosition(
                ticker=order.ticker,
                trade_type=trade_type,
                quantity=order.quantity,
                average_cost=price,
                market_value=market_value,
                unrealized_pnl=0.0,
                realized_pnl=-trading_fees,
            )
        else:
            total_quantity = position.quantity + order.quantity
            position.average_cost = (
                position.average_cost * position.quantity + market_value
            ) / total_quantity
            position.quantity = total_quantity
            position.realized_pnl -= trading_fees

        self._update_cash(
            cash_available=-(market_value + trading_fees),
            cash_balance=-trading_fees
            - (market_value if trade_type == TradeType.LONG else 0.0),
        )
        self.assets.realized_pnl -= trading_fees

    def _close_position(
        self, position: MarketPosition, quantity: float, price: float
    ) -> None:
        qty = min(quantity, position.quantity)
        trading_fees = self.get_trading_fees(
            shares=qty,
            price=price,
            trade_type=position.trade_type,
        )

        if position.trade_type == TradeType.LONG:
            gross_pnl = (price - position.average_cost) * qty
            self._update_cash(
                cash_available=price * qty - trading_fees,
                cash_balance=price * qty - trading_fees,
            )
        else:
            gross_pnl = (position.average_cost - price) * qty
            # The value of the short goes back to the available cash
            self._update_cash(
                cash_available=position.average_cost * qty + gross_pnl - trading_fees,
                cash_balance=gross_pnl - trading_fees,
            )

        position.quantity -= qty
        position.realized_pnl += gross_pnl - trading_fees
        self.assets.realized_pnl += gross_pnl - trading_fees

        if math.isclose(position.quantity, 0, abs_tol=1e-9):
            del self.positions[position.ticker]

    def _update_positions(self) -> None:
        """Values the positions at the latest close and refreshes the assets that depend on it."""
        assets = self.assets
        assets.gross_position_value = 0.0
        assets.unrealized_pnl = 0.0
        # Longs are worth their market value, shorts only their profit or loss
        assets.net_liquidation = assets.cash_balance

        for position in self.positions.values():
            price = self._get_market_price(position)
            position.market_value = position.quantity * price

            if position.trade_type == TradeType.LONG:
                position.unrealized_pnl = (
                    price - position.average_cost
                ) * position.quantity
                assets.net_liquidation += position.market_value
            else:
                position.unrealized_pnl = (
                    position.average_cost - price
                ) * position.quantity
                assets.net_liquidation += position.unrealized_pnl

            assets.gross_position_value += position.market_value
            assets.unrealized_pnl += position.unrealized_pnl

    def _get_current_bar(self, ticker: str) -> pd.Series | None:
        bars = self.bars.get(ticker)
        if bars is None:
            return None

        index = bars.times.searchsorted(self.current_datetime, side="left")
        if index >= len(bars.times) or bars.times[index] != self.current_datetime:
            return None

        return bars.frame.iloc[index]

    def _get_market_price(self, position: MarketPosition) -> float:
        current_bar = self._get_current_bar(position.ticker)
        if current_bar is None:
            return position.average_cost

        return current_bar[Indicator.CLOSE]

    def __str__(self) -> str:
        return (
            f"StubBrokerClient ({self.get_name()}, "
            f"tickers={len(self.bars)}, "
            f"current_datetime={self.current_datetime})"
        )
