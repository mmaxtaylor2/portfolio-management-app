import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import datetime
import os
import math

# ============================================
# BASIC SETUP
# ============================================
st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("Portfolio Management App")

TRADES_FILE = "transactions.csv"
CASH_FILE = "cash_balance.csv"
HISTORY_FILE = "value_history.csv"

TODAY = datetime.date.today().isoformat()

# ============================================
# INITIALIZE FILES (IF MISSING)
# ============================================
if not os.path.exists(TRADES_FILE):
    pd.DataFrame(
        columns=["Date", "Action", "Ticker", "Shares", "Price", "Total"]
    ).to_csv(TRADES_FILE, index=False)

if not os.path.exists(CASH_FILE):
    pd.DataFrame({"Cash": [0.0]}).to_csv(CASH_FILE, index=False)

if not os.path.exists(HISTORY_FILE):
    pd.DataFrame(
        columns=["Date", "PortfolioValue", "Cash", "NetWorth", "UnrealizedPL", "RealizedPL"]
    ).to_csv(HISTORY_FILE, index=False)

# ============================================
# LOAD DATA
# ============================================
trades = pd.read_csv(TRADES_FILE)
cash = float(pd.read_csv(CASH_FILE)["Cash"].iloc[0])
history = pd.read_csv(HISTORY_FILE)

def to_num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0.0)

if not trades.empty:
    trades["Shares"] = to_num(trades["Shares"])
    trades["Price"] = to_num(trades["Price"])
    trades["Total"] = to_num(trades["Total"])
    trades["Ticker"] = trades["Ticker"].astype(str).str.upper()

# ============================================
# FIFO ENGINE
# ============================================
def build_fifo(trades_df: pd.DataFrame):
    """
    From raw trades, build FIFO lots, realized P/L per trade, and end positions.
    """
    if trades_df.empty:
        return pd.Series(dtype=float), {}

    trades_df = trades_df.reset_index(drop=True)
    realized = pd.Series(0.0, index=trades_df.index)
    positions = {}

    for ticker, subset in trades_df.groupby("Ticker", sort=False):
        lots = []
        for i, row in subset.iterrows():
            sh = float(row["Shares"])
            price = float(row["Price"])
            action = row["Action"]

            if action == "Buy":
                lots.append({"shares": sh, "cost": price})
                realized.loc[i] = 0.0
            else:  # Sell
                remaining = sh
                pl = 0.0
                while remaining > 0 and lots:
                    lot = lots[0]
                    take = min(remaining, lot["shares"])
                    pl += take * (price - lot["cost"])
                    lot["shares"] -= take
                    remaining -= take
                    if lot["shares"] <= 0:
                        lots.pop(0)
                realized.loc[i] = pl

        shares_left = sum(l["shares"] for l in lots)
        cost_left = sum(l["shares"] * l["cost"] for l in lots)
        positions[ticker] = {"shares": shares_left, "cost": cost_left}

    return realized, positions

realized_series, positions_dict = build_fifo(trades)
total_realized_pl = float(realized_series.sum()) if not realized_series.empty else 0.0

# ============================================
# PRICE LOADER (SAFE)
# ============================================
def load_prices(tickers):
    """
    Returns a Series mapping ticker -> latest price.
    Uses yfinance with safe fallbacks.
    """
    if not tickers:
        return pd.Series(dtype=float)

    try:
        data = yf.download(tickers, period="1d", progress=False)
    except Exception:
        return pd.Series(index=tickers, data=float("nan"))

    if data is None or len(data) == 0:
        return pd.Series(index=tickers, data=float("nan"))

    for col in ["Adj Close", "Close"]:
        try:
            if isinstance(data.columns, pd.MultiIndex) and col in data.columns.get_level_values(0):
                return data[col].iloc[-1]
            if col in data.columns:
                return data[col].iloc[-1]
        except Exception:
            pass

    return pd.Series(index=tickers, data=float("nan"))

def get_single_price(ticker: str) -> float:
    """
    Helper to get a single ticker's latest price.
    """
    s = load_prices([ticker])
    if ticker in s.index:
        p = s[ticker]
        try:
            p = float(p)
            if not math.isnan(p) and p > 0:
                return p
        except Exception:
            pass
    return float("nan")

