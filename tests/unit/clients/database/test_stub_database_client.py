import pandas as pd
import pytest
from clients.database import mappers
from clients.database.database_client import DatabaseClient, FileType
from clients.database.database_service import DatabaseService
from clients.database.stub_database_client import StubDatabaseClient
from custom_types.market import TradeType
from custom_types.ticker import Ticker
from system.portfolio.portfolio import Portfolio


@pytest.fixture
def stub() -> StubDatabaseClient:
    return StubDatabaseClient()


def assert_stub_round_trip(service: DatabaseService, portfolio: Portfolio):
    service.save_portfolio(portfolio)

    retrieved = service.get_portfolio()

    assert retrieved is not None
    assert retrieved == portfolio


class TestStubDatabaseServiceRoundTrip:
    def test_get_portfolio_returns_none_when_nothing_stored(
        self, stub_database_service: DatabaseService
    ):
        assert stub_database_service.get_portfolio() is None

    def test_empty_portfolio(self, stub_database_service: DatabaseService):
        assert_stub_round_trip(stub_database_service, Portfolio(initial_equity=10_000.0))

    @pytest.mark.parametrize("trade_type", [TradeType.LONG, TradeType.SHORT])
    def test_portfolio_with_open_campaign(
        self, stub_database_service: DatabaseService, add_leg, trade_type
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL, trade_type=trade_type)

        assert_stub_round_trip(stub_database_service, portfolio)

    def test_portfolio_with_open_and_closed_campaigns(
        self, stub_database_service: DatabaseService, add_leg
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL, qty=10.0)
        portfolio.sell_ticker_qty(
            ticker=Ticker.AAPL,
            qty=10.0,
            exit_price=110.0,
            exit_datetime=pd.Timestamp("2026-01-20 15:00"),
            broker=None,
        )
        add_leg(portfolio, Ticker.NVDA, entry_price=200.0, stop_price=190.0)

        assert len(portfolio.closed_trade_campaigns) == 1
        assert len(portfolio.open_trade_campaigns) == 1
        assert_stub_round_trip(stub_database_service, portfolio)

    def test_save_portfolio_overwrites_previous_state(
        self, stub_database_service: DatabaseService, add_leg
    ):
        first = Portfolio(initial_equity=10_000.0)
        add_leg(first, Ticker.AAPL)
        stub_database_service.save_portfolio(first)

        second = Portfolio(initial_equity=20_000.0)
        stub_database_service.save_portfolio(second)

        assert stub_database_service.get_portfolio() == second

    def test_retrieved_portfolio_is_a_new_object(
        self, stub_database_service: DatabaseService, add_leg
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL)
        stub_database_service.save_portfolio(portfolio)

        retrieved = stub_database_service.get_portfolio()
        retrieved.open_trade_campaigns[0].open_legs[0].current_qty = 1.0

        assert stub_database_service.get_portfolio() == portfolio

    def test_gives_the_same_portfolio_as_the_real_client(
        self, stub_database_service: DatabaseService, database_service, add_leg
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL, trade_type=TradeType.SHORT)
        add_leg(portfolio, Ticker.NVDA, entry_price=200.0, stop_price=190.0)

        stub_database_service.save_portfolio(portfolio)
        database_service.save_portfolio(portfolio)

        assert stub_database_service.get_portfolio() == database_service.get_portfolio()


class TestStubDatabaseClient:
    def test_saved_files_hold_the_same_csv_as_the_real_client(
        self, stub: StubDatabaseClient, tmp_path, add_leg
    ):
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL)
        real = DatabaseClient(data_dir=str(tmp_path))

        for client in (stub, real):
            DatabaseService(client).save_portfolio(portfolio)

        assert sorted(stub.file_names) == sorted(p.name for p in tmp_path.iterdir())
        for file_name in stub.file_names:
            pd.testing.assert_frame_equal(
                stub._read_csv(file_name), pd.read_csv(tmp_path / file_name)
            )

    def test_saves_and_loads_a_dataframe(self, stub: StubDatabaseClient):
        df = pd.DataFrame({"ticker": ["AAPL", "NVDA"], "close": [100.5, 200.25]})

        stub.save(df, "market.csv")

        pd.testing.assert_frame_equal(stub._read_csv("market.csv"), df)
        assert stub.load("market.csv", lambda row: row["close"]) == [100.5, 200.25]

    def test_loading_a_missing_file_returns_nothing(self, stub: StubDatabaseClient):
        assert stub.load("missing.csv", mappers.map_leg) == []

    def test_loading_an_empty_list_returns_nothing(self, stub: StubDatabaseClient):
        stub.save([], "empty.csv")

        assert stub.load("empty.csv", mappers.map_leg) == []

    def test_does_not_touch_the_file_system(
        self, stub: StubDatabaseClient, tmp_path, monkeypatch, add_leg
    ):
        monkeypatch.chdir(tmp_path)
        portfolio = Portfolio(initial_equity=10_000.0)
        add_leg(portfolio, Ticker.AAPL)

        DatabaseService(stub).save_portfolio(portfolio)
        DatabaseService(stub).get_portfolio()

        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        "file_operation",
        [
            lambda client: client.backup("system_portfolio.csv"),
            lambda client: client.save("text", "evaluation.txt", FileType.TXT),
            lambda client: client.get_csv_data("source", "data.csv"),
            lambda client: client.does_raw_data_exist(Ticker.AAPL, "tiger"),
        ],
    )
    def test_rejects_operations_that_need_the_file_system(
        self, stub: StubDatabaseClient, file_operation
    ):
        with pytest.raises(NotImplementedError, match="in memory"):
            file_operation(stub)
