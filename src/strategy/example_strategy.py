from strategy.strategy import Strategy
from system.models.entry.example_entry_model import ExampleEntryModel
from system.models.position_sizing.example_sizing_model import ExampleSizingModel
from system.models.pyramiding.example_pyramid_model import ExamplePyramidModel
from system.models.risk.example_risk_model import ExampleRiskModel
from system.models.stops.example_stop_model import ExampleStopModel


class ExampleStrategy(Strategy):
    """A simple rolling high/low breakout strategy built from the example models."""

    def __init__(self, lookback_period: int = 20) -> None:
        super().__init__(
            entry_model=ExampleEntryModel(lookback_period=lookback_period),
            position_sizing_model=ExampleSizingModel(),
            stop_model=ExampleStopModel(),
            pyramid_model=ExamplePyramidModel(),
            risk_model=ExampleRiskModel(),
        )

    def __str__(self) -> str:
        return f"Example{super().__str__()}"
