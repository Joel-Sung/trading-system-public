import pandas as pd
import pytest
from clients.broker.stub_broker_client import StubBrokerClient
from custom_types.exception import MyValueError
from custom_types.market import (
    Action,
    MarketBarPeriod,
    OrderType,
    TradeType,
)
from custom_types.ticker import Ticker
from util.market_data_util import format_market_data

DAYS = pd.to_datetime(
    ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
)

# Each day opens at the close of the previous one, the lows and highs set up the scenarios
BARS = [
    # open, high, low, close
    (100.0, 105.0, 95.0, 100.0),
    (100.0, 110.0, 98.0, 108.0),
    (108.0, 112.0, 90.0, 95.0),
    (95.0, 100.0, 94.0, 99.0),
    (99.0, 103.0, 97.0, 102.0),
]


def make_market_data() -> pd.DataFrame:
    rows = []
    for ticker in (Ticker.AAPL, Ticker.NVDA):
        for day, (open_, high, low, close) in zip(DAYS, BARS):
            rows.append(
                {
                    "ticker": str(ticker),
                    "datetime": day,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 1_000,
                }
            )
    return format_market_data(pd.DataFrame(rows))


@pytest.fixture
def broker(fee_broker) -> StubBrokerClient:
    return StubBrokerClient(
        market_data=make_market_data(), initial_cash=10_000.0, fee_broker=fee_broker
    )


def next_day(broker: StubBrokerClient, days: int = 1) -> None:
    for _ in range(days):
        broker.advance()


def place_limit(broker: StubBrokerClient, action: Action, qty: float, price: float):
    return broker.place_limit_order(
        ticker=Ticker.AAPL, quantity=qty, action=action, limit_price=price
    )


def place_stop(broker: StubBrokerClient, action: Action, qty: float, price: float):
    return broker.place_stop_order(
        ticker=Ticker.AAPL, quantity=qty, action=action, stop_price=price
    )


def get_last_bar_datetime(broker: StubBrokerClient) -> pd.Timestamp:
    bars = broker.get_market_data(
        ticker=Ticker.AAPL, begin_time=DAYS[0], end_time=DAYS[-1]
    )
    return bars["datetime"].iloc[-1]


class TestClock:
    def test_starts_on_the_first_datetime(self, broker: StubBrokerClient):
        assert get_last_bar_datetime(broker) == DAYS[0]

    def test_starts_on_the_first_datetime_from_the_start_datetime(self, fee_broker):
        stub = StubBrokerClient(
            market_data=make_market_data(),
            initial_cash=1_000.0,
            fee_broker=fee_broker,
            start_datetime=DAYS[2],
        )

        assert get_last_bar_datetime(stub) == DAYS[2]

    def test_start_datetime_after_the_data_is_rejected(self, fee_broker):
        with pytest.raises(MyValueError, match="no bars from the start datetime"):
            StubBrokerClient(
                market_data=make_market_data(),
                initial_cash=1_000.0,
                fee_broker=fee_broker,
                start_datetime=DAYS[-1] + pd.Timedelta(days=1),
            )

    def test_advancing_moves_to_the_next_datetime(self, broker: StubBrokerClient):
        broker.advance()

        assert get_last_bar_datetime(broker) == DAYS[1]

    def test_stays_on_the_last_datetime_and_never_fills_later_orders(
        self, broker: StubBrokerClient
    ):
        next_day(broker, len(DAYS) - 1)
        place_limit(broker, Action.BUY, 10, 100.0)

        next_day(broker)

        assert get_last_bar_datetime(broker) == DAYS[-1]
        assert broker.get_positions() == []


