แน่นอนครับ นี่คือแนวทางการแก้ไขพร้อมโค้ดที่ปรับปรุงแล้วสำหรับแต่ละไฟล์ เพื่อแก้ปัญหาที่พบและปรับปรุงโครงสร้างของแอปพลิเคชันให้ดียิ่งขึ้น

### 1. แก้ไข `server.py` (แก้ไข Bug หลัก)

**ปัญหา:** Tool `get_stock_price` ดึงข้อมูลเพียงวันเดียว (`1d`) แต่ Agent คาดหวังข้อมูลย้อนหลัง (`10d`)

**แนวทางการแก้ไข:** ปรับปรุงฟังก์ชัน `get_stock_price` ให้สามารถรับ `period` (จำนวนวัน) เป็นพารามิเตอร์ได้ ทำให้มีความยืดหยุ่น และเปลี่ยนโค้ดให้คืนค่าข้อมูลย้อนหลังเป็น list ของแต่ละวันตามที่ Agent คาดหวัง

**ไฟล์: `server.py`**
```python
# server.py

from fastmcp import FastMCP
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import re
import yfinance as yf
import time
import json

mcp = FastMCP("My Free Web Agent MCP Server")

@mcp.tool()
def web_search(query: str, num_results: int = 5) -> str:
    """ค้นหาข้อมูลทั่วเว็บแบบเรียลไทม์ด้วย DuckDuckGo. Args: query (str), num_results (int, default=5)"""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=num_results)]
        output = json.dumps([{
            "title": r['title'],
            "snippet": r['body'][:200] + "..." if len(r['body']) > 200 else r['body'],
            "url": r['href']
        } for r in results], ensure_ascii=False, indent=2)
        return output
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def browse_url(url: str, summarize: bool = True) -> str:
    """เข้าไปอ่าน content จาก URL ที่ให้มา แล้ว return text หลัก ๆ (หรือ summarize ถ้า summarize=True). Args: url (str), summarize (bool, default=True)"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        time.sleep(1)
        
        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        if summarize:
            summary = text[:200] + "..." if len(text) > 200 else text
            sentences = re.split(r'[.!?]+', text)
            key_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
            return json.dumps({
                "summary": summary,
                "key_points": key_sentences
            }, ensure_ascii=False)
        else:
            return json.dumps({"full_text": text[:5000]})
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- 💡 โค้ดที่แก้ไขแล้ว ---
@mcp.tool()
def get_stock_price(ticker: str, period: str = "10d") -> str:
    """
    ดึงข้อมูลราคาย้อนหลังของหุ้นจาก Yahoo Finance.
    Args:
        ticker (str): สัญลักษณ์ของหุ้น เช่น 'NVDA', 'AAPL'.
        period (str): ช่วงเวลาที่ต้องการข้อมูลย้อนหลัง ค่าเริ่มต้นคือ '10d'. ตัวอย่าง: '1d', '5d', '1mo', '3mo', '1y'.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return json.dumps({"error": f"ไม่พบข้อมูลสำหรับ ticker '{ticker}' ในช่วงเวลา '{period}'"})
        
        # รีเซ็ต index เพื่อให้ 'Date' กลายเป็นคอลัมน์ปกติ
        df = hist.reset_index()

        # แปลงข้อมูลเป็น format ที่ Agent ต้องการ (list of dictionaries)
        data = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
        
        # ใช้ default=str เพื่อจัดการกับ object ประเภทวันที่ (datetime) ตอนแปลงเป็น JSON
        return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
```
**คำอธิบายเพิ่มเติม:**
*   แก้ไข docstring ให้ชัดเจนว่า Tool นี้รับพารามิเตอร์ `period` ได้ ซึ่งจะช่วยให้ LLM Agent สามารถเรียกใช้งานได้อย่างถูกต้องเมื่อเจอกับคำสั่ง เช่น "ขอดูหุ้นย้อนหลัง 5 วัน"
*   เปลี่ยน logic การดึงและคืนค่าข้อมูลให้ตรงกับที่ test case ใน `agent.py` ต้องการ

---

### 2. แก้ไข `agent.py` (ปรับปรุงสถาปัตยกรรมและ Async)

**ปัญหา:**
1.  มีการสร้าง Event loop ใหม่ทุกครั้งที่เรียกใช้ Tool ซึ่งไม่มีประสิทธิภาพ
2.  โค้ดไม่เป็นไปในทิศทางเดียวกัน: Tool บางตัวเรียกผ่าน MCP Server แต่ `sync_get_stock_price` มี Logic การทำงานของตัวเองอยู่

