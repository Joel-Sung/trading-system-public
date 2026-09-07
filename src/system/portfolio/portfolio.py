from datetime import datetime

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import TradeType
from custom_types.sector import Sector
from custom_types.ticker import Ticker
from system.portfolio.campaign import Campaign
from system.portfolio.leg import Leg


class Portfolio:
    def __init__(
        self,
        initial_equity: float,
        cash_balance: float | None = None,
        cash_available_for_trading: float | None = None,
    ) -> None:
        self.initial_equity: float = initial_equity
        self.cash_balance: float = (
            initial_equity if cash_balance is None else cash_balance
        )
        self.cash_available_for_trading: float = (
            initial_equity
            if cash_available_for_trading is None
            else cash_available_for_trading
        )
        self.open_trade_campaigns: list[Campaign] = []
        self.closed_trade_campaigns: list[Campaign] = []

    @property
    def total_equity(self) -> float:
        return self.cash_available_for_trading + self.position_value

    @property
    def position_value(self) -> float:
        position_value = 0.0
        for campaign in self.open_trade_campaigns:
            position_value += campaign.current_value
        return position_value

    @property
    def cam_count(self) -> int:
        return len(self.open_trade_campaigns)

    @property
    def cam_sect_count(self) -> dict[Sector, int]:
        cam_sect_count: dict[Sector, int] = {}

        for sector in Sector:
            cam_sect_count[sector] = 0

        for campaign in self.open_trade_campaigns:
            sector = campaign.sector
            cam_sect_count[sector] = cam_sect_count.get(sector, 0) + 1

        return cam_sect_count

    def get_open_campaign(self, ticker: Ticker) -> Campaign | None:
        for campaign in self.open_trade_campaigns:
            if campaign.ticker == ticker:
                return campaign
        return None

    def update_with_current_bar(
        self, ticker: Ticker, current_bar: pd.Series, broker: BrokerClient
    ) -> None:
        campaign = self.get_open_campaign(ticker=ticker)

        if campaign is None:
            raise MyValueError(
                "Unable to find open campaign to update with current bar",
                ticker=ticker,
                portfolio=self,
            )

        campaign.update_with_current_bar(current_bar=current_bar, broker=broker)

    def create_campaign(
        self,
        ticker: Ticker,
        trade_type: TradeType,
        entry_datetime: datetime,
    ) -> Campaign:
        existing_campaign = self.get_open_campaign(ticker=ticker)
        if existing_campaign is not None:
            raise MyValueError(
                "Trying to open campaign for ticker that already has an open campaign",
                ticker=ticker,
                trade_type=trade_type,
                entry_datetime=entry_datetime,
                portfolio=self,
            )

        campaign = Campaign(
            ticker=ticker,
            trade_type=trade_type,
            entry_datetime=entry_datetime,
        )
        self.open_trade_campaigns.append(campaign)

        return campaign

    def create_leg(
        self,
        ticker: Ticker,
        trade_type: TradeType,
        entry_price: float,
        entry_datetime: datetime,
        trading_fees: float,
        qty: float,
        stop_price: float,
    ) -> Leg:
        campaign = self.get_open_campaign(ticker=ticker)

        if campaign is None:
            campaign = self.create_campaign(
                ticker=ticker,
                trade_type=trade_type,
                entry_datetime=entry_datetime,
            )

        leg = Leg(
            campaign_id=campaign.campaign_id,
            leg_number=campaign.next_leg_num,
            ticker=ticker,
            trade_type=campaign.trade_type,
            entry_price=entry_price,
            entry_datetime=entry_datetime,
            trading_fees=trading_fees,
            qty=qty,
            stop_price=stop_price,
        )

        campaign.create_leg(leg=leg)

        if leg.trade_type == TradeType.LONG:
            self.cash_balance -= leg.entry_price * leg.current_qty - leg.trading_fees
        else:
            self.cash_balance += leg.entry_price * leg.current_qty - leg.trading_fees

        self.cash_available_for_trading -= (
            leg.entry_price * leg.current_qty - leg.trading_fees
        )

        return leg

    def sell_ticker_qty(
        self,
        ticker: Ticker,
        qty: float,
        exit_price: float,
        exit_datetime: datetime,
        broker: BrokerClient,
    ) -> Campaign:
        campaign = self.get_open_campaign(ticker=ticker)
        margin_fees = campaign.sell_qty(
            qty=qty,
            exit_price=exit_price,
            exit_datetime=exit_datetime,
        )
        if not campaign.is_open:
            self.open_trade_campaigns.remove(campaign)
            self.closed_trade_campaigns.append(campaign)

        if campaign.trade_type == TradeType.LONG:
            self.cash_balance += exit_price * qty - margin_fees
        else:
            self.cash_balance -= exit_price * qty - margin_fees

        self.cash_available_for_trading += exit_price * qty - margin_fees

        return campaign

    def __str__(self) -> str:
        indent = " " * 4

        return (
            f"Portfolio(\n"
            f"{indent}initial_equity             = {self.initial_equity:.3f},\n"
            f"{indent}cash_balance               = {self.cash_balance:.3f},\n"
            f"{indent}cash_available_for_trading = {self.cash_available_for_trading:.3f},\n"
            f"{indent}open_trade_campaigns       = [{len(self.open_trade_campaigns)}],\n"
            f"{indent}closed_trade_campaigns     = [{len(self.closed_trade_campaigns)}]\n"
            f")"
        )

    def verbose_str(self) -> str:
        result = [str(self)]

        if self.open_trade_campaigns:
            result.append("\nOpen Trade Campaigns:\n")
            for campaign in self.open_trade_campaigns:
                result.append(campaign.verbose_str())

        if self.closed_trade_campaigns:
            result.append("\nClosed Trade Campaigns:\n")
            for campaign in self.closed_trade_campaigns:
                result.append(campaign.verbose_str())

        return "\n".join(result)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Portfolio):
            return NotImplemented

        return (
            self.initial_equity == other.initial_equity
            and self.cash_balance == other.cash_balance
            and self.cash_available_for_trading == other.cash_available_for_trading
            and self.open_trade_campaigns == other.open_trade_campaigns
            and self.closed_trade_campaigns == other.closed_trade_campaigns
        )
