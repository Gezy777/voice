import pyaudio
import queue
import config

# 选择监听的音频设备
input_device_index = -1

# 配置录音参数
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# 设定的说话间隔时间
Internal = config.Internal

# 指定音频转文字模型
VoiceToWordModel = config.VoiceToWordModel

# 源语言
SourceLanguage = config.SourceLanguage

# 目的语言
TargetLanguage = config.TargetLanguage

# 载入语音活动检测模型
import torch
torch.hub._validate_not_a_forked_repo = lambda a, b, c: True
vad_model, funcs = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True
        )
detect_speech = funcs[0]
# print(torch.cuda.is_available())   # True 表示 GPU 可用
# if torch.cuda.is_available():
#     device = torch.device("cpu")
#     print("使用 GPU:", torch.cuda.get_device_name(0))
# else:
#     device = torch.device("cpu")
#     print("使用 CPU")

# 调用翻译API
import requests
def mymemory_translate(text, source=SourceLanguage, target=TargetLanguage):
    url = "https://api.mymemory.translated.net/get"
    params = {
        "q": text,
        "langpair": f"{source}|{target}"
    }
    r = requests.get(url, params=params)
    return r.json()["responseData"]["translatedText"]


import whisper
import opencc
import numpy as np
import time
cc = opencc.OpenCC('t2s')
model = whisper.load_model(VoiceToWordModel)
# model = model.to(device)
options = whisper.DecodingOptions(language=None, task="transcribe", fp16=torch.cuda.is_available())

# 翻译音频并输出中文
def get_audio_text(audio_data):
    start_time = time.time()
    audio = whisper.pad_or_trim(audio_data)
    mel = whisper.log_mel_spectrogram(audio).to(model.device)
    result = whisper.decode(model, mel, options)
    end_time = time.time()
    print("原文:" + result.text)
    print("翻译结果:" + cc.convert(mymemory_translate(result.text)))
    print(f"翻译耗时:{end_time - start_time:.3f}s")


# 创建队列用于存储录音数据
q = queue.Queue()

# 语音活动检测函数 
# 合并相近的语音片段
def detect_voice_activity(audio):
    speeches = detect_speech(
        audio, vad_model, sampling_rate=16000
    ) # 检测语音活动
    print(speeches,len(audio)) # 打印检测到的语音片段和音频长度

    # if len(speeches) == 2: # 如果检测到两段语音，检查它们是否相近
    #     if speeches[1]['start'] - speeches[0]['end'] < 8000:
    #         return [{"start": speeches[0]['start'], "end": speeches[1]['end']}]
    return speeches

def recording_callback(in_data, frame_count, time_info, status):
    # 将录制的数据存入队列
    q.put(in_data)
    return (in_data, pyaudio.paContinue)

def record():
    p = pyaudio.PyAudio()
    # 检测系统扬声器
    # 检测系统中所有可以监听的音频设备
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        # print(info)
        if "CABLE" in info["name"] and info["maxInputChannels"] > 0:
            print("USE THIS:", i, info["name"])

    # 指定监听的音频源，监听的是系统音频输出
    input_device_index = 3
    # 获取音频流
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index = input_device_index,
                    frames_per_buffer=CHUNK,
                    # 回调函数
                    stream_callback=recording_callback)
    # 开始录音
    stream.start_stream()

    # 定义并初始化变量
    alldata = np.array([],np.float32) # 存储完整的录音数据
    temp = np.array([],np.float32) # 存储临时的录音数据
    data = b'' # 存储从队列中获取的字节数据
    Recording = False # 录音状态标志
    LastEnd = 0 # 上一段录音的结束位

    while True:
        # 从队列中获取录音数据
        while len(data) < 2 * RATE * 2: # 确保获取到足够1秒的音频数据
            data += q.get() # 获取队列中的数据
        # 将获取到的字节数据转换为numpy数组并归一化
        temp = np.concatenate((temp, np.frombuffer(data, np.int16).flatten().astype(np.float32) / 32768.0), axis=0)
        
        speeches = detect_voice_activity(temp) # 检测语音活动
        
        if len(speeches) == 0: # 没有检测到语音
            if Recording:
                Recording = False
                if len(alldata) > 0:
                    get_audio_text(alldata) # 处理录音数据

            # 重置变量
            alldata = np.array([],np.float32)
            data = b''
            temp = np.array([],np.float32)

        elif len(speeches) == 1: # 检测到一段语音
            Recording = True
            start = int(speeches[0]['start']) 
            end = int(speeches[0]['end'])

            if start + LastEnd < Internal:
                # 这是一句话
                alldata = np.concatenate((alldata,temp[start:end]), axis=0)
                LastEnd = len(temp[end:])
                # get_audio_text(alldata)
                # 重置变量
                data = b''
                temp = np.array([],np.float32)
            else:
                # 这是两句话
                # 先处理前一句话
                if len(alldata) > 0:
                    get_audio_text(alldata)
                
                alldata = temp[start:end]
                LastEnd = len(temp[end:])

                # 重置变量
                data = b''
                temp = np.array([],np.float32)

        elif len(speeches) == 2:
            Recording = True
            start = int(speeches[0]['start']) 
            end = int(speeches[0]['end'])
            start2 = int(speeches[1]['start'])
            end2 = int(speeches[1]['end'])

            # 获取并添加第一句话之后再处理
            if start + LastEnd < Internal:
                # 这是一句话
                alldata = np.concatenate((alldata,temp[start:end]), axis=0)
                if start2 - end < Internal:
                    alldata = np.concatenate((alldata, temp[start2:end2]), axis=0)
                    LastEnd = len(temp[end2:])
                    
                    # 重置变量
                    data = b''
                    temp = np.array([],np.float32)
                else:
                    get_audio_text(alldata)
                    alldata = temp[start2:end2]
                    LastEnd = len(temp[end2:])

                    # 重置变量
                    data = b''
                    temp = np.array([],np.float32)

            else:
                # 这是两句话
                if len(alldata) > 0:
                    get_audio_text(alldata)
                alldata = temp[start:end]
                if start2 - end < Internal:
                    alldata = np.concatenate((alldata, temp[start2:end2]), axis=0)
                    LastEnd = len(temp[end2:])
                    
                    # 重置变量
                    data = b''
                    temp = np.array([],np.float32)
                else:
                    get_audio_text(alldata)
                    alldata = temp[start2:end2]
                    LastEnd = len(temp[end2:])

                    # 重置变量
                    data = b''
                    temp = np.array([],np.float32)

record()