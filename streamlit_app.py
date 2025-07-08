import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import openai
import os
import feedparser

# === SETUP OPENAI API KEY from environment variable ===
openai.api_key = st.secrets["openai"]["api_key"]
if not openai.api_key:
    st.error("⚠️ Please set your OPENAI_API_KEY as an environment variable.")
    st.stop()

st.title("🧠 CEO Influence Tracker")

# Sidebar Inputs
st.sidebar.header("Track a CEO")
ceo_name = st.sidebar.text_input("CEO Name", "Elon Musk")
company = st.sidebar.text_input("Company", "Tesla")
ticker = st.sidebar.text_input("Stock Ticker", "TSLA")
event_description = st.sidebar.text_area("Event Description")
event_date = st.sidebar.date_input("Event Date", datetime.date.today())
news_link = st.sidebar.text_input("News Source Link")

# Initialize or load data
@st.cache_data(show_spinner=False)
def load_data():
    return pd.DataFrame(columns=[
        "Date", "CEO", "Company", "Ticker", "Event", "Sentiment",
        "Price Before", "Price After", "% Change", "News Link"
    ])

df = load_data()

# === Stock price fetch function with corrected date logic ===
def get_stock_price(ticker, news_date):
    try:
        start = news_date - datetime.timedelta(days=7)
        end = news_date + datetime.timedelta(days=2)

        data = yf.download(ticker, start=start, end=end, progress=False)
        if data.empty:
            return None, None

        data = data['Close'].sort_index()

        # trading day <= news_date
        after_dates = data.index[data.index.date <= news_date]
        if len(after_dates) == 0:
            price_after = None
        else:
            price_after = data.loc[after_dates[-1]]

        # trading day before price_after
        before_dates = data.index[data.index < after_dates[-1]] if len(after_dates) > 0 else []
        if len(before_dates) == 0:
            price_before = None
        else:
            price_before = data.loc[before_dates[-1]]

        return float(price_before) if price_before is not None else None, float(price_after) if price_after is not None else None

    except Exception as e:
        st.error(f"Error fetching stock price: {e}")
        return None, None

# === Sentiment analysis function using OpenAI GPT-3.5 Turbo ===
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

# === News scraping function ===
def fetch_news(ceo_name, company, max_articles=5):
    query = f"{ceo_name} {company}"
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    
    events = []
    for entry in feed.entries[:max_articles]:
        headline = entry.title
        link = entry.link
        published = datetime.datetime(*entry.published_parsed[:6]).date()
        events.append({"headline": headline, "link": link, "date": published})
    
    return events

# === Add single manual event ===
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

# === Auto-fetch recent CEO news and add events ===
if st.sidebar.button("📰 Auto-Fetch CEO News"):
    st.subheader(f"Latest news on {ceo_name}")
    articles = fetch_news(ceo_name, company)

    for article in articles:
        st.markdown(f"**{article['headline']}**  \n[{article['link']}]({article['link']})  \n_Date: {article['date']}_")

        sentiment = analyze_sentiment(article['headline'])
        before, after = get_stock_price(ticker, article['date'])

        if before is not None and after is not None:
            change = round(((after - before) / before) * 100, 2)
        else:
            change = None

        new_row = {
            "Date": article['date'], "CEO": ceo_name, "Company": company,
            "Ticker": ticker, "Event": article['headline'], "Sentiment": sentiment,
            "Price Before": before, "Price After": after, "% Change": change,
            "News Link": article['link']
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    st.success("News events added!")

# === Display data table ===
st.subheader("📋 Logged CEO Events")
st.dataframe(df)

# === CSV Download ===
st.download_button("📥 Download CSV", df.to_csv(index=False), file_name="ceo_influence_log.csv")
