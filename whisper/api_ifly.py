# -*- coding:utf-8 -*-
#
#   author: iflytek
#
#  本demo测试时运行的环境为：Windows + Python3.7
#  本demo测试成功运行时所安装的第三方库及其版本如下，您可自行逐一或者复制到一个新的txt文件利用pip一次性安装：
#   cffi==1.12.3
#   gevent==1.4.0
#   greenlet==0.4.15
#   pycparser==2.19
#   six==1.12.0
#   websocket==0.2.1
#   websocket-client==0.56.0
#
#  语音听写流式 WebAPI 接口调用示例 接口文档（必看）：https://doc.xfyun.cn/rest_api/语音听写（流式版）.html
#  webapi 听写服务参考帖子（必看）：http://bbs.xfyun.cn/forum.php?mod=viewthread&tid=38947&extra=
#  语音听写流式WebAPI 服务，热词使用方式：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写（流式）---服务管理--个性化热词，
#  设置热词
#  注意：热词只能在识别的时候会增加热词的识别权重，需要注意的是增加相应词条的识别率，但并不是绝对的，具体效果以您测试为准。
#  语音听写流式WebAPI 服务，方言试用方法：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写（流式）---服务管理--识别语种列表
#  可添加语种或方言，添加后会显示该方言的参数值
#  错误码链接：https://www.xfyun.cn/document/error-code （code返回错误码时必看）
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
from dotenv import load_dotenv
import os

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识


class Ws_Param(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret, AudioFile):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioFile = AudioFile

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}

    # 生成url
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        # print("date: ",date)
        # print("v: ",v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        # print('websocket url :', url)
        return url
import queue

audio_queue = queue.Queue()

def ifly_api():
    global api_data
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
    server = config.SERVER

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

    # 语音活动检测函数 
    # 合并相近的语音片段
    def detect_voice_activity(audio):
        speeches = detect_speech(
            audio, vad_model, sampling_rate=16000
        ) # 检测语音活动
        print(speeches,len(audio)) # 打印检测到的语音片段和音频长度

        return speeches


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
                audio_queue.put(alldata.tobytes())
                get_audio_text(alldata)
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
                        audio_queue.put(alldata.tobytes())
                        get_audio_text(alldata) # 处理录音数据

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
                        audio_queue.put(alldata.tobytes())
                        get_audio_text(alldata)
                    alldata = temp[start:end]
                    alldata, i, LastEnd = joint_sentences(start2, end2, start2 - end < Internal, alldata, i, temp)
            
            # 清空data和temp，继续录音
            data = b''
            temp = np.array([],np.float32)

    record()


# 收到websocket消息的处理
def on_message(ws, message):
    try:
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        if code != 0:
            errMsg = json.loads(message)["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))

        else:
            data = json.loads(message)["data"]["result"]["ws"]
            # print(json.loads(message))
            # result = ""
            # for i in data:
            #     for w in i["cw"]:
            #         result += w["w"]
            # print("sid:%s call success!,data is:%s" % (sid, json.dumps(data, ensure_ascii=False)))
            result = ""
            for i in data:
                result += i["cw"][0]["w"]

            print("识别结果：", result)

    except Exception as e:
        print("receive msg,but parse exception:", e)



# 收到websocket错误的处理
def on_error(ws, error):
    print("### error:", error)


# 收到websocket关闭的处理
def on_close(ws,a,b):
    print("### closed ###")


# 收到websocket连接建立的处理
def on_open(ws):
    def run(*args):
        frameSize = 8000  # 每一帧的音频大小
        intervel = 0.04  # 发送音频间隔(单位:s)
        status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

        fp = open(wsParam.AudioFile, "rb")
        while True:
            buf = audio_queue.get()   # ⬅ 阻塞等待
            # 文件结束
            if not buf:
                status = STATUS_LAST_FRAME
            # 第一帧处理
            # 发送第一帧音频，带business 参数
            # appid 必须带上，只需第一帧发送
            if status == STATUS_FIRST_FRAME:

                d = {"common": wsParam.CommonArgs,
                        "business": wsParam.BusinessArgs,
                        "data": {"status": 0, "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": "raw"}}
                d = json.dumps(d)
                ws.send(d)
                status = STATUS_CONTINUE_FRAME
            # 中间帧处理
            elif status == STATUS_CONTINUE_FRAME:
                d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": "raw"}}
                ws.send(json.dumps(d))
            # 最后一帧处理
            elif status == STATUS_LAST_FRAME:
                d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": "raw"}}
                ws.send(json.dumps(d))
                time.sleep(1)
                break
            # 模拟音频采样间隔
            time.sleep(intervel)
        ws.close()

    thread.start_new_thread(run, ())


if __name__ == "__main__":
    # 测试时候在此处正确填写相关信息即可运行
    load_dotenv()
    time1 = datetime.now()
    wsParam = Ws_Param(APPID=os.getenv("IFLYTEK_APPID"), APISecret=os.getenv("IFLYTEK_APISecret"),
                       APIKey=os.getenv("IFLYTEK_APIKey"),
                       AudioFile=r'./test2.wav')
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    thread.start_new_thread(ifly_api, ())
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    time2 = datetime.now()
    print(time2-time1)
