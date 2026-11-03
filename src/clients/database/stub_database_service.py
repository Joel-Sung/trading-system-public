from clients.database.database_service import DatabaseService
from system.portfolio.portfolio import Portfolio


class StubDatabaseService(DatabaseService):
    """
    In-memory DatabaseService for backtests. Holds the portfolio as a property
    and hands it back as-is; no database client, files or mappers are involved.
    """

    PORTFOLIO_FILE_NAME = ""
    CAMPAIGN_FILE_NAME = ""
    LEG_FILE_NAME = ""

    def __init__(self) -> None:
        self.portfolio: Portfolio | None = None

    def save_portfolio(
        self,
        portfolio: Portfolio,
        portfolio_file_name: str = PORTFOLIO_FILE_NAME,
        campaign_file_name: str = CAMPAIGN_FILE_NAME,
        leg_file_name: str = LEG_FILE_NAME,
    ) -> None:
        self.portfolio = portfolio

    def get_portfolio(
        self,
        portfolio_file_name: str = PORTFOLIO_FILE_NAME,
        campaign_file_name: str = CAMPAIGN_FILE_NAME,
        leg_file_name: str = LEG_FILE_NAME,
    ) -> Portfolio | None:
        return self.portfolio

    def __str__(self) -> str:
        return "Stub Database Service"
