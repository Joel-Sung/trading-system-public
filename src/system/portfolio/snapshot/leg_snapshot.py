from dataclasses import dataclass
from datetime import datetime

from custom_types.market import TradeType
from custom_types.sector import Sector
from custom_types.ticker import Ticker
from system.portfolio.leg import Leg
from system.portfolio.snapshot.snapshot import Snapshot


@dataclass(frozen=True)
class LegSnapshot(Snapshot):
    timestamp: datetime
    campaign_id: str
    leg_id: str
    leg_number: int
    ticker: Ticker
    trade_type: TradeType

    order_datetime: datetime
    order_price: float
    order_qty: float
    fill_datetime: datetime | None
    fill_price: float
    fill_qty: float
    pending_qty: float
    initial_stop_price: float
    risk_per_share: float
    initial_risk: float

    is_open: bool

    exit_datetime: datetime | None
    avg_exit_price: float
    absolute_profit: float
    profit_in_r: float
    duration_days: float
    duration_months: float

    trading_fees: float
    margin_fees: float

    peak_profit_datetime: datetime
    peak_absolute_profit: float
    peak_profit_in_r: float

    current_datetime: datetime
    current_qty: float
    current_price: float
    current_stop_price: float
    current_absolute_profit: float
    current_profit_in_r: float

    sector: Sector

    @classmethod
    def from_leg(
        cls,
        leg: Leg,
        timestamp: datetime,
    ) -> "LegSnapshot":
        return cls(
            timestamp=timestamp,
            campaign_id=leg.campaign_id,
            leg_id=leg.leg_id,
            leg_number=leg.leg_number,
            ticker=leg.ticker,
            trade_type=leg.trade_type,
            order_datetime=leg.order_datetime,
            order_price=round(leg.order_price, 3),
            order_qty=round(leg.order_qty, 3),
            fill_datetime=leg.fill_datetime,
            fill_price=round(leg.fill_price, 3),
            fill_qty=round(leg.fill_qty, 3),
            pending_qty=round(leg.pending_qty, 3),
            initial_stop_price=round(leg.initial_stop_price, 3),
            risk_per_share=round(leg.risk_per_share, 3),
            initial_risk=round(leg.initial_risk, 3),
            is_open=leg.is_open,
            exit_datetime=leg.exit_datetime,
            avg_exit_price=round(leg.avg_exit_price, 3),
            absolute_profit=round(leg.absolute_profit, 3),
            profit_in_r=round(leg.profit_in_r, 3),
            duration_days=leg.duration_days,
            duration_months=round(leg.duration_months, 3),
            trading_fees=round(leg.trading_fees, 3),
            margin_fees=round(leg.margin_fees, 3),
            peak_profit_datetime=leg.peak_profit_datetime,
            peak_absolute_profit=round(leg.peak_absolute_profit, 3),
            peak_profit_in_r=round(leg.peak_profit_in_r, 3),
            current_datetime=leg.current_datetime,
            current_qty=round(leg.current_qty, 3),
            current_price=round(leg.current_price, 3),
            current_stop_price=round(leg.current_stop_price, 3),
            current_absolute_profit=round(leg.current_absolute_profit, 3),
            current_profit_in_r=round(leg.current_profit_in_r, 3),
            sector=leg.sector,
        )