class TestMarketData:
    def test_returns_bars_up_to_the_current_datetime_only(
        self, broker: StubBrokerClient
    ):
        next_day(broker, 2)

        bars = broker.get_market_data(
            ticker=Ticker.AAPL,
            begin_time=DAYS[0] - pd.Timedelta(days=30),
            end_time=DAYS[4],
            period=MarketBarPeriod.DAY,
        )

        assert list(bars["datetime"]) == list(DAYS[:3])

    def test_respects_the_requested_window(self, broker: StubBrokerClient):
        next_day(broker, 3)

        bars = broker.get_market_data(
            ticker=Ticker.AAPL, begin_time=DAYS[1], end_time=DAYS[2]
        )

        assert list(bars["datetime"]) == [DAYS[1], DAYS[2]]

    def test_only_returns_the_requested_ticker(self, broker: StubBrokerClient):
        bars = broker.get_market_data(
            ticker=Ticker.NVDA, begin_time=DAYS[0], end_time=DAYS[4]
        )

        assert set(bars["ticker"]) == {"NVDA"}

    def test_unknown_ticker_has_no_bars(self, broker: StubBrokerClient):
        bars = broker.get_market_data(
            ticker=Ticker.MSFT, begin_time=DAYS[0], end_time=DAYS[4]
        )

        assert bars.empty

    def test_returned_bars_are_a_copy(self, broker: StubBrokerClient):
        bars = broker.get_market_data(
            ticker=Ticker.AAPL, begin_time=DAYS[0], end_time=DAYS[0]
        )
        bars["close"] = -1.0

        again = broker.get_market_data(
            ticker=Ticker.AAPL, begin_time=DAYS[0], end_time=DAYS[0]
        )
        assert again["close"].iloc[0] == 100.0

    def test_only_daily_bars_are_supported(self, broker: StubBrokerClient):
        with pytest.raises(MyValueError, match="only has daily bars"):
            broker.get_market_data(
                ticker=Ticker.AAPL,
                begin_time=DAYS[0],
                end_time=DAYS[1],
                period=MarketBarPeriod.HOUR,
            )

    def test_format_requires_the_ohlc_columns(self):
        with pytest.raises(MyValueError, match="essential columns"):
            format_market_data(pd.DataFrame({"ticker": ["AAPL"]}))

    def test_format_sorts_by_datetime_and_converts_strings(self):
        raw = pd.DataFrame(
            {
                "ticker": ["AAPL", "AAPL"],
                "datetime": ["2026-01-06", "2026-01-05"],
                "open": [1.0, 1.0],
                "high": [1.0, 1.0],
                "low": [1.0, 1.0],
                "close": [1.0, 1.0],
                "volume": [1, 1],
            }
        )

        formatted = format_market_data(raw)

        assert formatted["datetime"].is_monotonic_increasing
        assert pd.api.types.is_datetime64_any_dtype(formatted["datetime"])
        assert raw["datetime"].iloc[0] == "2026-01-06"


class TestAccount:
    def test_starts_with_only_cash(self, broker: StubBrokerClient):
        assets = broker.get_assets()

        assert assets.net_liquidation == 10_000.0
        assert assets.cash_balance == 10_000.0
        assert assets.cash_available_for_trading == 10_000.0
        assert assets.gross_position_value == 0.0
        assert broker.get_positions() == []
        assert broker.get_orders() == []

    def test_delegates_fees_to_the_fee_broker(self, broker: StubBrokerClient):
        assert broker.get_trading_fees(10, 100.0, TradeType.LONG) == 1.0
        assert broker.get_margin_interest(1_000.0, 2) == 1.0
        assert broker.get_name() == "stub broker client"


