# Backtest Engine Flow

Orange boxes modify data or state. Blue cylinders are data.

## Level 1: Backtest Overview

The whole backtest in four steps. Everything after setup replays the live trading application on historical data.

```mermaid
flowchart LR
    RAW[("Raw market data")]:::data
    subgraph BE["BacktestEngine"]
        I["__init__()<br/>clean data, build stubs and TradingEngine"]:::modify
        R["_run_backtest()<br/>replay every bar day"]:::modify
        O["run()<br/>save snapshots, evaluate"]:::modify
    end
    OUT[("snaps_*.csv<br/>snaps_evaluation.txt")]:::data

    RAW -->|"input bars"| I
    I -->|"engine ready"| R
    R -->|"snapshots collected"| O
    O --> OUT

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
    classDef data fill:#dfefff,stroke:#3b7dd8,color:#000
```

## Level 2: Daily Loop Overview

What happens on each bar day, and which system does it. The loop repeats until the data runs out or equity falls to 1% of the starting equity.

```mermaid
flowchart TD
    subgraph BE["BacktestEngine"]
        L{"next bar_datetime?"}
        BR{"equity <= 1% of initial?"}
        END["final snapshot, then post-run steps"]
    end
    subgraph TE["TradingEngine"]
        T["run(end_time)<br/>read, align, decide, place orders, save"]
    end
    subgraph SB["StubBrokerClient"]
        K["advance()<br/>next bar, fill orders, re-value positions"]:::modify
    end
    subgraph SC["SnapshotCollector"]
        C["collect_state()<br/>record the day"]:::modify
    end

    L -->|"day left: trade it"| T
    T -->|"orders placed, move the market on"| K
    K -->|"day complete, record it"| C
    C -->|"check for ruin"| BR
    BR -->|"no: LOOP to next day"| L
    BR -->|"yes: stop early"| END
    L -->|"no days left"| END

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
```

## Level 3a: Initialisation

`BacktestEngine.__init__()` runs once. It prepares the data and wires the stubs into a `TradingEngine`, so `run()` only replays.

```mermaid
flowchart TD
    RAW[("Raw market_data")]:::data
    PF[("Initial Portfolio")]:::data

    subgraph BE["BacktestEngine"]
        B1["_preprocess_data()<br/>filter included/excluded tickers (DOW),<br/>format_market_data: sort by datetime"]:::modify
        B2["_get_run_datetimes()<br/>skip first min_bars_req_for_inds-1 bars,<br/>keep bars >= start_date"]:::modify
        B3["__init__()<br/>build TradingEngine with BrokerService,<br/>Strategy, DatabaseService, Logger"]
    end
    subgraph SB["StubBrokerClient"]
        S1["__init__()<br/>split bars per ticker, set cash,<br/>set clock to first run day"]:::modify
    end
    subgraph SD["StubDatabaseClient + DatabaseService"]
        D1["save_portfolio()<br/>store the starting portfolio in memory"]:::modify
    end
    subgraph TE["TradingEngine"]
        T1["__init__()<br/>create AlignDataHandler and PositionManager"]
    end

    RAW -->|"all bars"| B1
    B1 -->|"need the days to replay"| B2
    B2 -->|"cleaned bars and start day"| S1
    PF -->|"initial cash"| S1
    PF -->|"starting portfolio"| D1
    B2 -->|"days found, wire up engine"| B3
    S1 -->|"broker client"| B3
    D1 -->|"database service"| B3
    B3 --> T1

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
    classDef data fill:#dfefff,stroke:#3b7dd8,color:#000
```

## Level 3b: TradingEngine.run()

One trading day. This is the same code the live application runs, just against the stub broker and stub database.

```mermaid
flowchart TD
    subgraph TE["TradingEngine.run(end_time)"]
        T1["_get_broker_data()<br/>assets, positions, last min_bars_req_for_inds bars"]
        T2["_get_portfolio_data()<br/>load yesterday's portfolio"]
        T3["_align_portfolio_data()<br/>make the portfolio match the broker"]:::modify
        T4["_create_orders()<br/>decide orders for every ticker"]:::modify
        T5["_place_orders()<br/>send orders to the broker"]
        T6["_save_portfolio()<br/>store the updated portfolio"]:::modify
    end
    subgraph ST["Strategy"]
        P["prepare_data()<br/>ticker/sector filters, entry model adds indicators"]:::modify
    end
    subgraph BS["BrokerService to StubBrokerClient"]
        G["get_assets / get_positions / get_market_data<br/>(bars never later than the current clock)"]
        PO["place_orders()<br/>add to pending_orders"]:::modify
    end
    subgraph DS["DatabaseService"]
        GP["get_portfolio()"]
        SP["save_portfolio()"]:::modify
    end
    subgraph AL["AlignDataHandler"]
        A["align_campaigns() / align_portfolio()<br/>see 3c"]:::modify
    end
    subgraph PM["PositionManager"]
        M["create_system_orders()<br/>see 3d"]:::modify
    end

    T1 -.-> G
    T1 -->|"raw bars need indicators"| P
    P -->|"need the system's own state"| T2
    T2 -.-> GP
    T2 -->|"broker is the source of truth for fills"| T3
    T3 -.-> A
    T3 -->|"portfolio up to date, look for trades"| T4
    T4 -.-> M
    T4 -->|"orders ready"| T5
    T5 -.-> PO
    T5 -->|"persist for tomorrow"| T6
    T6 -.-> SP

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
```

