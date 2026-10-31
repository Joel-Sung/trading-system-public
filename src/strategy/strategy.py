import pandas as pd
from custom_types.mode import Mode
from custom_types.sector import Sector
from custom_types.ticker import Ticker
from system.models.entry.base_entry_model import BaseEntryModel
from system.models.position_sizing.base_sizing_model import BaseSizingModel
from system.models.pyramiding.base_pyramid_model import BasePyramidModel
from system.models.risk.base_risk_model import BaseRiskModel
from system.models.stops.base_stop_model import BaseStopModel
from system.portfolio.campaign import Campaign
from system.portfolio.portfolio import Portfolio
from util.trading_util import TICKER_TO_SECTOR


class Strategy:
    """
    Sits between the trading engine and the individual models, so the engine
    never calls a model directly. Each campaign carries its own mode, which
    the strategy refreshes through the entry model, so models can behave
    differently per mode (e.g. stops, risk, pyramiding).
    """

    def __init__(
        self,
        entry_model: BaseEntryModel,
        position_sizing_model: BaseSizingModel,
        stop_model: BaseStopModel,
        pyramid_model: BasePyramidModel,
        risk_model: BaseRiskModel,
        included_tickers: list[Ticker] | None = None,
        excluded_tickers: list[Ticker] | None = None,
        sector_filter: list[Sector] | None = None,
    ) -> None:
        self.entry_model = entry_model
        self.position_sizing_model = position_sizing_model
        self.stop_model = stop_model
        self.pyramid_model = pyramid_model
        self.risk_model = risk_model
        self._candidate_tickers = included_tickers or [t for t in Ticker]
        self.excluded_tickers = excluded_tickers or []
        self.sector_filter = sector_filter or [Sector.UNKNOWN]

    @property
    def min_bars_req_for_inds(self) -> int:
        return self.entry_model.min_bars_req_for_inds

    @property
    def min_bars_req_for_entry(self) -> int:
        return self.entry_model.min_bars_req_for_signals

    @property
    def included_tickers(self) -> list[Ticker]:
        """Tickers to retrieve market data for, after applying the ticker and sector filters."""
        return [
            ticker
            for ticker in self._candidate_tickers
            if ticker not in self.excluded_tickers
            and TICKER_TO_SECTOR.get(ticker, Sector.UNKNOWN) not in self.sector_filter
        ]

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.entry_model.prepare_market_data(data)

    def get_long_signal(self, ticker_data: pd.DataFrame) -> bool:
        return self.entry_model.get_long_signal(ticker_data=ticker_data)

    def get_short_signal(self, ticker_data: pd.DataFrame) -> bool:
        return self.entry_model.get_short_signal(ticker_data=ticker_data)

    def get_new_mode(self, campaign: Campaign, ticker_data: pd.DataFrame) -> Mode:
        return self.entry_model.get_new_mode(
            campaign=campaign, ticker_data=ticker_data
        )

    def get_new_stops(self, current_price: float, campaign: Campaign) -> list[float]:
        return self.stop_model.get_new_stops(
            current_price=current_price, campaign=campaign
        )

    def should_pyramid(self, campaign: Campaign) -> bool:
        return self.pyramid_model.should_pyramid(campaign=campaign)

    def get_r_value(self, current_bar: pd.Series, campaign: Campaign) -> float:
        return self.risk_model.get_r_value(current_bar=current_bar, campaign=campaign)

    def calculate_qty(
        self, portfolio: Portfolio, bar_data: pd.Series, leg_num: int
    ) -> float:
        return self.position_sizing_model.calculate_qty(
            portfolio=portfolio, bar_data=bar_data, leg_num=leg_num
        )

    def __str__(self) -> str:
        INDENT = "  "

        sector_filter_str = (
            ", ".join(str(sector) for sector in self.sector_filter)
            if self.sector_filter
            else "None"
        )

        only_these_tickers_str = (
            ", ".join(str(ticker) for ticker in self.included_tickers)
            if self.included_tickers
            else "None"
        )
        excluded_tickers_str = ", ".join(
            str(ticker) for ticker in self.excluded_tickers
        )

        return (
            "Strategy (\n"
            f"{INDENT}entry_model={self.entry_model}\n"
            f"{INDENT}position_sizing_model={self.position_sizing_model}\n"
            f"{INDENT}stop_model={self.stop_model}\n"
            f"{INDENT}pyramid_model={self.pyramid_model}\n"
            f"{INDENT}risk_model={self.risk_model}\n"
            f"{INDENT}sector_filter=[{sector_filter_str}]\n"
            f"{INDENT}only_these_tickers=[{only_these_tickers_str}]\n"
            f"{INDENT}excluded_tickers=[{excluded_tickers_str}]\n"
            ")"
        )
