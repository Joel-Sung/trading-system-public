from dataclasses import dataclass


@dataclass
class Expectancy:
    expectancy: float
    win_rate: float = None
    avg_win: float = None
    avg_loss: float = None

    def __str__(self) -> str:
        return (
            f"expectancy (R) = {self.expectancy:.3f}\n"
            f"win_rate   (%) = {f'{self.win_rate:.2f}' if self.win_rate is not None else 'None'}\n"
            f"avg_win    (R) = {f'{self.avg_win:.3f}' if self.avg_win is not None else 'None'}\n"
            f"avg_loss   (R) = {f'{self.avg_loss:.3f}' if self.avg_loss is not None else 'None'}"
        )


@dataclass
class Opportunity:
    opportunity: float
    avg_trades_per_year: float
    num_years: int

    def __str__(self) -> str:
        return (
            f"opportunity (R)     = {self.opportunity:.3f}\n"
            f"avg_trades_per_year = {self.avg_trades_per_year:.2f}\n"
            f"num_years           = {self.num_years}"
        )


@dataclass
class Drawdown:
    value: float
    percentage: float
    recovery_duration_in_days: int

    def __str__(self) -> str:
        return (
            f"drawdown_value             ($) = {self.value:.2f}\n"
            f"drawdown_percentage        (%) = {self.percentage:.2f}\n"
            f"drawdown_recovery_duration (D) = {self.recovery_duration_in_days}\n"
            f"drawdown_recovery_duration (M) = {(self.recovery_duration_in_days / 30):.2f}\n"
            f"drawdown_recovery_duration (Y) = {(self.recovery_duration_in_days / 365):.2f}"
        )


@dataclass
class LegMetrics:
    absolute_profit: float
    total_fees: float

    def __str__(self) -> str:
        return (
            f"absolute_profit ($) = {self.absolute_profit:.2f}\n"
            f"total_fees      ($) = {self.total_fees:.2f}"
        )


@dataclass
class EquityGrowth:
    total_years: int
    initial_equity: float
    final_equity: float
    total_percentage_increase: float
    avg_annual_percentage_increase: float
    yearly_equity: dict[int, float]
    yearly_percentage_increase: dict[int, float]


@dataclass
class GroupMetrics:
    """Aggregated leg performance for an arbitrary condition (e.g. duration bucket, sector)."""

    label: str
    num_legs: int
    total_win_rate: float
    total_absolute_profit: float
    total_profit_in_r: float
    expectancy: float
    opportunity: float
    num_long_legs: int
    long_win_rate: float
    long_absolute_profit: float
    long_profit_in_r: float
    num_short_legs: int
    short_win_rate: float
    short_absolute_profit: float
    short_profit_in_r: float

    def __str__(self) -> str:
        return (
            f"group                     = {self.label}\n"
            f"num_legs                  = {self.num_legs}\n"
            f"total_win_rate        (%) = {self.total_win_rate:.2f}\n"
            f"total_absolute_profit ($) = {self.total_absolute_profit:.2f}\n"
            f"total_profit_in_r     (R) = {self.total_profit_in_r:.2f}\n"
            f"expectancy            (R) = {self.expectancy:.2f}\n"
            f"opportunity           (R) = {self.opportunity:.2f}\n"
            f"num_long_legs             = {self.num_long_legs}\n"
            f"long_absolute_profit  ($) = {self.long_absolute_profit:.2f}\n"
            f"long_profit_in_r      (R) = {self.long_profit_in_r:.2f}\n"
            f"long_win_rate         (%) = {self.long_win_rate:.2f}\n"
            f"num_short_legs            = {self.num_short_legs}\n"
            f"short_win_rate        (%) = {self.short_win_rate:.2f}\n"
            f"short_absolute_profit ($) = {self.short_absolute_profit:.2f}\n"
            f"short_profit_in_r     (R) = {self.short_profit_in_r:.2f}"
        )


PerformanceMetrics = tuple[Expectancy, Opportunity, Drawdown, LegMetrics]
