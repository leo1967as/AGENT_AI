# Cipher AI Assistant

AI Assistant ที่ทรงพลังพร้อม MCP (Model Context Protocol) server สำหรับการทำงานต่างๆ ในชีวิตประจำวัน

## Features

### 🔍 Web Tools
- **Web Search**: ค้นหาข้อมูลจากเว็บด้วย DuckDuckGo
- **Browse URL**: อ่านและสรุปเนื้อหาจาก URL ใดๆ

### 📊 Finance Tools
- **Stock Price**: ดึงข้อมูลราคาหุ้นย้อนหลัง (รองรับหลายหุ้นพร้อมกัน)
- **Calculator**: คำนวณทางคณิตศาสตร์อย่างปลอดภัย

### 📁 File Management
- **Read File**: อ่านเนื้อหาจากไฟล์ใน workspace
- **Write File**: เขียนข้อมูลลงไฟล์

### ⏰ Utilities
- **Current Date**: รับวันที่และเวลาปัจจุบัน
- **Ask User**: ถามคำถามกลับไปยังผู้ใช้ (Human-in-the-Loop)

### 🤖 AI Features
- Plan-Execute-Critique-Refine workflow
- Parallel tool calling
- Error handling ที่แข็งแกร่ง
- รองรับภาษาไทยอย่างสมบูรณ์

## Installation

1. Clone repository:
```bash
git clone <repository-url>
cd cipher-ai-assistant
```

2. Create virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# หรือ source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# แก้ไข .env ใส่ API keys ของคุณ
```

## Environment Variables

สร้างไฟล์ `.env` และใส่ค่าเหล่านี้:

- `OPENROUTER_API_KEY`: API key จาก OpenRouter (จำเป็น)
- `OPENROUTER_MODEL`: ชื่อโมเดล (ค่าเริ่มต้น: google/gemini-2.0-flash-001)
- `BRAVESEARCH_API_KEY`: API key สำหรับ Brave Search (จำเป็นสำหรับ web search)

## Usage

### เริ่ม MCP Server
```bash
python server.py
```

### รัน Chainlit UI (แนะนำ)
```bash
chainlit run app.py
```

### หรือรัน Streamlit UI (alternative)
```bash
streamlit run streamlit_app.py
```

### ทดสอบ Agent โดยตรง
```bash
python agent.py
```

## Architecture

- **server.py**: MCP server ที่มี tools ต่างๆ
- **agent.py**: Cipher AI Assistant พร้อม LangChain
- **app.py**: Chainlit UI สำหรับการใช้งาน
- **requirements.txt**: Python dependencies

## License

MIT License