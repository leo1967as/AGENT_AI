import streamlit as st
import asyncio
import pandas as pd
import io
from agent import WebAgent

st.title("My Web AI Agent UI 🚀")
st.sidebar.write("ถามเกี่ยวกับ search, URL, หรือ stock ได้เลย!")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("พิมพ์ query ที่นี่..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("กำลังประมวลผล..."):
            agent = WebAgent()
            async def run_agent():
                async with agent._setup_mcp():
                    agent.messages[0]["content"] += " Always use tools for real-time data."
                    result = await agent.process_query(prompt)
                    return result
            result = asyncio.run(run_agent())

            # Parse และ render table ถ้า detect
            if "Date" in result and "|" in result:
                lines = [line.strip() for line in result.split('\n') if '|' in line]
                if len(lines) > 1:
                    df = pd.read_csv(io.StringIO('\n'.join(lines)), sep='|', engine='python')
                    df.columns = df.columns.str.strip()
                    st.dataframe(df, use_container_width=True)  # Render interactive table
                    st.session_state.messages.append({"role": "assistant", "content": result})
                    st.rerun()
                    st.stop()  # Exit to avoid double message 
            
            st.markdown(result)
            st.session_state.messages.append({"role": "assistant", "content": result})