## Level 3c: AlignDataHandler

Syncs the system's portfolio and campaigns with what the broker actually holds, because the broker filled or closed orders since yesterday.

```mermaid
flowchart TD
    subgraph AL["AlignDataHandler"]
        A0["align_campaigns()<br/>start with the broker's positions"]
        A1{"next broker position?"}
        A2["no campaign:<br/>_create_campaign()<br/>create campaign, pending leg, fill it"]:::modify
        A3["campaign qty < position qty:<br/>_get_fill_price(), Portfolio.fill_legs()<br/>fill pending legs"]:::modify
        A4["campaign qty > position qty:<br/>Portfolio.sell_campaign_qty()<br/>reduce the campaign"]:::modify
        A5{"next open campaign<br/>with no position?"}
        A6["qty is 0:<br/>Portfolio.cancel_unfilled_campaign()"]:::modify
        A7["qty > 0:<br/>Portfolio.sell_campaign_qty()<br/>close at latest close"]:::modify
        A8["align_portfolio()<br/>overwrite cash_balance and cash_available<br/>with the broker's assets"]:::modify

        A0 --> A1
        A1 -->|"position found"| A2
        A1 -->|"position found"| A3
        A1 -->|"position found"| A4
        A2 -->|"LOOP: next position"| A1
        A3 -->|"LOOP: next position"| A1
        A4 -->|"LOOP: next position"| A1
        A1 -->|"positions done, check campaigns the broker no longer holds"| A5
        A5 -->|"unfilled"| A6
        A5 -->|"was filled, now closed"| A7
        A6 -->|"LOOP: next campaign"| A5
        A7 -->|"LOOP: next campaign"| A5
        A5 -->|"campaigns done, sync cash last"| A8
    end

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
```

Branches that need no change (quantities already match) skip straight to the next position. `AlignDataHandler` also calls `Strategy.get_r_value()` when it creates a campaign.

## Level 3d: PositionManager

Decides the orders for the day. The outer loop runs once per ticker. Each ticker either looks for an entry or manages its open campaign.

```mermaid
flowchart TD
    subgraph PM["PositionManager.create_system_orders()"]
        P0{"next ticker?<br/>(market_data.groupby)"}
        P1["_create_system_orders_for_ticker()<br/>skip if fewer than min_bars_req_for_entry bars"]
        P2["_check_for_entry()<br/>no open campaign"]
        P3["_create_leg_order()<br/>size, risk, limit and stop prices,<br/>create a pending leg"]:::modify
        P4["_manage_existing_campaign()<br/>open campaign"]
        P5["_check_for_mode_change()<br/>change_mode() if the mode differs"]:::modify
        P6["Portfolio.update_with_current_bar()<br/>update campaign with the latest bar"]:::modify
        P7["_update_trailing_stops()<br/>leg.move_stop(), build STP orders"]:::modify
        P8["_check_for_pyramid_add()<br/>only if no leg is pending"]
        P9["system_orders.extend()<br/>collect this ticker's orders"]
    end
    subgraph ST["Strategy (delegates to models)"]
        M1["get_long_signal / get_short_signal<br/>(entry_model)"]
        M2["calculate_qty()<br/>(position_sizing_model)"]
        M3["get_r_value()<br/>(risk_model)"]
        M4["get_new_mode()<br/>(entry_model)"]
        M5["get_new_stops()<br/>(stop_model)"]
        M6["should_pyramid()<br/>(pyramid_model)"]
    end

    P0 -->|"ticker's bars"| P1
    P1 -->|"no open campaign"| P2
    P1 -->|"open campaign"| P4
    P2 -->|"one signal fired"| P3
    P2 -->|"no signal"| P9
    P3 -->|"entry or add order"| P9
    P4 -->|"mode may have changed"| P5
    P5 -->|"refresh campaign values"| P6
    P6 -->|"protect the position"| P7
    P7 -->|"may add a leg"| P8
    P7 -->|"stop orders"| P9
    P8 -->|"pyramid: add leg"| P3
    P8 -->|"no add"| P9
    P9 -->|"LOOP: next ticker"| P0
    P0 -->|"all tickers done, return orders"| END["to TradingEngine._place_orders()"]

    P2 -.-> M1
    P3 -.-> M2
    P3 -.-> M3
    P5 -.-> M4
    P7 -.-> M5
    P8 -.-> M6

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
```

