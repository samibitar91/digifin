import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px


# Function to load CSV files
def load_csv(file_path):
    try:
        return pd.read_csv(file_path, parse_dates=["Datum"])
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame()


# Function to process transactions and extract "Kontostand" rows
def process_transactions(transactions_file):
    transactions = load_csv(transactions_file)
    
    if transactions.empty:
        return transactions, pd.DataFrame()
    
    # Extract "Kontostand" rows
    kontostand_rows = transactions[transactions['Erläuterung'].str.contains('Kontostand', na=False)]
    
    # Remove "Kontostand" rows from the original transactions
    transactions = transactions[~transactions['Erläuterung'].str.contains('Kontostand', na=False)]
    
    # Sort by 'Datum'
    transactions = transactions.sort_values(by="Datum")
    
    # Initialize 'Saldo' column
    transactions['Saldo'] = None
    
    # Set initial balance as the 'Betrag EUR' of the first row
    transactions.at[transactions.index[0], 'Saldo'] = transactions.at[transactions.index[0], 'Betrag EUR']
    
    # Calculate 'Saldo' for the rest of the rows
    current_balance = transactions.at[transactions.index[0], 'Saldo']
    for index, row in transactions.iloc[1:].iterrows():
        if 'Kontostand' in row['Erläuterung']:
            transactions.at[index, 'Saldo'] = current_balance
        else:
            current_balance += row['Betrag EUR']
            transactions.at[index, 'Saldo'] = current_balance

    return transactions, kontostand_rows


# Function to filter transactions by date and keywords
def filter_transactions(df, start_date, end_date, keywords):
    # Convert 'Datum' column to datetime, coercing errors
    df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce')

    # Separate invalid/missing dates
    invalid_date_rows = df[df['Datum'].isna()]

    # Filter by date range
    filtered_df = df[(df['Datum'] >= pd.Timestamp(start_date)) & (df['Datum'] <= pd.Timestamp(end_date))]

    # Filter by keywords
    if keywords:
        keyword_filter = filtered_df['Erläuterung'].str.contains('|'.join(keywords), case=False, na=False)
        filtered_df = filtered_df[keyword_filter]

    return filtered_df, invalid_date_rows


# Function to calculate income, expenses, net balance, and averages
def calculate_financials(filtered_transactions):
    # Total income and expenses
    total_income = filtered_transactions[filtered_transactions['Betrag EUR'] > 0]['Betrag EUR'].sum()
    total_expenses = filtered_transactions[filtered_transactions['Betrag EUR'] < 0]['Betrag EUR'].sum()

    # Net balance (income - expenses)
    net_balance = total_income + total_expenses  # Expenses are negative, so this is the same as total_income - abs(total_expenses)

    # Calculate unique days in the filtered transactions
    unique_days = filtered_transactions['Datum'].dt.date.nunique()

    # Average income per day (divide by number of unique days)
    avg_income_per_day = total_income / unique_days if unique_days > 0 else 0

    # Average expense per day (divide by number of unique days)
    avg_expense_per_day = total_expenses / unique_days if unique_days > 0 else 0

    return total_income, total_expenses, net_balance, avg_income_per_day, avg_expense_per_day


# Function to generate a monthly summary chart
def generate_monthly_summary_chart(filtered_transactions):
    # Aggregate data by month for income and expenses
    monthly_summary = (
        filtered_transactions
        .groupby(filtered_transactions['Datum'].dt.to_period('M'))
        ['Betrag EUR']
        .agg(
            Income=lambda x: x[x > 0].sum(),
            Expenses=lambda x: x[x < 0].sum()* -1 
        )
        .reset_index()
    )
    monthly_summary['Datum'] = monthly_summary['Datum'].dt.to_timestamp()

    # Create Plotly chart
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly_summary['Datum'],
            y=monthly_summary['Income'],
            name="Income",
            marker_color="green"
        )
    )
    fig.add_trace(
        go.Bar(
            x=monthly_summary['Datum'],
            y=monthly_summary['Expenses'],
            name="Expenses",
            marker_color="red"
        )
    )

    # Update layout
    fig.update_layout(
        title="Monthly Income and Expenses",
        xaxis_title="Month",
        yaxis_title="Amount (€)",
        barmode="group",
        template="plotly_white"
    )

    return fig

# Function to generate a bar chart with a line for Saldo
def generate_plot(transactions_df):
    fig = go.Figure()

    # Add bars for Income
    fig.add_trace(go.Bar(
        x=transactions_df['Datum'],
        y=transactions_df['Betrag EUR'].where(transactions_df['Betrag EUR'] > 0, 0),
        name="Income",
        marker_color='green'
    ))

    # Add bars for Expenses
    fig.add_trace(go.Bar(
        x=transactions_df['Datum'],
        y=transactions_df['Betrag EUR'].where(transactions_df['Betrag EUR'] < 0, 0).abs(),
        name="Expenses",
        marker_color='red'
    ))

    # Add line for Saldo
    fig.add_trace(go.Scatter(
        x=transactions_df['Datum'],
        y=transactions_df['Saldo'],
        mode='lines',
        name="Account Balance",
        line=dict(color='yellow', width=2)
    ))

    # Update layout
    fig.update_layout(
        title="Income, Expenses, and Balance Over Time",
        xaxis_title="Date",
        yaxis_title="Amount (€)",
        barmode="stack",
        template="plotly_white"
    )

    # Show the plot in Streamlit
    st.plotly_chart(fig, use_container_width=True)

