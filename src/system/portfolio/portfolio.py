import math
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

    def create_pending_leg(
        self,
        ticker: Ticker,
        trade_type: TradeType,
        order_price: float,
        order_qty: float,
        order_datetime: datetime,
        stop_price: float,
    ) -> Leg:
        campaign = self.get_open_campaign(ticker=ticker)

        if campaign is None:
            campaign = self.create_campaign(
                ticker=ticker,
                trade_type=trade_type,
                entry_datetime=order_datetime,
            )

        leg = Leg(
            campaign_id=campaign.campaign_id,
            leg_number=campaign.next_leg_num,
            ticker=ticker,
            trade_type=campaign.trade_type,
            order_price=order_price,
            order_qty=order_qty,
            order_datetime=order_datetime,
            stop_price=stop_price,
        )

        campaign.create_leg(leg=leg)

        return leg

    def fill_legs(
        self,
        ticker: Ticker,
        qty: float,
        fill_price: float,
        fill_datetime: datetime,
        trading_fees: float,
    ) -> float:
        """
        Fills the campaign's pending legs (oldest first) with the broker's newly filled qty.
        Trading fees cover the whole qty and are split across legs by qty.
        Any qty beyond the pending qty is added to the main leg. Returns that excess qty.
        """
        campaign = self.get_open_campaign(ticker=ticker)

        if campaign is None:
            raise MyValueError(
                "Unable to find open campaign to fill legs",
                ticker=ticker,
                qty=qty,
                portfolio=self,
            )

        qty_to_fill = qty
        for leg in campaign.open_legs:
            if qty_to_fill <= 0 or math.isclose(qty_to_fill, 0, abs_tol=1e-9):
                break

            leg_qty = min(qty_to_fill, leg.pending_qty)
            if leg_qty <= 0 or math.isclose(leg_qty, 0, abs_tol=1e-9):
                continue

            leg_fees = trading_fees * leg_qty / qty
            campaign.fill_leg(
                leg=leg,
                fill_price=fill_price,
                fill_qty=leg_qty,
                fill_datetime=fill_datetime,
                trading_fees=leg_fees,
            )
            self._apply_fill_cash(
                trade_type=leg.trade_type,
                fill_price=fill_price,
                fill_qty=leg_qty,
                trading_fees=leg_fees,
            )
            qty_to_fill -= leg_qty

        excess_qty = 0.0 if math.isclose(qty_to_fill, 0, abs_tol=1e-9) else qty_to_fill
        if excess_qty > 0:
            main_leg = campaign.main_leg
            if main_leg is None:
                raise MyValueError(
                    "Unable to find main leg to add excess qty to",
                    ticker=ticker,
                    excess_qty=excess_qty,
                    campaign=campaign,
                )
            main_leg.current_qty += excess_qty

        return excess_qty

    def cancel_unfilled_campaign(self, campaign: Campaign) -> None:
        if campaign.total_qty != 0 or any(not l.is_pending for l in campaign.open_legs):
            raise MyValueError(
                "Trying to cancel campaign that has filled legs",
                campaign=campaign,
            )

        self.open_trade_campaigns.remove(campaign)

    def _apply_fill_cash(
        self,
        trade_type: TradeType,
        fill_price: float,
        fill_qty: float,
        trading_fees: float,
    ) -> None:
        if trade_type == TradeType.LONG:
            self.cash_balance -= fill_price * fill_qty - trading_fees
        else:
            self.cash_balance += fill_price * fill_qty - trading_fees

        self.cash_available_for_trading -= fill_price * fill_qty - trading_fees

    def sell_ticker_qty(
        self,
        ticker: Ticker,
        qty: float,
        exit_price: float,
        exit_datetime: datetime,
    ) -> Campaign:
        campaign = self.get_open_campaign(ticker=ticker)
        return self.sell_campaign_qty(
            campaign=campaign,
            qty=qty,
            exit_price=exit_price,
            exit_datetime=exit_datetime,
        )

    def sell_campaign_qty(
        self,
        campaign: Campaign,
        qty: float,
        exit_price: float,
        exit_datetime: datetime,
    ) -> Campaign:
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
        return (
            f"Portfolio("
            f"initial_equity={self.initial_equity:.3f}, "
            f"cash_balance={self.cash_balance:.3f}, "
            f"cash_available_for_trading={self.cash_available_for_trading:.3f}, "
            f"open_trade_campaigns={len(self.open_trade_campaigns)}, "
            f"closed_trade_campaigns={len(self.closed_trade_campaigns)}"
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
