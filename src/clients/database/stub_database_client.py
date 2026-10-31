import io

import pandas as pd
from clients.database.database_client import DatabaseClient


class StubDatabaseClient(DatabaseClient):
    """
    In-memory DatabaseClient for backtests. Files are kept as CSV text in an
    internal dict and read back through the same CSV parsing as the real client,
    so what a backtest loads is exactly what DatabaseClient would load, but
    nothing is ever written to disk.
    """

    def __init__(self) -> None:
        super().__init__(data_dir="<in-memory>")
        self._files: dict[str, str] = {}

    @property
    def file_names(self) -> list[str]:
        return list(self._files)

    def _get_path(self, *parts: str, create_dir: bool = True):
        raise NotImplementedError(
            "StubDatabaseClient only stores CSV data in memory, "
            "it does not support file system access."
        )

    def _write_csv(self, df: pd.DataFrame, file_name: str) -> None:
        self._files[file_name] = df.to_csv(index=False)

    def _read_csv(self, file_name: str) -> pd.DataFrame | None:
        content = self._files.get(file_name)
        if content is None:
            return None
        try:
            return pd.read_csv(io.StringIO(content))
        except pd.errors.EmptyDataError:
            return None

    def __str__(self) -> str:
        return f"StubDatabaseClient ({len(self._files)} in-memory files)"