class TestLongOrders:
    def test_limit_order_waits_for_the_next_day(self, broker: StubBrokerClient):
        place_limit(broker, Action.BUY, 10, 100.0)

        assert broker.get_positions() == []
        assert [o.order_type for o in broker.get_orders()] == [OrderType.LMT]

    def test_limit_buy_fills_at_the_limit_price_on_the_next_day(
        self, broker: StubBrokerClient
    ):
        place_limit(broker, Action.BUY, 10, 100.0)

        next_day(broker)

        [position] = broker.get_positions()
        assert position.ticker == "AAPL"
        assert position.trade_type == TradeType.LONG
        assert position.quantity == 10
        assert position.average_cost == 100.0
        # Marked at the close of the current day, 108
        assert position.market_value == pytest.approx(1_080.0)
        assert position.unrealized_pnl == pytest.approx(80.0)
        assert position.realized_pnl == pytest.approx(-1.0)

        assets = broker.get_assets()
        assert assets.cash_balance == pytest.approx(10_000.0 - 1_000.0 - 1.0)
        assert assets.cash_available_for_trading == assets.cash_balance
        assert assets.gross_position_value == pytest.approx(1_080.0)
        assert assets.net_liquidation == pytest.approx(8_999.0 + 1_080.0)
        assert assets.unrealized_pnl == pytest.approx(80.0)
        assert assets.realized_pnl == pytest.approx(-1.0)

    def test_orders_are_matched_once_and_then_dropped(self, broker: StubBrokerClient):
        place_limit(broker, Action.BUY, 10, 100.0)

        next_day(broker)

        assert broker.get_orders() == []

    def test_unfilled_limit_order_expires(self, broker: StubBrokerClient):
        # Day 2 trades between 98 and 110
        place_limit(broker, Action.BUY, 10, 90.0)

        next_day(broker)

        assert broker.get_positions() == []
        assert broker.get_orders() == []
        assert broker.get_assets().cash_balance == 10_000.0

    def test_stop_order_closes_the_position_at_the_stop_price(
        self, broker: StubBrokerClient
    ):
        place_limit(broker, Action.BUY, 10, 100.0)
        next_day(broker)
        # Day 3 trades down to 90
        place_stop(broker, Action.SELL, 10, 96.0)

        next_day(broker)

        assert broker.get_positions() == []
        assets = broker.get_assets()
        assert assets.cash_balance == pytest.approx(
            10_000.0 - 1_000.0 - 1.0 + 960.0 - 1.0
        )
        assert assets.net_liquidation == assets.cash_balance
        # (96 - 100) * 10 less the fees of both fills
        assert assets.realized_pnl == pytest.approx(-42.0)

    def test_stop_order_that_is_not_reached_leaves_the_position(
        self, broker: StubBrokerClient
    ):
        place_limit(broker, Action.BUY, 10, 100.0)
        next_day(broker)
        # Day 3 low is 90
        place_stop(broker, Action.SELL, 10, 85.0)

        next_day(broker)

        [position] = broker.get_positions()
        assert position.quantity == 10

    def test_stop_order_can_close_part_of_the_position(self, broker: StubBrokerClient):
        place_limit(broker, Action.BUY, 10, 100.0)
        next_day(broker)
        place_stop(broker, Action.SELL, 4, 96.0)

        next_day(broker)

        [position] = broker.get_positions()
        assert position.quantity == 6
        assert position.average_cost == 100.0

    def test_stop_order_cannot_close_more_than_the_position(
        self, broker: StubBrokerClient
    ):
        place_limit(broker, Action.BUY, 10, 100.0)
        next_day(broker)
        place_stop(broker, Action.SELL, 25, 96.0)

        next_day(broker)

        assert broker.get_positions() == []
        assert broker.get_assets().cash_balance == pytest.approx(
            10_000.0 - 1_000.0 - 1.0 + 960.0 - 1.0
        )

    def test_stop_order_without_a_position_is_rejected(self, broker: StubBrokerClient):
        place_stop(broker, Action.SELL, 10, 96.0)

        next_day(broker)

        assert broker.get_positions() == []
        assert broker.get_assets().cash_balance == 10_000.0

    def test_adding_to_a_position_averages_the_cost(self, broker: StubBrokerClient):
        place_limit(broker, Action.BUY, 10, 100.0)
        next_day(broker)
        place_limit(broker, Action.BUY, 10, 110.0)

        next_day(broker)

        [position] = broker.get_positions()
        assert position.quantity == 20
        assert position.average_cost == pytest.approx(105.0)

    def test_order_without_enough_cash_is_rejected(self, fee_broker):
        stub = StubBrokerClient(
            market_data=make_market_data(), initial_cash=500.0, fee_broker=fee_broker
        )
        place_limit(stub, Action.BUY, 10, 100.0)

        next_day(stub)

        assert stub.get_positions() == []
        assert stub.get_assets().cash_balance == 500.0

    def test_order_is_not_matched_on_a_day_without_a_bar(self, fee_broker):
        data = make_market_data()
        data = data[~((data["ticker"] == "AAPL") & (data["datetime"] == DAYS[1]))]
        stub = StubBrokerClient(
            market_data=data, initial_cash=10_000.0, fee_broker=fee_broker
        )
        place_limit(stub, Action.BUY, 10, 100.0)

        next_day(stub)

        assert stub.get_positions() == []

    def test_order_quantity_must_be_positive(self, broker: StubBrokerClient):
        with pytest.raises(MyValueError, match="must be positive"):
            place_limit(broker, Action.BUY, 0, 100.0)

    def test_placing_an_order_returns_unique_ids(self, broker: StubBrokerClient):
        first = place_limit(broker, Action.BUY, 1, 100.0)
        second = place_stop(broker, Action.SELL, 1, 90.0)

        assert first != second
        assert [o.order_id for o in broker.get_orders()] == [first, second]

    def test_listed_orders_carry_the_placed_details(self, broker: StubBrokerClient):
        place_limit(broker, Action.BUY, 10, 100.0)
        place_stop(broker, Action.SELL, 5, 90.0)

        limit_order, stop_order = broker.get_orders()

        assert (limit_order.ticker, limit_order.action, limit_order.quantity) == (
            "AAPL",
            Action.BUY,
            10,
        )
        assert limit_order.limit_price == 100.0
        assert limit_order.submitted_at == DAYS[0]
        assert (stop_order.order_type, stop_order.stop_price) == (OrderType.STP, 90.0)


