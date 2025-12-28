Portfolio Management & Tracking App

This project is a Python and Streamlit-based portfolio tracker for managing stock holdings, tracking performance over time, monitoring cash balances, and visualizing changes in portfolio value. The application uses yfinance to pull real-time market data and stores activity in CSV files, allowing the portfolio state to persist across sessions.

Features:

Add, edit, and delete stock holdings
Real-time quote updates through yfinance
Track buy/sell transactions and cost basis
Store portfolio value history over time
Maintain a cash ledger and current cash balance
CSV-based data storage (no database required)
Streamlit user interface with multiple pages

File Structure:

portfolio-management-app/
│
├── app.py                # Main Streamlit application
├── portfolio.csv         # Active positions and quantities
├── transactions.csv      # Historical buy/sell records
├── value_history.csv     # Logged portfolio value per update
├── cash_balance.csv      # Current cash amount
├── cash_ledger.csv       # Cash activity over time
├── requirements.txt      # Dependency file for setup and deployment
└── README.md


Local Installation and Running:

Clone the repository:

git clone https://github.com/mmaxtaylor2/portfolio-management-app.git
cd portfolio-management-app

Install dependencies:

pip install -r requirements.txt

Run the Streamlit application:

streamlit run app.py

Deployment (Streamlit Cloud):

Go to: https://share.streamlit.io/
Connect your GitHub account
Select the repository: mmaxtaylor2/portfolio-management-app
Choose branch: main
Choose file to run: app.py
Deploy the application
