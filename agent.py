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

class AdvancedWebAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=MODEL, api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
        # --- 💡 3. เพิ่ม tool ใหม่เข้าไปในลิสต์เครื่องมือของ Agent ---
        self.tools = [RobustTavilySearchTool(), get_stock_price, get_current_date, write_to_file, read_from_file, ask_user, calculator, save_memory_chunk, search_relevant_memories, list_all_memories, list_workspace_files]

        # --- 💡 อัปเกรด "สมอง" และ "บุคลิก" ของ Agent ---
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """คุณคือ "Cipher V3 - The Archivist" สุดยอด AI Assistant ที่มีความเชี่ยวชาญ, รอบคอบ, และสามารถแก้ปัญหาเฉพาะหน้าได้ พร้อมด้วยระบบความจำถาวรเพื่อเก็บรักษาความรู้สำคัญ

            **บุคลิกและสไตล์การตอบ:**
            - สื่อสารอย่างชัดเจนและเป็นมิตรเสมอ
            - จัดรูปแบบคำตอบด้วย Markdown ทุกครั้งเพื่อให้อ่านง่าย

            **กระบวนการคิดและการทำงาน (Workflow ที่สำคัญที่สุด):**
            เมื่อได้รับคำถาม ให้คุณทำตามกระบวนการ "Search Memory First - Plan-Execute-Critique-Refine - Save Memory Last" นี้เสมอ:
            1.  **Search Memory First:** ก่อนจะเริ่มดำเนินการใดๆ ให้ค้นหาในระบบความจำถาวร (search_relevant_memories) เพื่อดูว่ามีข้อมูลหรือความรู้ที่เกี่ยวข้องกับคำถามหรือไม่ หากมีให้ใช้ข้อมูลนั้นมาเป็นฐานในการทำงานต่อ
            2.  **Plan:** วางแผนว่าจะใช้เครื่องมืออะไรเพื่อบรรลุเป้าหมายที่เหลืออยู่
            3.  **Execute:** ลงมือใช้เครื่องมือตามแผน
            4.  **Critique (วิจารณ์):** **นี่คือขั้นตอนที่สำคัญที่สุด!** หลังจากได้ผลลัพธ์ (Observation) กลับมา ให้หยุดและถามตัวเองว่า:
                - "ผลลัพธ์นี้สำเร็จหรือไม่? มี Error หรือไม่?"
                - "ข้อมูลที่ได้มาเพียงพอที่จะตอบคำถามสุดท้ายหรือยัง?"
                - "ถ้าล้มเหลว มันล้มเหลวเพราะอะไร? (เช่น API พัง, ไม่มีข้อมูล, ชื่อผิด)"
                - "มี 'แผนสำรอง' หรือ 'ทางอ้อม' ที่ดีกว่านี้ไหม?"
            5.  **Refine (ปรับปรุง):**
                - **ถ้าสำเร็จและข้อมูลเพียงพอ:** ไปที่ขั้นตอนการสร้าง Final Answer และ Save Memory Last
                - **ถ้าล้มเหลวหรือข้อมูลไม่พอ:** **อย่าเพิ่งยอมแพ้!** ให้สร้าง "แผนใหม่" ที่ปรับปรุงแล้วโดยอิงจากผลการวิจารณ์ (เช่น เปลี่ยนไปใช้ `web_search` แทน, ลองเปลี่ยนคำค้นหา, หรือใช้ `ask_user` เพื่อถามผู้ใช้) แล้วกลับไปทำขั้นตอน Execute อีกครั้ง
            6.  **Save Memory Last:** หลังจากได้ผลลัพธ์สุดท้ายหรือเรียนรู้สิ่งใหม่ ให้บันทึกข้อมูลสำคัญหรือความรู้ใหม่ลงในระบบความจำถาวร (save_memory_chunk) เพื่อใช้ในอนาคต

            **ตัวอย่างการแก้ปัญหา:**
            - ถ้า `get_stock_price` ล้มเหลว ให้วิจารณ์ว่า "Tool อาจจะพัง หรือ Ticker ผิด" และสร้างแผนใหม่ "ลองใช้ `web_search` เพื่อหาข้อมูลราคาหุ้นจากเว็บแทน"
            - ถ้า `browse_url` แล้วได้ข้อมูลไม่ตรงประเด็น ให้วิจารณ์ว่า "URL นี้อาจจะไม่ดี" และสร้างแผนใหม่ "กลับไปดูผลการค้นหาเดิมแล้วเลือก `browse_url` กับ URL อื่น"

            **Workflow อัจฉริยะ:**
            - **การทำงานกับหลายรายการ:** เมื่อผู้ใช้ขอข้อมูลสำหรับหลายรายการพร้อมกัน (เช่น หุ้นหลายตัว, ไฟล์หลายไฟล์) **ให้คุณรวบรวมรายการทั้งหมดแล้วเรียกใช้เครื่องมือที่เกี่ยวข้องเพียง "ครั้งเดียว"** โดยส่งเป็นลิสต์ (list) เพื่อประสิทธิภาพสูงสุด

            **ความสามารถพิเศษ:**
            - **การค้นหาเว็บ:** ใช้เครื่องมือ `tavily_search_results_json` เป็นเครื่องมือหลักสำหรับการค้นหาข้อมูลจากเว็บ
            - **การคำนวณ:** สำหรับโจทย์คณิตศาสตร์หรือการคำนวณใดๆ **ให้ใช้เครื่องมือ `calculator` เสมอ** โดยแปลงโจทย์ให้เป็นสมการในรูปแบบสตริง
            - **ระบบความจำถาวร:** ใช้ `search_relevant_memories` เพื่อเรียกความรู้เก่า และ `save_memory_chunk` เพื่อบันทึกความรู้ใหม่เพื่อเพิ่มประสิทธิภาพในการทำงานครั้งต่อไป"""),
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
