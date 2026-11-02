import logging
from datetime import datetime

import pandas as pd
import pytest
from custom_types.market import MarketAssets, MarketPosition, TradeType
from custom_types.ticker import Ticker
from system.engine.align_data_handler import AlignDataHandler
from system.models.risk.example_risk_model import ExampleRiskModel
from system.portfolio.portfolio import Portfolio


class FakeBrokerService:
    def get_trading_fees(self, shares: float, price: float, trade_type: TradeType):
        return 1.0


@pytest.fixture
def handler() -> AlignDataHandler:
    return AlignDataHandler(
        strategy=ExampleRiskModel(risk_percentage=0.02),
        broker_service=FakeBrokerService(),
        logger=logging.getLogger("test"),
    )


@pytest.fixture
def market_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": [Ticker.AAPL, Ticker.AAPL, Ticker.NVDA],
            "datetime": [
                datetime(2026, 1, 5),
                datetime(2026, 1, 6),
                datetime(2026, 1, 6),
            ],
            "close": [99.0, 100.0, 200.0],
        }
    )


@pytest.fixture
def portfolio_with_two_legs(add_leg) -> Portfolio:
    """AAPL campaign with a main leg of 10 shares and a pyramid leg of 5 shares."""
    portfolio = Portfolio(initial_equity=10_000.0)
    add_leg(portfolio, Ticker.AAPL, qty=10.0)
    add_leg(portfolio, Ticker.AAPL, entry_price=105.0, stop_price=95.0, qty=5.0)
    return portfolio


def make_position(
    ticker: Ticker = Ticker.AAPL,
    quantity: float = 15.0,
    trade_type: TradeType = TradeType.LONG,
    average_cost: float = 100.0,
) -> MarketPosition:
    return MarketPosition(
        ticker=ticker,
        trade_type=trade_type,
        quantity=quantity,
        average_cost=average_cost,
        market_value=quantity * average_cost,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
    )


class TestAlignPortfolio:
    def test_creates_portfolio_from_assets_when_none(self, handler: AlignDataHandler):
        assets = MarketAssets(
            net_liquidation=25_000.0,
            cash_balance=20_000.0,
            cash_available_for_trading=18_000.0,
            buying_power=40_000.0,
            gross_position_value=5_000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )

        portfolio: Portfolio = handler.align_portfolio(
            portfolio=None,
            market_assets=assets,
        )

        assert portfolio.initial_equity == 25_000.0
        assert portfolio.cash_balance == 20_000.0
        assert portfolio.cash_available_for_trading == 18_000.0

    def test_updates_cash_of_existing_portfolio(self, handler: AlignDataHandler):
        portfolio = Portfolio(initial_equity=10_000.0)
        assets = MarketAssets(
            net_liquidation=99_999.0,
            cash_balance=7_000.0,
            cash_available_for_trading=6_000.0,
            buying_power=0.0,
            gross_position_value=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )

        result = handler.align_portfolio(portfolio=portfolio, market_assets=assets)

        assert result is portfolio
        assert result.initial_equity == 10_000.0
        assert result.cash_balance == 7_000.0
        assert result.cash_available_for_trading == 6_000.0


