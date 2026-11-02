# Trading System

A Python-based systematic trading and backtesting system for researching and evaluating trading strategies.

The system is inspired by the position sizing, risk management, and trading principles discussed in *Trade Your Way to Financial Freedom* by Van K. Tharp.

The trading strategies and models are maintained separately and are not included in this public repository.

## Setup

### 1. Create and activate a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

## Run Backtest

```bash
python scripts/backtest.py
```

## Run Tests

Run from the project root. Install pytest first if needed: `pip install -e ".[dev]"`.

```bash
pytest                                  # all tests
pytest tests/unit/clients -v            # one folder, verbose
pytest -k closed_campaign               # by name
```

If `pytest` or `python -m pytest` reports `No module named pytest`, the virtual environment is not active. Activate it (`.venv\Scripts\activate`), or call it directly with `.venv\Scripts\python.exe -m pytest`.
