import asyncio
import threading
from fastapi import FastAPI, WebSocket
import uvicorn
import audio_capture

def backend(ws_client):
    # 启动 FastAPI 应用
    ac = audio_capture.AudioCapture(True, ws_client)
    ac.start_capture()

class WebSocketHandler:
    def __init__(self, app: FastAPI):
        self.app = app
        self.ws_client = None
        self.loop = None

        # 设置 WebSocket 端点
        self.app.websocket("/ws")(self.websocket_endpoint)

        # 使用 Lifespan 事件处理器替代 on_event
        self.app = app

    async def lifespan(self, app: FastAPI):
        # 启动时设置事件循环
        self.loop = asyncio.get_event_loop()

        # 启动音频记录线程
        t = threading.Thread(target=self.record, daemon=True)
        t.start()

        yield

    def send_in_thread(self, message):
        if self.ws_client is None:
            print("⚠️ ws_client 还未连接，消息丢弃", flush=True)
            return

        if self.loop is None:
            print("❌ loop 为空，无法发送", flush=True)
            return

        print("✅ 准备通过 WebSocket 发送消息", flush=True)

        # 通过 asyncio 事件循环发送消息
        future = asyncio.run_coroutine_threadsafe(
            self.ws_client.send_json(message),
            self.loop
        )

        # 捕获真正的异常（关键！）
        try:
            future.result(timeout=1)
            print("✅ WebSocket 消息发送成功", flush=True)
        except Exception as e:
            print("❌ WebSocket 发送失败:", repr(e), flush=True)


    def record(self):
        # 在这里添加音频录制逻辑
        backend(self.ws_client)

    async def websocket_endpoint(self, ws: WebSocket):
        self.ws_client = ws  # 保存 WebSocket 连接对象
        await ws.accept()  # 接受 WebSocket 连接

        try:
            while True:
                msg = await ws.receive_text()  # 接收消息
                print(f"收到客户端消息: {msg}")
        except:
            print("客户端断开连接")



# 初始化 FastAPI 应用
app = FastAPI()

# 创建 WebSocketHandler 实例并将其传递给 FastAPI 应用
ws_handler = WebSocketHandler(app)

uvicorn.run(app, host="0.0.0.0", port=8001)
