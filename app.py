import chainlit as cl
from agent import AdvancedWebAgent

@cl.on_chat_start
async def start():
    """
    ฟังก์ชันนี้จะถูกเรียกเมื่อผู้ใช้เริ่มแชทใหม่
    เพื่อสร้างและเตรียม Agent สำหรับ session นั้นๆ
    """
    agent_instance = AdvancedWebAgent()
    cl.user_session.set("agent", agent_instance)
    await cl.Message(
        content="สวัสดี! Agent พร้อมแล้ว – ถามอะไรได้เลย (e.g. 'ราคาหุ้น NVDA ย้อนหลัง 5 วัน')\n\nฉันจะแสดงขั้นตอนการทำงานให้ดู และสรุปคำตอบสุดท้ายให้ครับ 🚀"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """
    ฟังก์ชันนี้จะทำงานทุกครั้งที่ผู้ใช้ส่งข้อความเข้ามา
    """
    agent = cl.user_session.get("agent")

    # --- 💡 จุดแก้ไขที่สำคัญ ---

    # 1. ตั้งค่า Callback handler ให้ "ไม่ต้อง" stream คำตอบสุดท้ายโดยอัตโนมัติ
    #    หน้าที่ของมันตอนนี้คือแสดงแค่ Steps (Thought, Action, Observation) เท่านั้น
    callbacks = [cl.LangchainCallbackHandler(stream_final_answer=False)]

    # 2. รัน Agent และ "รอจนกว่าจะได้ผลลัพธ์สุดท้าย" กลับมาเป็น dictionary
    #    เราจะเก็บผลลัพธ์ไว้ในตัวแปร response
    response = await agent.agent_executor.ainvoke(
        {"input": message.content},
        config={"callbacks": callbacks}
    )

    # 3. ดึงคำตอบสุดท้ายจาก key 'output' ใน dictionary ของ response
    final_answer = response.get("output", "ขออภัย, ไม่สามารถหาคำตอบสุดท้ายได้")

    # 4. "ส่งคำตอบสุดท้าย" ที่เราดึงออกมา ไปเป็นข้อความใหม่ในแชทด้วยตัวเอง
    await cl.Message(content=final_answer).send()