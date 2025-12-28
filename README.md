# Portfolio Management App

A personal brokerage-style portfolio tracker that simulates live trading, FIFO/AvgCost valuation, cash management, and performance visualization. Built with Python and Streamlit.

## Key Features
- Add, buy, and sell positions with live pricing
- FIFO & Average Cost valuation methods
- Automated net worth tracking and history logging
- Realized vs Unrealized P/L calculations
- Cash balance management (deposit/withdraw)
- Performance charts (Net Worth & P/L over time)
- Downloadable account statement (CSV export)

## How to Run Locally
git clone https://github.com/mmaxtaylor2/portfolio-management-app.git
cd portfolio-management-app
pip install -r requirements.txt
streamlit run app.py

## File Structure
portfolio-management-app/
│ app.py
│ portfolio.csv
│ transactions.csv
│ value_history.csv
│ cash.txt
│ README.md

