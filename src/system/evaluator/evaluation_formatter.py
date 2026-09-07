from system.evaluator.evaluation_types import Drawdown, EquityGrowth, GroupMetrics


def format_evaluation(
    equity_growth: EquityGrowth,
    drawdown: Drawdown,
    desc: str = "",
    group_metrics: dict[str, list[GroupMetrics]] | None = None,
) -> str:
    """Formats evaluation metrics into a human-readable report string."""
    lines: list[str] = []
    border = "=" * 115

    if desc:
        lines.append(border)
        lines.append("DESCRIPTION")
        lines.append(border)
        lines.append(f"{desc}\n")

    lines.append(border)
    lines.append("DRAWDOWN")
    lines.append(border)
    lines.append(f"{drawdown}\n")

    lines.append(border)
    lines.append("EQUITY GROWTH")
    lines.append(border)
    lines.append(_format_equity_growth(equity_growth))

    # Group Comparison Tables (e.g. leg number, duration bucket, sector)
    if group_metrics:
        for title, metrics in group_metrics.items():
            lines.append(_format_group_table(title, metrics))

    return "\n".join(lines) + "\n"


def _format_equity_growth(equity_growth: EquityGrowth) -> str:
    yearly_lines = "\n".join(
        f"  {year}: equity ($) = {equity:,.2f}"
        + (
            f", yoy_increase (%) = {equity_growth.yearly_percentage_increase[year]:.2f}"
            if year in equity_growth.yearly_percentage_increase
            else ""
        )
        for year, equity in sorted(equity_growth.yearly_equity.items())
    )
    return (
        f"initial_equity            ($) = {equity_growth.initial_equity:,.2f}\n"
        f"final_equity              ($) = {equity_growth.final_equity:,.2f}\n"
        f"total_percentage_increase (%) = {equity_growth.total_percentage_increase:.2f}\n"
        f"average_annual_percentage_increase (%) = {equity_growth.avg_annual_percentage_increase:.2f}\n"
        f"yearly_equity (as of 1 Jan):\n{yearly_lines}\n"
    )


def _format_group_table(title: str, metrics: list[GroupMetrics]) -> str:
    header = (
        f"{'Label':<25} | "
        f"{'Expectancy':>10} | {'Opportunity':>11} | "
        f"{'# Legs':>8} | {'Total Win (%)':>14} | {'Total Profit ($)':>17} | {'Total Profit (R)':>17} | "
        f"{'# Long':>8} | {'Long Win (%)':>12} | {'Long Profit ($)':>15} | {'Long Profit (R)':>15} | "
        f"{'# Short':>8} | {'Short Win (%)':>13} | {'Short Profit ($)':>16} | {'Short Profit (R)':>16}"
    )
    border = "=" * len(header)

    lines = [border, title, f"{border}\n", header, "-" * len(header)]

    for group in metrics:
        total_win_pct = f"{group.total_win_rate * 100:.2f}%"
        long_win_pct = f"{group.long_win_rate * 100:.2f}%"
        short_win_pct = f"{group.short_win_rate * 100:.2f}%"

        row = (
            f"{group.label:<25} | "
            f"{group.expectancy:>10.3f} | "
            f"{group.opportunity:>11.3f} | "
            f"{group.num_legs:>8} | "
            f"{total_win_pct:>14} | "
            f"{group.total_absolute_profit:>17,.3f} | "
            f"{group.total_profit_in_r:>17,.3f} | "
            f"{group.num_long_legs:>8} | "
            f"{long_win_pct:>12} | "
            f"{group.long_absolute_profit:>15,.3f} | "
            f"{group.long_profit_in_r:>15,.3f} | "
            f"{group.num_short_legs:>8} | "
            f"{short_win_pct:>13} | "
            f"{group.short_absolute_profit:>16,.3f} | "
            f"{group.short_profit_in_r:>16,.3f}"
        )
        lines.append(row)

    lines.append("-" * len(header) + "\n")
    return "\n".join(lines)
