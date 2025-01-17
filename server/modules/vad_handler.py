import os
import sys

# 将项目根目录添加到Python路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

import logging
import numpy as np
from typing import Generator, Any
from threading import Event
from funasr import AutoModel
import soundfile as sf
import argparse

from server.modules.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class VADHandler(BaseHandler):
    """语音活动检测处理器，使用FunASR的FSMN-VAD模型"""
    
    def setup(self, should_listen: Event, sample_rate: int = 16000, 
             chunk_size: int = 1000, min_duration: float = 0.5,
             max_duration: float = float('inf'), threshold: float = 0.3) -> None:
        """
        设置VAD参数
        
        Args:
            should_listen: 控制是否进行语音检测的事件
            sample_rate: 音频采样率
            chunk_size: 每次处理的音频长度(ms)
            min_duration: 最小语音片段时长(秒)
            max_duration: 最大语音片段时长(秒)，设为float('inf')表示无限制
            threshold: VAD阈值，越大越严格，范围[0-1]
        """
        self.should_listen = should_listen
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.threshold = threshold
        
        # 计算每个chunk的采样点数
        self.chunk_stride = int(self.chunk_size * self.sample_rate / 1000)
        
        # 初始化VAD模型
        self.model = AutoModel(
            model="fsmn-vad",
            model_revision="v2.0.4",
            vad_threshold=self.threshold,  # 设置VAD阈值
            max_end_silence_time=0  # 禁用内部的静音检测
        )
        logger.info("FSMN-VAD model loaded")
        
        # 初始化状态
        self.cache = {}  # VAD模型的缓存
        self.accumulated_audio = np.array([], dtype=np.float32)  # 累积的音频数据
        self.is_speaking = False  # 当前是否正在说话
        self.current_speech = []  # 当前语音片段的帧列表
        self.speech_start_idx = 0  # 当前语音片段的起始帧索引
        
        logger.info(f"VAD initialized with: sample_rate={sample_rate}, "
                   f"chunk_size={chunk_size}ms, min_duration={min_duration}s, "
                   f"max_duration={'无限制' if max_duration == float('inf') else f'{max_duration}s'}, "
                   f"threshold={threshold}")

    def process(self, audio_chunk: bytes) -> Generator[bytes, None, None]:
        """
        处理音频数据
        
        Args:
            audio_chunk: 输入的音频数据块（int16格式）
            
        Yields:
            bytes: 检测到的语音片段
        """
        if not self.should_listen.is_set():
            logger.debug("VAD is not listening")
            return
            
        # 将音频数据转换为float32格式，范围归一化到[-1,1]
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        
        # 将新的音频数据添加到累积缓冲区
        self.accumulated_audio = np.concatenate([self.accumulated_audio, audio_data])
        
        # 如果累积的音频数据足够长，进行VAD处理
        while len(self.accumulated_audio) >= self.chunk_stride:
            # 提取当前chunk
            current_chunk = self.accumulated_audio[:self.chunk_stride]
            self.accumulated_audio = self.accumulated_audio[self.chunk_stride:]
            
            try:
                # 获取VAD输出
                res = self.model.generate(
                    input=current_chunk,
                    cache=self.cache,
                    is_final=False,
                    chunk_size=self.chunk_size
                )
                
                # 检查是否有语音
                has_speech = len(res[0]["value"]) > 0
                
                # 处理语音片段
                if has_speech:
                    if not self.is_speaking:
                        # 开始新的语音片段
                        self.is_speaking = True
                        self.speech_start_idx = len(self.current_speech)
                        self.current_speech = [current_chunk]
                        logger.debug("Speech started")
                    else:
                        # 继续当前语音片段
                        self.current_speech.append(current_chunk)
                elif self.is_speaking:
                    # 添加当前帧并检查是否应该结束语音片段
                    self.current_speech.append(current_chunk)
                    current_duration = len(self.current_speech) * self.chunk_size / 1000
                    
                    # 检查是否结束语音（达到最小时长）
                    if current_duration >= self.min_duration:
                        # 合并语音片段
                        speech_audio = np.concatenate(self.current_speech)
                        # 转换回int16格式
                        audio_int16 = (speech_audio * 32768.0).astype(np.int16)
                        logger.debug(f"Speech ended, duration: {current_duration:.3f}s")
                        yield audio_int16.tobytes()
                    
                    # 重置状态
                    self.is_speaking = False
                    self.current_speech = []
                    self.cache = {}
                
            except Exception as e:
                logger.error(f"Error in VAD processing: {e}", exc_info=True)
                self.is_speaking = False
                self.current_speech = []
                self.cache = {}
        
        # 如果这是最后一个数据块，处理剩余的语音片段
        if self.is_speaking and self.current_speech:
            current_duration = len(self.current_speech) * self.chunk_size / 1000
            if current_duration >= self.min_duration:
                # 合并并输出最后的语音片段
                speech_audio = np.concatenate(self.current_speech)
                audio_int16 = (speech_audio * 32768.0).astype(np.int16)
                logger.debug(f"Final speech segment, duration: {current_duration:.3f}s")
                yield audio_int16.tobytes()

    def cleanup(self) -> None:
        """清理资源"""
        self.cache = {}
        self.accumulated_audio = np.array([], dtype=np.float32)
        self.is_speaking = False
        self.current_speech = []
        self.speech_start_idx = 0