## Level 3e: StubBrokerClient.advance()

Moves the fake market one bar forward. Orders placed on the previous day are filled here, using the new bar's high and low.

```mermaid
flowchart TD
    subgraph SB["StubBrokerClient.advance()"]
        K1["advance()<br/>current_index += 1, set current_datetime<br/>(does nothing on the last bar)"]:::modify
        K2["_charge_margin_interest()<br/>daily interest on every short"]:::modify
        K3{"next pending order?"}
        K4["_get_fill_price()<br/>LMT: low/high reaches limit.<br/>STP: high/low reaches stop"]
        K5["_fill_order()<br/>_open_position() or _close_position(),<br/>update cash and realised PnL"]:::modify
        K6["_trigger_attached_stop()<br/>LMT_STP: close at the stop if the bar reached it"]:::modify
        K7["pending_orders = []<br/>unfilled orders are dropped"]:::modify
        K8["_update_positions()<br/>re-value at the close,<br/>update net liquidation and unrealised PnL"]:::modify
    end

    K1 -->|"a new day costs interest"| K2
    K2 -->|"fill yesterday's orders"| K3
    K3 -->|"order found"| K4
    K4 -->|"price reached"| K5
    K4 -->|"not reached: LOOP"| K3
    K5 -->|"LMT_STP order opened"| K6
    K5 -->|"LOOP: next order"| K3
    K6 -->|"LOOP: next order"| K3
    K3 -->|"orders done, clear the list"| K7
    K7 -->|"positions changed, refresh values"| K8

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
```

## Level 3f: SnapshotCollector

`collect_state()` is called three ways: once at the start, once per day, and once at the end. Only the final call produces leg and closed campaign snapshots.

```mermaid
flowchart TD
    subgraph SC["SnapshotCollector.collect_state()"]
        S0["collect_state(is_start)<br/>PortfolioSnapshot.from_portfolio()"]:::modify
        S1["collect_state() each day<br/>PortfolioSnapshot.from_portfolio()"]:::modify
        S2{"timestamp.day == 1?"}
        S3["CampaignSnapshot.from_campaign()<br/>for each open campaign"]:::modify
        S4["collect_state(is_end)<br/>LegSnapshot.from_leg() for each filled leg"]:::modify
        S5["CampaignSnapshot.from_campaign()<br/>for each closed campaign"]:::modify
    end
    BE["BacktestEngine._run_backtest()"]

    BE -->|"before the loop"| S0
    BE -->|"LOOP: after every day"| S1
    S1 -->|"monthly campaign check"| S2
    S2 -->|"yes"| S3
    BE -->|"after the loop"| S4
    S4 -->|"closed campaigns"| S5

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
```

## Level 3g: Post-run (save and evaluate)

After the loop, `BacktestEngine.run()` writes the snapshots to disk, then evaluates them and writes the report.

```mermaid
flowchart TD
    SNAP[("SnapshotCollector<br/>portfolio, campaign, leg snapshots")]:::data

    subgraph BE["BacktestEngine.run()"]
        R1["_save_states()<br/>write the snapshot lists"]
        R2["_evaluate_and_save_evaluation()<br/>evaluate and write the report"]
    end
    subgraph DB["DatabaseClient (writes to disk)"]
        W1["save() + backup()<br/>snaps_portfolio.csv<br/>snaps_campaigns.csv<br/>snaps_legs.csv (sorted by ticker, fill time)"]:::modify
        W2["save() + backup()<br/>snaps_evaluation.txt"]:::modify
    end
    subgraph EV["SystemEvaluator"]
        V1["evaluate()<br/>equity growth, drawdown,<br/>leg, duration bucket and sector metrics"]:::modify
        V2["format_evaluation()<br/>build the text report"]:::modify
    end

    SNAP -->|"snapshots"| R1
    R1 --> W1
    W1 -->|"files written, now measure them"| R2
    R2 -->|"leg and portfolio snapshots"| V1
    V1 -->|"metrics computed"| V2
    V2 -->|"report text"| W2

    classDef modify fill:#ffe3c2,stroke:#d9822b,color:#000
    classDef data fill:#dfefff,stroke:#3b7dd8,color:#000
```
