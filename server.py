import json
import os
import uuid
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP

# --- 💡 1. เพิ่ม import สำหรับความสามารถใหม่ ---
import chromadb
import pypdf
import docx
from duckduckgo_search import DDGS
import numexpr as ne
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# สร้าง MCP instance
mcp = FastMCP("The Archivist's Tools")

# กำหนดพื้นที่ทำงานที่ปลอดภัย
WORKSPACE_DIR = "workspace"
os.makedirs(WORKSPACE_DIR, exist_ok=True)

# --- Memory Setup ---
MEMORY_DIR = "memory_db"
os.makedirs(MEMORY_DIR, exist_ok=True)
client = chromadb.PersistentClient(path=MEMORY_DIR)
memory_collection = client.get_or_create_collection(name="memories")

# --- NEW MEMORY TOOLS ---

@mcp.tool()
def save_memory_chunk(content: str, metadata: dict = None) -> str:
    """
    บันทึก "ชิ้นส่วนของความทรงจำ" (content) ที่สำคัญลงในฐานข้อมูลความจำระยะยาว
    """
    print(f"--- Saving memory chunk: '{content[:50]}...' ---")
    try:
        doc_id = f"mem_{int(datetime.now().timestamp())}"

        # --- 💡 จุดแก้ไขที่สำคัญ ---
        # สร้าง final_metadata ขึ้นมา
        final_metadata = metadata or {}

        # เพิ่ม timestamp เข้าไปโดยอัตโนมัติเสมอ
        # เพื่อให้แน่ใจว่า metadata จะไม่ว่างเปล่า
        final_metadata['saved_at'] = datetime.now().isoformat()

        memory_collection.add(
            documents=[content],
            metadatas=[final_metadata], # <--- ใช้ final_metadata ที่มีข้อมูลเสมอ
            ids=[doc_id]
        )
        return json.dumps({"status": "success", "message": f"Memory chunk saved with ID {doc_id}."})
    except Exception as e:
        return json.dumps({"error": f"Failed to save memory: {str(e)}"})

@mcp.tool()
def search_relevant_memories(query: str, n_results: int = 5) -> str:
    """
    ค้นหา memories ที่เกี่ยวข้องจาก ChromaDB โดยใช้ semantic search
    Args:
        query (str): คำค้นหา
        n_results (int): จำนวนผลลัพธ์สูงสุดที่ต้องการ (default=5)
    """
    try:
        results = memory_collection.query(query_texts=[query], n_results=n_results)
        memories = []
        if results['documents']:
            for doc, meta, id in zip(results['documents'][0], results['metadatas'][0], results['ids'][0]):
                memories.append({"id": id, "content": doc, "metadata": meta})
        return json.dumps({"memories": memories}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

# ------------------- EXISTING TOOLS -------------------

@mcp.tool()
def browse_url(url: str) -> str:
    """
    เข้าไปอ่านและดึง "เนื้อหาหลักที่สะอาด" ทั้งหมดจาก URL ที่ให้มา
    เครื่องมือนี้จะพยายามลบเมนู, โฆษณา, และส่วนที่ไม่จำเป็นออก
    """
    print(f"--- Server browsing URL with Simple Method: {url} ---")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')

        # ลบแท็กที่ไม่ใช่เนื้อหาหลักออกไปให้มากที่สุด
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()
        
        # ดึงข้อความออกมา โดยให้มีการขึ้นบรรทัดใหม่เพื่อให้อ่านง่าย
        text = soup.get_text(separator='\n', strip=True)
        
        if not text:
            return json.dumps({"error": "Could not extract text content from the URL."}, ensure_ascii=False)

        # จำกัดความยาวสูงสุดเพื่อไม่ให้ context ของ Agent ยาวเกินไป
        max_length = 15000
        truncated_text = text[:max_length]

        print(f"--- Extracted text length: {len(truncated_text)} characters. ---")
        # คืนค่าเป็นเนื้อหาที่สะอาด ไม่มีการสรุปใน tool นี้
        return json.dumps({"url": url, "content": truncated_text}, ensure_ascii=False)

    except Exception as e:
        print(f"!!! ERROR in browse_url tool: {e} !!!")
        return json.dumps({"error": f"An exception occurred while browsing the URL: {str(e)}"}, ensure_ascii=False)

@mcp.tool()
def web_search(query: str, num_results: int = 5) -> str:
    """ค้นหาข้อมูลเว็บด้วย DuckDuckGo อย่างเดียวเท่านั้น Args: query (str), num_results (int, default=5)"""
    print(f"--- Server received web_search request for query: '{query}' ---")
    try:
        with DDGS() as ddgs:
            # --- 💡 จุดที่แก้ไข: เราจะเพิ่ม `backend="lite"` ---
            # "lite" backend จะใช้ DuckDuckGo เวอร์ชันที่เรียบง่าย, รวดเร็ว, และเสถียรที่สุด
            # และที่สำคัญคือ "จะไม่" พยายามไปเรียกใช้เอนจิ้นอื่น เช่น Brave
            results = list(ddgs.text(query, backend="lite", max_results=num_results))

        if not results:
            return json.dumps({"error": "No results found from DuckDuckGo."})

        output = [{
            "title": r.get('title', 'No Title'),
            "snippet": r.get('body', '')[:300] + "...",
            "url": r.get('href', '')
        } for r in results]

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"!!! ERROR in web_search tool: {e} !!!")
        return json.dumps({"error": f"An exception occurred during search: {str(e)}"})

