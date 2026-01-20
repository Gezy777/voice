def ifly_api():
    import pyaudio
    import queue
    import config
    import torch
    import requests
    import google_translate as translate
    import numpy as np

    # 配置录音参数
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    # 设定的说话间隔时间
    Internal = config.Internal

    # 指定翻译服务器
    server = config.SERVER_WINDOWS

    # 源语言
    SourceLanguage = config.SourceLanguage

    # 目的语言
    TargetLanguage = config.TargetLanguage

    # 监听的音频设备
    InputDeviceIndex = config.InputDeviceIndex

    # 载入语音活动检测函数
    torch.hub._validate_not_a_forked_repo = lambda a, b, c: True
    vad_model, funcs = torch.hub.load(
                repo_or_dir="../silero-vad", model="silero_vad", source="local"
            )
    detect_speech = funcs[0]

    # 从服务器端获取音频转文字结果
    def voice_to_text_server(audio_data):
        resp = requests.post(
            server,
            json={"audio": audio_data.tolist()}
        )
        print("原文:" + resp.json()["origin"])
        print("翻译结果:" + translate.google_web_translate(resp.json()["translated"]))
        print("翻译耗时:" + str(resp.json()["cost"]) + "s")


    # 翻译音频并输出中文
    def get_audio_text(audio_data):

        voice_to_text_server(audio_data)

    # 语音活动检测函数 
    # 合并相近的语音片段
    def detect_voice_activity(audio):
        speeches = detect_speech(
            audio, vad_model, sampling_rate=16000
        ) # 检测语音活动
        print(speeches,len(audio)) # 打印检测到的语音片段和音频长度

        return speeches


    # 创建队列用于存储录音数据
    q = queue.Queue()

    def recording_callback(in_data, frame_count, time_info, status):
        # 将录制的数据存入队列
        q.put(in_data)
        return (None, pyaudio.paContinue)

    def joint_sentences(start, end, isJoint, alldata, i, temp):
        if isJoint:
            # 这是一句话
            alldata = np.concatenate((alldata,temp[start:end]), axis=0)

        else:
            # 这是两句话
            # 先处理前一句话
            if len(alldata) > 0:
                print(f"第{i}句话翻译完成")
                i += 1
                api_data += alldata.tobytes()
                # get_audio_text(alldata)
            alldata = temp[start:end]

        print(f"这是第{i}句话")
        # # get_audio_text(alldata)
        LastEnd = len(temp[end:])
        return alldata, i, LastEnd

    def record():
        p = pyaudio.PyAudio()

        # 指定监听的音频源，监听的是系统音频输出
        input_device_index = InputDeviceIndex

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
        i = 1 # 第几句话

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
                        print(f"第{i}句话翻译完成")
                        # print(f"这是第{i}句话")
                        i += 1
                        api_data += alldata.tobytes()
                        ##get_audio_text(alldata) # 处理录音数据

                # 重置变量
                alldata = np.array([],np.float32)

            elif len(speeches) == 1: # 检测到一段语音
                Recording = True
                start = int(speeches[0]['start']) 
                end = int(speeches[0]['end'])
                alldata, i, LastEnd = joint_sentences(start, end, start + LastEnd < Internal, alldata, i, temp)

            elif len(speeches) == 2:
                Recording = True
                start = int(speeches[0]['start']) 
                end = int(speeches[0]['end'])
                start2 = int(speeches[1]['start'])
                end2 = int(speeches[1]['end'])

                # 获取并添加第一句话之后再处理
                if start + LastEnd < Internal:
                    # 这是一句话
                    alldata = np.concatenate((alldata, temp[start:end]), axis=0)
                    alldata, i, LastEnd = joint_sentences(start2, end2, start2 - end < Internal, alldata, i, temp)

                else:
                    # 这是两句话
                    if len(alldata) > 0:
                        print(f"第{i}句话翻译完成")
                        i += 1
                        api_data += alldata.tobytes()
                        ##get_audio_text(alldata)
                    alldata = temp[start:end]
                    alldata, i, LastEnd = joint_sentences(start2, end2, start2 - end < Internal, alldata, i, temp)
            
            # 清空data和temp，继续录音
            data = b''
            temp = np.array([],np.float32)

    record()
