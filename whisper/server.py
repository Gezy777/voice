# server.py
import time
import torch
import numpy as np
import whisper
import config
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# ===== 全局只加载一次 =====
device = "cuda" if torch.cuda.is_available() else "cpu"
print(device)
model = whisper.load_model(config.VoiceToWordModel).to(device)

options = whisper.DecodingOptions(
    task="transcribe",
    language=None,
    fp16=torch.cuda.is_available()
)

class AudioRequest(BaseModel):
    audio: list[float]   # 16kHz mono PCM

@app.post("/translate")
def translate_audio(req: AudioRequest):
    start_time = time.time()

    audio = np.array(req.audio, dtype=np.float32)

    # === 30s 窗口 ===
    audio = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(audio).to(device)

    result = whisper.decode(model, mel, options)

    translated = result.text

    return {
        "origin": result.text,
        "translated": translated,
        "cost": round(time.time() - start_time, 3)
    }
