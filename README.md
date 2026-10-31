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
```bash
.venv\Scripts\python.exe -m pytest
pytest                                                    # all tests
pytest tests/unit/clients/database/test_database_service.py -v   # one file, verbose
pytest -k closed_campaign                                 # by name
```