def main():
    """测试VAD功能"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,  # 改为 INFO 级别，减少不必要的日志
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # 过滤掉 funasr 的性能日志
    logging.getLogger("funasr").setLevel(logging.WARNING)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='VAD测试程序')
    parser.add_argument('audio_file', help='要测试的音频文件路径')
    parser.add_argument('--chunk-size', type=int, default=200, help='VAD处理的音频块大小(ms)')
    parser.add_argument('--debug', action='store_true', help='是否显示调试信息')
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 初始化VAD模型
    print("\n=== 初始化VAD模型 ===")
    model = AutoModel(
            model="fsmn-vad",
            model_revision="v2.0.4",
            max_end_silence_time=240,
            speech_noise_thres=0.8,
            disable_update=True,
            disable_pbar=True
        )
    print("VAD模型加载完成")
    
    # 读取音频文件
    print(f"\n=== 读取音频文件: {args.audio_file} ===")
    speech, sample_rate = sf.read(args.audio_file)
    duration = len(speech)/sample_rate
    print(f"采样率: {sample_rate}Hz")
    print(f"时长: {duration:.2f}秒")
    
    # 如果音频是多声道的，只取第一个声道
    if len(speech.shape) > 1:
        speech = speech[:, 0]
        print("多声道音频，已转换为单声道")
    
    # 确保音频数据是float32类型，范围在[-1, 1]之间
    if speech.dtype != np.float32:
        if speech.dtype == np.int16:
            speech = speech.astype(np.float32) / 32768.0
        else:
            speech = speech.astype(np.float32)
    
    # 计算chunk大小和总块数
    chunk_stride = int(args.chunk_size * sample_rate / 1000)
    total_chunk_num = int((len(speech)-1)/chunk_stride + 1)
    print(f"\n=== 开始处理音频 ===")
    print(f"分块大小: {args.chunk_size}ms")
    print(f"总块数: {total_chunk_num}")
    
    # 处理音频
    cache = {}
    detected_segments = []
    
    for i in range(total_chunk_num):
        speech_chunk = speech[i*chunk_stride:(i+1)*chunk_stride]
        is_final = i == total_chunk_num - 1
        
        try:
            res = model.generate(
                input=speech_chunk,
                cache=cache,
                is_final=is_final,
                chunk_size=args.chunk_size
            )
            if len(res[0]["value"]):
                time_ms = i * args.chunk_size
                time_s = time_ms / 1000
                detected_segments.append((time_s, res[0]["value"]))
                if args.debug:
                    print(f"检测到语音 @ {time_s:.2f}s: {res[0]['value']}")
        except Exception as e:
            print(f"处理错误 @ chunk {i}: {e}")
    
    # 打印结果摘要
    print(f"\n=== 检测结果 ===")
    if detected_segments:
        print(f"共检测到 {len(detected_segments)} 个语音片段:")
        for i, (time_s, value) in enumerate(detected_segments, 1):
            print(f"{i}. {time_s:.2f}s: {value}")
    else:
        print("未检测到语音片段")


if __name__ == "__main__":
    main() 