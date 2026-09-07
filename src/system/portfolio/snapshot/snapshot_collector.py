from datetime import datetime

from system.portfolio.portfolio import Portfolio
from system.portfolio.snapshot.campaign_snapshot import CampaignSnapshot
from system.portfolio.snapshot.leg_snapshot import LegSnapshot
from system.portfolio.snapshot.portfolio_snapshot import PortfolioSnapshot


class SnapshotCollector:
    def __init__(self) -> None:
        self.portfolio_snapshots: list[PortfolioSnapshot] = []
        self.campaign_snapshots: list[CampaignSnapshot] = []
        self.leg_snapshots: list[LegSnapshot] = []

    def collect_state(
        self,
        portfolio: Portfolio,
        timestamp: datetime,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        if is_start:
            # Collect initial portfolio state
            self.portfolio_snapshots.append(
                PortfolioSnapshot.from_portfolio(
                    portfolio=portfolio,
                    timestamp=timestamp,
                )
            )
            return

        if is_end:
            # Collect all leg states
            all_campaigns = (
                portfolio.open_trade_campaigns + portfolio.closed_trade_campaigns
            )
            for campaign in all_campaigns:
                all_legs = campaign.open_legs + campaign.closed_legs
                for leg in all_legs:
                    self.leg_snapshots.append(
                        LegSnapshot.from_leg(
                            leg=leg,
                            timestamp=timestamp,
                        )
                    )

            # Collect closed campaign states
            for campaign in portfolio.closed_trade_campaigns:
                self.campaign_snapshots.append(
                    CampaignSnapshot.from_campaign(
                        campaign=campaign,
                        timestamp=campaign.exit_datetime,
                    )
                )

            return

        # Collect portfolio state on every bar
        self.portfolio_snapshots.append(
            PortfolioSnapshot.from_portfolio(
                portfolio=portfolio,
                timestamp=timestamp,
            )
        )

        # Collect open campaign states once a month
        if timestamp.day == 1:
            for campaign in portfolio.open_trade_campaigns:
                self.campaign_snapshots.append(
                    CampaignSnapshot.from_campaign(
                        campaign=campaign,
                        timestamp=timestamp,
                    )
                )

    def __str__(self) -> str:
        return (
            "StateCollector("
            f"portfolio_states={len(self.portfolio_snapshots)}, "
            f"campaign_states={len(self.campaign_snapshots)}, "
            f"leg_states={len(self.leg_snapshots)}"
            ")"
        )