# ============================================
# BUILD HOLDINGS VIEW
# ============================================
def build_holdings_view(positions: dict):
    """
    Create net positions with avg cost, price, and unrealized P/L.
    """
    if not positions:
        return pd.DataFrame(
            columns=[
                "Ticker", "Shares", "AvgCost", "Price",
                "MarketValue", "CostValue", "UnrealizedPL", "UnrealizedPL_%"
            ]
        )

    rows = []
    for t, pos in positions.items():
        sh = pos["shares"]
        if sh <= 0:
            continue
        cost = pos["cost"]
        avg_cost = cost / sh if sh != 0 else 0.0
        rows.append([t, sh, avg_cost])

    if not rows:
        return pd.DataFrame(
            columns=[
                "Ticker", "Shares", "AvgCost", "Price",
                "MarketValue", "CostValue", "UnrealizedPL", "UnrealizedPL_%"
            ]
        )

    df = pd.DataFrame(rows, columns=["Ticker", "Shares", "AvgCost"])
    prices = load_prices(df["Ticker"].tolist())
    df["Price"] = df["Ticker"].map(prices)
    df["MarketValue"] = df["Shares"] * df["Price"]
    df["CostValue"] = df["Shares"] * df["AvgCost"]
    df["UnrealizedPL"] = df["MarketValue"] - df["CostValue"]
    df["UnrealizedPL_%"] = (df["UnrealizedPL"] / df["CostValue"]) * 100
    df = df.fillna(0.0)
    return df

holdings = build_holdings_view(positions_dict)
portfolio_value = float(holdings["MarketValue"].sum()) if not holdings.empty else 0.0
total_unrealized_pl = float(holdings["UnrealizedPL"].sum()) if not holdings.empty else 0.0
net_worth = portfolio_value + cash

# ============================================
# SNAPSHOT HISTORY (AUTO AFTER TRADE / CASH CHANGE)
# ============================================
def record_snapshot():
    """
    Recompute holdings, P/L, and net worth from files and append
    a new row to value_history.csv.
    """
    trades_local = pd.read_csv(TRADES_FILE)
    cash_local = float(pd.read_csv(CASH_FILE)["Cash"].iloc[0])

    realized_local, positions_local = build_fifo(trades_local)
    holdings_local = build_holdings_view(positions_local)

    portfolio_val = float(holdings_local["MarketValue"].sum()) if not holdings_local.empty else 0.0
    unrealized_local = float(holdings_local["UnrealizedPL"].sum()) if not holdings_local.empty else 0.0
    realized_total = float(realized_local.sum()) if not realized_local.empty else 0.0
    net_worth_local = portfolio_val + cash_local

    hist = pd.read_csv(HISTORY_FILE)
    hist.loc[len(hist)] = [
        TODAY,
        portfolio_val,
        cash_local,
        net_worth_local,
        unrealized_local,
        realized_total
    ]
    hist.to_csv(HISTORY_FILE, index=False)

# ============================================
# STATEMENT BUILDER (FOR CSV DOWNLOAD)
# ============================================
def build_statement_df():
    sections = []

    # Holdings section
    if not holdings.empty:
        h = holdings.copy().round(2)
        h.insert(0, "Section", "Holdings")
        sections.append(h)

    # Trades section
    if not trades.empty:
        t = trades.copy()
        if not realized_series.empty:
            t["RealizedPL"] = realized_series.values
        else:
            t["RealizedPL"] = 0.0
        t = t.round(2)
        t.insert(0, "Section", "Trades")
        sections.append(t)

    # Summary section
    summary = pd.DataFrame(
        [{
            "Section": "Summary",
            "Date": TODAY,
            "NetWorth": net_worth,
            "PortfolioValue": portfolio_value,
            "Cash": cash,
            "TotalRealizedPL": total_realized_pl,
            "TotalUnrealizedPL": total_unrealized_pl
        }]
    )
    sections.append(summary)

    statement_df = pd.concat(sections, ignore_index=True, sort=False)
    return statement_df

# ============================================
# NAVIGATION
# ============================================
page = st.sidebar.selectbox(
    "Navigate",
    ["Dashboard", "Holdings", "Trade", "Cash", "Charts", "Transactions"]
)

# ============================================
# DASHBOARD
# ============================================
if page == "Dashboard":
    st.header("Portfolio Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net Worth", f"${net_worth:,.2f}")
    col2.metric("Portfolio Value", f"${portfolio_value:,.2f}")
    col3.metric("Cash", f"${cash:,.2f}")
    col4.metric("Realized P/L (FIFO)", f"${total_realized_pl:,.2f}")

    if not holdings.empty:
        st.subheader("Current Holdings")
        st.dataframe(holdings.round(2))
    else:
        st.info("No holdings yet. Record a trade to begin.")

    # Downloadable statement
    st.subheader("Export")
    statement_df = build_statement_df()
    statement_csv = statement_df.to_csv(index=False)
    st.download_button(
        label="Download Account Statement (CSV)",
        data=statement_csv,
        file_name="account_statement.csv",
        mime="text/csv"
    )

