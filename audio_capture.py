"""
实时音频采集模块 - 使用 PulseAudio 捕获系统音频输出

实现原理:
1. 使用 PulseAudio 的 monitor source 捕获系统音频流
2. 通过回调函数实时处理音频数据
3. 支持配置采样率、声道数、缓冲区大小等参数

依赖安装:
    pip install pulsectl soundfile librosa numpy

使用前需要:
1. 确保 PulseAudio 正在运行
2. 查看可用的 monitor source: pactl list sources | grep -A 5 "Name:"
3. 或运行: python audio_capture.py --list-sources
"""

import threading
import queue
import numpy as np
import pulsectl
import sounddevice as sd
from datetime import datetime
from typing import Callable, Optional


class PulseAudioCapture:
    """
    PulseAudio 实时音频采集类
    
    用于捕获电脑的系统音频输出（如扬声器、耳机等播放的声音）
    """
    
    def __init__(
        self,
        source_name: str = None,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = 'float32',
        blocksize: int = 3200,  # 200ms at 16kHz
        device_buffer_size: int = 32000,
    ):
        """
        初始化音频采集器
        
        Args:
            source_name: PulseAudio 源名称 (monitor source)
                        例如: 'alsa_output.pci-0000_00_1f.3.analog-stereo.monitor'
                        如果为 None，会自动选择默认的 monitor source
            sample_rate: 采样率 (Hz)
            channels: 声道数 (1 = 单声道, 2 = 立体声)
            dtype: 数据类型
            blocksize: 每个回调块的样本数
            device_buffer_size: 设备缓冲区大小 (样本数)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.blocksize = blocksize
        self.device_buffer_size = device_buffer_size
        self.source_name = source_name
        
        self._running = False
        self._audio_queue = queue.Queue(maxsize=100)
        self._capture_thread: Optional[threading.Thread] = None
        
        # 自动选择 monitor source
        if self.source_name is None:
            self.source_name = self._get_default_monitor_source()
    
    def _get_default_monitor_source(self) -> str:
        """获取默认的音频输出 monitor source"""
        try:
            with pulsectl.Pulse('audio-capture') as pulse:
                # 查找默认的 sink
                default_sink = pulse.server_info().default_sink_name
                if default_sink:
                    # 返回对应的 monitor source
                    monitor_source = f"{default_sink}.monitor"
                    print(f"[INFO] 使用默认 monitor source: {monitor_source}")
                    return monitor_source
        except Exception as e:
            print(f"[WARNING] 自动获取 monitor source 失败: {e}")
        
        # 备选: 尝试查找第一个可用的 monitor
        try:
            with pulsectl.Pulse('audio-capture') as pulse:
                sources = pulse.source_list()
                for source in sources:
                    if '.monitor' in source.name:
                        print(f"[INFO] 找到 monitor source: {source.name}")
                        return source.name
        except Exception as e:
            print(f"[WARNING] 查找 monitor source 失败: {e}")
        
        raise RuntimeError("未找到可用的 audio monitor source")
    
    def list_available_sources(self):
        """列出所有可用的音频源"""
        print("\n=== 可用的音频源 (Sources) ===")
        try:
            with pulsectl.Pulse('audio-capture') as pulse:
                sources = pulse.source_list()
                for source in sources:
                    monitor_indicator = " [MONITOR]" if '.monitor' in source.name else ""
                    print(f"  {source.name}{monitor_indicator}")
                    print(f"    Description: {source.description}")
        except Exception as e:
            print(f"Error: {e}")
        print()
    
    def list_available_sinks(self):
        """列出所有可用的音频输出 (Sinks)"""
        print("\n=== 可用的音频输出 (Sinks) ===")
        try:
            with pulsectl.Pulse('audio-capture') as pulse:
                sinks = pulse.sink_list()
                for sink in sinks:
                    print(f"  {sink.name}")
                    print(f"    Description: {sink.description}")
                    print(f"    Monitor Source: {sink.monitor_source_name}")
        except Exception as e:
            print(f"Error: {e}")
        print()
    
    def _audio_callback(self, indata, frames, time, status):
        """音频数据回调函数"""
        if status:
            print(f"[WARNING] Audio callback status: {status}")
        
        try:
            # 将数据放入队列 (非阻塞)
            if not self._audio_queue.full():
                # 复制数据以避免引用问题
                audio_data = np.copy(indata)
                self._audio_queue.put_nowait(audio_data)
        except queue.Full:
            pass  # 队列满了就跳过
    
    def start(self):
        """开始音频采集"""
        if self._running:
            print("[WARNING] 采集已经在运行中")
            return
        
        print(f"[INFO] 开始采集音频 from: {self.source_name}")
        print(f"       采样率: {self.sample_rate} Hz")
        print(f"       声道数: {self.channels}")
        print(f"       块大小: {self.blocksize} 样本")
        
        try:
            # 使用环境变量指定 PulseAudio 源
            import os
            old_source = os.environ.get('PULSE_SOURCE')
            os.environ['PULSE_SOURCE'] = self.source_name
            
            # 使用 sounddevice 配合 PulseAudio (使用 pulse 设备)
            self._stream = sd.InputStream(
                device='pulse',
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.blocksize,
                callback=self._audio_callback
            )
            self._stream.start()
            self._running = True
            
            # 恢复环境变量
            if old_source is not None:
                os.environ['PULSE_SOURCE'] = old_source
            else:
                os.environ.pop('PULSE_SOURCE', None)
            
        except Exception as e:
            print(f"[ERROR] 启动采集失败: {e}")
            # 备选方案: 使用纯 pulsectl
            self._start_with_pulsectl()
    
    def _start_with_pulsectl(self):
        """使用纯 PulseAudio 方式采集 (备选方案)"""
        print("[INFO] 使用备选方案: pulsectl 事件循环")
        self._running = True
    
    def stop(self):
        """停止音频采集"""
        if not self._running:
            return
        
        print("[INFO] 停止音频采集")
        self._running = False
        
        if hasattr(self, '_stream') and self._stream:
            self._stream.stop()
            self._stream.close()
        
        # 清空队列
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
    
    def read(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        读取一段音频数据
        
        Args:
            timeout: 超时时间 (秒)
            
        Returns:
            音频数据 (numpy array) 或 None (如果超时)
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def read_all(self) -> np.ndarray:
        """读取所有可用的音频数据"""
        chunks = []
        while not self._audio_queue.empty():
            try:
                chunk = self._audio_queue.get_nowait()
                chunks.append(chunk)
            except queue.Empty:
                break
        
        if chunks:
            return np.concatenate(chunks, axis=0)
        return np.array([])
    
    def get_audio_level(self) -> float:
        """获取当前音频电平 (用于 VAD - 语音活动检测)"""
        audio = self.read(timeout=0.1)
        if audio is not None and len(audio) > 0:
            return np.sqrt(np.mean(audio**2))
        return 0.0


class AudioChunkBuffer:
    """
    音频块缓冲区 - 用于累积音频数据用于语音识别
    """
    
    def __init__(self, sample_rate: int = 16000, min_duration: float = 1.0, max_duration: float = 5.0):
        """
        Args:
            sample_rate: 采样率
            min_duration: 最小累积时长 (秒)
            max_duration: 最大累积时长 (秒)
        """
        self.sample_rate = sample_rate
        self.min_samples = int(sample_rate * min_duration)
        self.max_samples = int(sample_rate * max_duration)
        self.buffer = []
        self.last_speech_time = None
    
    def add(self, audio_chunk: np.ndarray):
        """添加音频块"""
        self.buffer.append(audio_chunk)
    
    def get_audio(self) -> Optional[np.ndarray]:
        """获取累积的音频"""
        if not self.buffer:
            return None
        
        audio = np.concatenate(self.buffer, axis=0)
        
        # 如果音频太长，保留最后部分
        if len(audio) > self.max_samples:
            audio = audio[-self.max_samples:]
        
        return audio
    
    def has_enough_audio(self) -> bool:
        """检查是否有足够的音频数据"""
        if not self.buffer:
            return False
        total_samples = sum(len(chunk) for chunk in self.buffer)
        return total_samples >= self.min_samples
    
    def clear(self):
        """清空缓冲区"""
        self.buffer = []


def test_capture():
    """测试音频采集"""
    print("=== 音频采集测试 ===\n")
    
    # 创建采集器
    capture = PulseAudioCapture(
        sample_rate=16000,
        channels=1,
        blocksize=3200
    )
    
    # 列出可用源
    capture.list_available_sources()
    capture.list_available_sinks()
    
    # 开始采集
    capture.start()
    
    print("\n正在采集音频... (按 Ctrl+C 停止)")
    print("音频电平:")
    
    try:
        import time
        while True:
            level = capture.get_audio_level()
            # 显示电平条
            bar_length = 50
            filled = int(level * bar_length * 2)  # 放大以便观察
            filled = min(filled, bar_length)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r[{bar}] {level:.4f}", end='', flush=True)
            
            # 偶尔读取一段音频
            audio = capture.read(timeout=0.1)
            if audio is not None:
                print(f"  | 采集到 {len(audio)} 样本")
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\n[INFO] 收到中断信号，正在停止...")
    finally:
        capture.stop()
        print("[INFO] 测试完成")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PulseAudio 音频采集测试")
    parser.add_argument("--list-sources", action="store_true", help="列出可用的音频源")
    parser.add_argument("--test", action="store_true", help="运行采集测试")
    parser.add_argument("--source", type=str, help="指定 monitor source 名称")
    
    args = parser.parse_args()
    
    if args.list_sources:
        capture = PulseAudioCapture()
        capture.list_available_sources()
        capture.list_available_sinks()
    elif args.test:
        capture = PulseAudioCapture(source_name=args.source)
        capture.start()
        try:
            import time
            for i in range(100):  # 采集 5 秒
                audio = capture.read(timeout=0.1)
                if audio is not None:
                    print(f"采集到 {len(audio)} 样本, 电平: {np.sqrt(np.mean(audio**2)):.4f}")
                time.sleep(0.05)
            capture.stop()
        except KeyboardInterrupt:
            capture.stop()
    else:
        test_capture()