@mcp.tool()
def get_stock_price(tickers: list[str], period: str = "10d") -> str:
    """
    ดึงข้อมูลราคาย้อนหลังของหุ้นจาก Yahoo Finance สำหรับ Ticker "หลายตัว" พร้อมกัน
    Args:
        tickers (list[str]): ลิสต์ของสัญลักษณ์หุ้น เช่น ['NVDA', 'AAPL'].
        period (str): ช่วงเวลาที่ต้องการข้อมูลย้อนหลัง (e.g., '10d', '1mo').
    """
    try:
        # --- 💡 จุดที่แก้ไข: เราจะเพิ่ม `timeout=15` เข้าไป ---
        # เพื่อป้องกันไม่ให้ yfinance ค้างนานเกินไปเมื่อเจอ Ticker ที่ไม่มีอยู่จริง
        data = yf.download(tickers, period=period, timeout=15)

        if data.empty:
            return json.dumps({"error": f"ไม่พบข้อมูลสำหรับ tickers ที่ระบุ"})

        results = {}
        # ตรวจสอบว่า tickers ที่รับมาเป็น list หรือไม่ (กรณี yf.download ได้ ticker เดียว)
        ticker_list = tickers if isinstance(tickers, list) else [tickers]

        # จัดการกรณีที่ data มี column level เดียว (เมื่อได้ ticker เดียว)
        if not isinstance(data.columns, pd.MultiIndex):
            data.columns.name = 'Date'
            data = data.reset_index()
            records = data[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
            results[ticker_list[0]] = records
        else: # กรณีได้หลาย tickers
            for ticker in ticker_list:
                ticker_data = data.loc[:, (slice(None), ticker)]
                ticker_data.columns = ticker_data.columns.droplevel(1)

                if ticker_data.empty:
                    results[ticker] = {"error": "No data found for this specific ticker."}
                    continue

                df = ticker_data.reset_index()
                records = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
                results[ticker] = records

        return json.dumps(results, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
def calculator(expression: str) -> str:
    """
    ใช้สำหรับคำนวณนิพจน์ทางคณิตศาสตร์ที่ซับซ้อน
    รับ Input เป็นสตริงของสมการ (เช่น "5 + (9 - 4) * 3650") แล้วคืนค่าผลลัพธ์
    """
    print(f"--- Calculator received expression: '{expression}' ---")
    try:
        # ใช้ numexpr.evaluate ซึ่งปลอดภัยกว่า eval() มาก
        result = ne.evaluate(expression).item()
        return json.dumps({"result": result}, ensure_ascii=False)
    except Exception as e:
        print(f"!!! ERROR in calculator tool: {e} !!!")
        return json.dumps({"error": f"Invalid mathematical expression: {str(e)}"})

@mcp.tool()
def get_current_date() -> str:
    """ดึงวันที่และเวลาปัจจุบันในรูปแบบภาษาไทย"""
    try:
        now = datetime.now()
        thai_year = now.year + 543  # ปีพุทธศักราช
        
        # ใช้ helper functions แทน locale เพื่อรองรับภาษาไทยบน Windows
        thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                      "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        thai_days = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]
        
        thai_month = thai_months[now.month - 1]
        thai_day_name = thai_days[now.weekday()]
        
        formatted_date = f"{thai_day_name}ที่ {now.day} {thai_month} {thai_year} เวลา {now.hour:02d}:{now.minute:02d}:{now.second:02d}"
        
        return json.dumps({"current_datetime": formatted_date}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ------------------- FILE TOOLS -------------------

def _get_safe_path(filename: str) -> str | None:
    # ป้องกันการเข้าถึงไฟล์นอก workspace (e.g., "../secret.txt")
    if ".." in filename or "/" in filename or "\\" in filename:
        return None
    return os.path.join(WORKSPACE_DIR, filename)

@mcp.tool()
def write_to_file(filename: str, content: str) -> str:
    """เขียนเนื้อหาลงไฟล์ใน workspace ที่ปลอดภัย. Args: filename (str), content (str)"""
    safe_path = _get_safe_path(filename)
    if not safe_path:
        return json.dumps({"error": "Invalid filename. Path traversal not allowed."})
    
    try:
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return json.dumps({"success": f"File '{filename}' written successfully."})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def read_from_file(filename: str) -> str:
    """อ่านเนื้อหาจากไฟล์ใน workspace ที่ปลอดภัย. Args: filename (str)"""
    safe_path = _get_safe_path(filename)
    if not safe_path:
        return json.dumps({"error": "Invalid filename. Path traversal not allowed."})
    
    try:
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return json.dumps({"content": content})
    except FileNotFoundError:
        return json.dumps({"error": f"File '{filename}' not found."})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ------------------- MAIN EXECUTION BLOCK -------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")