**แนวทางการแก้ไข:**
1.  ใช้ `asyncio.run()` ซึ่งเป็นวิธีที่ทันสมัยและง่ายกว่าในการจัดการ Event loop สำหรับการรันฟังก์ชัน async แบบเดี่ยวๆ
2.  ปรับปรุง `sync_get_stock_price` ให้เรียกใช้ Tool ผ่าน MCP Server เหมือนกับฟังก์ชันอื่นๆ เพื่อให้สถาปัตยกรรมเป็นรูปแบบเดียวกันทั้งหมด

**ไฟล์: `agent.py`**
```python
# agent.py

import os
import json
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.tools import DuckDuckGoSearchRun
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
# yfinance ไม่จำเป็นต้องใช้ในไฟล์นี้แล้ว เพราะเราจะเรียกผ่าน server ทั้งหมด
# import yfinance as yf 
import pandas as pd

load_dotenv()

MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENROUTER_API_KEY")
SERVER_COMMAND = "python"
SERVER_ARGS = ["server.py"]

@asynccontextmanager
async def _setup_mcp():
    server_params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

# --- 💡 โค้ดที่แก้ไขแล้ว ---

def _run_async_tool(tool_name: str, arguments: dict) -> str:
    """Helper function to run an async MCP tool synchronously."""
    async def _async_call():
        async with _setup_mcp() as session:
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text if result.content else '{"error": "No content returned from tool"}'

    try:
        # ใช้ asyncio.run() ซึ่งจัดการ loop ให้เอง
        return asyncio.run(_async_call())
    except Exception as e:
        return json.dumps({"error": f"Failed to run async tool {tool_name}: {e}"})

# Sync wrappers ที่เรียกใช้ MCP Server ทั้งหมด
def sync_web_search(query: str) -> str:
    mcp_result = _run_async_tool("web_search", {"query": query})
    if "[]" in mcp_result or "error" in mcp_result.lower():
        search = DuckDuckGoSearchRun()
        fallback = search.run(query)
        return json.dumps([{"title": "Fallback Search", "snippet": fallback[:200], "url": ""}])
    return mcp_result

def sync_get_stock_price(ticker: str) -> str:
    # เปลี่ยนให้เรียก tool ผ่าน MCP server เพื่อให้สอดคล้องกัน
    return _run_async_tool("get_stock_price", {"ticker": ticker, "period": "10d"})

def sync_browse_url(url: str) -> str:
    return _run_async_tool("browse_url", {"url": url})

# LangChain Tools (clean description)
@tool
def web_search(query: str) -> str:
    """ค้นหาข้อมูลจากเว็บด้วย query."""
    return sync_web_search(query)

@tool
def get_stock_price(ticker: str) -> str:
    """ดึงข้อมูลหุ้น historical 10 วันล่าสุดของ ticker ที่ระบุ."""
    return sync_get_stock_price(ticker)

@tool
def browse_url(url: str) -> str:
    """อ่านและสรุปเนื้อหาจาก URL."""
    return sync_browse_url(url)

# Class AdvancedWebAgent ไม่มีการเปลี่ยนแปลง
class AdvancedWebAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=MODEL, api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
        self.tools = [web_search, get_stock_price, browse_url]
        self.memory = ConversationBufferWindowMemory(k=5, return_messages=True)
        self.prompt = PromptTemplate.from_template(
            "ตอบคำถามต่อไปนี้ให้ดีที่สุดโดยใช้ context จากการสนทนาก่อนหน้า. คุณมี tools ดังนี้:\n{tools}\n\nใช้ format นี้:\n\nQuestion: คำถามที่ต้องตอบ\nThought: คิดว่าต้องทำอะไร (ใช้ memory ถ้าจำเป็น)\nAction: action ที่จะทำ, ต้องเป็นหนึ่งใน [{tool_names}]\nAction Input: inputสำหรับ action\nObservation: ผลจาก action\n... (Thought/Action/Action Input/Observation ซ้ำได้ N ครั้ง)\nThought: รู้คำตอบแล้ว\nFinal Answer: คำตอบสุดท้าย (format เป็น Markdown table ถ้าข้อมูลเป็นตาราง)\n\nPrevious Conversation: {history}\n\nBegin!\n\nQuestion: {input}\nThought: {agent_scratchpad}"
        )
        self.agent = create_react_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True, max_iterations=3, memory=self.memory)

    def process_query(self, query: str):
        try:
            result = self.agent_executor.invoke({"input": query})
            return result['output']
        except Exception as e:
            return f"เกิดข้อผิดพลาด: {str(e)}"

# Test
def main():
    agent = AdvancedWebAgent()
    result1 = agent.process_query("NVDA stock last 10 days in table")
    print("\n=== ผลลัพธ์ 1 ===")
    print(result1)
    result2 = agent.process_query("แนวโน้มจากข้อมูล NVDA เมื่อกี้?")
    print("\n=== ผลลัพธ์ 2 (จาก memory) ===")
    print(result2)

if __name__ == "__main__":
    main()
```
**คำอธิบายเพิ่มเติม:**
*   สร้าง `_run_async_tool` เพื่อลดความซ้ำซ้อนของโค้ดในการเรียกใช้ MCP tool
*   ตอนนี้ Tool ทั้ง 3 ตัว (`web_search`, `get_stock_price`, `browse_url`) ทำงานในรูปแบบเดียวกันคือส่งคำสั่งไปยัง `server.py` ทำให้โค้ดสะอาดและง่ายต่อการดูแลรักษา

