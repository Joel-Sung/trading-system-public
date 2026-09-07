import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
from clients.database import mappers
from custom_types.market import MarketAssets, MarketOrder, MarketPosition
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker
from system.portfolio.portfolio import Portfolio
from system.portfolio.snapshot.snapshot import Snapshot
from util.datetime_util import format_datetime, get_current_datetime
from util.dict_util import flatten_dict

T = TypeVar("T")


class DatabaseClient:
    def __init__(self, data_dir: str | None = None) -> None:
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            project_root = Path(__file__).resolve().parents[2]
            self.data_dir = project_root / "data"

    def _get_path(self, *parts: str, create_dir: bool = True) -> Path:
        path = self.data_dir.joinpath(*parts)
        if create_dir:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _save(self, data: Any, file_name: str):
        path = self._get_path(file_name)
        if isinstance(data, pd.DataFrame):
            data.to_csv(path, index=False)
        else:
            # Convert objects or list of objects to dicts
            items = data if isinstance(data, list) else [data]
            dicts = [
                flatten_dict(i.to_dict() if hasattr(i, "to_dict") else i.__dict__)
                for i in items
            ]
            pd.DataFrame(dicts).to_csv(path, index=False)

    def _load(self, file_name: str, mapper: Callable[[pd.Series], T]) -> list[T]:
        path = self._get_path(file_name, create_dir=False)
        if not path.exists():
            return []
        df = pd.read_csv(path)
        return [mapper(row) for _, row in df.iterrows()]

    # --- Market & Raw Data ---

    def get_csv_data(self, *parts: str) -> pd.DataFrame:
        path = self._get_path(*parts, create_dir=False)
        return pd.read_csv(path)

    def save_csv_data(self, data: pd.DataFrame, *parts: str):
        path = self._get_path(*parts, create_dir=False)
        data.to_csv(path, index=False)

    def save_raw_data(self, df: pd.DataFrame, ticker: Ticker, client: str):
        self._save(df, f"raw/{client}/{ticker}.csv")

    def does_raw_data_exist(self, ticker: Ticker, client: str) -> bool:
        path = self._get_path("raw", client, f"{ticker}.csv", create_dir=False)
        return path.exists()

    def get_raw_data(self, ticker: Ticker, client: str = "") -> pd.DataFrame:
        path = self._get_path("raw", client, f"{ticker}.csv", create_dir=False)
        return pd.read_csv(path)

    def save_market_assets(self, assets: MarketAssets, file_name: str):
        self._save(assets, file_name)

    def get_market_assets(self, file_name: str) -> MarketAssets:
        return self._load(file_name, mappers.map_market_assets)[0]

    def save_market_positions(self, pos: list[MarketPosition], file_name: str):
        self._save(pos, file_name)

    def get_market_positions(self, file_name: str) -> list[MarketPosition]:
        return self._load(file_name, mappers.map_market_position)

    def save_market_orders(self, orders: list[MarketOrder], file_name: str):
        self._save(orders, file_name)

    def get_market_orders(self, file_name: str) -> list[MarketOrder]:
        return self._load(file_name, mappers.map_market_order)

    def save_system_orders(self, orders: list[SystemOrder], file_name: str):
        self._save(orders, file_name)

    def get_system_orders(self, file_name: str) -> list[SystemOrder]:
        return self._load(file_name, mappers.map_system_order)

    def save_market_data(self, df: pd.DataFrame, file_name: str):
        self._save(df, file_name)

    def get_market_data(self, file_name: str) -> pd.DataFrame:
        return pd.read_csv(self._get_path(file_name, create_dir=False))

    # --- State Management ---

    def get_system_state(
        self, portfolio_file: str, campaign_file: str, leg_file: str
    ) -> Portfolio:
        portfolio = self._load(portfolio_file, mappers.map_portfolio)[0]
        campaigns = self._load(campaign_file, mappers.map_campaign)
        legs = self._load(leg_file, mappers.map_leg)

        # Reconstruct Tree
        for camp in campaigns:
            camp_legs = [l for l in legs if l.campaign_id == camp.campaign_id]
            camp.open_legs = [l for l in camp_legs if l.is_open]
            camp.closed_legs = [l for l in camp_legs if not l.is_open]
            target_list = (
                portfolio.open_trade_campaigns
                if camp.is_open
                else portfolio.closed_trade_campaigns
            )
            target_list.append(camp)

        return portfolio

    def save_system_state(
        self, portfolio: Portfolio, port_file: str, camp_file: str, leg_file: str
    ):
        self._save(portfolio, port_file)
        camps = portfolio.open_trade_campaigns + portfolio.closed_trade_campaigns
        self._save(camps, camp_file)
        legs = [l for c in camps for l in (c.open_legs + c.closed_legs)]
        self._save(legs, leg_file)

    def save_system_snapshots(self, snapshots: list[Snapshot], file_name: str):
        self._save(snapshots, file_name)

    # --- Backups & Eval ---

    def save_backup(self, file_name: str, timestamp: datetime | None = None):
        src = self._get_path(file_name, create_dir=False)
        dest = self._get_path(
            "backup",
            f"{format_datetime(timestamp or get_current_datetime())}_{src.stem}_{src.suffix}",
        )
        shutil.copy2(src, dest)

    def save_evaluation_data(self, content: str, file_name: str):
        path = self._get_path(file_name)
        with open(path, "w") as f:
            f.write(content)

    def __str__(self):
        return f"DatabaseClient ({self.data_dir})"
