import pyaudio
import queue

input_device_index = -1
# 配置录音参数
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

import torch
torch.hub._validate_not_a_forked_repo = lambda a, b, c: True
vad_model, funcs = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True
        )
detect_speech = funcs[0]

import whisper
import opencc
import numpy as np
cc = opencc.OpenCC('t2s')
model = whisper.load_model("base")
options = whisper.DecodingOptions(language='zh')

def get_audio_text(audio_data):
    audio = whisper.pad_or_trim(audio_data)
    mel = whisper.log_mel_spectrogram(audio).to(model.device)
    result = whisper.decode(model, mel, options)
    print(cc.convert(result.text))


# 创建队列用于存储录音数据
q = queue.Queue()

# 语音活动检测函数 
# 合并相近的语音片段
def detect_voice_activity(audio):
    speeches = detect_speech(
        audio, vad_model, sampling_rate=16000
    ) # 检测语音活动
    print(speeches,len(audio)) # 打印检测到的语音片段和音频长度

    if len(speeches) == 2: # 如果检测到两段语音，检查它们是否相近
        if speeches[1]['start'] - speeches[0]['end'] < 8000:
            return [{"start": speeches[0]['start'], "end": speeches[1]['end']}]
    return speeches

def recording_callback(in_data, frame_count, time_info, status):
    # 将录制的数据存入队列
    q.put(in_data)
    return (in_data, pyaudio.paContinue)

LastEndD = 0 # 上一段检测到的语音的结束位置在临时数据中的位置
def record():
    p = pyaudio.PyAudio()
    # 检测系统扬声器
    # 检测系统中所有可以监听的音频设备
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        print(dev)
        # if '立体声混音' in dev['name']:
        #     input_device_index = i
        #     break
    # 指定监听的音频源，监听的是系统音频输出
    input_device_index = 2
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

    while True:
        # 从队列中获取录音数据
        while len(data) < 2 * RATE * 2: # 确保获取到足够1秒的音频数据
            data += q.get() # 获取队列中的数据
        # 将获取到的字节数据转换为numpy数组并归一化
        temp = np.concatenate((temp, np.frombuffer(data, np.int16).flatten().astype(np.float32) / 32768.0), axis=0)
        
        speeches = detect_voice_activity(temp) # 检测语音活动
        
        if len(speeches) == 0: # 没有检测到语音
            if Recording: # 如果之前处于录音状态
                Recording = False # 停止录音
                alldata = np.concatenate((alldata,temp), axis=0) # 合并录音数据
                get_audio_text(alldata) # 处理录音数据

            # 重置变量
            alldata = np.array([],np.float32)
            data = b''
            temp = np.array([],np.float32)
            LastEndD = 0

        elif len(speeches) == 1: # 检测到一段语音
            Recording = True # 继续录音
            start = int(speeches[0]['start']) 
            end = int(speeches[0]['end'])

            if start + LastEndD < 8000:
                # 这是一句话
                alldata = np.concatenate((alldata,temp[:end]), axis=0)
                temp = temp[end:]
                get_audio_text(alldata)
                data = b''
                LastEndD = len(temp)
            else:
                # 这是两句话
                alldata = temp[:end]
                temp = temp[end:]
                get_audio_text(alldata)
                data = b''
                LastEndD = len(temp) - end
        elif len(speeches) == 2:
            Recording = True
            temp = alldata[int(speeches[0]['end']):]
            alldata = alldata[:int(speeches[0]['end'])]
            data = b''
            get_audio_text(alldata)
            alldata = np.array([],np.float32)
            LastEndD = 0

record()