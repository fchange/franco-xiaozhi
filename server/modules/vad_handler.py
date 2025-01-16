import logging
import numpy as np
from typing import Generator, Any
from threading import Event
from funasr import AutoModel

from server.modules.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class VADHandler(BaseHandler):
    """语音活动检测处理器，使用FunASR的FSMN-VAD模型"""
    
    def setup(self, should_listen: Event, sample_rate: int = 16000, 
             chunk_size: int = 200, # chunk大小(ms)
             min_speech_ms: int = 300) -> None:
        """
        设置VAD参数
        
        Args:
            should_listen: 控制是否进行语音检测的事件
            sample_rate: 音频采样率
            chunk_size: 每次处理的音频长度(ms)
            min_speech_ms: 最小语音时长(ms)
        """
        self.should_listen = should_listen
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.min_speech_ms = min_speech_ms
        
        # 计算每个chunk的采样点数
        self.chunk_stride = int(self.chunk_size * self.sample_rate / 1000)
        
        # 初始化VAD模型
        self.model = AutoModel(model="fsmn-vad", model_revision="v2.0.4")
        logger.info("FSMN-VAD model loaded")
        
        # 初始化状态
        self.cache = {}  # VAD模型的缓存
        self.accumulated_audio = np.array([], dtype=np.float32)  # 累积的音频数据
        
        logger.info(f"VAD initialized with: sample_rate={sample_rate}, "
                   f"chunk_size={chunk_size}ms, min_speech_ms={min_speech_ms}ms")

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
            
            # VAD处理
            res = self.model.generate(
                input=current_chunk,
                cache=self.cache,
                is_final=False,
                chunk_size=self.chunk_size
            )
            
            # 如果检测到语音段
            if len(res[0]["value"]) > 0:
                logger.debug(f"VAD detected speech segment: {res[0]['value']}")
                # 将float32转回int16
                audio_int16 = (current_chunk * 32768.0).astype(np.int16)
                yield audio_int16.tobytes()

    def cleanup(self) -> None:
        """清理资源"""
        # 处理剩余的音频数据
        if len(self.accumulated_audio) > 0:
            res = self.model.generate(
                input=self.accumulated_audio,
                cache=self.cache,
                is_final=True,
                chunk_size=self.chunk_size
            )
            if len(res[0]["value"]) > 0:
                logger.debug(f"VAD final speech segment: {res[0]['value']}")
                audio_int16 = (self.accumulated_audio * 32768.0).astype(np.int16)
                for queue in self.output_queues:
                    queue.put(audio_int16.tobytes())
        
        self.cache = {}
        self.accumulated_audio = np.array([], dtype=np.float32) 