# 上传音频文件，识别其中语音活动并翻译为指定语言，输出文本
## 1. 上传音频文件并转化为可处理的数据
## 2. 使用VAD检测音频中的语音活动段
## 3. 对检测到的语音活动段进行翻译
## 4. 输出翻译结果到文本文件
import whisper
import config

fileName = "./test.wav"  # 替换为实际音频文件路径

model = whisper.load_model(config.VoiceToWordModel)

result = model.transcribe(fileName, task="translate")

print(result["text"])


# # 1. 加载并转换音频
# audio = whisper.load_audio(fileName)

# # 2. 截断或补零到 30s（Whisper 要求）
# audio = whisper.pad_or_trim(audio)

# # 3. 转 Mel 频谱
# mel = whisper.log_mel_spectrogram(audio).to(model.device)

# # 4. 解码
# options = whisper.DecodingOptions(language=None, task="transcribe", fp16=torch.cuda.is_available())
# result = whisper.decode(model, mel, options)

# print(result.text)
