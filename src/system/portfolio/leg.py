import math
from datetime import datetime

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import TradeType
from custom_types.sector import Sector
from custom_types.ticker import Ticker
from system.indicator.indicator_types import Indicator
from util.datetime_util import format_date
from util.trading_util import TICKER_TO_SECTOR


class Leg:
    def __init__(
        self,
        # Campaign information
        campaign_id: str,
        leg_number: int,
        ticker: Ticker,
        trade_type: TradeType,
        # Leg information
        entry_price: float,
        entry_datetime: datetime,
        trading_fees: float,
        qty: float,
        stop_price: float,
    ) -> None:
        self.campaign_id = campaign_id
        self.leg_number = leg_number
        self.ticker = ticker
        self.trade_type = trade_type

        self.entry_price = entry_price
        self.entry_datetime = entry_datetime
        self.trading_fees = trading_fees

        self.initial_qty = qty
        self.initial_stop_price = stop_price

        self.risk_per_share = abs(entry_price - stop_price)
        self.initial_risk = self.risk_per_share * qty
        if self.initial_risk <= 0:
            raise MyValueError(
                "Leg's initial risk must be positive",
                campaign_id=campaign_id,
                entry_price=entry_price,
                stop_price=stop_price,
                qty=qty,
            )

        self.current_qty = qty
        self.current_stop_price = stop_price
        self.current_price = entry_price
        self.current_absolute_profit = -trading_fees
        self.current_profit_in_r = -trading_fees / self.initial_risk
        self.current_datetime = entry_datetime

        self.peak_absolute_profit = self.current_absolute_profit
        self.peak_profit_in_r = self.current_profit_in_r
        self.peak_profit_datetime = entry_datetime

        self.is_open = True
        self.sector = TICKER_TO_SECTOR.get(ticker, Sector.UNKNOWN)
        self.leg_id = f"leg_{ticker}_{leg_number}_{format_date(date=entry_datetime)}"

        self.exit_datetime = None
        self.avg_exit_price = 0.0
        self.absolute_profit = 0.0
        self.profit_in_r = 0.0
        self.margin_fees = 0.0

    @property
    def current_value(self) -> float:
        return self.current_qty * self.current_price

    @property
    def duration_days(self) -> float:
        end_time = self.exit_datetime if not self.is_open else self.current_datetime
        return (end_time - self.entry_datetime).days

    @property
    def duration_months(self) -> float:
        return self.duration_days / 30.0

    # Returns [Absolute profit, Profit in R]
    def calculate_profit(
        self, current_price: float, qty: float | None = None
    ) -> tuple[float, float]:
        if qty is None:
            qty = self.current_qty

        current_value = qty * current_price
        initial_value = qty * self.entry_price

        if self.trade_type == TradeType.LONG:
            absolute_profit = current_value - initial_value - self.trading_fees
        else:
            absolute_profit = initial_value - current_value - self.trading_fees

        profit_in_r = absolute_profit / self.initial_risk

        return absolute_profit, profit_in_r

    def update_with_current_bar(
        self, current_bar: pd.Series, broker: BrokerClient
    ) -> None:
        current_price = current_bar[Indicator.CLOSE]
        current_datetime = current_bar[Indicator.DATETIME]

        self.current_price = current_price
        self.current_datetime = current_datetime
        self.current_absolute_profit, self.current_profit_in_r = self.calculate_profit(
            current_price=current_price
        )

        if self.current_absolute_profit > self.peak_absolute_profit:
            self.peak_absolute_profit = self.current_absolute_profit
            self.peak_profit_in_r = self.current_profit_in_r
            self.peak_profit_datetime = current_datetime

        if self.trade_type == TradeType.SHORT:
            self.margin_fees += broker.get_margin_interest(
                margin_amount=self.initial_qty * self.entry_price,
                duration_days=1,
            )

    def move_stop(self, new_stop_price: float) -> float:
        self.current_stop_price = new_stop_price
        return self.current_stop_price

    def _update_exit_profits(
        self, exit_price: float, exit_qty: float, exit_datetime: datetime
    ) -> None:
        absolute_profit, profit_in_r = self.calculate_profit(
            current_price=exit_price, qty=exit_qty
        )
        self.absolute_profit += absolute_profit
        self.profit_in_r += profit_in_r
        self.exit_datetime = exit_datetime
        self.avg_exit_price += (exit_price * exit_qty) / self.initial_qty

    def _close(self) -> None:
        self.is_open = False

    def sell_qty(
        self,
        qty: float,
        exit_datetime: datetime,
        exit_price: float,
    ) -> None:
        self._update_exit_profits(
            exit_price=exit_price,
            exit_qty=qty,
            exit_datetime=exit_datetime,
        )
        self.current_qty -= qty

        if math.isclose(self.current_qty, 0):
            self._close()

    def __str__(self) -> str:
        return (
            f"Leg("
            f"campaign_id={self.campaign_id}, "
            f"leg_id={self.leg_id}, "
            f"leg_number={self.leg_number}, "
            f"ticker={self.ticker}, "
            f"sector={self.sector}, "
            f"trade_type={self.trade_type}, "
            f"is_open={self.is_open}, "
            f"entry_datetime={self.entry_datetime.isoformat()}, "
            f"entry_price={self.entry_price:.3f}, "
            f"initial_qty={self.initial_qty:.3f}, "
            f"initial_stop_price={self.initial_stop_price:.3f}, "
            f"current_stop_price={self.current_stop_price:.3f}, "
            f"current_price={self.current_price:.3f}, "
            f"current_qty={self.current_qty:.3f}, "
            f"current_absolute_profit={self.current_absolute_profit:.3f}, "
            f"current_profit_in_r={self.current_profit_in_r:.3f}, "
            f"trading_fees={self.trading_fees:.3f}, "
            f"margin_fees={self.margin_fees:.3f}, "
            f"risk_per_share={self.risk_per_share:.3f}, "
            f"initial_risk={self.initial_risk:.3f}, "
            f"peak_absolute_profit={self.peak_absolute_profit:.3f}, "
            f"peak_profit_in_r={self.peak_profit_in_r:.3f}, "
            f"peak_profit_datetime={self.peak_profit_datetime.isoformat()}, "
            f"exit_datetime={self.exit_datetime.isoformat() if self.exit_datetime else None}, "
            f"exit_price={self.avg_exit_price:.3f}, "
            f"absolute_profit={self.absolute_profit:.3f}, "
            f"profit_in_r={self.profit_in_r:.3f}"
            f")"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Leg):
            return NotImplemented

        return (
            self.campaign_id == other.campaign_id
            and self.leg_id == other.leg_id
            and self.leg_number == other.leg_number
            and self.ticker == other.ticker
            and self.sector == other.sector
            and self.trade_type == other.trade_type
            and self.entry_datetime == other.entry_datetime
            and self.current_qty == other.current_qty
            and self.entry_price == other.entry_price
            and self.risk_per_share == other.risk_per_share
            and self.initial_risk == other.initial_risk
            and self.trading_fees == other.trading_fees
            and self.margin_fees == other.margin_fees
            and self.initial_stop_price == other.initial_stop_price
            and self.is_open == other.is_open
            and self.current_stop_price == other.current_stop_price
            and self.current_price == other.current_price
            and self.current_absolute_profit == other.current_absolute_profit
            and self.current_profit_in_r == other.current_profit_in_r
            and self.peak_absolute_profit == other.peak_absolute_profit
            and self.peak_profit_in_r == other.peak_profit_in_r
            and self.peak_profit_datetime == other.peak_profit_datetime
            and self.exit_datetime == other.exit_datetime
            and self.avg_exit_price == other.avg_exit_price
            and self.absolute_profit == other.absolute_profit
            and self.profit_in_r == other.profit_in_r
        )
