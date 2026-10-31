from datetime import datetime, timedelta
from unittest.mock import MagicMock, call

import pandas as pd
import pytest
from clients.broker.broker_service import BrokerService
from custom_types.exception import MyValueError
from custom_types.market import Action, OrderType
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker

SUBMITTED_DT = datetime(2026, 1, 6, 9, 30)


def make_order(
    ticker: Ticker,
    action: Action,
    order_type: OrderType,
    qty: float,
    submitted_dt: datetime = SUBMITTED_DT,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> SystemOrder:
    return SystemOrder(
        ticker=ticker,
        action=action,
        order_type=order_type,
        quantity=qty,
        submitted_dt=submitted_dt,
        limit_price=limit_price,
        stop_price=stop_price,
    )


@pytest.fixture
def broker() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(broker) -> BrokerService:
    return BrokerService(broker)


class TestPlaceOrders:
    def test_places_each_order_type_with_the_matching_broker_call(
        self, service: BrokerService, broker: BrokerService
    ):
        orders = [
            make_order(
                ticker=Ticker.AAPL,
                action=Action.BUY,
                order_type=OrderType.LMT,
                qty=10,
                limit_price=100.0,
            ),
            make_order(
                ticker=Ticker.AAPL,
                action=Action.SELL,
                order_type=OrderType.STP,
                qty=5.5,
                stop_price=90.0,
            ),
            make_order(
                ticker=Ticker.MSFT,
                action=Action.SELL,
                order_type=OrderType.LMT,
                qty=5.5,
                limit_price=55.5,
            ),
            make_order(
                ticker=Ticker.MSFT,
                action=Action.BUY,
                order_type=OrderType.STP,
                qty=10,
                stop_price=65.5,
            ),
        ]

        service.place_orders(orders)

        assert broker.place_limit_order.call_args_list == [
            call(
                ticker=Ticker.AAPL, quantity=10, action=Action.BUY, limit_price=100.0
            ),
            call(
                ticker=Ticker.MSFT, quantity=5.5, action=Action.SELL, limit_price=55.5
            ),
        ]
        assert broker.place_stop_order.call_args_list == [
            call(ticker=Ticker.AAPL, quantity=5.5, action=Action.SELL, stop_price=90.0),
            call(ticker=Ticker.MSFT, quantity=10, action=Action.BUY, stop_price=65.5),
        ]

    def test_places_orders_in_the_given_order(
        self, service: BrokerService, broker: BrokerService
    ):
        orders = [
            make_order(
                ticker=Ticker.AAPL,
                action=Action.SELL,
                order_type=OrderType.STP,
                qty=5.5,
                stop_price=90.0,
            ),
            make_order(
                ticker=Ticker.AAPL,
                action=Action.BUY,
                order_type=OrderType.LMT,
                qty=10,
                limit_price=100.0,
            ),
        ]

        service.place_orders(orders)

        assert [c[0] for c in broker.method_calls] == [
            "place_stop_order",
            "place_limit_order",
        ]

    def test_no_orders_places_nothing(
        self, service: BrokerService, broker: BrokerService
    ):
        assert service.place_orders([]) is None
        assert broker.method_calls == []

    @pytest.mark.parametrize(
        "unsupported",
        [
            make_order(
                ticker=Ticker.AAPL,
                action=Action.BUY,
                qty=10.0,
                order_type=OrderType.MKT,
            ),
            make_order(
                ticker=Ticker.AAPL,
                action=Action.BUY,
                qty=10.0,
                order_type=OrderType.LMT_STP,
                limit_price=100.0,
                stop_price=90.0,
            ),
        ],
    )
    def test_unsupported_order_type_raises(
        self, service: BrokerService, broker: BrokerService, unsupported: SystemOrder
    ):
        with pytest.raises(MyValueError, match="Unsupported order type"):
            service.place_orders([unsupported])

        assert broker.method_calls == []


class TestGetMarketData:
    def test_walks_back_from_the_given_clock_instead_of_the_real_time(
        self, broker: MagicMock
    ):
        simulated_now = datetime(2016, 3, 1)
        broker.get_market_data.return_value = pd.DataFrame()
        service = BrokerService(broker, get_now=lambda: simulated_now)

        service.get_market_data(tickers=[Ticker.AAPL], number_of_bars=5)

        broker.get_market_data.assert_called_once()
        kwargs = broker.get_market_data.call_args.kwargs
        assert kwargs["end_time"] == simulated_now
        assert kwargs["begin_time"] == simulated_now - timedelta(days=5)
