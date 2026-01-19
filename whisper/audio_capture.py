import config
import pyaudio
import queue
import numpy as np
import torch
import voice_to_text

def get_detect_speech():
    torch.hub._validate_not_a_forked_repo = lambda a, b, c: True
    vad_model, funcs = torch.hub.load(
                repo_or_dir="../silero-vad", model="silero_vad", source="local"
            )
    return vad_model, funcs[0]

class AudioCapture:
    def __init__(self, is_local: bool, f):
        self.p = pyaudio.PyAudio()
        self.q = queue.Queue()
        self.stream = None
        self.data = b''
        self.alldata = np.array([],np.float32)  # 存储完整的录音数据
        self.temp = np.array([],np.float32)     # 存储临时的录音数据
        self.Recording = False                  # 录音状态标志
        self.LastEnd = 0                        # 上一段录音的结束位
        self.i = 1                              # 第几句话
        self.vad_model, self.detect_speech = get_detect_speech()
        self.is_local = is_local
        self.voiceTotext = voice_to_text.VoiceToText(is_local)
        self.f = f

    def start_capture(self):
        self.stream = self.p.open(
            format=config.FORMAT,
            channels=config.CHANNELS,
            rate=config.RATE,
            input=True,
            input_device_index = config.InputDeviceIndex,
            frames_per_buffer=config.CHUNK,
            stream_callback=self.recording_callback
        )
        self.stream.start_stream()
        while True:
            # 从队列中获取录音数据
            # 确保获取到足够1秒的音频数据
            while len(self.data) < 2 * config.RATE * 2: 
                # 获取队列中的数据
                self.data += self.q.get() 
            
            # 将获取到的字节数据转换为numpy数组并归一化
            self.temp = np.concatenate((self.temp, np.frombuffer(self.data, np.int16).flatten().astype(np.float32) / 32768.0), axis=0)
            
            # 检测语音活动
            speeches = self.detect_speech(self.temp, self.vad_model, sampling_rate=config.RATE)
            
            # 打印检测到的语音片段和音频长度
            print(speeches, len(self.temp)) 
            
            # 没有检测到语音
            if len(speeches) == 0: 
                if self.Recording:
                    self.Recording = False
                    if len(self.alldata) > 0:
                        print(f"第{self.i}句话翻译完成")
                        self.i += 1
                        if self.is_local: 
                            self.f(self.voiceTotext.recognize_audio_local(self.alldata))
                        else:
                            self.f(self.voiceTotext.recognize_audio_server(self.alldata))
                # 重置变量
                self.alldata = np.array([], np.float32)

            elif len(speeches) == 1: # 检测到一段语音
                self.Recording = True
                start, end = int(speeches[0]['start']), int(speeches[0]['end'])
                self.joint_sentences(start, end, start + self.LastEnd < config.Internal)

            elif len(speeches) == 2:
                self.Recording = True
                start, end = int(speeches[0]['start']), int(speeches[0]['end'])
                start2, end2 = int(speeches[1]['start']), int(speeches[1]['end'])

                # 获取并添加第一句话之后再处理
                if start + self.LastEnd < config.Internal:
                    # 这是一句话
                    self.alldata = np.concatenate((self.alldata, self.temp[start:end]), axis=0)
                    self.joint_sentences(start2, end2, start2 - end < config.Internal)

                else:
                    # 这是两句话
                    if len(self.alldata) > 0:
                        print(f"第{self.i}句话翻译完成")
                        self.i += 1
                        if self.is_local: 
                            self.f(self.voiceTotext.recognize_audio_local(self.alldata))
                        else:
                            self.f(self.voiceTotext.recognize_audio_server(self.alldata))
                    self.alldata = self.temp[start:end]
                    self.joint_sentences(start2, end2, start2 - end < config.Internal)
            
            # 清空data和temp，继续录音
            self.data = b''
            self.temp = np.array([],np.float32)


    def recording_callback(self, in_data, frame_count, time_info, status):
        self.q.put(in_data)
        return (None, pyaudio.paContinue)
    
    def joint_sentences(self, start, end, isJoint):
        if isJoint:
            # 这是一句话
            self.alldata = np.concatenate((self.alldata, self.temp[start:end]), axis=0)

        else:
            # 这是两句话
            # 先处理前一句话
            if len(self.alldata) > 0:
                print(f"第{self.i}句话翻译完成")
                self.i += 1
                if self.is_local: 
                    self.f(self.voiceTotext.recognize_audio_local(self.alldata))
                else:
                    self.f(self.voiceTotext.recognize_audio_server(self.alldata))
            self.alldata = self.temp[start:end]

        print(f"这是第{self.i}句话")
        self.LastEnd = len(self.temp[end:])