import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import datetime
import openai

# Set your OpenAI API key
openai.api_key = st.secrets["openai"]["api_key"]

# Title
st.title("🧠 CEO Influence Tracker")

# Sidebar Inputs
st.sidebar.header("Track a CEO")
ceo_name = st.sidebar.text_input("CEO Name", "Elon Musk")
company = st.sidebar.text_input("Company", "Tesla")
ticker = st.sidebar.text_input("Stock Ticker", "TSLA")
event_description = st.sidebar.text_area("Event Description")
event_date = st.sidebar.date_input("Event Date", datetime.date.today())
news_link = st.sidebar.text_input("News Source Link")

# Load or initialize data
@st.cache_data
def load_data():
    return pd.DataFrame(columns=[
        "Date", "CEO", "Company", "Ticker", "Event", "Sentiment",
        "Price Before", "Price After", "% Change", "News Link"
    ])

df = load_data()

# Fetch stock price from yfinance
def get_stock_price(ticker, date):
    try:
        start = date - datetime.timedelta(days=3)
        end = date + datetime.timedelta(days=3)

        data = yf.download(ticker, start=start, end=end)

        if not data.empty:
            price_before = data['Close'].iloc[0]
            price_after = data['Close'].iloc[-1]
            return float(price_before), float(price_after)  # ✅ force conversion to float
    except Exception as e:
        st.error(f"Error fetching stock data: {e}")

    return None, None

# Analyze sentiment with OpenAI
def analyze_sentiment(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a sentiment analysis engine."},
                {"role": "user", "content": f"What is the sentiment of this news headline or event description? Respond only with Positive, Neutral, or Negative.\n\n{text}"}
            ]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        st.error(f"Error analyzing sentiment: {e}")
        return "Unknown"

# Log new entry
if st.sidebar.button("Add Event"):
    before, after = get_stock_price(ticker, event_date)
    sentiment = analyze_sentiment(event_description)
  
    if before is not None and after is not None:
        change = round(((after - before) / before) * 100, 2)
    else:
        change = None
    
    new_row = {
        "Date": event_date, "CEO": ceo_name, "Company": company,
        "Ticker": ticker, "Event": event_description, "Sentiment": sentiment,
        "Price Before": before, "Price After": after, "% Change": change,
        "News Link": news_link
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    st.success("Event added!")

# Display table
st.subheader("📋 Logged CEO Events")
st.dataframe(df)

# Download option
st.download_button("📥 Download CSV", df.to_csv(index=False), file_name="ceo_influence_log.csv")
