import streamlit as st
from supabase import create_client, Client
import pandas as pd
from collections import deque
import plotly.express as px

# Initialize Supabase connection using secrets.toml
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

# Streamlit App
st.title("Tradebook Analysis")

# Fetch Tradebook Data
def fetch_tradebook_entries():
    try:
        response = supabase.table("tradebook_entries").select("*").execute()
        if response and response.data:
            df = pd.DataFrame(response.data)
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            df.dropna(subset=['quantity', 'price'], inplace=True)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching tradebook data: {e}")
        return pd.DataFrame()

# Function to calculate P&L for a single trade
def calculate_trade_pnl(sell_qty, sell_price, buy_orders):
    pnl = 0
    while sell_qty > 0 and buy_orders:
        buy_qty, buy_price = buy_orders.popleft()
        match_qty = min(sell_qty, buy_qty)

        pnl += (sell_price - buy_price) * match_qty
        sell_qty -= match_qty
        buy_qty -= match_qty

        if buy_qty > 0:
            buy_orders.appendleft([buy_qty, buy_price])
    
    return pnl, sell_qty, buy_orders

# Function to process each client and symbol group
def process_trades_for_client_and_symbol(trades):
    buy_orders = deque()  
    total_buy_cost = 0
    remaining_qty = 0
    pnl = 0

    for _, trade in trades.iterrows():
        trade_type = trade["trade_type"].lower()
        trade_qty = trade["quantity"]
        trade_price = trade["price"]

        if trade_type == "buy":
            buy_orders.append([trade_qty, trade_price])  
            total_buy_cost += trade_qty * trade_price  
            remaining_qty += trade_qty  

        elif trade_type == "sell":
            sell_qty = trade_qty
            sell_price = trade_price

            pnl_for_trade, remaining_qty, buy_orders = calculate_trade_pnl(sell_qty, sell_price, buy_orders)
            pnl += pnl_for_trade  

    return pnl, total_buy_cost, remaining_qty, buy_orders

# Function to calculate the realized P&L and return results
def calculate_realized_pnl(df):
    if df.empty:
        return pd.DataFrame(), 0  

    df = df.sort_values(by=["tradedate", "order_execution_time"])
    realized_pnl_records = []
    total_realized_pnl = 0  

    grouped = df.groupby(["client_id", "symbol"])  

    for (client, symbol), trades in grouped:
        pnl, total_buy_cost, remaining_qty, buy_orders = process_trades_for_client_and_symbol(trades)
        total_realized_pnl += pnl

        pnl_percentage = (pnl / total_buy_cost) * 100 if total_buy_cost > 0 else 0

        # Calculate average cost based on remaining quantity and total buy cost using FIFO principles
        remaining_buy_cost = sum(qty * price for qty, price in buy_orders)
        average_cost = remaining_buy_cost / remaining_qty if remaining_qty > 0 else 0

        realized_pnl_records.append({
            "client_id": client,
            "symbol": trades["symbol"].iloc[0],
            "realized_pnl": pnl,
            "pnl_percentage": round(pnl_percentage, 2),
            "remaining_qty": remaining_qty,
            "average_cost": average_cost,  # Add average cost to records
            "invested": remaining_qty * average_cost  # Calculate invested amount
        })

    return pd.DataFrame(realized_pnl_records), total_realized_pnl

# Fetch and Filter Data
df = fetch_tradebook_entries()

if not df.empty:
    realized_pnl_df, total_realized_pnl = calculate_realized_pnl(df)

    # Display Current Holdings
    current_holdings = realized_pnl_df[realized_pnl_df['remaining_qty'] > 0].drop(columns=['realized_pnl', 'pnl_percentage'])
    if not current_holdings.empty:
        st.subheader("Current Holdings")
        st.dataframe(current_holdings.style.format({"remaining_qty": "{:.2f}", "average_cost": "₹{:.2f}", "invested": "₹{:.2f}"}))
    else:
        st.info("No current holdings available.")

# Calculate Realized PnL with FIFO
def calculate_realized_pnl(df):
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(by=["tradedate", "order_execution_time"])
    realized_records = []
    grouped = df.groupby("symbol")
    
    for symbol, trades in grouped:
        buy_orders = deque()
        realized_qty, buy_value, sell_value = 0, 0, 0

        for _, trade in trades.iterrows():
            if trade["trade_type"].lower() == "buy":
                buy_orders.append([trade["quantity"], trade["price"]])
        
        # Process sell trades
        df_sell = df[(df['symbol'] == symbol) & (df['trade_type'].str.lower() == 'sell')]
        for _, trade in df_sell.iterrows():
            sell_qty, sell_price = trade["quantity"], trade["price"]

            while sell_qty > 0 and buy_orders:
                buy_qty, buy_price = buy_orders.popleft()
                match_qty = min(sell_qty, buy_qty)

                realized_qty += match_qty
                buy_value += match_qty * buy_price
                sell_value += match_qty * sell_price

                sell_qty -= match_qty
                buy_qty -= match_qty
                if buy_qty > 0:
                    buy_orders.appendleft([buy_qty, buy_price])

        if realized_qty > 0:
            realized_pnl = sell_value - buy_value
            realized_records.append({
                "symbol": symbol,
                "qty": realized_qty,
                "buy_avg": buy_value / realized_qty,
                "buy_value": buy_value,
                "sell_avg": sell_value / realized_qty,
                "sell_value": sell_value,
                "realised_pnl": realized_pnl
            })
    
    return pd.DataFrame(realized_records)

if not df.empty:
    realized_pnl_df = calculate_realized_pnl(df)

    if not realized_pnl_df.empty:
        st.subheader("Realized PnL Summary")
        total_realized_pnl = realized_pnl_df["realised_pnl"].sum()
        st.dataframe(
            realized_pnl_df.style.format({
                "qty": "{:.0f}",
                "buy_avg": "₹{:.2f}",
                "buy_value": "₹{:.2f}",
                "sell_avg": "₹{:.2f}",
                "sell_value": "₹{:.2f}",
                "realised_pnl": "₹{:.2f}"
            })
        )

        st.markdown(f"### **Total Realized P&L: ₹{total_realized_pnl:,.2f}**")
        
        # Visualization
        fig = px.bar(realized_pnl_df, x="symbol", y="realised_pnl", 
                     title="Realized PnL per symbol", 
                     labels={"realised_pnl": "Realized PnL (₹)"}, 
                     text_auto=True)
        st.plotly_chart(fig)
    else:
        st.info("No realized PnL data available.")
else:
    st.warning("No tradebook entries found.")
# Summary Statistics
st.subheader("Summary Statistics")
st.write(f"Total Unique symbol: {df['symbol'].nunique()}")
st.write(f"Total Transactions: {len(df)}")
