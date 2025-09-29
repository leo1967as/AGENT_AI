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
import numexpr as ne
import pandas as pd
import yfinance as yf
import subprocess

# --- GUI Control Imports (HIGHLY DANGEROUS - USE WITH EXTREME CAUTION) ---
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("WARNING: pyautogui not available. GUI control tools will be disabled.")

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

# ------------------- NEW COMMAND CENTER TOOLS -------------------

@mcp.tool()
def list_all_memories() -> str:
    """
    ดึงข้อมูล "ความทรงจำ" ทั้งหมดที่ถูกบันทึกไว้ในฐานข้อมูล Vector DB
    คืนค่าเป็นลิสต์ของความทรงจำทั้งหมด
    """
    print("--- Listing all memories... ---")
    try:
        # .get() โดยไม่ใส่พารามิเตอร์ จะดึงข้อมูลทั้งหมดใน collection
        all_memories = memory_collection.get()
        # จัดรูปแบบให้อยู่ในโครงสร้างที่ชัดเจน
        formatted_memories = [
            {"id": mem_id, "content": content, "metadata": meta}
            for mem_id, content, meta in zip(all_memories['ids'], all_memories['documents'], all_memories['metadatas'])
        ]
        return json.dumps({"memories": formatted_memories}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to list memories: {str(e)}"})

@mcp.tool()
def list_workspace_files() -> str:
    """
    แสดงรายการไฟล์ทั้งหมดที่อยู่ในโฟลเดอร์ 'workspace'
    คืนค่าเป็นลิสต์ของไฟล์พร้อมรายละเอียด
    """
    print("--- Listing workspace files... ---")
    try:
        files_details = []
        for filename in os.listdir(WORKSPACE_DIR):
            path = os.path.join(WORKSPACE_DIR, filename)
            if os.path.isfile(path):
                file_stat = os.stat(path)
                files_details.append({
                    "filename": filename,
                    "size_kb": f"{file_stat.st_size / 1024:.2f} KB",
                    "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })
        return json.dumps({"files": files_details}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Failed to list workspace files: {str(e)}"})

# ------------------- EXISTING TOOLS -------------------

@mcp.tool()
def browse_url(url: str) -> str:
    """
    เข้าไปอ่านและดึง "เนื้อหาหลักที่สะอาด" ทั้งหมดจาก URL ที่ให้มาโดยตรง
    เครื่องมือนี้คือหัวใจของการค้นคว้าเชิงลึก
    """
    print(f"--- Server browsing URL with Simple Method: {url} ---")
    try:
        # สำหรับ GitHub raw content URL หรือ GitHub blob URL
        if 'raw.githubusercontent.com' in url or ('github.com' in url and '/blob/' in url):
            if 'github.com' in url:
                url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')

            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            text = response.text

        else: # สำหรับเว็บทั่วไป
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                element.decompose()
            text = soup.get_text(separator='\n', strip=True)

        if not text:
            return json.dumps({"error": "Could not extract text content from the URL."}, ensure_ascii=False)

        max_length = 20000 # เพิ่มความยาวสำหรับงานวิจัยเชิงลึก
        truncated_text = text[:max_length]

        print(f"--- Extracted text length: {len(truncated_text)} characters. ---")
        return json.dumps({"url": url, "content": truncated_text}, ensure_ascii=False)

    except Exception as e:
        print(f"!!! ERROR in browse_url tool: {e} !!!")
        return json.dumps({"error": f"An exception occurred while browsing the URL: {str(e)}"}, ensure_ascii=False)


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

# ------------------- REAL GUI CONTROL TOOLS (EXTREME CAUTION REQUIRED) -------------------

# Safety flag - GUI control is DISABLED by default for security
GUI_CONTROL_ENABLED = os.getenv("ENABLE_GUI_CONTROL", "true").lower() == "true"

if not GUI_CONTROL_ENABLED:
    print("WARNING: GUI control tools are DISABLED. Set ENABLE_GUI_CONTROL=true to enable (HIGH RISK)")

@mcp.tool()
def see_screen() -> str:
    """
    วิเคราะห์หน้าจอปัจจุบันและอธิบายองค์ประกอบที่เห็น
    ใช้สำหรับการวางแผนการทำงาน GUI
    """
    if not GUI_CONTROL_ENABLED:
        return json.dumps({"error": "GUI control is disabled for security reasons. Enable with ENABLE_GUI_CONTROL=true"})

    if not PYAUTOGUI_AVAILABLE:
        return json.dumps({"error": "pyautogui is not available"})

    print("--- Analyzing screen... ---")
    try:
        # ใช้ pyautogui เพื่อ capture screen และ analyze
        screenshot = pyautogui.screenshot()
        screen_width, screen_height = screenshot.size

        # ข้อมูลจำลองสำหรับ demonstration (ในโลกจริงควรใช้ computer vision)
        screen_data = {
            "screen_resolution": f"{screen_width}x{screen_height}",
            "current_mouse_position": pyautogui.position(),
            "elements": [
                {
                    "description": "Desktop screen with various windows and icons",
                    "bbox": [0, 0, screen_width, screen_height]
                }
            ]
        }
        return json.dumps({"screen_analysis": screen_data}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Failed to analyze screen: {str(e)}"}, ensure_ascii=False)

@mcp.tool()
def mouse_move(x: int, y: int) -> str:
    """ย้ายเคอร์เซอร์เมาส์ไปยังพิกัด (x, y) บนหน้าจอ"""
    if not GUI_CONTROL_ENABLED:
        return json.dumps({"error": "GUI control is disabled for security reasons"})

    if not PYAUTOGUI_AVAILABLE:
        return json.dumps({"error": "pyautogui is not available"})

    try:
        pyautogui.moveTo(x, y, duration=0.5)
        return json.dumps({"status": "success", "message": f"Mouse moved to ({x}, {y})"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def mouse_click(x: int, y: int, button: str = 'left') -> str:
    """คลิกเมาส์ที่พิกัด (x, y) บนหน้าจอ"""
    if not GUI_CONTROL_ENABLED:
        return json.dumps({"error": "GUI control is disabled for security reasons"})

    if not PYAUTOGUI_AVAILABLE:
        return json.dumps({"error": "pyautogui is not available"})

    try:
        pyautogui.click(x, y, button=button)
        return json.dumps({"status": "success", "message": f"Mouse {button}-clicked at ({x}, {y})"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def keyboard_type(text: str) -> str:
    """พิมพ์ข้อความด้วยคีย์บอร์ด"""
    if not GUI_CONTROL_ENABLED:
        return json.dumps({"error": "GUI control is disabled for security reasons"})

    if not PYAUTOGUI_AVAILABLE:
        return json.dumps({"error": "pyautogui is not available"})

    try:
        pyautogui.write(text, interval=0.05)
        return json.dumps({"status": "success", "message": f"Typed: '{text}'"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def execute_shell_command(command: str) -> str:
    """รันคำสั่งใน command line / terminal"""
    if not GUI_CONTROL_ENABLED:
        return json.dumps({"error": "GUI control is disabled for security reasons"})

    try:
        # อนุญาตเฉพาะคำสั่งที่ปลอดภัย
        SAFE_COMMANDS = ['ls', 'pwd', 'whoami', 'date', 'echo']
        command_base = command.split()[0]

        if command_base not in SAFE_COMMANDS:
            return json.dumps({"error": f"Command '{command_base}' is not in the allowed list for security"})

        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.dumps({"output": result.stdout or "Command executed successfully"})
        else:
            return json.dumps({"error": result.stderr})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ------------------- MAIN EXECUTION BLOCK -------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")