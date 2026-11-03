from datetime import datetime

import pytest
from clients.database.database_client import DatabaseClient
from clients.database.database_service import DatabaseService
from clients.database.stub_database_service import StubDatabaseService
from custom_types.market import TradeType
from custom_types.ticker import Ticker
from system.portfolio.portfolio import Portfolio
from util.logger import Logger


@pytest.fixture
def logger(tmp_path) -> Logger:
    return Logger(system_name="test", log_file_path=str(tmp_path / "logs" / "test.log"))


class FakeFeeBroker:
    """Fixed fees, the only parts of a broker that StubBrokerClient and BacktestEngine use."""

    TRADING_FEE = 1.0
    MARGIN_INTEREST = 0.5

    @staticmethod
    def get_name() -> str:
        return "fake"

    @staticmethod
    def get_trading_fees(shares: float, price: float, trade_type: TradeType) -> float:
        return FakeFeeBroker.TRADING_FEE

    @staticmethod
    def get_margin_interest(margin_amount: float, duration_days: int) -> float:
        return FakeFeeBroker.MARGIN_INTEREST * duration_days


@pytest.fixture
def fee_broker() -> FakeFeeBroker:
    return FakeFeeBroker()


@pytest.fixture
def database_service(tmp_path) -> DatabaseService:
    return DatabaseService(DatabaseClient(data_dir=str(tmp_path)))


@pytest.fixture
def stub_database_service() -> StubDatabaseService:
    return StubDatabaseService()


@pytest.fixture
def add_leg():
    def _add_leg(
        portfolio: Portfolio,
        ticker: Ticker,
        trade_type: TradeType = TradeType.LONG,
        entry_price: float = 100.0,
        stop_price: float = 90.0,
        qty: float = 10.0,
    ):
        order_datetime = datetime(2026, 1, 5, 9, 30)
        leg = portfolio.create_pending_leg(
            ticker=ticker,
            trade_type=trade_type,
            order_price=entry_price,
            order_qty=qty,
            order_datetime=order_datetime,
            stop_price=stop_price,
        )
        portfolio.fill_legs(
            ticker=ticker,
            qty=qty,
            fill_price=entry_price,
            fill_datetime=order_datetime,
            trading_fees=1.5,
        )
        return leg

    return _add_leg