st.set_page_config(
    page_title="Financial Transactions Analysis",  # Title of the app
    layout="wide"  # Use wide layout mode
)
# Streamlit app layout
def main():
    st.title("Financial Dashboard")

    # File upload or input
    transactions_file = st.sidebar.file_uploader("Upload Transactions CSV", type=["csv"])
    default_path = "D:/Sparkasse-Duisburg-Kontoauszuege/transactions.csv"
    transactions_file_path = st.sidebar.text_input("Or input file path", value=default_path)

    if transactions_file or transactions_file_path:
        # Use the file uploader or input path
        file_path = transactions_file if transactions_file else transactions_file_path
        transactions, kontostand_rows = process_transactions(file_path)
        
        if transactions.empty:
            st.error("No transactions found in the file.")
            return

        # Get earliest and latest dates
        earliest_date = transactions["Datum"].min()
        latest_date = transactions["Datum"].max()

        # Initialize session state for dates if not already set
        if "start_date" not in st.session_state:
            st.session_state.start_date = earliest_date
        if "end_date" not in st.session_state:
            st.session_state.end_date = latest_date

        # Sidebar filters
        st.sidebar.header("Select Time Period")

        # Date inputs
        start_date = st.sidebar.date_input(
            "Start Date", value=st.session_state.start_date, min_value=earliest_date, max_value=latest_date
        )
        end_date = st.sidebar.date_input(
            "End Date", value=st.session_state.end_date, min_value=earliest_date, max_value=latest_date
        )

        # Reset button
        if st.sidebar.button("Reset Dates"):
            st.session_state.start_date = earliest_date
            st.session_state.end_date = latest_date
            start_date = earliest_date
            end_date = latest_date

        # Date range validation
        if start_date > end_date:
            st.error("Start date cannot be after end date.")
        else:
            # Input keywords for filtering
            keywords_input = st.sidebar.text_area("Enter keywords (comma-separated)", value="")
            keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]

            # Filter transactions
            filtered_transactions, invalid_date_rows = filter_transactions(transactions, start_date, end_date, keywords)

            # Create monthly summary
            monthly_chart = generate_monthly_summary_chart(filtered_transactions)

            # Calculate financial metrics
            total_income, total_expenses, net_balance, avg_income_per_day, avg_expense_per_day = calculate_financials(filtered_transactions)

            # Format 'Datum' column for display
            if 'Datum' in filtered_transactions.columns:
                filtered_transactions['Datum'] = filtered_transactions['Datum'].dt.strftime('%d.%m.%Y')

            # Display dataframe and chart side by side
            col1, col2 = st.columns([1, 1])  # Adjust column ratios if needed

            with col1:
                st.write("### Filtered Transactions")
                st.dataframe(filtered_transactions)

            with col2:
                st.write("### Monthly Summary Chart")
                st.plotly_chart(monthly_chart, use_container_width=True)

            # Display rows with invalid/missing dates
            if not invalid_date_rows.empty:
                st.warning("Rows with invalid or missing dates (not included in analysis):")
                st.write(invalid_date_rows)

            # Display financial summary with the new metrics
            st.subheader(f"Financial Summary from {start_date.strftime('%d.%m.%Y')} to {end_date.strftime('%d.%m.%Y')}")
            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric("Total Income", f"€{total_income:,.2f}")
            col2.metric("Total Expenses", f"€{total_expenses:,.2f}")
            col3.metric("Net Balance", f"€{net_balance:,.2f}")
            col4.metric("Avg. Income per Day", f"€{avg_income_per_day:,.2f}")
            col5.metric("Avg. Expense per Day", f"€{avg_expense_per_day:,.2f}")

        # Show Kontostand rows in the sidebar
        if not kontostand_rows.empty:
        # Format 'Datum' column for display
            if 'Datum' in kontostand_rows.columns:
                kontostand_rows['Datum'] = kontostand_rows['Datum'].dt.strftime('%d.%m.%Y')
            st.sidebar.header("Kontostand")
            st.sidebar.write(kontostand_rows)

            # Display Plot
            if not filtered_transactions.empty:
                generate_plot(filtered_transactions)

            # Export CSV button
            st.download_button(
                label="Download Processed Transactions",
                data=filtered_transactions.to_csv(index=False).encode('utf-8'),
                file_name="filtered_transactions.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()
