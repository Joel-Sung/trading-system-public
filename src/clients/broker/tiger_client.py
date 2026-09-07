import os
from datetime import timedelta

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.market import (
    Action,
    MarketAssets,
    MarketBarPeriod,
    MarketOrder,
    MarketPosition,
    TradeType,
)
from custom_types.ticker import Ticker
from dotenv import load_dotenv
from tigeropen.common.consts import BarPeriod
from tigeropen.common.util.contract_utils import stock_contract
from tigeropen.common.util.order_utils import (
    limit_order,
    limit_order_with_legs,
    market_order,
    order_leg,
    stop_order,
)
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.trade.domain.contract import Contract
from tigeropen.trade.domain.prime_account import Segment
from tigeropen.trade.trade_client import (
    Order,
    OrderStatus,
    PortfolioAccount,
    Position,
    TradeClient,
)
from util.broker_util import retry_on_rate_limit
from util.datetime_util import get_current_datetime


class TigerClient(BrokerClient):
    def _get_client_config(self):
        load_dotenv()
        client_config = TigerOpenClientConfig()
        client_config.private_key = os.environ["TIGER_PRIVATE_KEY_PK1"]
        client_config.tiger_id = os.environ["TIGER_ID"]
        client_config.account = os.environ["TIGER_DEMO_ACCOUNT"]
        # client_config.timezone = 'US/Eastern' # Optional timezone setting
        return client_config

    def __init__(self):
        client_config = self._get_client_config()

        self.quote_client = QuoteClient(client_config=client_config)
        self.trade_client = TradeClient(client_config=client_config)
        self.account = client_config.account

    @staticmethod
    def get_name() -> str:
        return "tiger"

    @staticmethod
    def calculate_fees(shares: float, price: float, trade_type: TradeType) -> float:
        # Tiger broker fees: https://www.itiger.com/sg/commissions?lang=en_US
        # Excluded Consolidated Audit Trail Fee as its negligible
        trade_value = shares * price

        if shares >= 1:
            commission = min(0.005 * trade_value, max(0.99, 0.005 * shares))
            platform_fee = min(0.005 * trade_value, max(1, 0.005 * shares))
        else:
            commission = 0
            platform_fee = min(1, 0.01 * trade_value)

        settlement_fee = min(0.005 * trade_value, 0.003 * shares)

        if trade_type == TradeType.LONG:
            sec_membership_fee = 0
            trading_activity_fee = 0
        else:
            sec_membership_fee = max(0.01, 0.0000206 * trade_value)
            trading_activity_fee = min(9.79, max(0.01, 0.000195 * shares))

        total_fees = (
            commission
            + platform_fee
            + settlement_fee
            + sec_membership_fee
            + trading_activity_fee
        )

        # print(
        #     commission,
        #     platform_fee,
        #     settlement_fee,
        #     sec_membership_fee,
        #     trading_activity_fee,
        # )
        return total_fees

    @staticmethod
    def calculate_margin_interest(margin_amount: float, duration_days: int) -> float:
        # Tiger broker margin interest rates: https://www.itiger.com/hk/en/invest/margin-account
        usd_annual_rate = 0.048
        return (margin_amount * usd_annual_rate / 360) * duration_days

    def get_market_data(
        self,
        ticker: Ticker,
        number_of_bars: int | None = None,
        period: MarketBarPeriod = MarketBarPeriod.DAY,
    ) -> pd.DataFrame:
        """
        Set window = None to retrieve full history
        """

        if period == MarketBarPeriod.HOUR:
            bar_period = BarPeriod.ONE_HOUR
        elif period == MarketBarPeriod.DAY:
            bar_period = BarPeriod.DAY
        elif period == MarketBarPeriod.MONTH:
            bar_period = BarPeriod.MONTH
        elif period == MarketBarPeriod.YEAR:
            bar_period = BarPeriod.YEAR
        else:
            raise ValueError(f"Unsupported market bar period: {period}")

        end_time = get_current_datetime()
        all_data: list[pd.DataFrame] = []
        total_bars: int = 0
        lookback_period = 365 if number_of_bars is None else number_of_bars

        while True:
            begin_time = end_time - timedelta(days=lookback_period)

            data = retry_on_rate_limit(
                lambda begin_time=begin_time, end_time=end_time: (
                    self.quote_client.get_bars(
                        symbols=[ticker],
                        period=bar_period,
                        begin_time=begin_time.strftime("%Y-%m-%d"),
                        end_time=end_time.strftime("%Y-%m-%d"),
                    )
                ),
                retries=5 if number_of_bars is None else 15,
            )

            if data.empty:
                break

            all_data.append(data)

            total_bars += len(data)
            if number_of_bars is not None and total_bars >= number_of_bars:
                break

            end_time = begin_time

        ticker_df = pd.concat(all_data, ignore_index=True)

        if ticker_df.empty:
            return ticker_df

        ticker_df = (
            ticker_df.rename(columns={"time": "datetime", "symbol": "ticker"})[
                [
                    "ticker",
                    "datetime",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ]
            .assign(datetime=lambda x: pd.to_datetime(x["datetime"], unit="ms"))
            .sort_values("datetime")
            .reset_index(drop=True)
        )

        if number_of_bars is None:
            return ticker_df

        return ticker_df.tail(number_of_bars)

    def place_market_order(self, ticker: Ticker, quantity: int, action: Action):
        contract = stock_contract(symbol=ticker, currency="USD")

        order = market_order(
            account=self.account,
            contract=contract,
            action=action,
            quantity=quantity,
        )

        return self.trade_client.place_order(order)

    def place_limit_order(
        self, ticker: Ticker, quantity: int, action: Action, limit_price: float
    ):
        contract = stock_contract(symbol=ticker, currency="USD")

        order = limit_order(
            account=self.account,
            contract=contract,
            action=action,
            limit_price=limit_price,
            quantity=quantity,
        )

        return self.trade_client.place_order(order)

    def place_stop_order(
        self, ticker: Ticker, quantity: int, action: Action, stop_price: float
    ):
        contract = stock_contract(symbol=ticker, currency="USD")

        order = stop_order(
            account=self.account,
            contract=contract,
            action=action,
            aux_price=stop_price,
            quantity=quantity,
            # time_in_force="GTC", # Not allowed in paper account api
        )

        return self.trade_client.place_order(order)

    def place_limit_order_with_stop(
        self,
        ticker: Ticker,
        quantity: int,
        action: Action,
        limit_price: float,
        stop_price: float,
    ):
        contract = stock_contract(symbol=ticker, currency="USD")

        stop_loss_order_leg = order_leg(
            leg_type="LOSS",
            price=stop_price,
            time_in_force="DAY",
            outside_rth=False,
        )

        main_order = limit_order_with_legs(
            account=self.account,
            contract=contract,
            action=action,
            quantity=quantity,
            limit_price=limit_price,
            order_legs=[stop_loss_order_leg],
        )

        return self.trade_client.place_order(main_order)

    def update_stop_order(self, order_id: int, new_stop_price: float):
        orders = self.trade_client.get_orders()

        order = next((o for o in orders if o.id == order_id), None)

        if order is None:
            raise ValueError(f"Order {order_id} not found.")

        if not order.can_modify:
            raise ValueError("Order can no longer be modified.")

        order.aux_price = new_stop_price

        return self.trade_client.modify_order(order)

    def cancel_order(self, order_id: int):
        # Sets the order status to "Cancelled"
        return self.trade_client.cancel_order(id=order_id)

    def get_orders(self) -> list[MarketOrder]:
        # Order documentation: https://docs-en.itigerup.com/docs/appendix-object-detail#order
        orders: list[Order] = self.trade_client.get_orders()

        if len(orders) == 0:
            return []

        market_orders: list[MarketOrder] = []

        excluded_statuses = {
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.FILLED,
            OrderStatus.PENDING_CANCEL,
            OrderStatus.REJECTED,
        }
        for o in orders:
            # Cancelled,       // Cancelled
            # Expired,         // Expired
            # Filled,          // Fully filled
            # Held,
            # New,
            # Partially_Filled, // Partially filled
            # Pending_Cancel,   // Pending cancel
            # Pending_New,      // Pending new
            # Rejected,
            status: OrderStatus = o.status

            if status in excluded_statuses:
                continue

            contract: Contract = o.contract

            market_order = MarketOrder(
                order_id=o.id,
                ticker=contract.symbol,
                action=o.action,
                order_type=o.order_type,
                quantity=o.quantity,
                filled_quantity=o.filled,
                avg_fill_price=o.avg_fill_price,
                fees=o.commission + o.gst,
                submitted_at=pd.to_datetime(o.order_time, unit="ms"),
                limit_price=o.limit_price,
                stop_price=o.aux_price,
                status=status.value,
            )

            market_orders.append(market_order)

        return market_orders

    def get_positions(self) -> list[MarketPosition]:
        positions: list[Position] = self.trade_client.get_positions()

        if len(positions) == 0:
            return []

        my_positions: list[MarketPosition] = []
        for p in positions:
            contract: Contract = p.contract

            my_position = MarketPosition(
                ticker=contract.symbol,
                trade_type=TradeType.LONG if p.quantity > 0 else TradeType.SHORT,
                quantity=p.quantity,
                average_cost=p.average_cost,
                market_value=p.market_value,
                unrealized_pnl=p.unrealized_pnl,
                realized_pnl=p.realized_pnl,
            )

            my_positions.append(my_position)

        return my_positions

    def get_assets(self) -> MarketAssets:
        assets: PortfolioAccount = self.trade_client.get_prime_assets(
            account=self.account
        )

        if assets is None or "S" not in assets.segments:
            return {}

        # Segment documentation: https://docs-en.itigerup.com/docs/appendix-object-detail
        segment: Segment = assets.segments["S"]

        return MarketAssets(
            net_liquidation=segment.net_liquidation,
            cash_balance=segment.cash_balance,
            cash_available_for_trading=segment.cash_available_for_trade,
            buying_power=segment.buying_power,
            gross_position_value=segment.gross_position_value,
            unrealized_pnl=segment.unrealized_pl,
            realized_pnl=segment.realized_pl,
        )

    def __str__(self) -> str:
        return "Tiger Client"


if __name__ == "__main__":
    client = TigerClient()

    # latest_bar = client.get_latest_bar(ticker=Ticker.AAPL)
    # print("latest bar:\n", latest_bar)
    # print()

    # print(
    #     "limit buy: ",
    #     client.limit_buy(
    #         ticker=Ticker.AAPL, quantity=10, limit_price=latest_bar["close"]
    #     ),
    # )
    # print("limit sell: ", client.limit_sell(ticker=Ticker.AAPL, quantity=5, limit_price=160.0))
    # print()

    # print("cancel order: ", client.cancel_order(order_id=43836371158843392))
    # print()

    # print(
    #     "stop order: ",
    #     client.place_stop_order(
    #         ticker=Ticker.AAPL, quantity=8, action=Action.SELL, stop_price=150.0
    #     ),
    #     "\n",
    # )
    # print(
    #     "stop order: ",
    #     client.place_stop_order(
    #         ticker=Ticker.AAPL, quantity=7, action=Action.SELL, stop_price=170.0
    #     ),
    #     "\n",
    # )
    # print(
    #     "stop order: ",
    #     client.place_stop_order(
    #         ticker=Ticker.NVDA, quantity=5, action=Action.BUY, stop_price=350.0
    #     ),
    #     "\n",
    # )

    # print(
    #     "update stop order: ",
    #     client.update_stop_order(order_id=43836345752635392, new_stop_price=306.9),
    # )
    # print()

    # print("orders: [")
    # for o in client.get_orders():
    #     print("  ", o)
    # print("]\n")

    # print("positions: [")
    # for p in client.get_positions():
    #     print("  ", p)
    # print("]\n")

    # print("assets:\n", client.get_assets(), "\n")

    # print(
    #     "latest bar:\n", client.get_market_data(ticker=Ticker.AAPL, number_of_bars=21)
    # )

    print(
        "calculated fees:\n",
        client.calculate_fees(shares=15.0, price=308.854, trade_type=TradeType.LONG),
    )
