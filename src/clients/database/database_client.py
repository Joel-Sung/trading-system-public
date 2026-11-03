import shutil
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
from custom_types.ticker import Ticker
from util.datetime_util import format_dt
from util.dict_util import flatten_dict

T = TypeVar("T")


class FileType(StrEnum):
    CSV = "csv"
    TXT = "txt"


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

    @staticmethod
    def _to_dataframe(data: Any) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data

        # Convert objects or list of objects to dicts
        items = data if isinstance(data, list) else [data]
        dicts = [
            flatten_dict(i.to_dict() if hasattr(i, "to_dict") else i.__dict__)
            for i in items
        ]
        return pd.DataFrame(dicts)

    def _write_csv(self, df: pd.DataFrame, file_name: str) -> None:
        df.to_csv(self._get_path(file_name), index=False)

    def _write_txt(self, content: str, file_name: str) -> None:
        path = self._get_path(file_name)
        with open(path, "w") as f:
            f.write(content)

    def save(self, data: Any, file_name: str, file_type: FileType = FileType.CSV):
        if file_type == FileType.CSV:
            self._write_csv(self._to_dataframe(data), file_name)
        elif file_type == FileType.TXT:
            self._write_txt(data, file_name)
        else:
            raise NotImplementedError(
                f"Saving for file type {file_type} is not implemented."
            )

    def _read_csv(self, file_name: str) -> pd.DataFrame | None:
        """Returns None if the file does not exist or is empty."""
        path = self._get_path(file_name, create_dir=False)
        if not path.exists():
            return None
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return None

    def load(self, file_name: str, mapper: Callable[[pd.Series], T]) -> list[T]:
        df = self._read_csv(file_name)
        if df is None:
            return []
        return [mapper(row) for _, row in df.iterrows()]

    def get_csv_data(self, *parts: str) -> pd.DataFrame:
        path = self._get_path(*parts, create_dir=False)
        return pd.read_csv(path)

    def save_raw_data(self, df: pd.DataFrame, ticker: Ticker, client: str):
        self.save(df, f"raw/{client}/{ticker}.csv")

    def does_raw_data_exist(self, ticker: Ticker, client: str) -> bool:
        path = self._get_path("raw", client, f"{ticker}.csv", create_dir=False)
        return path.exists()

    def backup(self, file_name: str, timestamp: datetime | None = None):
        src = self._get_path(file_name, create_dir=False)
        dest = self._get_path(
            "backup",
            f"{format_dt(timestamp)}_{src.stem}_{src.suffix}",
        )
        shutil.copy2(src, dest)

    def __str__(self):
        return f"DatabaseClient ({self.data_dir})"
