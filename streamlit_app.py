# Combined CEO Influence Tracker with Big Drop Scanner
# Original user code followed by scanner

import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import openai
import os
import feedparser
from requests_html import HTMLSession
import yahoo_fin.stock_info as si
import requests
from bs4 import BeautifulSoup
     
# === SETUP OPENAI API KEY from environment variable ===
openai.api_key = st.secrets["openai"]["api_key"]
if not openai.api_key:
    st.error("⚠️ Please set your OPENAI_API_KEY as an environment variable.")
    st.stop()

si.HTMLSession = HTMLSession

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

# === Yahoo Finance Top Daily Losers ===
st.subheader("📉 Yahoo Finance Top Daily Losers")

@st.cache_data(show_spinner=False)
def fetch_yahoo_losers(top_n=5):
    url = "https://finance.yahoo.com/losers"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        rows = table.find("tbody").find_all("tr")

        data = []
        for row in rows[:top_n]:
            cols = row.find_all("td")
            symbol = cols[0].text.strip()
            name = cols[1].text.strip()
            price = cols[2].text.strip()
            change_data = cols[3].text.strip().split()
            if len(change_data) == 3:
                 price, change, percent_change = change_data
            else:
                 price, change, percent_change = "", "", ""
            data.append({
                "Symbol": symbol,
                "Name": name,
                "Price": price,
                "Change": change,
                "% Change": percent_change
            })
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"⚠️ Failed to scrape Yahoo Finance losers: {e}")
        return pd.DataFrame()
        
top_n = st.slider("Number of top losers to display", 5)
if st.button("🔄 Load Top Losers"):
    yahoo_losers = fetch_yahoo_losers(top_n)
    if not yahoo_losers.empty:
        st.dataframe(yahoo_losers, use_container_width=True)

        # === Auto-Fetch News for Each Top Loser Symbol ===
        st.subheader("📰 Logging News for Top Losers to Grid")
        added_events = []
        for i, row in yahoo_losers.iterrows():
            ticker = row["Symbol"]
            company = row["Name"]

            st.markdown(f"#### {ticker} - {company}")
            articles = fetch_news("", company)
            if not articles:
                st.markdown("_No recent news found._")
            else:
                for article in articles[:3]:  # Limit to 3 per company
                    headline = article["headline"]
                    link = article["link"]
                    date = article["date"]
                    #st.markdown(f"- **{headline}**  \\n[{link}]({link}) (_{date}_)")
                    
                    sentiment = analyze_sentiment(headline)
                    before, after = get_stock_price(ticker, date)

                    if before is not None and after is not None:
                        change = round(((after - before) / before) * 100, 2)
                    else:
                        change = None

                    new_row = {
                        "Date": date,
                        "CEO": "",
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
                    added_events.append(new_row)

        if added_events:
            st.success(f"{len(added_events)} events added to the grid.")
             
# === Display data table ===
st.subheader("📋 Logged CEO Events")
df_sorted = df.sort_values(by=["Ticker", "Date"], ascending=False)
st.dataframe(df_sorted, use_container_width=True)

# === CSV Download ===
st.download_button("📥 Download CSV", df.to_csv(index=False), file_name="ceo_influence_log.csv")
