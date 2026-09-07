from dataclasses import dataclass
from datetime import datetime

from custom_types.market import TradeType
from custom_types.sector import Sector
from custom_types.ticker import Ticker
from system.portfolio.campaign import Campaign
from system.portfolio.snapshot.leg_snapshot import LegSnapshot
from system.portfolio.snapshot.snapshot import Snapshot


@dataclass(frozen=True)
class CampaignSnapshot(Snapshot):
    timestamp: datetime

    campaign_id: str
    ticker: Ticker
    sector: Sector
    trade_type: TradeType

    entry_datetime: datetime
    capital_invested: float

    is_open: bool

    exit_datetime: datetime | None
    capital_returned: float

    main_leg_state: LegSnapshot

    @classmethod
    def from_campaign(
        cls,
        campaign: Campaign,
        timestamp: datetime,
    ) -> "CampaignSnapshot":
        return cls(
            timestamp=timestamp,
            campaign_id=campaign.campaign_id,
            ticker=campaign.ticker,
            sector=campaign.sector,
            trade_type=campaign.trade_type,
            entry_datetime=campaign.entry_datetime,
            capital_invested=round(campaign.capital_invested, 3),
            is_open=campaign.is_open,
            exit_datetime=campaign.exit_datetime,
            capital_returned=round(campaign.capital_returned, 3),
            main_leg_state=None
            if campaign.main_leg is None
            else LegSnapshot.from_leg(campaign.main_leg, timestamp),
        )
