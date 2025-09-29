# ขั้นที่ 1: เลือก Base Image ที่มี Python 3.11
FROM python:3.11-slim

# --- 💡 จุดแก้ไขที่สำคัญที่สุด ---
# ขั้นที่ 2: ติดตั้ง "ชิ้นส่วนพื้นฐาน" ของระบบปฏิบัติการที่จำเป็น
# ก่อนที่จะทำอะไรเกี่ยวกับ Python เลย
# apt-get คือคำสั่งจัดการ package ของ Debian/Ubuntu (ซึ่งเป็นพื้นฐานของ Python Image)
# gcc คือ C compiler, build-essential คือชุดเครื่องมือพื้นฐานสำหรับการคอมไพล์
# libsqlite3-dev คือไลบรารีของ SQLite ที่ ChromaDB ต้องการ
RUN apt-get update && apt-get install -y gcc build-essential libsqlite3-dev

# ตั้งค่าให้ Python Log แสดงผลทันที (ดีสำหรับการดีบัก)
ENV PYTHONUNBUFFERED 1

# กำหนด Working Directory
WORKDIR /app

# คัดลอกและติดตั้งไลบรารี Python (เหมือนเดิม)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดโปรเจกต์ทั้งหมดของเรา
COPY . .

# เปิดพอร์ต 8000
EXPOSE 8000

# คำสั่งสุดท้ายที่จะรันแอป
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]