from datetime import datetime

import pytest
from clients.database.database_service import DatabaseService
from custom_types.market import TradeType
from custom_types.ticker import Ticker
from system.portfolio.portfolio import Portfolio


def assert_round_trip(database_service: DatabaseService, portfolio: Portfolio):
    database_service.save_portfolio(portfolio)

    retrieved = database_service.get_portfolio()

    assert retrieved is not None
    assert retrieved == portfolio


def test_get_portfolio_returns_none_when_nothing_stored(
    database_service: DatabaseService,
):
    assert database_service.get_portfolio() is None


def test_empty_portfolio_round_trip(database_service: DatabaseService):
    assert_round_trip(database_service, Portfolio(initial_equity=10_000.0))


def test_portfolio_with_custom_cash_round_trip(database_service: DatabaseService):
    portfolio = Portfolio(
        initial_equity=10_000.0,
        cash_balance=8_500.5,
        cash_available_for_trading=7_250.25,
    )

    assert_round_trip(database_service, portfolio)


@pytest.mark.parametrize(
    ("trade_type", "entry_price", "stop_price"),
    [
        (TradeType.LONG, 100.0, 90.0),
        (TradeType.SHORT, 200.0, 210.0),
    ],
)
def test_portfolio_with_open_campaign_round_trip(
    database_service: DatabaseService, add_leg, trade_type, entry_price, stop_price
):
    portfolio = Portfolio(initial_equity=10_000.0)
    add_leg(
        portfolio,
        Ticker.AAPL,
        trade_type=trade_type,
        entry_price=entry_price,
        stop_price=stop_price,
    )

    assert_round_trip(database_service, portfolio)


def test_portfolio_with_multiple_campaigns_and_legs_round_trip(
    database_service: DatabaseService, add_leg
):
    portfolio = Portfolio(initial_equity=50_000.0)
    add_leg(portfolio, Ticker.AAPL)
    add_leg(portfolio, Ticker.AAPL, entry_price=105.0, stop_price=95.0)
    add_leg(
        portfolio,
        Ticker.NVDA,
        trade_type=TradeType.SHORT,
        entry_price=200.0,
        stop_price=210.0,
    )

    assert_round_trip(database_service, portfolio)


def test_portfolio_with_closed_campaign_round_trip(
    database_service: DatabaseService, add_leg
):
    portfolio = Portfolio(initial_equity=10_000.0)
    add_leg(portfolio, Ticker.AAPL, qty=10.0)
    portfolio.sell_campaign_qty(
        campaign=portfolio.get_open_campaign(Ticker.AAPL),
        qty=10.0,
        exit_price=110.0,
        exit_datetime=datetime(2026, 1, 20, 15, 0),
    )
    add_leg(portfolio, Ticker.NVDA, entry_price=200.0, stop_price=190.0)

    assert len(portfolio.closed_trade_campaigns) == 1
    assert len(portfolio.open_trade_campaigns) == 1
    assert_round_trip(database_service, portfolio)


def test_save_portfolio_writes_csv_files(
    database_service: DatabaseService, add_leg, tmp_path
):
    portfolio = Portfolio(initial_equity=10_000.0)
    add_leg(portfolio, Ticker.AAPL)

    database_service.save_portfolio(portfolio)

    for file_name in (
        DatabaseService.PORTFOLIO_FILE_NAME,
        DatabaseService.CAMPAIGN_FILE_NAME,
        DatabaseService.LEG_FILE_NAME,
    ):
        assert (tmp_path / file_name).is_file()


def test_save_portfolio_overwrites_previous_state(
    database_service: DatabaseService, add_leg
):
    first = Portfolio(initial_equity=10_000.0)
    add_leg(first, Ticker.AAPL)
    database_service.save_portfolio(first)

    second = Portfolio(initial_equity=20_000.0)
    database_service.save_portfolio(second)

    assert database_service.get_portfolio() == second
