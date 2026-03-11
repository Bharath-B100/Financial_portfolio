import streamlit as st
import pandas as pd
import re
import time
from datetime import datetime
import json
import os

# Streamlit App
st.title('Extract Dates, Zerodha Client ID, and Tradebook Data (Offline Mode)')

uploaded_file = st.file_uploader('Upload Zerodha Tradebook Excel', type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file, header=None)

    # Ensure the expected cell exists before accessing it
    try:
        cell_value = df.iloc[10, 1]
    except IndexError:
        st.error("The uploaded file does not contain expected data at cell B11.")
        st.stop()  # Stop further execution

    st.write(f"Cell B11 contains: {cell_value}")

    # Regex to match date format YYYY-MM-DD
    date_pattern = r'(\d{4}-\d{2}-\d{2})'
    dates = re.findall(date_pattern, str(cell_value))

    if len(dates) >= 2:
        from_date, to_date = dates[0], dates[1]
        st.success(f"From Date: {from_date}")
        st.success(f"To Date: {to_date}")
    else:
        st.error("Couldn't extract two dates from the provided cell.")

    # Extract Zerodha Client ID from cell C7
    client_id = df.iloc[6, 2]
    st.success(f"Zerodha Client ID: {client_id}")

    # Ensure the expected columns exist in the tradebook data
    expected_columns = ["Trade Date", "Symbol", "ISIN", "Trade Type", "Segment", "Series", 
                        "Quantity", "Price", "Exchange", "Order ID", "Trade ID", "Order Execution Time"]

    if not all(col in df.iloc[14].values for col in expected_columns):
        st.error("The uploaded file does not match the expected Zerodha Tradebook format.")
        st.stop()

    # Extract trade data from row 15 onwards
    extracted_data = df.iloc[14:, 1:14]
    extracted_data.columns = extracted_data.iloc[0].str.strip()
    extracted_data = extracted_data[1:].reset_index(drop=True)

    # Explicitly drop unwanted 'Auction' column if present
    if 'Auction' in extracted_data.columns:
        extracted_data.drop(columns=['Auction'], inplace=True)

    st.subheader("Extracted Data")
    st.dataframe(extracted_data)

    if st.button('Save Data Locally'):
        # Create data directory if it doesn't exist
        if not os.path.exists('data'):
            os.makedirs('data')
        
        # Save summary data
        task_date = datetime.now().isoformat()
        client_summary = {
            'client_id': client_id,
            'from_date': from_date,
            'to_date': to_date,
            'task_date': task_date
        }
        
        with open('data/client_summary.json', 'w') as f:
            json.dump(client_summary, f, indent=2)
        
        # Adjust columns for consistency
        rename_mapping = {
            'Trade Date': 'tradedate',
            'Symbol': 'symbol',
            'ISIN': 'isin',
            'Trade Type': 'trade_type',
            'Segment': 'segment',
            'Series': 'series',
            'Quantity': 'quantity',
            'Price': 'price',
            'Exchange': 'exchange',
            'Order ID': 'order_id',
            'Trade ID': 'trade_id',
            'Order Execution Time': 'order_execution_time'
        }

        extracted_data.rename(columns=rename_mapping, inplace=True)
        
        # Add client info
        extracted_data['client_id'] = client_id
        
        # Save trade data
        extracted_data.to_csv('data/tradebook_entries.csv', index=False)
        
        st.success('Data successfully saved locally!')
        st.info('Files saved in "data" directory:')
        st.code('- client_summary.json\n- tradebook_entries.csv')
