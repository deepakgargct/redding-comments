import streamlit as st
import praw
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re
from textblob import TextBlob

# === Reddit API Setup using st.secrets ===
reddit = praw.Reddit(
    client_id=st.secrets["client_id"],
    client_secret=st.secrets["client_secret"],
    user_agent=st.secrets["user_agent"]
)
reddit.read_only = True

# === Timeframe Mapping ===
time_mapping = {
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "12 Months": 365
}

# === Helper Functions ===
def analyze_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        return "Positive"
    elif polarity < -0.1:
        return "Negative"
    else:
        return "Neutral"

def get_comments(keyword, days, subreddits):
    comments_data = []
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    search_query = f'title:"{keyword}"'
    target_subreddits = subreddits if subreddits else ["all"]

    for sr in target_subreddits:
        try:
            subreddit = reddit.subreddit(sr)
            search_results = subreddit.search(search_query, sort="top", limit=100, time_filter="year")

            for submission in search_results:
                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list():
                    created = datetime.utcfromtimestamp(comment.created_utc)
                    if start_date <= created <= end_date:
                        comments_data.append({
                            "Comment": comment.body,
                            "Author": str(comment.author),
                            "Score": comment.score,
                            "Subreddit": submission.subreddit.display_name,
                            "Post Title": submission.title,
                            "Permalink": f"https://reddit.com{comment.permalink}",
                            "Created": created.date(),
                            "Sentiment": analyze_sentiment(comment.body)
                        })
                    if len(comments_data) >= 100:
                        break
        except Exception as e:
            st.warning(f"Failed to fetch from r/{sr}: {e}")
            continue
    return comments_data

def generate_wordcloud(text_list):
    text = ' '.join(text_list)
    text = re.sub(r"http\S+|[^A-Za-z\s]", "", text)
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    return wordcloud

# === Streamlit UI ===
st.set_page_config(page_title="Reddit Comment Explorer", layout="wide")
st.title("💬 Reddit Comment Explorer")

col1, col2 = st.columns(2)
with col1:
    keyword = st.text_input("Enter a keyword to search Reddit posts & comments")
with col2:
    timeframe = st.selectbox("Select timeframe", options=list(time_mapping.keys()))

sub_input = st.text_input("Optional: Specify up to 5 subreddits (comma separated)", placeholder="e.g. gaming, crypto, movies")
selected_subreddits = [s.strip() for s in sub_input.split(",") if s.strip()][:5]

if st.button("Fetch Comments") and keyword:
    with st.spinner("Fetching Reddit comments..."):
        comments = get_comments(keyword, time_mapping[timeframe], selected_subreddits)

        if comments:
            df = pd.DataFrame(comments)

            # === Subreddit Filter ===
            unique_subs = df["Subreddit"].unique().tolist()
            selected_subs = st.multiselect("Filter by Subreddit", unique_subs, default=unique_subs)
            df = df[df["Subreddit"].isin(selected_subs)]

            st.success(f"Collected {len(df)} comments.")
            st.dataframe(df, use_container_width=True)

            # === CSV Download ===
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", data=csv, file_name=f"{keyword}_reddit_comments.csv", mime='text/csv')

            # === Sentiment Chart ===
            st.markdown("### 📈 Sentiment Breakdown")
            sentiment_chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("Sentiment:N", title="Sentiment"),
                    y=alt.Y("count()", title="Number of Comments"),
                    color="Sentiment:N"
                )
                .properties(width="container")
            )
            st.altair_chart(sentiment_chart, use_container_width=True)

            # === Word Cloud ===
            st.markdown("### ☁️ Word Cloud from Comments")
            wordcloud = generate_wordcloud(df["Comment"].tolist())
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.warning("No comments found. Try a different keyword or timeframe.")
