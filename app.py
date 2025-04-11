import streamlit as st
import praw
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re

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
def generate_wordcloud(texts):
    text = ' '.join(texts)
    text = re.sub(r"http\S+|[^A-Za-z\s]", "", text)
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    return wordcloud

def get_reddit_comments(keyword, days, subreddits=None):
    comments_data = []
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    query = f'title:"{keyword}"'
    target_subreddits = subreddits if subreddits else ["all"]

    for sub in target_subreddits:
        try:
            submissions = reddit.subreddit(sub).search(query, sort="top", limit=100, time_filter="year")
            for submission in submissions:
                created = datetime.utcfromtimestamp(submission.created_utc)
                if not (start_date <= created <= end_date):
                    continue

                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list():
                    comment_created = datetime.utcfromtimestamp(comment.created_utc)
                    if keyword.lower() in comment.body.lower() and start_date <= comment_created <= end_date:
                        comments_data.append({
                            "Comment": comment.body,
                            "Score": comment.score,
                            "Submission Title": submission.title,
                            "Subreddit": submission.subreddit.display_name,
                            "Permalink": f"https://reddit.com{comment.permalink}",
                            "Created": comment_created.date()
                        })
                    if len(comments_data) >= 100:
                        break
                if len(comments_data) >= 100:
                    break
        except Exception as e:
            st.warning(f"Error fetching comments from r/{sub}: {e}")
    return comments_data

# === Streamlit UI ===
st.set_page_config(page_title="Reddit Comments Explorer", layout="wide")
st.title("💬 Reddit Comments Explorer")

# === Inputs ===
col1, col2 = st.columns(2)
with col1:
    keyword = st.text_input("Enter a keyword to search in Reddit comments")
with col2:
    timeframe = st.selectbox("Select timeframe", options=list(time_mapping.keys()))

custom_subs = st.text_input("Optionally specify up to 5 subreddits (comma-separated)", help="Leave blank to search across all of Reddit")
selected_subreddits = [s.strip() for s in custom_subs.split(",") if s.strip()][:5] if custom_subs else None

# === Run Button ===
if st.button("Fetch Comments") and keyword:
    with st.spinner("Fetching relevant Reddit comments..."):
        comments = get_reddit_comments(keyword, time_mapping[timeframe], selected_subreddits)
        if comments:
            df = pd.DataFrame(comments)

            # === Subreddit Filter ===
            subreddits = df["Subreddit"].unique().tolist()
            selected_subs = st.multiselect("Filter by Subreddit", subreddits, default=subreddits)
            df = df[df["Subreddit"].isin(selected_subs)]

            # === Sort Option ===
            sort_by = st.selectbox("Sort by", options=["Score", "Created"])
            df = df.sort_values(by=sort_by, ascending=False)

            # === Display Table ===
            st.success(f"Found {len(df)} Reddit comments.")
            st.dataframe(df, use_container_width=True)

            # === CSV Download ===
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", data=csv, file_name=f"{keyword}_reddit_comments.csv", mime='text/csv')

            # === Comment Activity Chart ===
            st.markdown("### 📊 Comment Activity Over Time")
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("Created:T", title="Date"),
                    y=alt.Y("count()", title="Number of Comments"),
                    tooltip=["Created", "count()"]
                )
                .properties(width="container")
            )
            st.altair_chart(chart, use_container_width=True)

            # === Word Cloud ===
            st.markdown("### ☁️ Word Cloud from Comment Text")
            wordcloud = generate_wordcloud(df["Comment"].tolist())
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.warning("No comments found. Try another keyword, subreddit, or time frame.")