# ============================================
# HOLDINGS
# ============================================
elif page == "Holdings":
    st.header("Net Positions")
    if not holdings.empty:
        st.dataframe(holdings.round(2))
    else:
        st.info("No holdings to display yet.")

# ============================================
# TRADE
# ============================================
elif page == "Trade":
    st.header("Submit a Trade")

    action = st.selectbox("Action", ["Buy", "Sell"])

    ticker = st.text_input("Ticker").upper().strip()

    latest_price = float("nan")
    if ticker:
        latest_price = get_single_price(ticker)
        if not math.isnan(latest_price) and latest_price > 0:
            st.write(f"Latest market price for {ticker}: {latest_price:.2f}")
        else:
            st.warning("Could not fetch a valid price for this ticker. You can still enter a price manually.")

    default_price = 0.0
    if not math.isnan(latest_price) and latest_price > 0:
        default_price = float(latest_price)

    price = st.number_input("Trade Price", min_value=0.0, value=default_price, step=0.01)
    shares = st.number_input("Shares", min_value=0.0, step=1.0)

    if st.button("Submit Trade"):
        if ticker == "" or shares <= 0 or price <= 0:
            st.error("Please enter a valid ticker, positive number of shares, and positive price.")
        else:
            total = shares * price
            owned = positions_dict.get(ticker, {}).get("shares", 0.0)

            if action == "Sell" and shares > owned + 1e-9:
                st.error(f"Cannot sell {shares} shares; you only own {owned:.2f}.")
            elif action == "Buy" and total > cash + 1e-9:
                st.error(f"Not enough cash to buy. Need ${total:,.2f}, have ${cash:,.2f}.")
            else:
                new_trade = pd.DataFrame(
                    [[TODAY, action, ticker, shares, price, total]],
                    columns=["Date", "Action", "Ticker", "Shares", "Price", "Total"]
                )
                all_trades = pd.concat([trades, new_trade], ignore_index=True)
                all_trades.to_csv(TRADES_FILE, index=False)

                new_cash = cash - total if action == "Buy" else cash + total
                pd.DataFrame({"Cash": [new_cash]}).to_csv(CASH_FILE, index=False)

                record_snapshot()
                st.success("Trade recorded.")
                st.rerun()

# ============================================
# CASH
# ============================================
elif page == "Cash":
    st.header("Cash Management")
    st.write(f"Available Cash: ${cash:,.2f}")

    amount = st.number_input("Amount", min_value=0.0, step=10.0)

    col_dep, col_wd = st.columns(2)

    if col_dep.button("Deposit"):
        new_cash = cash + amount
        pd.DataFrame({"Cash": [new_cash]}).to_csv(CASH_FILE, index=False)
        record_snapshot()
        st.rerun()

    if col_wd.button("Withdraw"):
        if amount > cash + 1e-9:
            st.error("Insufficient cash for withdrawal.")
        else:
            new_cash = cash - amount
            pd.DataFrame({"Cash": [new_cash]}).to_csv(CASH_FILE, index=False)
            record_snapshot()
            st.rerun()

# ============================================
# CHARTS
# ============================================
elif page == "Charts":
    st.header("Performance Charts")

    if not history.empty:
        history = pd.read_csv(HISTORY_FILE)
        history["Date"] = pd.to_datetime(history["Date"]).dt.date

        fig1 = px.line(history, x="Date", y="NetWorth", title="Net Worth Over Time")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.line(
            history,
            x="Date",
            y=["RealizedPL", "UnrealizedPL"],
            title="Realized vs Unrealized P/L"
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No history data yet. Record a trade or cash movement to create history.")

    if not holdings.empty:
        fig3 = px.pie(holdings, names="Ticker", values="MarketValue", title="Portfolio Allocation")
        st.plotly_chart(fig3, use_container_width=True)

# ============================================
# TRANSACTIONS
# ============================================
elif page == "Transactions":
    st.header("Transaction History")

    if trades.empty:
        st.info("No transactions recorded yet.")
    else:
        trades_display = trades.copy()
        if not realized_series.empty and len(realized_series) == len(trades_display):
            trades_display["RealizedPL"] = realized_series.values
        else:
            trades_display["RealizedPL"] = 0.0
        st.dataframe(trades_display.round(2))

