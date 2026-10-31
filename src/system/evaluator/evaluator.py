from collections.abc import Callable
from itertools import pairwise
from typing import TYPE_CHECKING

from custom_types.market import TradeType
from custom_types.sector import Sector
from system.evaluator.evaluation_formatter import format_evaluation
from system.evaluator.evaluation_types import (
    Drawdown,
    EquityGrowth,
    GroupMetrics,
)
from system.portfolio.snapshot.leg_snapshot import LegSnapshot
from system.portfolio.snapshot.portfolio_snapshot import PortfolioSnapshot

if TYPE_CHECKING:
    from system.engine.backtest_engine import BacktestEngine


class SystemEvaluator:
    def __init__(
        self,
        leg_snapshots: list[LegSnapshot],
        portfolio_snapshots: list[PortfolioSnapshot],
        backtest_engine: "BacktestEngine",
    ) -> None:
        self.leg_snapshots = leg_snapshots
        self.portfolio_snapshots = portfolio_snapshots
        self.backtest_engine = backtest_engine

    @property
    def duration_years(self) -> float:
        if not self.portfolio_snapshots:
            return 0.0
        start_date = self.portfolio_snapshots[0].timestamp
        end_date = self.portfolio_snapshots[-1].timestamp
        return (end_date - start_date).days / 365.0

    def _get_drawdown(self, portfolio_snapshots: list[PortfolioSnapshot]) -> Drawdown:
        if not portfolio_snapshots:
            return Drawdown(value=0.0, percentage=0.0, recovery_duration_in_days=0)

        peak_equity = portfolio_snapshots[0].total_equity
        drawdown_start = portfolio_snapshots[0].timestamp
        peak_drawdown_value = 0.0
        peak_drawdown_percentage = 0.0
        peak_drawdown_recovery_duration_days = 0
        peak_drawdown_recovered = True

        for snapshot in portfolio_snapshots:
            equity = snapshot.total_equity

            if equity >= peak_equity:
                if not peak_drawdown_recovered:
                    peak_drawdown_recovery_duration_days = (
                        snapshot.timestamp - drawdown_start
                    ).days
                    peak_drawdown_recovered = True
                peak_equity = equity
                drawdown_start = snapshot.timestamp
                continue

            drawdown_value = peak_equity - equity
            drawdown_percentage = drawdown_value / peak_equity if peak_equity > 0 else 0

            if drawdown_percentage > peak_drawdown_percentage:
                peak_drawdown_value = drawdown_value
                peak_drawdown_percentage = drawdown_percentage
                peak_drawdown_recovered = False

        if not peak_drawdown_recovered:
            peak_drawdown_recovery_duration_days = -1

        return Drawdown(
            value=peak_drawdown_value,
            percentage=peak_drawdown_percentage,
            recovery_duration_in_days=peak_drawdown_recovery_duration_days,
        )

    def _get_equity_growth(
        self, portfolio_snapshots: list[PortfolioSnapshot]
    ) -> EquityGrowth:
        if not portfolio_snapshots:
            return EquityGrowth(
                initial_equity=0,
                final_equity=0,
                total_percentage_increase=0,
                yearly_equity={},
                yearly_percentage_increase={},
            )

        sorted_snapshots = sorted(portfolio_snapshots, key=lambda snap: snap.timestamp)
        initial_equity = sorted_snapshots[0].total_equity
        final_equity = sorted_snapshots[-1].total_equity
        total_percentage_increase = (
            (final_equity - initial_equity) / initial_equity * 100
            if initial_equity
            else 0
        )

        start_year = sorted_snapshots[0].timestamp.year
        end_year = sorted_snapshots[-1].timestamp.year

        # Equity as of 1 Jan of each year: last known equity at or before that date.
        yearly_equity: dict[int, float] = {}
        snapshot_idx = 0
        last_equity = initial_equity
        for year in range(start_year, end_year + 1):
            year_start = sorted_snapshots[0].timestamp.replace(
                year=year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            while (
                snapshot_idx < len(sorted_snapshots)
                and sorted_snapshots[snapshot_idx].timestamp <= year_start
            ):
                last_equity = sorted_snapshots[snapshot_idx].total_equity
                snapshot_idx += 1
            yearly_equity[year] = last_equity

        average_annual_percentage_increase = (
            total_percentage_increase / self.duration_years
            if self.duration_years
            else 0
        )

        sorted_years = sorted(yearly_equity)
        yearly_percentage_increase: dict[int, float] = {
            year: (
                (yearly_equity[year] - yearly_equity[prev_year])
                / yearly_equity[prev_year]
                * 100
                if yearly_equity[prev_year]
                else 0
            )
            for prev_year, year in pairwise(sorted_years)
        }

        return EquityGrowth(
            total_years=int(self.duration_years),
            initial_equity=initial_equity,
            final_equity=final_equity,
            total_percentage_increase=total_percentage_increase,
            avg_annual_percentage_increase=average_annual_percentage_increase,
            yearly_equity=yearly_equity,
            yearly_percentage_increase=yearly_percentage_increase,
        )

    def _get_group_metrics(
        self, label: str, condition: Callable[[LegSnapshot], bool]
    ) -> GroupMetrics:
        """Metrics for closed legs matching an arbitrary condition (e.g. duration bucket, sector)."""
        closed_snaps = [snap for snap in self.leg_snapshots if not snap.is_open]
        groups = [snap for snap in closed_snaps if condition(snap)]

        longs = [snap for snap in groups if snap.trade_type == TradeType.LONG]
        shorts = [snap for snap in groups if snap.trade_type == TradeType.SHORT]

        total_profit_in_r = sum(snap.profit_in_r for snap in groups)
        expectancy = total_profit_in_r / len(groups) if groups else 0
        opportunity = expectancy * len(groups) / self.duration_years if groups else 0

        wins = [snap for snap in groups if snap.profit_in_r > 0]
        win_rate = len(wins) / len(groups) if groups else 0
        long_wins = [snap for snap in longs if snap.profit_in_r > 0]
        long_win_rate = len(long_wins) / len(longs) if longs else 0
        short_wins = [snap for snap in shorts if snap.profit_in_r > 0]
        short_win_rate = len(short_wins) / len(shorts) if shorts else 0

        return GroupMetrics(
            label=label,
            num_legs=len(groups),
            total_win_rate=win_rate,
            total_absolute_profit=sum(snap.absolute_profit for snap in groups),
            total_profit_in_r=total_profit_in_r,
            expectancy=expectancy,
            opportunity=opportunity,
            num_long_legs=len(longs),
            long_win_rate=long_win_rate,
            long_absolute_profit=sum(snap.absolute_profit for snap in longs),
            long_profit_in_r=sum(snap.profit_in_r for snap in longs),
            num_short_legs=len(shorts),
            short_win_rate=short_win_rate,
            short_absolute_profit=sum(snap.absolute_profit for snap in shorts),
            short_profit_in_r=sum(snap.profit_in_r for snap in shorts),
        )

    @staticmethod
    def _format_duration_label(min_months: float, max_months: float) -> str:
        max_label = "inf" if max_months == float("inf") else f"{max_months:g}"
        return f"[{min_months:g}, {max_label})"

    def _get_leg_performance(self) -> list[GroupMetrics]:
        leg_numbers = sorted({snap.leg_number for snap in self.leg_snapshots})
        return [
            self._get_group_metrics(
                label=f"Leg {leg_number}",
                condition=lambda snap, ln=leg_number: snap.leg_number == ln,
            )
            for leg_number in leg_numbers
        ]

    def _get_duration_bucket_performance(self) -> list[GroupMetrics]:
        duration_ranges = [
            (0, 1),
            (1, 3),
            (3, 6),
            (6, 12),
            (12, 24),
            (24, 36),
            (36, 48),
            (48, float("inf")),
        ]
        return [
            self._get_group_metrics(
                label=self._format_duration_label(min_months, max_months),
                condition=lambda snap, lo=min_months, hi=max_months: (
                    lo <= snap.duration_months < hi
                ),
            )
            for min_months, max_months in duration_ranges
        ]

    def _get_sector_performance(self) -> list[GroupMetrics]:
        return [
            self._get_group_metrics(
                label=sector.value,
                condition=lambda snap, s=sector: snap.sector == s,
            )
            for sector in Sector
        ]

    def evaluate(self) -> str:
        description = f"Backtest Engine:\n{self.backtest_engine}\n"

        sector_perf = sorted(
            self._get_sector_performance(),
            key=lambda metrics: metrics.total_profit_in_r,
            reverse=True,
        )

        return format_evaluation(
            equity_growth=self._get_equity_growth(self.portfolio_snapshots),
            drawdown=self._get_drawdown(self.portfolio_snapshots),
            desc=description,
            group_metrics={
                "LEG COMPARISON": self._get_leg_performance(),
                "DURATION BUCKET COMPARISON": self._get_duration_bucket_performance(),
                "SECTOR COMPARISON": sector_perf,
            },
        )
