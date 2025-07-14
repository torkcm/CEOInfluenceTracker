# Combined CEO Influence Tracker with Big Drop Scanner
# Original user code followed by scanner

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

    # ✅ Keywords to filter by (source names in event text)
    allowed_keywords = ["cnbc", "the new york times", "wsj", "barrons"]

    if not articles:
        st.warning("No recent articles found.")
    else:
        added_any = False
        for article in articles:
            headline = article["headline"]
            link = article["link"]
            date = article["date"]

            # ✅ Check if any keyword is in the headline (case-insensitive)
            if not any(keyword in headline.lower() for keyword in allowed_keywords):
                continue  # Skip if source not mentioned in headline

            st.markdown(f"**{headline}**  \n[{link}]({link})  \n_Date: {date}_")

            sentiment = analyze_sentiment(headline)
            before, after = get_stock_price(ticker, date)

            if before is not None and after is not None:
                change = round(((after - before) / before) * 100, 2)
            else:
                change = None

            new_row = {
                "Date": date,
                "CEO": ceo_name,
                "Company": company,
                "Ticker": ticker,
                "Event": headline,
                "Sentiment": sentiment,
                "Price Before": before,
                "Price After": after,
                "% Change": change,
                "News Link": link
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            added_any = True

        if added_any:
            st.success("Filtered news added (based on headline content).")
        else:
            st.info("No matching articles found containing CNBC, NYT, or WSJ.")

# === Display data table ===
st.subheader("📋 Logged CEO Events")
df_sorted = df.sort_values(by="Date", ascending=False)
st.dataframe(df_sorted, use_container_width=True)

# === CSV Download ===
st.download_button("📥 Download CSV", df.to_csv(index=False), file_name="ceo_influence_log.csv")


# === 📉 Big Drop Scanner ===
st.subheader("📉 Daily Drop Scanner (-7% or more)")

@st.cache_data(show_spinner=False)
def load_yahoo_losers(top_n=50):
    url = "https://finance.yahoo.com/markets/stocks/losers/"
    dfs = pd.read_html(url)
    if dfs:
        df = dfs[0]
        # Ensure 'Symbol' column exists
        return df['Symbol'].head(top_n).tolist()
    return []
    
# Load dynamically
use_yahoo = st.checkbox("Scan today's top Yahoo Finance losers", value=True)

if use_yahoo:
    tickers_list = load_yahoo_losers()
else:
    tickers_input = st.text_area(
        "Enter tickers to scan (comma-separated):",
        "TSLA,AAPL,NFLX,NVDA,META,DIS"
    )
    tickers_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

drop_threshold = st.slider("Drop Threshold (%)", min_value=1, max_value=20, value=7)

def get_big_drops(tickers, drop_threshold=-7.0):
    big_drops = []
    end = datetime.date.today()
    start = end - datetime.timedelta(days=5)
    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start, end=end)
            if len(data) < 2:
                continue
            data["% Change"] = data["Close"].pct_change() * 100
            recent = data.iloc[-1]
            if recent["% Change"] <= -abs(drop_threshold):
                big_drops.append({
                    "Ticker": ticker,
                    "Date": recent.name.date(),
                    "Close": round(recent["Close"], 2),
                    "% Change": round(recent["% Change"], 2)
                })
        except:
            continue
    return pd.DataFrame(big_drops)

if st.button("📊 Scan for -7% Drops"):
    df_drops = get_big_drops(tickers_list, drop_threshold)
    if df_drops.empty:
        st.info("✅ No stocks dropped more than {}% in the last session.".format(drop_threshold))
    else:
        st.dataframe(df_drops.sort_values(by="% Change"), use_container_width=True)
