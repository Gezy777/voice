#!/usr/bin/env python3
"""
实时语音翻译字幕系统

功能:
1. 实时采集电脑音频输出 (PulseAudio)
2. 使用 OpenAI Whisper 进行语音识别
3. 实时翻译并显示字幕

依赖:
    pip install -r requirements.txt

使用:
    python realtime_translator.py --help
"""

import sys
import time
import threading
import queue
import argparse
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Callable

import numpy as np
import torch

# 音频处理
import soundfile as sf

# 语音识别
import whisper

# 翻译
from deep_translator import GoogleTranslator, DeepLTranslator

# 从同目录导入音频采集模块
from audio_capture import PulseAudioCapture, AudioChunkBuffer


class RealtimeTranslator:
    """
    实时翻译字幕系统主类
    """
    
    def __init__(
        self,
        whisper_model: str = "base",
        source_language: str = "en",
        target_language: str = "zh",
        min_audio_duration: float = 2.0,
        max_audio_duration: float = 10.0,
        silence_threshold: float = 0.02,
        silence_duration: float = 1.5,
        output_file: Optional[str] = None,
        source_name: Optional[str] = None,
    ):
        """
        初始化翻译器
        
        Args:
            whisper_model: Whisper 模型大小 ("tiny", "base", "small", "medium", "large")
            source_language: 源语言代码 (如 "en", "zh", "ja", "ko")
            target_language: 目标语言代码
            min_audio_duration: 最小音频时长 (秒) - 用于触发识别
            max_audio_duration: 最大音频时长 (秒)
            silence_threshold: 静音阈值 (用于检测语音结束)
            silence_duration: 静音等待时长 (秒)
            output_file: 输出字幕文件路径
            source_name: PulseAudio monitor source 名称
        """
        self.whisper_model = whisper_model
        self.source_language = source_language
        self.target_language = target_language
        self.min_audio_duration = min_audio_duration
        self.max_audio_duration = max_audio_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.output_file = output_file
        self.source_name = source_name
        
        # 状态
        self._running = False
        self._whisper_model = None
        self._translator = None
        
        # 音频采集
        self._audio_capture: Optional[PulseAudioCapture] = None
        self._audio_buffer = AudioChunkBuffer(
            sample_rate=16000,
            min_duration=min_audio_duration,
            max_duration=max_audio_duration
        )
        
        # 字幕回调
        self._subtitle_callbacks: List[Callable] = []
        
        # 语音状态
        self._is_speaking = False
        self._last_speech_time = time.time()
        
        # 线程
        self._recognition_thread: Optional[threading.Thread] = None
        self._recognition_queue = queue.Queue()
        
        # 翻译器初始化
        self._init_translator()
    
    def _init_translator(self):
        """初始化翻译器"""
        try:
            self._translator = GoogleTranslator(
                source=self.source_language,
                target=self.target_language
            )
        except Exception as e:
            print(f"[WARNING] Google Translator 初始化失败: {e}")
            try:
                self._translator = DeepLTranslator(
                    source=self.source_language.upper(),
                    target=self.target_language.upper()
                )
            except Exception as e2:
                print(f"[WARNING] DeepL Translator 也失败: {e2}")
                self._translator = None
    
    def _load_whisper_model(self):
        """加载 Whisper 模型"""
        print(f"[INFO] 加载 Whisper 模型: {self.whisper_model}")
        
        # 检查 CUDA
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] 使用设备: {device}")
        
        # 加载模型
        self._whisper_model = whisper.load_model(
            self.whisper_model,
            device=device
        )
        
        print("[INFO] Whisper 模型加载完成")
    
    def add_subtitle_callback(self, callback: Callable[[str, str, float], None]):
        """
        添加字幕回调函数
        
        Args:
            callback: 接收 (原始文本, 翻译文本, 时间戳) 的函数
        """
        self._subtitle_callbacks.append(callback)
    
    def _emit_subtitle(self, original: str, translated: str):
        """发送字幕到所有回调"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        for callback in self._subtitle_callbacks:
            try:
                callback(original, translated, timestamp)
            except Exception as e:
                print(f"[WARNING] 字幕回调失败: {e}")
        
        # 写入文件
        if self.output_file:
            self._write_subtitle_to_file(original, translated, timestamp)
    
    def _write_subtitle_to_file(self, original: str, translated: str, timestamp: str):
        """写入字幕到文件"""
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {original}\n")
                f.write(f"[{timestamp}] 翻译: {translated}\n\n")
        except Exception as e:
            print(f"[WARNING] 写入字幕文件失败: {e}")
    
    def _detect_speech_activity(self, audio_chunk: np.ndarray) -> bool:
        """检测是否有语音活动"""
        rms = np.sqrt(np.mean(audio_chunk**2))
        return rms > self.silence_threshold
    
    def _process_audio(self):
        """处理音频的线程函数"""
        print("[INFO] 音频处理线程已启动")
        
        temp_dir = tempfile.mkdtemp()
        
        while self._running:
            try:
                # 读取音频块
                audio_chunk = self._audio_capture.read(timeout=0.5)
                
                if audio_chunk is None:
                    continue
                
                # 检测语音活动
                has_speech = self._detect_speech_activity(audio_chunk)
                current_time = time.time()
                
                if has_speech:
                    self._is_speaking = True
                    self._last_speech_time = current_time
                    self._audio_buffer.add(audio_chunk)
                else:
                    # 检测语音是否结束 (静音超过阈值)
                    if self._is_speaking:
                        silence_elapsed = current_time - self._last_speech_time
                        
                        if silence_elapsed >= self.silence_duration:
                            # 语音结束，处理累积的音频
                            self._is_speaking = False
                            
                            if self._audio_buffer.has_enough_audio():
                                audio = self._audio_buffer.get_audio()
                                if audio is not None and len(audio) > 0:
                                    # 发送到识别队列
                                    self._recognition_queue.put(audio.copy())
                            
                            self._audio_buffer.clear()
                
                # 强制处理超长音频
                if self._is_speaking and self._audio_buffer.has_enough_audio():
                    audio = self._audio_buffer.get_audio()
                    if audio is not None:
                        audio_duration = len(audio) / 16000
                        if audio_duration >= self.max_audio_duration:
                            self._recognition_queue.put(audio.copy())
                            self._audio_buffer.clear()
                
            except Exception as e:
                if self._running:
                    print(f"[ERROR] 音频处理错误: {e}")
        
        # 清理
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("[INFO] 音频处理线程已停止")
    
    def _recognize_and_translate(self):
        """识别和翻译的线程函数"""
        print("[INFO] 识别翻译线程已启动")
        
        while self._running:
            try:
                # 从队列获取音频
                audio = self._recognition_queue.get(timeout=1.0)
                
                if audio is None:
                    continue
                
                # 保存临时音频文件
                temp_dir = tempfile.gettempdir()
                temp_file = Path(temp_dir) / f"audio_{int(time.time() * 1000)}.wav"
                
                try:
                    # 保存音频
                    sf.write(str(temp_file), audio, 16000)
                    
                    # 语音识别
                    result = self._whisper_model.transcribe(
                        str(temp_file),
                        language=self.source_language,
                        fp16=False
                    )
                    
                    text = result["text"].strip()
                    
                    if text and len(text) > 3:  # 过滤太短的识别结果
                        print(f"\n🎤 识别: {text}")
                        
                        # 翻译
                        if self._translator:
                            try:
                                translated = self._translator.translate(text)
                                print(f"🌐 翻译: {translated}")
                            except Exception as e:
                                print(f"[WARNING] 翻译失败: {e}")
                                translated = "[翻译失败]"
                        else:
                            translated = "[翻译器未初始化]"
                        
                        # 发送字幕
                        self._emit_subtitle(text, translated)
                
                finally:
                    # 清理临时文件
                    try:
                        temp_file.unlink()
                    except:
                        pass
                    
                    self._recognition_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                if self._running:
                    print(f"[ERROR] 识别翻译错误: {e}")
        
        print("[INFO] 识别翻译线程已停止")
    
    def start(self):
        """启动系统"""
        if self._running:
            print("[WARNING] 系统已在运行中")
            return
        
        print("=" * 60)
        print("🎙️  实时语音翻译字幕系统")
        print("=" * 60)
        
        # 加载模型
        self._load_whisper_model()
        
        # 初始化音频采集
        self._audio_capture = PulseAudioCapture(
            source_name=self.source_name,
            sample_rate=16000,
            channels=1,
            blocksize=3200
        )
        
        # 列出音频设备
        self._audio_capture.list_available_sinks()
        
        # 启动音频采集
        self._audio_capture.start()
        
        # 设置运行状态
        self._running = True
        
        # 启动处理线程
        self._recognition_thread = threading.Thread(
            target=self._process_and_recognize,
            daemon=True
        )
        self._recognition_thread.start()
        
        print("\n[INFO] 系统已启动!")
        print("[INFO] 正在监听音频... (按 Ctrl+C 停止)")
        print("-" * 60)
    
    def _process_and_recognize(self):
        """处理和识别的主循环"""
        temp_dir = tempfile.mkdtemp()
        
        while self._running:
            try:
                # 读取音频块
                audio_chunk = self._audio_capture.read(timeout=0.5)
                
                if audio_chunk is None:
                    continue
                
                # 检测语音活动
                has_speech = self._detect_speech_activity(audio_chunk)
                current_time = time.time()
                
                if has_speech:
                    self._is_speaking = True
                    self._last_speech_time = current_time
                    self._audio_buffer.add(audio_chunk)
                else:
                    # 检测语音结束
                    if self._is_speaking:
                        silence_elapsed = current_time - self._last_speech_time
                        
                        if silence_elapsed >= self.silence_duration:
                            self._is_speaking = False
                            
                            if self._audio_buffer.has_enough_audio():
                                audio = self._audio_buffer.get_audio()
                                if audio is not None and len(audio) > 0:
                                    self._recognize_audio(audio, temp_dir)
                            
                            self._audio_buffer.clear()
                
                # 处理超长音频
                if self._is_speaking and self._audio_buffer.has_enough_audio():
                    audio = self._audio_buffer.get_audio()
                    if audio is not None:
                        audio_duration = len(audio) / 16000
                        if audio_duration >= self.max_audio_duration:
                            self._recognize_audio(audio, temp_dir)
                            self._audio_buffer.clear()
                
            except Exception as e:
                if self._running:
                    print(f"[ERROR] 处理错误: {e}")
        
        # 清理
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _recognize_audio(self, audio: np.ndarray, temp_dir: str):
        """识别单个音频段"""
        temp_file = Path(temp_dir) / f"audio_{int(time.time() * 1000)}.wav"
        
        try:
            sf.write(str(temp_file), audio, 16000)
            
            result = self._whisper_model.transcribe(
                str(temp_file),
                language=self.source_language,
                fp16=False
            )
            
            text = result["text"].strip()
            
            if text and len(text) > 2:
                print(f"\n🎤 [{datetime.now().strftime('%H:%M:%S')}] {text}")
                
                if self._translator:
                    try:
                        translated = self._translator.translate(text)
                        print(f"🌐 翻译: {translated}")
                    except Exception as e:
                        print(f"[WARNING] 翻译失败: {e}")
                        translated = "[翻译失败]"
                else:
                    translated = "[翻译器未初始化]"
                
                self._emit_subtitle(text, translated)
        
        except Exception as e:
            print(f"[ERROR] 识别错误: {e}")
        
        finally:
            try:
                temp_file.unlink()
            except:
                pass
    
    def stop(self):
        """停止系统"""
        if not self._running:
            return
        
        print("\n[INFO] 正在停止系统...")
        self._running = False
        
        # 停止音频采集
        if self._audio_capture:
            self._audio_capture.stop()
        
        # 等待线程结束
        if self._recognition_thread:
            self._recognition_thread.join(timeout=5.0)
        
        # 清理模型
        if self._whisper_model:
            del self._whisper_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        print("[INFO] 系统已停止")
    
    def run(self):
        """主运行循环 (阻塞)"""
        try:
            self.start()
            
            # 主循环
            while self._running:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n[INFO] 收到中断信号")
        finally:
            self.stop()


def console_subtitle_callback(original: str, translated: str, timestamp: str):
    """控制台字幕显示回调"""
    print(f"\n{'='*60}")
    print(f"⏰ {timestamp}")
    print(f"📝 原文: {original}")
    print(f"🌐 译文: {translated}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="实时语音翻译字幕系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认设置运行
  python realtime_translator.py
  
  # 使用更大的模型 (更准确但更慢)
  python realtime_translator.py --model medium
  
  # 翻译日语到中文
  python realtime_translator.py --source ja --target zh
  
  # 保存字幕到文件
  python realtime_translator.py --output subtitles.srt
  
  # 查看可用的音频源
  python realtime_translator.py --list-sources
        """
    )
    
    parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 模型大小 (默认: base)"
    )
    
    parser.add_argument(
        "--source", "-s",
        default="en",
        help="源语言代码 (默认: en)"
    )
    
    parser.add_argument(
        "--target", "-t",
        default="zh",
        help="目标语言代码 (默认: zh)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出字幕文件路径"
    )
    
    parser.add_argument(
        "--source-name",
        default=None,
        help="PulseAudio monitor source 名称"
    )
    
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="列出可用的音频源并退出"
    )
    
    parser.add_argument(
        "--silence-threshold",
        type=float,
        default=0.02,
        help="静音检测阈值 (默认: 0.02)"
    )
    
    parser.add_argument(
        "--silence-duration",
        type=float,
        default=1.5,
        help="静音等待时长 (秒) (默认: 1.5)"
    )
    
    args = parser.parse_args()
    
    # 列出音频源
    if args.list_sources:
        capture = PulseAudioCapture()
        capture.list_available_sources()
        capture.list_available_sinks()
        return
    
    # 创建翻译器
    translator = RealtimeTranslator(
        whisper_model=args.model,
        source_language=args.source,
        target_language=args.target,
        silence_threshold=args.silence_threshold,
        silence_duration=args.silence_duration,
        output_file=args.output,
        source_name=args.source_name
    )
    
    # 添加控制台输出回调
    translator.add_subtitle_callback(console_subtitle_callback)
    
    # 运行
    translator.run()


if __name__ == "__main__":
    main()
