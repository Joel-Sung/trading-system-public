import pandas as pd
import pytest
from custom_types.market import TradeType
from custom_types.ticker import Ticker
from strategy.example_strategy import ExampleStrategy
from system.engine.backtest_engine import BacktestEngine
from system.portfolio.portfolio import Portfolio

INITIAL_EQUITY = 100_000.0
DAYS = pd.bdate_range("2026-01-05", periods=10)

# open, high, low, close
FLAT = (100.0, 101.0, 99.0, 100.0)
BARS = [
    FLAT,
    FLAT,
    FLAT,
    FLAT,
    FLAT,
    FLAT,
    (100.0, 111.0, 100.0, 110.0),  # Breakout above the rolling high: entry signal
    (110.0, 112.0, 108.0, 111.0),  # Trades down to the 110 limit price: entry fills
    (111.0, 112.0, 100.0, 101.0),  # Trades through the stop of the position
    (101.0, 102.0, 100.0, 101.0),
]
ENTRY_PRICE = 110.0
ENTRY_DAY = DAYS[7]
STOP_DAY = DAYS[8]


def make_market_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": str(Ticker.AAPL),
                "datetime": day,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000,
                "sector": "TECHNOLOGY",
            }
            for day, (open_, high, low, close) in zip(DAYS, BARS)
        ]
    )


def make_engine(tmp_path, fee_broker, **kwargs) -> BacktestEngine:
    return BacktestEngine(
        strategy=ExampleStrategy(lookback_period=2),
        broker=fee_broker,
        market_data=make_market_data(),
        portfolio=Portfolio(initial_equity=INITIAL_EQUITY),
        data_dir=str(tmp_path / "data"),
        log_dir=str(tmp_path / "logs"),
        **kwargs,
    )


def data_files(tmp_path) -> list:
    data_dir = tmp_path / "data"
    return [p for p in data_dir.rglob("*") if p.is_file()] if data_dir.exists() else []


def get_broker_datetime(engine: BacktestEngine) -> pd.Timestamp:
    bars = engine.stub_broker_client.get_market_data(
        ticker=Ticker.AAPL, begin_time=DAYS[0], end_time=DAYS[-1]
    )
    return bars["datetime"].iloc[-1]


@pytest.fixture
def engine(tmp_path, fee_broker) -> BacktestEngine:
    return make_engine(tmp_path, fee_broker)


def test_runs_the_trading_engine_once_for_every_day(engine: BacktestEngine):
    snapshots = engine._run_backtest()

    # The initial state, then one portfolio snapshot per day
    assert [s.timestamp for s in snapshots.portfolio_snapshots] == [
        DAYS[0] - pd.Timedelta(days=1),
        *DAYS,
    ]
    assert get_broker_datetime(engine) == DAYS[-1]


def test_order_placed_on_a_day_fills_on_the_next_day(engine: BacktestEngine):
    engine._run_backtest()

    portfolio = engine.trading_engine.database_service.get_portfolio()
    [campaign] = portfolio.closed_trade_campaigns
    [leg] = campaign.closed_legs
    assert campaign.ticker == Ticker.AAPL
    assert campaign.trade_type == TradeType.LONG
    # The breakout was on DAYS[6], the limit order only filled on the next bar
    assert campaign.entry_datetime == ENTRY_DAY
    assert leg.entry_price == ENTRY_PRICE
    assert campaign.exit_datetime == STOP_DAY
    assert portfolio.open_trade_campaigns == []


def test_stop_order_closes_the_position_and_the_account_matches_the_portfolio(
    engine: BacktestEngine, fee_broker
):
    engine._run_backtest()

    broker = engine.stub_broker_client
    portfolio = engine.trading_engine.database_service.get_portfolio()
    assert broker.get_positions() == []
    assert broker.get_orders() == []

    # 1% of the capital is bought at 110 and stopped out at 2% of the close below
    qty = 0.01 * INITIAL_EQUITY / ENTRY_PRICE
    stop_price = ENTRY_PRICE - 0.02 * 111.0
    expected_cash = (
        INITIAL_EQUITY + (stop_price - ENTRY_PRICE) * qty - 2 * fee_broker.TRADING_FEE
    )
    assets = broker.get_assets()
    assert assets.cash_balance == pytest.approx(expected_cash)
    assert portfolio.cash_balance == pytest.approx(expected_cash)
    assert portfolio.cash_available_for_trading == pytest.approx(expected_cash)


def test_snapshots_follow_the_equity_of_the_account(engine: BacktestEngine):
    snapshots = engine._run_backtest()

    equity_by_day = {s.timestamp: s.total_equity for s in snapshots.portfolio_snapshots}
    assert equity_by_day[DAYS[6]] == INITIAL_EQUITY
    # Bought on DAYS[7] and marked at the close of 111
    assert equity_by_day[ENTRY_DAY] != INITIAL_EQUITY
    assert snapshots.portfolio_snapshots[-1].cam_count == 0


def test_start_date_only_skips_the_days_but_not_the_history(tmp_path, fee_broker):
    engine = make_engine(tmp_path, fee_broker, start_date=DAYS[6].to_pydatetime())

    snapshots = engine._run_backtest()

    assert [s.timestamp for s in snapshots.portfolio_snapshots][1] == DAYS[6]
    # The rolling high of the breakout comes from the days before start_date
    [campaign] = engine.trading_engine.database_service.get_portfolio().closed_trade_campaigns
    assert campaign.entry_datetime == ENTRY_DAY


def test_stubs_are_created_for_every_run(engine: BacktestEngine):
    engine._run_backtest()
    first_broker = engine.stub_broker_client
    first_database = engine.stub_database_client

    engine._run_backtest()

    assert engine.stub_broker_client is not first_broker
    assert engine.stub_database_client is not first_database
    assert get_broker_datetime(engine) == DAYS[-1]


def test_daily_portfolio_is_stored_in_the_stub_without_creating_files(
    engine: BacktestEngine, tmp_path
):
    engine._run_backtest()

    assert sorted(engine.stub_database_client.file_names) == [
        "system_campaigns.csv",
        "system_legs.csv",
        "system_portfolio.csv",
    ]
    assert data_files(tmp_path) == []


def test_run_only_stores_the_results_with_the_real_client(engine: BacktestEngine, tmp_path):
    engine.run()

    stored = {p.name for p in data_files(tmp_path) if p.parent.name == "data"}
    assert stored == {
        "snaps_portfolio.csv",
        "snaps_campaigns.csv",
        "snaps_legs.csv",
        "snaps_evaluation.txt",
    }


def test_market_data_without_bars_to_run_raises(tmp_path, fee_broker):
    engine = make_engine(tmp_path, fee_broker, start_date=DAYS[-1] + pd.Timedelta(days=1))

    with pytest.raises(ValueError, match="no bars"):
        engine._run_backtest()
