import chainlit as cl
from agent import AdvancedWebAgent
import json
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# (import sync functions ยังคงจำเป็นสำหรับ action callbacks)
from agent import sync_list_all_memories, sync_list_workspace_files


@cl.on_chat_start
async def start():
    """
    ฟังก์ชันนี้จะถูกเรียกเมื่อผู้ใช้เริ่มแชทใหม่
    """
    # สร้าง Agent instance
    agent_instance = AdvancedWebAgent()

    # สร้าง Agent ที่มีความจำที่ถูกต้อง
    agent_with_memory = RunnableWithMessageHistory(
        agent_instance.agent_executor,
        # ใช้ cl.user_session.get("chat_history") เพื่อให้ Chainlit จัดการ memory ให้
        lambda session_id: cl.user_session.get("chat_history"),
        input_messages_key="input",
        history_messages_key="chat_history",
    )
    
    # บันทึกประวัติแชทและ Agent ไว้ใน session
    cl.user_session.set("chat_history", ChatMessageHistory())
    cl.user_session.set("agent_with_memory", agent_with_memory)

    # --- 💡 จุดแก้ไขที่สำคัญ: เราลบ Avatar และ Persona ทั้งหมด ---
    # เราจะส่งข้อความต้อนรับพร้อมปุ่มและคำแนะนำต่างๆ เพื่อให้ใช้งานง่ายขึ้น

    actions = [
        cl.Action(name="view_memories", payload={}, label="🧠 ดูความทรงจำทั้งหมด"),
        cl.Action(name="explore_workspace", payload={}, label="📂 สำรวจพื้นที่ทำงาน"),
        cl.Action(name="help", payload={}, label="❓ ดูความสามารถและคำสั่ง")
    ]

    await cl.Message(
        content="""**สวัสดีครับ ผม Cipher V3**

ผู้ช่วย AI ส่วนตัวของคุณ พร้อมสำหรับภารกิจใหม่แล้วครับ!

### 💡 คำแนะนำการใช้งาน:
- **พิมพ์ข้อความธรรมดา:** ถามคำถามหรือให้งานอะไรก็ได้ ผมจะช่วยเหลือคุณ
- **ใช้ปุ่มพิเศษ:** กดปุ่มด้านล่างเพื่อเข้าถึงฟีเจอร์ต่างๆ ได้ทันที
- **คำสั่งพิเศษ:** พิมพ์ `"help"` เพื่อดูความสามารถทั้งหมดและคำสั่งเพิ่มเติม

ลองเริ่มต้นด้วยการกดปุ่มด้านล่าง หรือพิมพ์คำถามแรกของคุณได้เลยครับ! 🚀""",
        actions=actions
    ).send()


# --- Action Callbacks ยังคงจำเป็นสำหรับ Help Command ---
@cl.action_callback("view_memories")
async def on_action_view_memories(action: cl.Action):
    await cl.Message(content="กำลังดึงข้อมูลความทรงจำทั้งหมด...").send()
    
    response_str = sync_list_all_memories()
    response_data = json.loads(response_str)

    if "error" in response_data:
        await cl.ErrorMessage(content=f"Error: {response_data['error']}").send()
        return

    memories = response_data.get("memories", [])
    if not memories:
        await cl.Message(content="ยังไม่มีความทรงจำใดๆ ถูกบันทึกไว้ครับ").send()
        return

    formatted_text = "### 🧠 All Saved Memories\n\n"
    for mem in memories:
        formatted_text += f"**ID:** `{mem['id']}`\n"
        formatted_text += f"**Content:**\n```\n{mem['content']}\n```\n"
        formatted_text += f"**Metadata:** `{json.dumps(mem['metadata'])}`\n---\n"

    await cl.Message(content=formatted_text).send()


@cl.action_callback("explore_workspace")
async def on_action_explore_workspace(action: cl.Action):
    await cl.Message(content="กำลังสำรวจพื้นที่ทำงาน...").send()
    
    response_str = sync_list_workspace_files()
    response_data = json.loads(response_str)

    if "error" in response_data:
        await cl.ErrorMessage(content=f"Error: {response_data['error']}").send()
        return

    files = response_data.get("files", [])
    if not files:
        await cl.Message(content="โฟลเดอร์ `workspace` ยังว่างอยู่ครับ").send()
        return

    table_header = "| Filename | Size (KB) | Last Modified |\n|---|---|---|\n"
    table_rows = [
        f"| `{f['filename']}` | {f['size_kb']} | {f['last_modified']} |"
        for f in files
    ]

    formatted_text = "### 📂 Files in Workspace\n\n" + table_header + "\n".join(table_rows)
    formatted_text += "\n\nคุณสามารถใช้คำสั่ง `read_from_file('filename')` เพื่ออ่านเนื้อหาของไฟล์เหล่านี้ได้ครับ"

    await cl.Message(content=formatted_text).send()


