import pandas as pd
from custom_types.sector import Sector
from system.models.entry.base_entry_model import BaseEntryModel
from system.models.position_sizing.base_sizing_model import BaseSizingModel
from system.models.pyramiding.base_pyramid_model import BasePyramidModel
from system.models.risk.base_risk_model import BaseRiskModel
from system.models.stops.base_stop_model import BaseStopModel


class Strategy:
    def __init__(
        self,
        entry_model: BaseEntryModel,
        position_sizing_model: BaseSizingModel,
        stop_model: BaseStopModel,
        pyramid_model: BasePyramidModel,
        risk_model: BaseRiskModel,
        sector_filter: list[Sector] | None = None,
    ) -> None:
        self.entry_model = entry_model
        self.position_sizing_model = position_sizing_model
        self.stop_model = stop_model
        self.pyramid_model = pyramid_model
        self.risk_model = risk_model
        self.sector_filter = sector_filter

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.entry_model.prepare_market_data(data)

    def __str__(self) -> str:
        INDENT = "    " * 2
        return (
            "Strategy (\n"
            f"{INDENT}entry_model={self.entry_model}\n"
            f"{INDENT}position_sizing_model={self.position_sizing_model}\n"
            f"{INDENT}stop_model={self.stop_model}\n"
            f"{INDENT}pyramid_model={self.pyramid_model}\n"
            f"{INDENT}risk_model={self.risk_model}\n"
            f"{INDENT}sector_filter={self.sector_filter}\n"
            ")"
        )
