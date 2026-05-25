"""Minimal Streamlit app — ready for Streamlit Community Cloud."""

import streamlit as st

st.set_page_config(
    page_title="Vulcan Examples",
    page_icon="🚀",
    layout="centered",
)

try:
    app_name = st.secrets.get("APP_NAME", "Vulcan Examples")
except Exception:
    app_name = "Vulcan Examples"

st.title(app_name)
st.caption("A basic Python app you can deploy on Streamlit Cloud.")

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
- **Local:** `pip install -r requirements.txt` then `streamlit run app.py`
- **Cloud:** Connect this repo folder on [Streamlit Cloud](https://share.streamlit.io)
  and set the main file to `app.py`.
- **Secrets (optional):** Add `APP_NAME = "My App"` in Streamlit Cloud → App settings → Secrets.
        """
    )
