from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from custom_types.sector import Sector
from system.portfolio.portfolio import Portfolio
from system.portfolio.snapshot.snapshot import Snapshot


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot(Snapshot):
    timestamp: datetime

    total_equity: float
    cash_balance: float
    cash_available_for_trading: float
    position_value: float
    cam_count: int
    cam_sect_count: dict[Sector, int]

    @classmethod
    def from_portfolio(
        cls,
        portfolio: Portfolio,
        timestamp: datetime,
    ) -> "PortfolioSnapshot":
        return cls(
            timestamp=timestamp,
            total_equity=round(portfolio.total_equity, 3),
            cash_balance=round(portfolio.cash_balance, 3),
            cash_available_for_trading=round(portfolio.cash_available_for_trading, 3),
            position_value=round(portfolio.position_value, 3),
            cam_count=portfolio.cam_count,
            cam_sect_count=deepcopy(portfolio.cam_sect_count),
        )