class TestAlignCampaigns:
    def test_creates_campaign_with_the_latest_market_bar_datetime(
        self, market_data: pd.DataFrame
    ):
        handler = AlignDataHandler(
            strategy=ExampleRiskModel(risk_percentage=0.02),
            broker_service=FakeBrokerService(),
            logger=logging.getLogger("test"),
        )
        portfolio = Portfolio(initial_equity=10_000.0)

        handler.align_campaigns(
            portfolio, [make_position(quantity=15.0)], market_data=market_data
        )

        campaign = portfolio.get_open_campaign(Ticker.AAPL)
        expected_datetime = datetime(2026, 1, 6)
        assert campaign.entry_datetime == expected_datetime
        assert campaign.open_legs[0].entry_datetime == expected_datetime

    def test_aligning_portfolio_after_campaigns_restores_broker_cash(
        self, handler: AlignDataHandler, market_data: pd.DataFrame
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        assets = MarketAssets(
            net_liquidation=10_000.0,
            cash_balance=8_500.0,
            cash_available_for_trading=8_000.0,
            buying_power=0.0,
            gross_position_value=1_500.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )

        handler.align_campaigns(
            portfolio, [make_position(quantity=15.0)], market_data=market_data
        )
        handler.align_portfolio(portfolio=portfolio, market_assets=assets)

        assert portfolio.cash_balance == 8_500.0
        assert portfolio.cash_available_for_trading == 8_000.0

    def test_closes_campaign_when_the_position_is_gone(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        portfolio_with_two_legs: Portfolio,
    ):
        handler.align_campaigns(portfolio_with_two_legs, [], market_data=market_data)

        assert portfolio_with_two_legs.open_trade_campaigns == []
        [campaign] = portfolio_with_two_legs.closed_trade_campaigns
        assert not campaign.is_open
        assert campaign.open_legs == []
        assert campaign.exit_datetime == datetime(2026, 1, 6)
        assert [leg.avg_exit_price for leg in campaign.closed_legs] == [
            pytest.approx(100.0),
            pytest.approx(100.0),
        ]

    def test_closing_campaign_only_affects_tickers_without_a_position(
        self, handler: AlignDataHandler, market_data: pd.DataFrame, add_leg
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL, qty=10.0)
        add_leg(portfolio, Ticker.NVDA, qty=5.0, entry_price=200.0, stop_price=190.0)

        handler.align_campaigns(
            portfolio,
            [make_position(ticker=Ticker.NVDA, quantity=5.0, average_cost=200.0)],
            market_data=market_data,
        )

        assert [c.ticker for c in portfolio.open_trade_campaigns] == [Ticker.NVDA]
        assert [c.ticker for c in portfolio.closed_trade_campaigns] == [Ticker.AAPL]

    def test_creates_campaign_for_untracked_position(
        self, handler: AlignDataHandler, market_data: pd.DataFrame
    ):
        portfolio = Portfolio(initial_equity=10_000.0)

        handler.align_campaigns(
            portfolio, [make_position(quantity=15.0)], market_data=market_data
        )

        campaign = portfolio.get_open_campaign(Ticker.AAPL)
        assert campaign is not None
        assert campaign.total_qty == 15.0
        leg = campaign.open_legs[0]
        assert leg.entry_price == 100.0
        assert leg.trading_fees == 1.0
        # 2% of the latest close (100.0)
        assert leg.risk_per_share == pytest.approx(2.0)
        assert leg.initial_stop_price == pytest.approx(98.0)

    def test_missing_market_data_logs_warning_without_creating_campaign(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        caplog: pytest.LogCaptureFixture,
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        position = make_position(ticker=Ticker.MSFT)

        with caplog.at_level(logging.WARNING, logger="test"):
            handler.align_campaigns(portfolio, [position], market_data=market_data)

        assert "No market data found for ticker MSFT" in caplog.text
        assert portfolio.open_trade_campaigns == []

    def test_matching_quantity_leaves_campaign_unchanged(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        portfolio_with_two_legs: Portfolio,
    ):
        handler.align_campaigns(
            portfolio_with_two_legs,
            [make_position(quantity=15.0)],
            market_data=market_data,
        )

        campaign = portfolio_with_two_legs.get_open_campaign(Ticker.AAPL)
        assert [leg.current_qty for leg in campaign.open_legs] == [10.0, 5.0]
        assert campaign.closed_legs == []

    def test_larger_position_adds_qty_to_main_leg(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        portfolio_with_two_legs: Portfolio,
    ):
        handler.align_campaigns(
            portfolio_with_two_legs,
            [make_position(quantity=18.0)],
            market_data=market_data,
        )

        campaign = portfolio_with_two_legs.get_open_campaign(Ticker.AAPL)
        assert campaign.total_qty == 18.0
        assert [leg.current_qty for leg in campaign.open_legs] == [13.0, 5.0]

    def test_smaller_position_reduces_latest_leg_without_closing_it(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        portfolio_with_two_legs: Portfolio,
    ):
        handler.align_campaigns(
            portfolio_with_two_legs,
            [make_position(quantity=12.0)],
            market_data=market_data,
        )

        campaign = portfolio_with_two_legs.get_open_campaign(Ticker.AAPL)
        assert campaign.total_qty == 12.0
        assert [leg.current_qty for leg in campaign.open_legs] == [10.0, 2.0]
        assert campaign.closed_legs == []

    def test_smaller_position_closes_latest_leg_when_qty_reaches_zero(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        portfolio_with_two_legs: Portfolio,
    ):
        handler.align_campaigns(
            portfolio_with_two_legs,
            [make_position(quantity=10.0)],
            market_data=market_data,
        )

        campaign = portfolio_with_two_legs.get_open_campaign(Ticker.AAPL)
        assert campaign.total_qty == 10.0
        assert [leg.leg_number for leg in campaign.open_legs] == [0]
        assert [leg.leg_number for leg in campaign.closed_legs] == [1]
        closed_leg = campaign.closed_legs[0]
        assert closed_leg.current_qty == 0
        assert not closed_leg.is_open
        assert closed_leg.avg_exit_price == pytest.approx(100.0)

    def test_smaller_position_carries_over_to_previous_leg(
        self,
        handler: AlignDataHandler,
        market_data: pd.DataFrame,
        portfolio_with_two_legs: Portfolio,
    ):
        handler.align_campaigns(
            portfolio_with_two_legs,
            [make_position(quantity=8.0)],
            market_data=market_data,
        )

        campaign = portfolio_with_two_legs.get_open_campaign(Ticker.AAPL)
        assert campaign.total_qty == 8.0
        assert [(leg.leg_number, leg.current_qty) for leg in campaign.open_legs] == [
            (0, 8.0)
        ]
        assert [leg.leg_number for leg in campaign.closed_legs] == [1]
        assert campaign.is_open
