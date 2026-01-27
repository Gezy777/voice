import torch
import config
import whisper
import requests
import time
import translator

class VoiceToText:
    def __init__(self, is_local):
        if is_local:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = whisper.load_model(config.VoiceToWordModel).to(self.device)
            print(self.device)

    def recognize_audio_local(self, audio_data):
        start = time.time()
        result = whisper.decode(
            self.model,
            whisper.log_mel_spectrogram(whisper.pad_or_trim(audio_data)).to(self.device), 
            whisper.DecodingOptions(
            task="transcribe",
            language=None,
            fp16=torch.cuda.is_available()
        ))
        text, cost = result.text, round(time.time() - start, 3)
        translated = translator.tencent_translate_api(text)
        data = {
            "original": text,
            "translated": translated,
            "final": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }
        self.text_write_file(text)
        print("原文:" + text)
        print("翻译结果:" + translated)
        print("翻译耗时:" + str(cost) + "s")
        return data
    
    def recognize_audio_server(self, audio_data):
        resp = requests.post(
            config.SERVER,
            json={"audio": audio_data.tolist()}
        )        
        text, cost = resp.json()["origin"], resp.json()["cost"]
        translated = translator.tencent_translate_api(text)
        data = {
            "original": text,
            "translated": translated,
            "final": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }
        # self.text_write_file(text)
        print("原文:" + text)
        print("翻译结果:" + translated)
        print("翻译耗时:" + str(cost) + "s")
        return data
    def text_write_file(self, text):
        with open(config.FileName, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        


