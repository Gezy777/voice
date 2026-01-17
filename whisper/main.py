import audio_capture
import threading
from fastapi import FastAPI, WebSocket
import uvicorn
import asyncio
import audio_capture
import time

def backend():
    # 启动 FastAPI 应用
    ac = audio_capture.AudioCapture(True, send_in_thread)
    ac.start_capture()

app = FastAPI()

# 用来保存 WebSocket 连接
ws_client = None
loop = None

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global ws_client
    await ws.accept()  # 接受连接
    ws_client = ws     # 保存连接对象
    try:
        while True:
            msg = await ws.receive_text()  # 接收消息
            print(f"收到客户端消息: {msg}")
    except:
        print("客户端断开连接")
        ws_client = None

def send_in_thread(message):
    global ws_client, loop
    if ws_client is None:
        print("⚠️ ws_client 还未连接，消息丢弃", flush=True)
        return

    if loop is None:
        print("❌ loop 为空，无法发送", flush=True)
        return

    print("✅ 准备通过 WebSocket 发送消息", flush=True)

    future = asyncio.run_coroutine_threadsafe(
        ws_client.send_json(message),
        loop
    )

    # 捕获真正的异常（关键！）
    try:
        future.result(timeout=1)
        print("✅ WebSocket 消息发送成功", flush=True)
    except Exception as e:
        print("❌ WebSocket 发送失败:", repr(e), flush=True)

@app.on_event("startup")
def on_startup():
    global loop
    loop = asyncio.get_event_loop()
    time.sleep(2)

    t = threading.Thread(target=backend, daemon=True)
    t.start()
uvicorn.run(app, host="0.0.0.0", port=8001)