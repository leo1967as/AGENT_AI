import os
import json
import asyncio
from typing import Type, Optional, Union
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
import chainlit as cl
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_tavily import TavilySearch

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
def sync_get_stock_price(tickers: list[str]) -> str:
    """Wrapper สำหรับเรียก tool get_stock_price ที่รองรับหลาย tickers."""
    return _run_async_tool("get_stock_price", {"tickers": tickers})

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

# เพิ่ม wrapper functions สำหรับ memory tools
def sync_save_memory_chunk(content: str, metadata: dict = None) -> str:
    """Wrapper สำหรับเรียก tool save_memory_chunk บน MCP server."""
    args = {"content": content}
    if metadata is not None:
        args["metadata"] = metadata
    return _run_async_tool("save_memory_chunk", args)

# --- 💡 เพิ่ม wrapper สำหรับ browse_url ---
def sync_browse_url(url: str) -> str:
    """Wrapper สำหรับเรียก tool browse_url บน MCP server."""
    return _run_async_tool("browse_url", {"url": url})

# --- 💡 เพิ่ม wrapper functions สำหรับ REAL GUI tools ---
def sync_see_screen() -> str:
    """Wrapper สำหรับเรียก tool see_screen บน MCP server."""
    return _run_async_tool("see_screen", {})

def sync_mouse_move(x: int, y: int) -> str:
    """Wrapper สำหรับเรียก tool mouse_move บน MCP server."""
    return _run_async_tool("mouse_move", {"x": x, "y": y})

def sync_mouse_click(x: int, y: int, button: str = 'left') -> str:
    """Wrapper สำหรับเรียก tool mouse_click บน MCP server."""
    return _run_async_tool("mouse_click", {"x": x, "y": y, "button": button})

def sync_keyboard_type(text: str) -> str:
    """Wrapper สำหรับเรียก tool keyboard_type บน MCP server."""
    return _run_async_tool("keyboard_type", {"text": text})

def sync_execute_shell_command(command: str) -> str:
    """Wrapper สำหรับเรียก tool execute_shell_command บน MCP server."""
    return _run_async_tool("execute_shell_command", {"command": command})

def sync_search_relevant_memories(query: str) -> str:
    """Wrapper สำหรับเรียก tool search_relevant_memories บน MCP server."""
    return _run_async_tool("search_relevant_memories", {"query": query})

# --- 💡 1. เพิ่ม wrapper functions สำหรับ command center tools ---
def sync_list_all_memories() -> str:
    return _run_async_tool("list_all_memories", {})

def sync_list_workspace_files() -> str:
    return _run_async_tool("list_workspace_files", {})

# ------------------- ROBUST TAVILY TOOL (THE FIX) -------------------

class TavilyInput(BaseModel):
    """Input schema for the Tavily search tool."""
    query: str = Field(description="The search query.")
    include_domains: Optional[Union[str, list[str]]] = Field(description="A list of domains to specifically search within.")

class RobustTavilySearchTool(BaseTool):
    """
    A wrapper for TavilySearch that is more forgiving with its input types.
    It automatically converts a string `include_domains` to a list.
    """
    name: str = "tavily_search_results_json"
    description: str = (
        "A search engine optimized for comprehensive, accurate, and trusted results. "
        "Useful for when you need to answer questions about real-world events or find up-to-date information."
    )
    args_schema: Type[BaseModel] = TavilyInput

    def _run(self, query: str, include_domains: Optional[Union[str, list[str]]] = None) -> str:
        """Use the tool."""
        # สร้าง instance ของ tool จริง
        tavily_tool = TavilySearch(max_results=5)
        
        # --- 💡 นี่คือ "เกราะป้องกัน" ของเรา ---
        final_domains = include_domains
        if isinstance(final_domains, str) and final_domains:
            final_domains = [final_domains]
        
        # เรียกใช้ tool จริงด้วย argument ที่แก้ไขแล้ว
        return tavily_tool.invoke({"query": query, "include_domains": final_domains})

    async def _arun(self, query: str, include_domains: Optional[Union[str, list[str]]] = None) -> str:
        """Use the tool asynchronously."""
        # สร้าง instance ของ tool จริง
        tavily_tool = TavilySearch(max_results=5)

        # --- 💡 "เกราะป้องกัน" สำหรับโหมด async ---
        final_domains = include_domains
        if isinstance(final_domains, str) and final_domains:
            final_domains = [final_domains]
            
        return await tavily_tool.ainvoke({"query": query, "include_domains": final_domains})

