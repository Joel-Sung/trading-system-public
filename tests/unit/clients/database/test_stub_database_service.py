import pytest
from clients.database.stub_database_service import StubDatabaseService
from custom_types.market import TradeType
from custom_types.ticker import Ticker
from system.portfolio.portfolio import Portfolio


def test_get_portfolio_returns_none_when_nothing_stored(
    stub_database_service: StubDatabaseService,
):
    assert stub_database_service.get_portfolio() is None


def test_empty_portfolio_is_returned_as_is(stub_database_service: StubDatabaseService):
    portfolio = Portfolio(initial_equity=10_000.0)

    stub_database_service.save_portfolio(portfolio)

    assert stub_database_service.portfolio is portfolio
    assert stub_database_service.get_portfolio() is portfolio


@pytest.mark.parametrize("trade_type", [TradeType.LONG, TradeType.SHORT])
def test_portfolio_with_campaigns_is_not_duplicated(
    stub_database_service: StubDatabaseService, add_leg, trade_type
):
    portfolio = Portfolio(initial_equity=10_000.0)
    add_leg(portfolio, Ticker.AAPL, trade_type=trade_type)

    stub_database_service.save_portfolio(portfolio)

    retrieved = stub_database_service.get_portfolio()
    assert retrieved is portfolio
    assert len(retrieved.open_trade_campaigns) == 1


def test_save_portfolio_overwrites_previous_state(
    stub_database_service: StubDatabaseService,
):
    stub_database_service.save_portfolio(Portfolio(initial_equity=10_000.0))
    second = Portfolio(initial_equity=20_000.0)

    stub_database_service.save_portfolio(second)

    assert stub_database_service.get_portfolio() is second


def test_file_names_are_blank_and_ignored(stub_database_service: StubDatabaseService):
    portfolio = Portfolio(initial_equity=10_000.0)

    stub_database_service.save_portfolio(portfolio, "a.csv", "b.csv", "c.csv")

    assert StubDatabaseService.PORTFOLIO_FILE_NAME == ""
    assert StubDatabaseService.CAMPAIGN_FILE_NAME == ""
    assert StubDatabaseService.LEG_FILE_NAME == ""
    assert stub_database_service.get_portfolio("x.csv") is portfolio
