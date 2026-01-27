import sys
import json
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtWebSockets import QWebSocket

class WebSocketClient(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("WebSocket 客户端")
        self.setGeometry(100, 100, 500, 400)

        # 布局设置
        self.layout = QVBoxLayout(self)
        
        # 历史消息区域
        self.history_log = QTextEdit(self)
        self.history_log.setReadOnly(True)  # 设置为只读
        self.history_log.setStyleSheet("background-color: #f1f1f1; color: black;")
        self.layout.addWidget(self.history_log)

        # 实时消息区域
        self.realtime_log = QTextEdit(self)
        self.realtime_log.setReadOnly(True)  # 设置为只读
        self.realtime_log.setStyleSheet("background-color: #333; color: #0f0;")
        self.layout.addWidget(self.realtime_log)

        # 输入框区域
        self.message_input = QLineEdit(self)
        self.layout.addWidget(self.message_input)

        # 连接按钮
        self.connect_button = QPushButton("建立连接", self)
        self.layout.addWidget(self.connect_button)
        self.connect_button.clicked.connect(self.connect_ws)


        # 发送按钮
        self.send_button = QPushButton("发送", self)
        self.layout.addWidget(self.send_button)

        # WebSocket 连接
        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_connected)
        self.ws.textMessageReceived.connect(self.on_message_received)
        self.ws.error.connect(self.on_error)
        self.ws.disconnected.connect(self.on_disconnected)

        # 绑定事件
        self.send_button.clicked.connect(self.send_message)

        # 连接到 WebSocket 服务器
        # self.connect_ws()

    def connect_ws(self):
        """ 连接到 WebSocket 服务器 """
        if self.ws.state() == 3:
            self.append_to_history("[!] 已经连接，无需重复连接")
            return

        self.ws.open(QUrl("ws://localhost:8001/ws"))
        self.append_to_history("[✓] 正在连接 WebSocket...")


    def on_connected(self):
        self.append_to_history("[✓] WebSocket 已连接")
        self.connect_button.setEnabled(False)
        self.connect_button.setText("已连接")


    def on_message_received(self, message):
        """ 接收到消息 """
        message = self.edit_message(message)
        self.append_to_history(f"{message}\n")
        self.realtime_log.setText(f"{message}")  # 实时显示

    def on_error(self, error):
        self.append_to_history(f"[✗] WebSocket 错误: {error}")
        self.connect_button.setEnabled(True)
        self.connect_button.setText("建立连接")


    def on_disconnected(self):
        """ WebSocket 断开连接 """
        self.append_to_history("[×] WebSocket 已断开连接")
        self.connect_button.setEnabled(True)
        self.connect_button.setText("建立连接")

    def send_message(self):
        """ 发送消息 """
        message = self.message_input.text().strip()
        if message:
            if self.ws.state() == 3:
                self.ws.sendTextMessage(message)
                self.realtime_log.append(f"[→] 发送消息: {message}")  # 实时显示
                self.message_input.clear()  # 清空输入框
            else:
                self.append_to_history("[!] WebSocket 未连接")
        else:
            self.append_to_history("[!] 请输入消息")

    def append_to_history(self, message):
        """ 在历史日志中添加消息 """
        self.history_log.append(message)
    
    def edit_message(self, message):
        """ 编辑接收到的消息，将字典中的内容格式化 """
        # 如果 message 是字符串，尝试将其转换为字典
        if isinstance(message, str):
            try:
                message = json.loads(message)  # 解析 JSON 字符串为字典
            except json.JSONDecodeError:
                self.append_to_history("[✗] 无法解析消息")
                return "错误：无法解析消息"
        return f"{message['timestamp']}\n原文:{message['original']}\n翻译结果:{message['translated']}"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebSocketClient()
    window.show()
    sys.exit(app.exec_())
