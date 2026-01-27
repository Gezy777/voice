import pyaudio

# 设定的说话间隔时间
Internal = 8000

# 指定音频转文字模型
# 可选模型有：tiny, base, small, medium, large
VoiceToWordModel = 'tiny'

# 源语言
SourceLanguage = "en"

# 目的语言
TargetLanguage = "zh"

# 监听的音频设备
# windows一般是13，linux一般是pulse
# windows一般选择第二个CABLE OUTPUT设备
InputDeviceIndex = 5

# Whisper模型是否运行在本地
# False表示运行在服务器上，在服务器上运行server.py文件，同时修改下方SERVER参数
IS_LOCAL = True

# 指定翻译服务器
SERVER = "http://192.168.186.31:8000/translate"

# 配置录音参数
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

PROXY = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
}

IS_LOCAL = False  # 是否在本地运行翻译服务
FileName = "voice_transcription.txt"  # 保存转录文本的文件名

