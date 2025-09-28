# agent.py

import os
import json
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
import chainlit as cl
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
    server_params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS, env={"PYTHONUTF8": "1"})
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
# --- 💡 โค้ดที่แก้ไขแล้ว ---
def sync_web_search(query: str) -> str:
    """
    ฟังก์ชัน Wrapper สำหรับเรียก web_search tool บน MCP server.
    ลบ Fallback logic ออกเพื่อให้ server จัดการการค้นหาทั้งหมด
    """
    return _run_async_tool("web_search", {"query": query})

def sync_get_stock_price(tickers: list[str]) -> str:
    """Wrapper สำหรับเรียก tool get_stock_price ที่รองรับหลาย tickers."""
    return _run_async_tool("get_stock_price", {"tickers": tickers})

def sync_browse_url(url: str) -> str:
    return _run_async_tool("browse_url", {"url": url})

# --- 💡 1. เพิ่ม wrapper functions สำหรับ file tools ---
def sync_get_current_date() -> str:
    """Wrapper สำหรับเรียก tool get_current_date บน MCP server."""
    return _run_async_tool("get_current_date", {})

def sync_write_to_file(filename: str, content: str) -> str:
    """Wrapper สำหรับเรียก tool write_to_file บน MCP server."""
    return _run_async_tool("write_to_file", {"filename": filename, "content": content})

def sync_read_from_file(filename: str) -> str:
    """Wrapper สำหรับเรียก tool read_from_file บน MCP server."""
    return _run_async_tool("read_from_file", {"filename": filename})

def sync_calculator(expression: str) -> str:
    """Wrapper สำหรับเรียก tool calculator บน MCP server."""
    return _run_async_tool("calculator", {"expression": expression})

# LangChain Tools (clean description)
@tool
def web_search(query: str) -> str:
    """ค้นหาข้อมูลจากเว็บด้วย query."""
    return sync_web_search(query)

@tool
def get_stock_price(tickers: list[str]) -> str:
    """
    ใช้ดึงข้อมูลหุ้นย้อนหลัง 10 วันล่าสุดสำหรับ Ticker "หลายตัว" พร้อมกันในครั้งเดียว
    เช่น ["NVDA", "GOOGL"]
    """
    return sync_get_stock_price(tickers)

@tool
def browse_url(url: str) -> str:
    """อ่านและสรุปเนื้อหาจาก URL."""
    return sync_browse_url(url)

# --- 💡 2. เพิ่ม LangChain tool definitions สำหรับ file tools ---
@tool
def get_current_date() -> str:
    """
    ใช้เครื่องมือนี้เมื่อต้องการทราบวันที่หรือเวลาปัจจุบัน
    """
    return sync_get_current_date()

@tool
def write_to_file(filename: str, content: str) -> str:
    """
    ใช้เครื่องมือนี้เพื่อเขียนหรือบันทึกข้อมูลที่เป็นข้อความ (content) ลงในไฟล์ (filename)
    มีประโยชน์มากสำหรับการบันทึกสรุป, ร่างอีเมล, หรือผลลัพธ์การทำงาน
    """
    return sync_write_to_file(filename, content)

@tool
def read_from_file(filename: str) -> str:
    """
    ใช้เครื่องมือนี้เพื่ออ่านเนื้อหาทั้งหมดจากไฟล์ (filename) ที่มีอยู่
    มีประโยชน์เมื่อต้องการข้อมูลจากไฟล์เพื่อนำมาตอบคำถามหรือทำงานต่อ
    """
    return sync_read_from_file(filename)

@tool
def calculator(expression: str) -> str:
    """
    ใช้เครื่องมือนี้เมื่อต้องการคำนวณทางคณิตศาสตร์เท่านั้น
    เช่น '2 * (3 + 4)', '(8000 + 36500)', etc.
    """
    return sync_calculator(expression)

# --- 💡 เพิ่ม Tool ใหม่สำหรับ Human-in-the-Loop ---
@tool
async def ask_user(question: str) -> str:
    """
    ใช้เครื่องมือนี้ "เมื่อจำเป็นเท่านั้น" เพื่อถามคำถามกลับไปยังผู้ใช้
    มีประโยชน์มากเมื่อคุณต้องการข้อมูลเพิ่มเติม, ต้องการคำชี้แนะ, หรือไม่แน่ใจว่าจะทำอะไรต่อ
    ห้ามใช้เครื่องมือนี้เพื่อถามคำถามที่ไม่จำเป็นหรือถามเพื่อยืนยันสิ่งที่รู้อยู่แล้ว
    """
    # ใช้ cl.AskUserMessage ของ Chainlit เพื่อแสดงกล่องข้อความรอ input
    response = await cl.AskUserMessage(content=question, timeout=120).send()
    if response:
        return f"User responded: {response['output']}"
    else:
        return "The user did not respond in time."

class AdvancedWebAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=MODEL, api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
        # --- 💡 3. เพิ่ม tool ใหม่เข้าไปในลิสต์เครื่องมือของ Agent ---
        self.tools = [web_search, get_stock_price, browse_url, get_current_date, write_to_file, read_from_file, ask_user, calculator]
        self.memory = ConversationBufferWindowMemory(k=5, return_messages=True, memory_key="chat_history") # เพิ่ม memory_key

        # --- 💡 อัปเกรด "สมอง" และ "บุคลิก" ของ Agent ---
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """คุณคือ "Cipher" สุดยอด AI Assistant ที่มีความเชี่ยวชาญ, รอบคอบ, และสามารถแก้ปัญหาเฉพาะหน้าได้

            **บุคลิกและสไตล์การตอบ:**
            - สื่อสารอย่างชัดเจนและเป็นมิตรเสมอ
            - จัดรูปแบบคำตอบด้วย Markdown ทุกครั้งเพื่อให้อ่านง่าย

            **กระบวนการคิดและการทำงาน (Workflow ที่สำคัญที่สุด):**
            เมื่อได้รับคำสั่ง ให้คุณทำตามกระบวนการ "Plan-Execute-Critique-Refine" นี้เสมอ:
            1.  **Plan:** วางแผนว่าจะใช้เครื่องมืออะไรเพื่อบรรลุเป้าหมาย
            2.  **Execute:** ลงมือใช้เครื่องมือตามแผน
            3.  **Critique (วิจารณ์):** **นี่คือขั้นตอนที่สำคัญที่สุด!** หลังจากได้ผลลัพธ์ (Observation) กลับมา ให้หยุดและถามตัวเองว่า:
                - "ผลลัพธ์นี้สำเร็จหรือไม่? มี Error หรือไม่?"
                - "ข้อมูลที่ได้มาเพียงพอที่จะตอบคำถามสุดท้ายหรือยัง?"
                - "ถ้าล้มเหลว มันล้มเหลวเพราะอะไร? (เช่น API พัง, ไม่มีข้อมูล, ชื่อผิด)"
                - "มี 'แผนสำรอง' หรือ 'ทางอ้อม' ที่ดีกว่านี้ไหม?"
            4.  **Refine (ปรับปรุง):**
                - **ถ้าสำเร็จและข้อมูลเพียงพอ:** ไปที่ขั้นตอนการสร้าง Final Answer
                - **ถ้าล้มเหลวหรือข้อมูลไม่พอ:** **อย่าเพิ่งยอมแพ้!** ให้สร้าง "แผนใหม่" ที่ปรับปรุงแล้วโดยอิงจากผลการวิจารณ์ (เช่น เปลี่ยนไปใช้ `web_search` แทน, ลองเปลี่ยนคำค้นหา, หรือใช้ `ask_user` เพื่อถามผู้ใช้) แล้วกลับไปทำขั้นตอน Execute อีกครั้ง

            **ตัวอย่างการแก้ปัญหา:**
            - ถ้า `get_stock_price` ล้มเหลว ให้วิจารณ์ว่า "Tool อาจจะพัง หรือ Ticker ผิด" และสร้างแผนใหม่ "ลองใช้ `web_search` เพื่อหาข้อมูลราคาหุ้นจากเว็บแทน"
            - ถ้า `browse_url` แล้วได้ข้อมูลไม่ตรงประเด็น ให้วิจารณ์ว่า "URL นี้อาจจะไม่ดี" และสร้างแผนใหม่ "กลับไปดูผลการค้นหาเดิมแล้วเลือก `browse_url` กับ URL อื่น"

            **Workflow อัจฉริยะ:**
            - **การทำงานกับหลายรายการ:** เมื่อผู้ใช้ขอข้อมูลสำหรับหลายรายการพร้อมกัน (เช่น หุ้นหลายตัว, ไฟล์หลายไฟล์) **ให้คุณรวบรวมรายการทั้งหมดแล้วเรียกใช้เครื่องมือที่เกี่ยวข้องเพียง "ครั้งเดียว"** โดยส่งเป็นลิสต์ (list) เพื่อประสิทธิภาพสูงสุด

            **ความสามารถพิเศษ:**
            - **การคำนวณ:** สำหรับโจทย์คณิตศาสตร์หรือการคำนวณใดๆ **ให้ใช้เครื่องมือ `calculator` เสมอ** โดยแปลงโจทย์ให้เป็นสมการในรูปแบบสตริง"""),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        # --- 💡 2. เปลี่ยน "สมอง" ของ Agent ---
        # ใช้ create_openai_tools_agent ซึ่งฉลาดกว่าในการวางแผน
        self.agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
        
        # --- 💡 3. กำหนดค่า AgentExecutor ให้ทำงานกับ Agent ใหม่ ---
        # เพิ่ม max_iterations ให้เผื่อต้องมีรอบแก้ไข
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=12, # เพิ่มให้เผื่อต้องมีรอบแก้ไข
            memory=self.memory,
            handle_parsing_errors=True
        )

    def process_query(self, query: str):
        # Tools Agent ต้องการ history ใน key 'chat_history'
        try:
            # ใช้ ainvoke เพื่อการทำงานแบบ async ที่ถูกต้อง
            result = self.agent_executor.invoke({"input": query, "chat_history": self.memory.chat_memory.messages})
            return result.get('output', 'Agent did not return an output.')
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