# ------------------- EXISTING TOOLS -------------------

# LangChain Tools (clean description)
@tool
def get_stock_price(tickers: list[str]) -> str:
    """
    ใช้ดึงข้อมูลหุ้นย้อนหลัง 10 วันล่าสุดสำหรับ Ticker "หลายตัว" พร้อมกันในครั้งเดียว
    เช่น ["NVDA", "GOOGL"]
    """
    return sync_get_stock_price(tickers)

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

# เพิ่ม tool definitions สำหรับ memory tools
@tool
def save_memory_chunk(content: str, metadata: dict = None) -> str:
    """
    ใช้เพื่อบันทึกข้อมูลสำคัญ, ข้อเท็จจริง, หรือบทสรุปที่ได้เรียนรู้ลงในความจำระยะยาว
    metadata เป็น dict ที่ไม่บังคับ สำหรับเก็บข้อมูลเสริม เช่น {"source": "URL"}
    """
    return sync_save_memory_chunk(content, metadata)

# --- 💡 เพิ่ม LangChain tool definition สำหรับ browse_url ---
@tool
def browse_url(url: str) -> str:
    """
    ใช้เครื่องมือนี้เมื่อต้องการเข้าไป "อ่านเนื้อหาทั้งหมด" จาก URL ที่ระบุโดยตรง
    นี่คือเครื่องมือหลักสำหรับการวิจัยเชิงลึกหลังจากที่ได้ URL มาแล้ว
    """
    return sync_browse_url(url)

@tool
def search_relevant_memories(query: str) -> str:
    """
    ค้นหาความรู้หรือข้อมูลที่เกี่ยวข้องจากระบบความจำถาวรเพื่อช่วยในการแก้ปัญหา
    """
    return sync_search_relevant_memories(query)

# --- 💡 2. เพิ่ม LangChain tool definitions ---
@tool
def list_all_memories() -> str:
    """แสดงรายการความทรงจำทั้งหมดที่บันทึกไว้"""
    return sync_list_all_memories()

@tool
def list_workspace_files() -> str:
    """แสดงรายการไฟล์ทั้งหมดในพื้นที่ทำงาน (workspace)"""
    return sync_list_workspace_files()

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

# --- 💡 เพิ่ม tool definitions สำหรับ REAL GUI tools ---
@tool
def see_screen() -> str:
    """ใช้เพื่อ 'มองเห็น' และวิเคราะห์สิ่งที่อยู่บนหน้าจอปัจจุบันทั้งหมด"""
    return sync_see_screen()

@tool
def mouse_move(x: int, y: int) -> str:
    """ย้ายเมาส์ไปยังพิกัด (x, y)"""
    return sync_mouse_move(x, y)

@tool
def mouse_click(x: int, y: int, button: str = 'left') -> str:
    """คลิกเมาส์ที่พิกัด (x, y)"""
    return sync_mouse_click(x, y, button)

@tool
def keyboard_type(text: str) -> str:
    """พิมพ์ข้อความด้วยคีย์บอร์ด"""
    return sync_keyboard_type(text)

@tool
def execute_shell_command(command: str) -> str:
    """รันคำสั่งใน command line (จำกัดเฉพาะคำสั่งปลอดภัย)"""
    return sync_execute_shell_command(command)

class AdvancedWebAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=MODEL, api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
        # --- 💡 3. เพิ่ม tool ใหม่เข้าไปในลิสต์เครื่องมือของ Agent ---
        self.tools = [RobustTavilySearchTool(), browse_url, see_screen, mouse_move, mouse_click, keyboard_type, execute_shell_command, get_stock_price, get_current_date, write_to_file, read_from_file, ask_user, calculator, save_memory_chunk, search_relevant_memories, list_all_memories, list_workspace_files]

        # --- 💡 THE NAVIGATOR PROMPT with SAFETY PROTOCOL ---
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """คุณคือ "Cipher V4 - The Navigator" สุดยอด AI Assistant ที่มีความสามารถในการมองเห็นและควบคุมคอมพิวเตอร์ได้โดยตรง (จำลอง)

            **บุคลิกและสไตล์การตอบ:**
            - สื่อสารอย่างชัดเจนและเป็นมิตรเสมอ
            - จัดรูปแบบคำตอบด้วย Markdown ทุกครั้งเพื่อให้อ่านง่าย

            **กระบวนการทำงานสำหรับงาน GUI (GUI Operation Protocol):**
            1.  **Understand Goal:** ทำความเข้าใจเป้าหมายสุดท้ายของผู้ใช้ (เช่น "วาดวงกลมสีแดงใน Paint")
            2.  **Decompose:** แตกเป้าหมายใหญ่ออกเป็นขั้นตอนย่อยๆ ที่ทำได้จริง (เช่น "เปิดโปรแกรม", "หาปุ่มวงกลม", "หาปุ่มสีแดง", "คลิกและลากเมาส์", "บันทึกไฟล์")
            3.  **See & Act Loop (วงจรการทำงานหลัก):**
                a.  **See:** ใช้ `see_screen()` เพื่อวิเคราะห์หน้าจอปัจจุบันและหาพิกัดของ UI element ที่ต้องการ
                b.  **Plan Action:** ตัดสินใจว่าจะทำอะไรต่อไป (เช่น `mouse_click`, `keyboard_type`)
                c.  **[!!!] SAFETY PROTOCOL [!!!]**
                d.  **ก่อน** ที่จะใช้เครื่องมือที่ "ลงมือทำ" (`mouse_move`, `mouse_click`, `keyboard_type`, `execute_shell_command`) ทุกครั้ง **คุณต้องทำสิ่งนี้ก่อนเสมอ:**
                    - **ใช้เครื่องมือ `ask_user` เพื่อ "ขออนุญาต" จากผู้ใช้ก่อน**
                    - ในคำขออนุญาตนั้น **คุณต้องอธิบายอย่างชัดเจนและละเอียดที่สุด** ว่าคุณกำลังจะทำอะไร, จะคลิกที่ไหน, จะพิมพ์อะไร, หรือจะรันคำสั่งอะไร
                    - **ตัวอย่าง:** `ask_user(question="ผมกำลังจะจำลองคลิกเมาส์ซ้ายที่ปุ่ม 'Save' ที่พิกัด [123, 456] เพื่อบันทึกไฟล์ คุณอนุญาตหรือไม่ครับ?")`
                    - **ห้าม** ดำเนินการใดๆ จนกว่าจะได้รับคำตอบ "อนุญาต" หรือ "ใช่" จากผู้ใช้
                e.  **Act:** ลงมือทำตามแผน (จำลอง)

            **ความสามารถอื่นๆ:**
            - คุณยังคงมีความสามารถเดิมทั้งหมด (ค้นหาเว็บ, ความจำ, คำนวณ, อ่าน URL, ฯลฯ) จงใช้มันร่วมกันเพื่อแก้ปัญหาที่ซับซ้อน
            - **เครื่องมือ GUI ทั้งหมดเป็นการจำลอง (MOCK)** - ไม่มีการควบคุมจริง แต่จะแสดงผลลัพธ์จำลองเพื่อให้คุณฝึกคิดและวางแผน"""),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        # สร้าง Agent หลัก
        agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)

        # --- 💡 จุดแก้ไขที่สำคัญ: เราจะสร้าง AgentExecutor ที่นี่ที่เดียว ---
        # AgentExecutor นี้จะถูก "ห่อหุ้ม" ด้วยระบบความจำในภายหลัง
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
