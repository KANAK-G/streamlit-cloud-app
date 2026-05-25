"""Greeting demo on Streamlit Cloud — opened from DataOS via link/app URL."""

import streamlit as st

st.set_page_config(
    page_title="Greeting App",
    page_icon="👋",
    layout="centered",
)

try:
    app_name = st.secrets.get("APP_NAME", "Greeting App")
except Exception:
    app_name = "Greeting App"

st.title(app_name)
st.caption(
    "Say hello from a hosted Streamlit app. Open this page from DataOS (link URL) "
    "or directly on Streamlit Cloud — no login or secrets needed to greet."
)

st.divider()

name = st.text_input("Your name", placeholder="Enter your name")
if name:
    st.success(f"Hello, {name}! 👋")

count = st.number_input("Pick a number", min_value=0, max_value=100, value=1)
if st.button("Show greeting", type="primary"):
    st.write(f"You chose **{count}** — thanks for trying the app.")

with st.expander("About this app"):
    st.markdown(
        """
**What this code does**

1. **Name** — when you type a name, the app greets you immediately (`Hello, {name}!`).
2. **Number + button** — pick a number, click **Show greeting**, and the app echoes your choice.
3. **`APP_NAME` secret (optional)** — only you set this in Streamlit Cloud → Secrets (or `.streamlit/secrets.toml` locally) to change the page title. DataOS users do not enter it.

**DataOS**

- Register this app’s Streamlit URL in a DataOS `link` or `app` resource (`apps/lnk.yaml`).
- Users click the catalog link → browser opens this hosted app → greet UI works with no extra steps.

**Run / deploy**

- **Local:** `pip install -r requirements.txt` then `streamlit run app.py`
- **Cloud:** [Streamlit Cloud](https://share.streamlit.io) — app root `apps/streamlit-cloud-app`, main file `app.py`
        """
    )
