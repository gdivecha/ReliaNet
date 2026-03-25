import streamlit as st
import requests
import os
import time

st.set_page_config(page_title="ReliaNet Dashboard", layout="wide")

# Internal Docker address for the Gateway
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:5000")

st.title("🌐 ReliaNet: Distributed KV Store")
st.subheader("Real-time Cluster Monitor & Data Entry")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📥 Write Data")
    with st.form("write_form"):
        key_input = st.text_input("Key", placeholder="e.g., weather_toronto")
        val_input = st.text_area("Value", placeholder="e.g., Sunny, 22°C")
        submitted = st.form_submit_button("Replicate to Cluster")
        
        if submitted:
            try:
                resp = requests.post(f"{GATEWAY_URL}/api/data", json={"key": key_input, "value": val_input})
                if resp.status_code == 201:
                    st.success(f"✅ Successfully replicated '{key_input}'!")
                else:
                    st.error(f"❌ Error: {resp.text}")
            except Exception as e:
                st.error(f"Could not connect to Gateway: {e}")

with col2:
    st.markdown("### 🔍 Read Data (Quorum)")
    search_key = st.text_input("Search Key", placeholder="Enter key to query...")
    if st.button("Execute Quorum Read"):
        if search_key:
            start_time = time.time()
            try:
                resp = requests.get(f"{GATEWAY_URL}/api/data/{search_key}")
                duration = time.time() - start_time
                
                if resp.status_code == 200:
                    data = resp.json()
                    st.info(f"**Consensus Value:** {data['consensus_value']}")
                    st.caption(f"Latency: {duration:.2f}s (Quorum achieved)")
                else:
                    st.warning(f"Status {resp.status_code}: {resp.json().get('detail', 'Not Found')}")
            except Exception as e:
                st.error(f"Communication failure: {e}")