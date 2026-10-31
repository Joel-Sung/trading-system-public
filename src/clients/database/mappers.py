from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd
from custom_types.market import (
    Action,
    MarketAssets,
    MarketOrder,
    MarketPosition,
    OrderType,
    TradeType,
)
from custom_types.mode import Mode
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker
from system.portfolio.campaign import Campaign
from system.portfolio.leg import Leg
from system.portfolio.portfolio import Portfolio


def _safe_parse(value: Any, parser: Callable, default: Any = None) -> Any:
    """Helper to handle NaN or empty strings from CSVs."""
    if pd.isna(value) or value == "" or value is None:
        return default
    try:
        return parser(value)
    except (ValueError, TypeError):
        return default


def map_market_assets(row: pd.Series) -> MarketAssets:
    return MarketAssets(
        net_liquidation=float(row["net_liquidation"]),
        cash_balance=float(row["cash_balance"]),
        cash_available_for_trading=float(row["cash_available_for_trading"]),
        buying_power=float(row["buying_power"]),
        gross_position_value=float(row["gross_position_value"]),
        unrealized_pnl=float(row["unrealized_pnl"]),
        realized_pnl=float(row["realized_pnl"]),
    )


def map_market_position(row: pd.Series) -> MarketPosition:
    return MarketPosition(
        ticker=row["ticker"],
        trade_type=TradeType(row["trade_type"]),
        quantity=float(row["quantity"]),
        average_cost=float(row["average_cost"]),
        market_value=float(row["market_value"]),
        unrealized_pnl=float(row["unrealized_pnl"]),
        realized_pnl=float(row["realized_pnl"]),
    )


def map_market_order(row: pd.Series) -> MarketOrder:
    return MarketOrder(
        order_id=row["order_id"],
        ticker=row["ticker"],
        action=Action[row["action"]],
        order_type=OrderType[row["order_type"]],
        quantity=float(row["quantity"]),
        filled_quantity=float(row["filled_quantity"]),
        avg_fill_price=float(row["avg_fill_price"]),
        fees=float(row["fees"]),
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        limit_price=_safe_parse(row["limit_price"], float),
        stop_price=_safe_parse(row["stop_price"], float),
        status=row["status"],
    )


def map_portfolio(row: pd.Series) -> Portfolio:
    return Portfolio(
        initial_equity=float(row["initial_equity"]),
        cash_balance=_safe_parse(row["cash_balance"], float),
        cash_available_for_trading=_safe_parse(
            row["cash_available_for_trading"], float
        ),
    )


def map_campaign(row: pd.Series) -> Campaign:
    return Campaign(
        campaign_id=row["campaign_id"],
        ticker=Ticker(row["ticker"]),
        trade_type=TradeType(row["trade_type"]),
        entry_datetime=datetime.fromisoformat(row["entry_datetime"]),
        capital_invested=float(row["capital_invested"]),
        is_open=str(row["is_open"]).lower() == "true",
        exit_datetime=_safe_parse(row["exit_datetime"], datetime.fromisoformat),
        capital_returned=_safe_parse(row["capital_returned"], float, 0.0),
        mode=_safe_parse(row.get("mode"), Mode, Mode.NONE),
    )


def map_leg(row: pd.Series) -> Leg:
    leg = Leg(
        campaign_id=row["campaign_id"],
        leg_number=int(row["leg_number"]),
        ticker=Ticker(row["ticker"]),
        trade_type=TradeType(row["trade_type"]),
        entry_price=float(row["entry_price"]),
        entry_datetime=datetime.fromisoformat(row["entry_datetime"]),
        trading_fees=float(row["trading_fees"]),
        qty=float(row["initial_qty"]),
        stop_price=float(row["initial_stop_price"]),
    )

    # Restore the state that changes after the leg is created
    leg.current_qty = float(row["current_qty"])
    leg.current_stop_price = float(row["current_stop_price"])
    leg.current_price = float(row["current_price"])
    leg.current_absolute_profit = float(row["current_absolute_profit"])
    leg.current_profit_in_r = float(row["current_profit_in_r"])
    leg.current_datetime = datetime.fromisoformat(row["current_datetime"])
    leg.peak_absolute_profit = float(row["peak_absolute_profit"])
    leg.peak_profit_in_r = float(row["peak_profit_in_r"])
    leg.peak_profit_datetime = datetime.fromisoformat(row["peak_profit_datetime"])
    leg.is_open = str(row["is_open"]).lower() == "true"
    leg.exit_datetime = _safe_parse(row["exit_datetime"], datetime.fromisoformat)
    leg.avg_exit_price = float(row["avg_exit_price"])
    leg.absolute_profit = float(row["absolute_profit"])
    leg.profit_in_r = float(row["profit_in_r"])
    leg.margin_fees = float(row["margin_fees"])

    return leg



def map_system_order(row: pd.Series) -> SystemOrder:
    return SystemOrder(
        ticker=Ticker[row["ticker"]],
        action=Action[row["action"]],
        order_type=OrderType[row["order_type"]],
        quantity=float(row["quantity"]),
        submitted_dt=datetime.fromisoformat(row["submitted_dt"]),
        limit_price=_safe_parse(row["limit_price"], float),
        stop_price=_safe_parse(row["stop_price"], float),
    )
