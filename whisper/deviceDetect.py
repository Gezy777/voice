import config
import pyaudio

# linux选pulse

def detect_audio_devices():
    p = pyaudio.PyAudio()

    # 检测系统中所有可以监听的音频设备
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"检测到的音频设备{info['index']}: {info['name']} ")

detect_audio_devices()
