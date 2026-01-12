import config
import pyaudio

def detect_audio_devices():
    p = pyaudio.PyAudio()

    # 检测系统中所有可以监听的音频设备
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"检测到的音频设备{info['index']}: {info['name']} ")

if __name__ == "__main__":
    detect_audio_devices()
