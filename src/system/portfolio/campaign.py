import math
from datetime import datetime

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import TradeType
from custom_types.mode import Mode
from custom_types.sector import Sector
from custom_types.ticker import Ticker
from system.indicator.indicator_types import Indicator
from system.portfolio.leg import Leg
from util.datetime_util import format_date
from util.trading_util import TICKER_TO_SECTOR


class Campaign:
    def __init__(
        self,
        ticker: Ticker,
        trade_type: TradeType,
        entry_datetime: datetime,
        campaign_id: str | None = None,
        capital_invested: float = 0.0,
        is_open: bool = True,
        exit_datetime: datetime | None = None,
        capital_returned: float = 0.0,
        mode: Mode = Mode.NONE,
    ) -> None:
        self.campaign_id = (
            f"campaign_{ticker}_{format_date(date=entry_datetime)}"
            if campaign_id is None
            else campaign_id
        )
        self.ticker = ticker
        self.sector = TICKER_TO_SECTOR.get(ticker, Sector.UNKNOWN)
        self.trade_type = trade_type
        self.mode = mode

        self.entry_datetime = entry_datetime
        self.capital_invested = capital_invested
        self.is_open = is_open
        self.open_legs: list[Leg] = []

        self.current_datetime = entry_datetime

        self.exit_datetime: datetime | None = exit_datetime
        self.capital_returned = capital_returned
        self.closed_legs: list[Leg] = []

    @property
    def main_leg(self) -> Leg | None:
        main_trade_leg = None

        if self.is_open:
            main_trade_leg = self.open_legs[0] if len(self.open_legs) > 0 else None
        else:
            for leg in self.closed_legs:
                if leg.leg_number == 0:
                    main_trade_leg = leg
                    break

        if main_trade_leg is not None and main_trade_leg.leg_number != 0:
            raise MyValueError(
                "Wrong leg retrieved as main leg for campaign.",
                main_trade_leg=main_trade_leg,
                campaign=self,
            )

        return main_trade_leg

    @property
    def current_value(self) -> float:
        value = 0.0
        for leg in self.open_legs:
            value += leg.current_value
        return value

    @property
    def total_qty(self) -> float:
        qty = 0.0
        for leg in self.open_legs:
            qty += leg.current_qty
        return qty

    @property
    def next_leg_num(self) -> int:
        return len(self.open_legs)

    def create_leg(self, leg: Leg):
        if not self.is_open:
            raise ValueError(
                "[ERROR] Trying to add leg to closed campaign\n"
                f"campaign [{self}]\n"
                f"leg [{leg}]"
            )

        if leg.trade_type != self.trade_type:
            raise ValueError(
                "[ERROR] Trying to add leg to campaign with different trade type\n"
                f"campaign [{self}]\n"
                f"leg [{leg}]"
            )

        self.open_legs.append(leg)
        self.capital_invested += leg.entry_price * leg.current_qty + leg.trading_fees

    def change_mode(self, new_mode: Mode) -> None:
        self.mode = new_mode

    def _close_leg(self, leg: Leg) -> None:
        self.open_legs.remove(leg)
        self.closed_legs.append(leg)
        self.capital_returned += leg.avg_exit_price * leg.initial_qty - leg.margin_fees

    def _close(self, exit_datetime: datetime) -> None:
        self.is_open = False
        self.exit_datetime = exit_datetime

    # Returns margin fees of closed legs. For simplicity, margin fees are only calculated when closing a leg.
    def sell_qty(
        self,
        qty: float,
        exit_price: float,
        exit_datetime: datetime,
    ) -> float:
        if not self.is_open:
            raise MyValueError(
                "Trying to sell trade leg qty for closed campaign.",
                exit_datetime=exit_datetime,
                exit_price=exit_price,
                qty=qty,
                campaign=self,
            )

        qty_to_sell = qty
        open_legs = self.open_legs.copy()
        margin_fees = 0.0

        for leg in reversed(open_legs):
            leg_qty = leg.current_qty
            leg.sell_qty(
                qty=qty_to_sell,
                exit_datetime=exit_datetime,
                exit_price=exit_price,
            )
            if not leg.is_open:
                margin_fees += leg.margin_fees
                self._close_leg(leg=leg)

            qty_to_sell = max(0, qty_to_sell - leg_qty)
            if math.isclose(qty_to_sell, 0):
                break

        if len(self.open_legs) == 0:
            self._close(exit_datetime=exit_datetime)

        return margin_fees

    def update_with_current_bar(
        self, current_bar: pd.Series, broker: BrokerClient
    ) -> None:
        current_datetime = current_bar[Indicator.DATETIME]
        self.current_datetime = current_datetime

        for leg in self.open_legs:
            leg.update_with_current_bar(current_bar=current_bar, broker=broker)

    def __str__(self) -> str:
        return (
            f"Campaign("
            f"campaign_id={self.campaign_id}, "
            f"ticker={self.ticker}, "
            f"sector={self.sector}, "
            f"trade_type={self.trade_type}, "
            f"mode={self.mode}, "
            f"entry_datetime={self.entry_datetime.isoformat()}, "
            f"exit_datetime={self.exit_datetime.isoformat() if self.exit_datetime else None}, "
            f"is_open={self.is_open}, "
            f"capital_invested={self.capital_invested:.3f}, "
            f"capital_returned={f'{self.capital_returned:.3f}' if self.capital_returned is not None else None}, "
            f"total_qty={self.total_qty:.3f}, "
            f"open_trade_legs=[{len(self.open_legs)}], "
            f"closed_trade_legs=[{len(self.closed_legs)}]"
            f")"
        )

    def verbose_str(self) -> str:
        result = [str(self)]

        if self.open_legs:
            result.append("\nOpen Trade Legs:\n")
            for leg in self.open_legs:
                result.append(str(leg))

        if self.closed_legs:
            result.append("\nClosed Trade Legs:\n")
            for leg in self.closed_legs:
                result.append(str(leg))

        return "\n".join(result)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Campaign):
            return NotImplemented

        return (
            self.campaign_id == other.campaign_id
            and self.ticker == other.ticker
            and self.sector == other.sector
            and self.trade_type == other.trade_type
            and self.mode == other.mode
            and self.entry_datetime == other.entry_datetime
            and self.capital_invested == other.capital_invested
            and self.is_open == other.is_open
            and self.exit_datetime == other.exit_datetime
            and self.capital_returned == other.capital_returned
            and self.open_legs == other.open_legs
            and self.closed_legs == other.closed_legs
        )