class TestLimitStopOrders:
    def place(
        self,
        broker: StubBrokerClient,
        action: Action,
        limit_price: float,
        stop_price: float,
    ):
        return broker.place_limit_stop_order(
            ticker=Ticker.AAPL,
            quantity=10,
            action=action,
            limit_price=limit_price,
            stop_price=stop_price,
        )

    def test_listed_order_carries_both_prices(self, broker: StubBrokerClient):
        self.place(broker, Action.BUY, 100.0, 90.0)

        [order] = broker.get_orders()

        assert order.order_type == OrderType.LMT_STP
        assert (order.limit_price, order.stop_price) == (100.0, 90.0)

    def test_stop_not_reached_leaves_the_position_open(self, broker: StubBrokerClient):
        # Day 2 trades between 98 and 110
        self.place(broker, Action.BUY, 100.0, 90.0)

        next_day(broker)

        [position] = broker.get_positions()
        assert position.quantity == 10
        assert position.average_cost == 100.0

    def test_stop_reached_on_the_entry_bar_closes_the_position(
        self, broker: StubBrokerClient
    ):
        # Day 2 trades between 98 and 110
        self.place(broker, Action.BUY, 100.0, 99.0)

        next_day(broker)

        assert broker.get_positions() == []
        assert broker.get_assets().cash_balance == pytest.approx(
            10_000.0 - 1.0 - 10.0 - 1.0
        )

    def test_short_stop_reached_on_the_entry_bar_closes_the_position(
        self, broker: StubBrokerClient
    ):
        # Day 2 trades up to 110
        self.place(broker, Action.SELL, 100.0, 105.0)

        next_day(broker)

        assert broker.get_positions() == []

    def test_limit_not_reached_places_no_stop_and_no_position(
        self, broker: StubBrokerClient
    ):
        self.place(broker, Action.BUY, 90.0, 80.0)

        next_day(broker)

        assert broker.get_positions() == []
        assert broker.get_assets().cash_balance == 10_000.0

    def test_rejected_limit_does_not_activate_the_stop(self, fee_broker):
        stub = StubBrokerClient(
            market_data=make_market_data(), initial_cash=500.0, fee_broker=fee_broker
        )
        self.place(stub, Action.BUY, 100.0, 99.0)

        next_day(stub)

        assert stub.get_positions() == []
        assert stub.get_assets().cash_balance == 500.0


