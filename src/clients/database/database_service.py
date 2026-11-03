from clients.database import mappers
from clients.database.database_client import DatabaseClient
from system.portfolio.campaign import Campaign
from system.portfolio.leg import Leg
from system.portfolio.portfolio import Portfolio


class DatabaseService:
    """
    Interface layer between the trading engine and a DatabaseClient.
    Owns the use cases (e.g. store/retrieve portfolio state) and the names of the
    files they use, so that DatabaseClient only exposes basic storage calls.
    """

    PORTFOLIO_FILE_NAME = "system_portfolio.csv"
    CAMPAIGN_FILE_NAME = "system_campaigns.csv"
    LEG_FILE_NAME = "system_legs.csv"

    def __init__(self, database: DatabaseClient):
        self.database = database

    def save_portfolio(
        self,
        portfolio: Portfolio,
        portfolio_file_name: str = PORTFOLIO_FILE_NAME,
        campaign_file_name: str = CAMPAIGN_FILE_NAME,
        leg_file_name: str = LEG_FILE_NAME,
    ) -> None:
        self.database.save(portfolio, portfolio_file_name)
        campaigns = portfolio.open_trade_campaigns + portfolio.closed_trade_campaigns
        self.database.save(campaigns, campaign_file_name)
        legs = [l for c in campaigns for l in (c.open_legs + c.closed_legs)]
        self.database.save(legs, leg_file_name)

    def get_portfolio(
        self,
        portfolio_file_name: str = PORTFOLIO_FILE_NAME,
        campaign_file_name: str = CAMPAIGN_FILE_NAME,
        leg_file_name: str = LEG_FILE_NAME,
    ) -> Portfolio | None:
        portfolios: list[Portfolio] = self.database.load(
            portfolio_file_name, mappers.map_portfolio
        )
        if not portfolios:
            return None

        portfolio = portfolios[0]
        campaigns: list[Campaign] = self.database.load(
            campaign_file_name, mappers.map_campaign
        )
        legs: list[Leg] = self.database.load(leg_file_name, mappers.map_leg)

        # Reconstruct the portfolio -> campaigns -> legs tree
        for campaign in campaigns:
            campaign_legs = [l for l in legs if l.campaign_id == campaign.campaign_id]
            campaign.open_legs = [l for l in campaign_legs if l.is_open]
            campaign.closed_legs = [l for l in campaign_legs if not l.is_open]
            target_list = (
                portfolio.open_trade_campaigns
                if campaign.is_open
                else portfolio.closed_trade_campaigns
            )
            target_list.append(campaign)

        return portfolio

    def __str__(self) -> str:
        return f"Database Service ({self.database})"
