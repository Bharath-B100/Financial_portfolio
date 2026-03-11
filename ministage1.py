import streamlit as st
import pandas as pd
import re
import time
from supabase import create_client
from datetime import datetime
import httpx

# Initialize Supabase connection using secrets.toml
try:
    supabase_url = st.secrets['SUPABASE_URL']
    supabase_key = st.secrets['SUPABASE_KEY']
    supabase = create_client(supabase_url, supabase_key)
except httpx.ConnectError:
    print("Error: Unable to connect to Supabase. Check your internet connection or Supabase URL.")
except httpx.HTTPStatusError as e:
    print(f"HTTP error: {e.response.status_code} - {e.response.text}")
except httpx.RequestError as e:
    print("Request error:", e)
except Exception as e:
    print("An unexpected error occurred:", e)

# Streamlit App
st.title('Extract Dates, Zerodha Client ID, and Tradebook Data')

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

    if st.button('Upload Data to Supabase'):
        existing_records = supabase.table('client_tasks').select('*').eq('client_id', client_id).eq('from_date', from_date).eq('to_date', to_date).execute()

        if existing_records.data:
            st.warning('A record with the same Client ID and Date Range already exists.')
        else:
            task_date = datetime.now().isoformat()

            # Upload summary data
            client_summary = {
                'client_id': client_id,
                'from_date': from_date,
                'to_date': to_date,
                'task_date': task_date
            }
            response_client = supabase.table('client_tasks').insert(client_summary).execute()

            if response_client.data:
                client_task_id = response_client.data[0]['id']

                # Adjust columns explicitly
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

                columns_required = [
                    'client_task_id', 'client_id', 'symbol', 'isin', 'tradedate', 'exchange',
                    'segment', 'series', 'trade_type', 'quantity', 'price',
                    'trade_id', 'order_id', 'order_execution_time'
                ]

                extracted_data['client_id'] = client_id
                extracted_data['client_task_id'] = client_task_id

                missing_cols = set(columns_required) - set(extracted_data.columns)
                if missing_cols:
                    st.error(f"Missing columns: {missing_cols}")
                else:
                    extracted_data = extracted_data[columns_required]
                    data_dict = extracted_data.to_dict(orient='records')

                    # Progress Bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total_rows = len(data_dict)

                    for i, row in enumerate(data_dict):
                        time.sleep(1)  # Simulate reading each row for 1 second
                        
                        # Upload row to Supabase
                        response = supabase.table('tradebook_entries').insert(row).execute()
                        time.sleep(1)  # Simulate uploading each row for 1 second
                        
                        # Update Progress Bar
                        progress = (i + 1) / total_rows
                        progress_bar.progress(progress)
                        status_text.text(f"Uploading row {i+1}/{total_rows}...")

                    st.success('Data successfully uploaded to Supabase.')
            else:
                st.error('Failed to upload client summary data.')