class TestShortOrders:
    @pytest.fixture
    def short_broker(self, broker: StubBrokerClient) -> StubBrokerClient:
        # Day 2 trades up to 110
        place_limit(broker, Action.SELL, 10, 100.0)
        next_day(broker)
        return broker

    def test_limit_sell_opens_a_short_with_a_positive_quantity(
        self, short_broker: StubBrokerClient
    ):
        [position] = short_broker.get_positions()

        assert position.trade_type == TradeType.SHORT
        assert position.quantity == 10
        assert position.average_cost == 100.0
        assert position.market_value == pytest.approx(1_080.0)
        assert position.unrealized_pnl == pytest.approx(-80.0)

    def test_short_value_uses_up_available_cash_and_is_part_of_the_cash_balance(
        self, short_broker: StubBrokerClient
    ):
        assets = short_broker.get_assets()

        assert assets.cash_available_for_trading == pytest.approx(
            10_000.0 - 1_000.0 - 1.0
        )
        assert assets.buying_power == assets.cash_available_for_trading
        assert assets.cash_balance == pytest.approx(
            assets.cash_available_for_trading + 1_000.0
        )
        # The cash balance less the loss of the short
        assert assets.net_liquidation == pytest.approx(9_999.0 - 80.0)
        assert assets.gross_position_value == pytest.approx(1_080.0)
        assert assets.unrealized_pnl == pytest.approx(-80.0)

    def test_margin_interest_is_charged_every_day_after_the_short_opens(
        self, short_broker: StubBrokerClient
    ):
        cash_when_opened = short_broker.get_assets().cash_balance

        next_day(short_broker)

        assert short_broker.get_assets().cash_balance == pytest.approx(
            cash_when_opened - 0.5
        )

    def test_buy_stop_covers_the_short_at_the_stop_price(
        self, short_broker: StubBrokerClient
    ):
        # Day 3 trades between 90 and 112
        place_stop(short_broker, Action.BUY, 10, 105.0)

        next_day(short_broker)

        assert short_broker.get_positions() == []
        assets = short_broker.get_assets()
        # Sold at 100, bought back at 105: -50, less 2 fills and a day of margin interest
        assert assets.cash_balance == pytest.approx(
            10_000.0 + 1_000.0 - 1.0 - 0.5 - 1_050.0 - 1.0
        )
        assert assets.cash_available_for_trading == assets.cash_balance
        assert assets.realized_pnl == pytest.approx(-50.0 - 1.0 - 0.5 - 1.0)

    def test_adding_to_a_short_averages_the_cost_and_keeps_quantities_positive(
        self, short_broker: StubBrokerClient
    ):
        # Day 3 trades between 90 and 112
        place_limit(short_broker, Action.SELL, 10, 110.0)

        next_day(short_broker)

        [position] = short_broker.get_positions()
        assert position.trade_type == TradeType.SHORT
        assert position.quantity == 20
        assert position.average_cost == pytest.approx(105.0)
        assert position.market_value == pytest.approx(20 * 95.0)
        assert position.unrealized_pnl == pytest.approx(20 * (105.0 - 95.0))

    def test_sell_stop_does_not_close_a_short(self, short_broker: StubBrokerClient):
        place_stop(short_broker, Action.SELL, 10, 105.0)

        next_day(short_broker)

        [position] = short_broker.get_positions()
        assert position.trade_type == TradeType.SHORT
        assert position.quantity == 10