---

### 3. แก้ไข `app.py` (ปรับปรุงการแสดงผลให้เสถียร)

**ปัญหา:** การดักจับ Log จาก `sys.stdout` และใช้ Regex เพื่อแสดงผลเป็นวิธีที่เปราะบางมาก หาก LangChain เปลี่ยน Format การแสดงผล โค้ดส่วนนี้จะพังทันที

**แนวทางการแก้ไข:** ใช้ระบบ `Callback` ที่ LangChain ออกแบบมาโดยเฉพาะ `AsyncIteratorCallbackHandler` เหมาะสมที่สุดสำหรับการทำงานร่วมกับ `asyncio` และ Chainlit เพื่อสตรีมผลลัพธ์การทำงานของ Agent แบบเรียลไทม์

**ไฟล์: `app.py`**
```python
# app.py

import chainlit as cl
import asyncio
from langchain.memory import ConversationBufferWindowMemory
from agent import AdvancedWebAgent
from langchain.callbacks import AsyncIteratorCallbackHandler # 💡 Import ที่ต้องเพิ่ม

@cl.on_chat_start
async def start():
    # Agent และ Memory ถูกสร้างขึ้นใหม่ในแต่ละ session
    agent_instance = AdvancedWebAgent()
    cl.user_session.set("agent", agent_instance)
    cl.user_session.set("memory", agent_instance.memory) # ใช้ memory จาก instance เดียวกัน
    await cl.Message(content="สวัสดี! Agent พร้อมแล้ว – ถามอะไรได้เลย (e.g. 'ราคาหุ้น NVDA ตอนนี้') ฉันจะแสดงกระบวนการคิดแบบ step-by-step แล้วสรุปตอนเสร็จ! ตอบเป็นภาษาไทยเสมอ 🚀").send()

# --- 💡 โค้ดที่แก้ไขแล้ว ---
@cl.on_message
async def main(message: cl.Message):
    agent = cl.user_session.get("agent")
    memory = cl.user_session.get("memory")
    agent.memory = memory # อัปเดต memory ทุกครั้ง

    # สร้าง Callback Handler เพื่อรับ stream output จาก Agent
    callback_handler = AsyncIteratorCallbackHandler()

    # สร้าง Task สำหรับรัน Agent เพื่อไม่ให้ block การทำงานของ UI
    run_task = asyncio.create_task(
        agent.agent_executor.ainvoke(
            {"input": message.content},
            config={"callbacks": [callback_handler]}
        )
    )

    # แสดงขั้นตอนการทำงาน (Thought, Action, Observation) แบบ Real-time
    final_answer = ""
    async for token in callback_handler.aiter():
        # ส่ง token ที่ได้รับจาก Agent ไปยัง UI ทันที
        await cl.Message(content=token).send()

    # รอให้ Task ทำงานเสร็จสิ้นและรับผลลัพธ์สุดท้าย
    result = await run_task
    final_answer = result.get('output', 'ไม่พบคำตอบสุดท้าย')

    # ส่งข้อความสรุปสุดท้าย
    await cl.Message(content=f"**คำตอบสุดท้าย:**\n{final_answer}").send()
```
**คำอธิบายเพิ่มเติม:**
*   โค้ดแบบใหม่นี้จะสตรีม `Thought`, `Action`, `Observation` ของ Agent ออกมาที่หน้าจอแชททันทีที่มันเกิดขึ้น ทำให้ผู้ใช้เห็นกระบวนการทำงานแบบสดๆ
*   เป็นวิธีที่ถูกต้องและทนทานต่อการเปลี่ยนแปลงของไลบรารี LangChain ในอนาคต
*   ลบโค้ดที่ซับซ้อนเกี่ยวกับการดักจับ `sys.stdout` และการใช้ Regular Expression ออกไปทั้งหมด ทำให้โค้ดสะอาดและเข้าใจง่ายขึ้นมาก