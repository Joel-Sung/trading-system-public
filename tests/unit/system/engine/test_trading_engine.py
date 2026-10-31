import logging
from unittest.mock import MagicMock

import pandas as pd
from custom_types.market import Action, OrderType
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker
from system.engine.trading_engine import TradingEngine
from system.portfolio.portfolio import Portfolio


def make_engine(strategy=None, logger=None) -> TradingEngine:
    return TradingEngine(
        broker_service=MagicMock(),
        strategy=strategy or MagicMock(),
        database_service=MagicMock(),
        logger=logger,
    )


def test_save_portfolio_delegates_to_database_service():
    portfolio = Portfolio(initial_equity=10_000.0)
    engine = make_engine()

    engine._save_portfolio(portfolio)

    engine.database_service.save_portfolio.assert_called_once_with(portfolio)


def test_save_portfolio_data_matches_get_portfolio(database_service, add_leg):
    portfolio = Portfolio(initial_equity=10_000.0)
    add_leg(portfolio, Ticker.AAPL)
    engine = make_engine()
    engine.database_service = database_service

    engine._save_portfolio(portfolio)

    assert engine._get_portfolio_data() == portfolio


def test_create_orders_returns_position_manager_orders_for_prepared_bars():
    bars = pd.DataFrame({"ticker": [Ticker.AAPL], "close": [100.0]})
    prepared_bars = bars.assign(indicator=1.0)
    strategy = MagicMock()
    strategy.prepare_data.return_value = prepared_bars
    logger = logging.getLogger("test")
    portfolio = Portfolio(initial_equity=10_000.0)
    expected_orders = [
        SystemOrder(
            ticker=Ticker.AAPL,
            action=Action.BUY,
            order_type=OrderType.MKT,
            quantity=10.0,
            submitted_dt=pd.Timestamp("2026-01-06").to_pydatetime(),
        ),
        SystemOrder(
            ticker=Ticker.NVDA,
            action=Action.BUY,
            order_type=OrderType.MKT,
            quantity=5.0,
            submitted_dt=pd.Timestamp("2026-01-06").to_pydatetime(),
        ),
    ]
    engine = make_engine(strategy=strategy, logger=logger)
    engine.position_manager = MagicMock()
    engine.position_manager.create_system_orders.return_value = expected_orders

    orders = engine._create_orders(portfolio, bars)

    assert orders == expected_orders
    strategy.prepare_data.assert_called_once_with(bars)
    engine.position_manager.create_system_orders.assert_called_once_with(
        portfolio=portfolio, market_data=prepared_bars, logger=logger
    )
