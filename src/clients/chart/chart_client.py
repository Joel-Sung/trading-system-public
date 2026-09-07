import pandas as pd
import plotly.graph_objects as go
from custom_types.market import TradeType
from plotly.subplots import make_subplots
from system.indicator.indicator_types import Indicator
from util.df_util import does_df_contain_cols


class ChartClient:
    def __init__(self, ticker_data: pd.DataFrame, trade_data: pd.DataFrame):
        self.ticker_data = ticker_data
        self.trade_data = trade_data

        self.fig = make_subplots(
            rows=1,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.20,
        )

        self.fig.update_layout(
            dragmode="pan",
            hovermode="x unified",
            yaxis={
                "fixedrange": False,
                "autorange": True,
                "showgrid": True,
            },
            xaxis_rangeslider_visible=True,
            autosize=True,
        )

        self.fig.update_xaxes(
            showspikes=True,
            spikecolor="black",
            spikethickness=1,
            spikedash="dot",
            spikemode="across",
            type="date",
            tickformat="%Y-%m-%d",
            matches="x",
            showticklabels=True,
        )

    def add_candlesticks(self):
        df = self.ticker_data

        if not does_df_contain_cols(
            df,
            [
                Indicator.DATETIME,
                Indicator.OPEN,
                Indicator.HIGH,
                Indicator.LOW,
                Indicator.CLOSE,
            ],
        ):
            return self

        df[Indicator.DATETIME] = pd.to_datetime(df[Indicator.DATETIME])

        def make_range(n):
            n = min(n, len(df)) if n > 0 else len(df)
            return [
                df[Indicator.DATETIME].iloc[-n],
                df[Indicator.DATETIME].iloc[-1],
            ]

        self.fig.update_layout(
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.0,
                    "y": 1.15,
                    "showactive": True,
                    "buttons": [
                        {
                            "label": "100",
                            "method": "relayout",
                            "args": [{"xaxis.range": make_range(100)}],
                        },
                        {
                            "label": "200",
                            "method": "relayout",
                            "args": [{"xaxis.range": make_range(200)}],
                        },
                        {
                            "label": "All",
                            "method": "relayout",
                            "args": [{"xaxis.range": make_range(0)}],
                        },
                    ],
                }
            ]
        )

        self.fig.add_trace(
            go.Candlestick(
                x=df[Indicator.DATETIME],
                open=df[Indicator.OPEN],
                high=df[Indicator.HIGH],
                low=df[Indicator.LOW],
                close=df[Indicator.CLOSE],
                name="Price",
            ),
            row=1,
            col=1,
        )

        return self

    def add_rolling_high(self):
        df = self.ticker_data

        if not does_df_contain_cols(df, [Indicator.DATETIME, Indicator.ROLLING_HIGH]):
            return self

        self.fig.add_trace(
            go.Scatter(
                x=df[Indicator.DATETIME],
                y=df[Indicator.ROLLING_HIGH],
                line={"dash": "dash"},
                name="Rolling High",
            ),
            row=1,
            col=1,
        )

        return self

    def add_rolling_low(self):
        df = self.ticker_data

        if not does_df_contain_cols(df, [Indicator.DATETIME, Indicator.ROLLING_LOW]):
            return self

        self.fig.add_trace(
            go.Scatter(
                x=df[Indicator.DATETIME],
                y=df[Indicator.ROLLING_LOW],
                line={"dash": "dash"},
                name="Rolling Low",
            ),
            row=1,
            col=1,
        )

        return self

    def add_atr(self):
        df = self.ticker_data

        if not does_df_contain_cols(df, [Indicator.DATETIME, Indicator.ATR]):
            return self

        self.fig.add_trace(
            go.Scatter(
                x=df[Indicator.DATETIME],
                y=df[Indicator.ATR],
                name="ATR",
            ),
            row=2,
            col=1,
        )

        self.fig.add_annotation(
            text="ATR",
            x=0,
            y=1,
            xref="x2 domain",
            yref="y2 domain",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
        )

        return self

    def add_trades(self):
        df = self.trade_data

        if not does_df_contain_cols(
            df,
            [
                "type",
                Indicator.ENTRY_TIME,
                Indicator.ENTRY_PRICE,
                Indicator.EXIT_TIME,
                Indicator.EXIT_PRICE,
                "profit_in_r",
                "stops",
            ],
        ):
            return self

        symbols = df["type"].apply(
            lambda t: "triangle-up" if t == TradeType.LONG else "triangle-down"
        )

        entryTextPositions = df["type"].apply(
            lambda t: "bottom center" if t == TradeType.LONG else "top center"
        )

        exitTextPositions = df["type"].apply(
            lambda t: "top center" if t == TradeType.LONG else "bottom center"
        )

        self.fig.add_trace(
            go.Scatter(
                x=df[Indicator.ENTRY_TIME],
                y=df[Indicator.ENTRY_PRICE],
                mode="markers+text",
                name="Entry",
                marker={"symbol": symbols, "size": 10},
                text=df["type"],
                textposition=entryTextPositions,
                hovertemplate="Entry<br>Time: %{x}<br>Price: %{y}<br>Type: %{text}",
            )
        )

        self.fig.add_trace(
            go.Scatter(
                x=df[Indicator.EXIT_TIME],
                y=df[Indicator.EXIT_PRICE],
                mode="markers+text",
                name="Exit",
                marker={"symbol": symbols, "size": 10},
                text=df["profit_in_r"],
                textposition=exitTextPositions,
                hovertemplate="Exit<br>Time: %{x}<br>Price: %{y}<br>R: %{text}",
            )
        )

        for idx, stops in enumerate(df["stops"]):
            x = [s.date for s in stops]
            y = [s.val for s in stops]

            if len(y) == 1:
                x.append(df[Indicator.EXIT_TIME].iloc[idx])
                y.append(y[0])

            self.fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines+markers",
                    line={"color": "blue", "width": 2},
                    line_shape="hv",
                    marker={"symbol": "x", "size": 8, "color": "blue"},
                    opacity=0.7,
                    showlegend=False,
                    hovertemplate="Time: %{x}<br>Stop: %{y}",
                )
            )

        for _, row in df.iterrows():
            if pd.isna(row[Indicator.EXIT_TIME]):
                continue

            is_profit = row["profit_in_r"] > 0
            fill_color = "rgba(0, 200, 0, 0.2)" if is_profit else "rgba(200, 0, 0, 0.2)"
            line_color = "green" if is_profit else "red"

            self.fig.add_shape(
                type="rect",
                x0=row[Indicator.ENTRY_TIME],
                x1=row[Indicator.EXIT_TIME],
                y0=min(row[Indicator.ENTRY_PRICE], row[Indicator.EXIT_PRICE]),
                y1=max(row[Indicator.ENTRY_PRICE], row[Indicator.EXIT_PRICE]),
                fillcolor=fill_color,
                line={"color": line_color, "width": 1},
                layer="below",
            )

        return self

    def add_title(self, title: str):
        self.fig.update_layout(title=title)
        return self

    def plot(self):
        self.fig.show(config={"scrollZoom": True})
        return self