@cl.action_callback("help")
async def on_action_help(action: cl.Action):
    # --- ใช้โค้ดเดียวกันกับ on_message เมื่อพิมพ์ help ---
    actions = [
        cl.Action(name="view_memories", payload={}, label="🧠 ดูความทงจำทั้งหมด"),
        cl.Action(name="explore_workspace", payload={}, label="📂 สำรวจพื้นที่ทำงาน")
    ]

    await cl.Message(
        content="""## ความสามารถของผม (Cipher V3)

ผมเป็นผู้ช่วย AI ที่มีความสามารถหลากหลาย พร้อมช่วยเหลือคุณในงานต่างๆ ครับ:

*   **🔎 นักวิจัย:** ค้นหา, อ่าน, และสรุปข้อมูลที่ซับซ้อนจากอินเทอร์เน็ตให้คุณได้
*   **🧠 ผู้มีความจำ:** สามารถจดจำและเรียกคืนข้อมูลสำคัญที่เราเคยคุยกันได้
*   **✍️ นักเขียนและนักอ่าน:** ทำงานกับไฟล์ `.txt`, `.pdf`, และ `.docx`
*   **🔢 นักคำนวณ:** แก้โจทย์ปัญหาทางคณิตศาสตร์ได้อย่างแม่นยำ
*   **🗣️ นักสื่อสาร:** หากผมไม่แน่ใจ ผมจะถามคุณกลับเพื่อขอข้อมูลเพิ่มเติม

คุณสามารถใช้ปุ่มพิเศษด้านล่างนี้ได้เลยครับ!
""",
        actions=actions
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """
    ฟังก์ชันนี้จะทำงานทุกครั้งที่ผู้ใช้ส่งข้อความแชทเข้ามา
    """
    help_keywords = ["help", "ทำอะไรได้บ้าง", "ช่วยด้วย", "คำสั่ง"]
    if message.content.lower().strip() in help_keywords:
        # --- 💡 แก้ไข Help Command ให้มีปุ่มที่ทำงานได้ถูกต้อง ---
        actions = [
            cl.Action(name="view_memories", payload={}, label="🧠 ดูความทงจำทั้งหมด"),
            cl.Action(name="explore_workspace", payload={}, label="📂 สำรวจพื้นที่ทำงาน")
        ]
    
        await cl.Message(
            content="""## ความสามารถของผม (Cipher V3)
    
ผมเป็นผู้ช่วย AI ที่มีความสามารถหลากหลาย พร้อมช่วยเหลือคุณในงานต่างๆ ครับ:

*   **🔎 นักวิจัย:** ค้นหา, อ่าน, และสรุปข้อมูลที่ซับซ้อนจากอินเทอร์เน็ตให้คุณได้
*   **🧠 ผู้มีความจำ:** สามารถจดจำและเรียกคืนข้อมูลสำคัญที่เราเคยคุยกันได้
*   **✍️ นักเขียนและนักอ่าน:** ทำงานกับไฟล์ `.txt`, `.pdf`, และ `.docx`
*   **🔢 นักคำนวณ:** แก้โจทย์ปัญหาทางคณิตศาสตร์ได้อย่างแม่นยำ
*   **🗣️ นักสื่อสาร:** หากผมไม่แน่ใจ ผมจะถามคุณกลับเพื่อขอข้อมูลเพิ่มเติม

คุณสามารถใช้ปุ่มพิเศษด้านล่างนี้ได้เลยครับ!
""",
            actions=actions
        ).send()
        return

    # --- โค้ดส่วนรัน Agent (ถูกต้องและทรงพลังเหมือนเดิม) ---
    agent_with_memory = cl.user_session.get("agent_with_memory")
    session_id = cl.user_session.get("id")

    callbacks = [cl.LangchainCallbackHandler(stream_final_answer=False)]

    async with cl.Step(name="Cipher's Thought Process", type="chain"):
        response = await agent_with_memory.ainvoke(
            {"input": message.content},
            config={"callbacks": callbacks, "configurable": {"session_id": session_id}}
        )

    final_answer = response.get("output", "ขออภัย, ผมไม่สามารถหาคำตอบได้ในขณะนี้")
    await cl.Message(content=final_answer).send()