# 📈 KešMani — Trading Intelligence System

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red)
![License](https://img.shields.io/badge/License-MIT-green)
![Data](https://img.shields.io/badge/Data-yfinance%20%28free%29-yellow)

> **KešMani** is a professional-grade, Python-based trading intelligence platform that automatically fetches market data, runs technical and fundamental analysis, and delivers actionable trading recommendations via a **Streamlit web dashboard** and **automated email reports** — no paid API keys required.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Market Regime Detection** | Classifies market as BULLISH / BEARISH / NEUTRAL using benchmark ETFs |
| 🔍 **Composite Stock Screener** | Scores every ticker on a 0–100 scale across 5 dimensions |
| 🎯 **Signal Generation** | STRONG BUY / BUY / HOLD / SELL / AVOID with entry, stop, target prices |
| 🧮 **Risk Management** | Position sizing, portfolio heat gauge, R:R validation |
| 💼 **Portfolio Tracker** | Live P&L, add/remove positions, trade history |
| 📋 **Daily Report** | Automated morning briefing with actionable next steps |
| 📧 **Email Delivery** | HTML reports sent via SMTP (Gmail, Outlook, any provider) |
| 📈 **Interactive Charts** | Candlestick + RSI + MACD + Bollinger Bands in the browser |

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/eavdic87/kesmani.git
cd kesmani
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your email credentials (optional — only needed for email reports)
```

### 4. Run the dashboard

```bash
streamlit run dashboard/app.py
```

Open your browser at **http://localhost:8501** 🎉

---

## 📧 Email Reports

### Gmail Setup (recommended)

1. Enable 2-Factor Authentication on your Google account
2. Go to **Google Account → Security → App Passwords**
3. Create an app password for "Mail"
4. Add to your `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password_here
RECIPIENT_EMAIL=your@gmail.com
```

### Send a report manually

```python
from src.reports.email_sender import send_daily_report
send_daily_report()
```

### Schedule daily reports (Linux/macOS cron)

```bash
# Send report every weekday at 8:00 AM
crontab -e
# Add this line:
0 8 * * 1-5 /path/to/venv/bin/python -c "from src.reports.email_sender import send_daily_report; send_daily_report()" >> /var/log/kesmani.log 2>&1
```

---

## ⚙️ Configuration

All settings live in `config/settings.py`:

### Watchlist

```python
WATCHLIST = {
    "mega_cap": ["NVDA", "META", "AMZN", "MSFT", "AAPL", "GOOGL"],
    "semiconductors": ["SMH", "AMD", "AVGO"],
    "financials": ["JPM", "GS"],
    "energy": ["XLE", "CVX"],
    "growth": ["PLTR", "UBER", "CRWD"],
    "benchmarks": ["SPY", "QQQ", "IWM"],
}
```

### Portfolio settings

```python
PORTFOLIO_SETTINGS = {
    "starting_capital": 1000,       # change to your actual capital
    "max_risk_per_trade": 0.02,     # 2% risk per trade
    "max_portfolio_heat": 0.08,     # 8% max aggregate open risk
    "default_rr_ratio": 2.0,        # minimum reward-to-risk ratio
}
```

### Technical indicators

All RSI periods, MACD parameters, Bollinger Band settings, etc. are tunable in `TECHNICAL_SETTINGS`.

---

## 🏗️ Architecture

```
kesmani/
├── config/           Configuration (tickers, thresholds, email)
├── src/
│   ├── data/         Market data, fundamentals, news/catalysts (yfinance)
│   ├── analysis/     Technical indicators, screener, signals, risk manager
│   ├── portfolio/    Position tracker (portfolio.json)
│   ├── reports/      Daily report generator + email sender
│   └── utils/        Logging, formatters, helpers
├── dashboard/
│   ├── app.py        Main Streamlit app
│   ├── pages/        5 dashboard pages (market, screener, detail, portfolio, report)
│   └── components/   Reusable charts, tables, metric cards
├── data/
│   └── portfolio.json  Local portfolio state
└── tests/            pytest unit tests
```

### Data flow

```
yfinance API
    │
    ▼
src/data/              (fetch & cache OHLCV, fundamentals, earnings)
    │
    ▼
src/analysis/          (technical indicators → composite score → signal)
    │
    ├──► src/reports/  (daily_report.py → format_text / format_html → email)
    │
    └──► dashboard/    (Streamlit web UI with interactive charts)
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Tests use synthetic data — no network calls or API keys required.

---

## 📊 Dashboard Pages

| Page | URL Slug | Description |
|---|---|---|
| Home | `/` | Welcome & navigation |
| Market Overview | `01_market_overview` | Regime, benchmarks, catalysts |
| Stock Screener | `02_stock_screener` | Full scored watchlist |
| Stock Detail | `03_stock_detail` | Charts, indicators, signals |
| Portfolio | `04_portfolio` | Positions, P&L, risk heat |
| Daily Report | `05_daily_report` | Morning briefing + email |

---

## 💰 Stock Universe

| Group | Tickers |
|---|---|
| Mega-Cap Momentum | NVDA, META, AMZN, MSFT, AAPL, GOOGL |
| Semiconductors | SMH, AMD, AVGO |
| Financials | JPM, GS |
| Energy | XLE, CVX |
| Growth | PLTR, UBER, CRWD |
| Benchmarks | SPY, QQQ, IWM |

---

## ⚠️ Disclaimer

**KešMani is a trading intelligence tool, not financial advice.**

- All trading carries significant risk of loss
- Past performance does not guarantee future results
- Position sizing suggestions are based on mathematical models, not guaranteed outcomes
- Never risk more than you can afford to lose
- Always do your own research before entering any trade
- Consult a licensed financial advisor for personalised advice

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
