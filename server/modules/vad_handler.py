import os
import sys

import soundfile

# 将项目根目录添加到Python路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

import logging
import numpy as np
from typing import Generator
from threading import Event
from funasr import AutoModel

from server.modules.base_handler import BaseHandler
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


class VADHandler(BaseHandler):
    """语音活动检测处理器，使用FunASR的FSMN-VAD模型"""

    def __init__(self, stop_event: Event):
        super().__init__(stop_event)

    def setup(self, should_listen: Event) -> None:
        self.should_listen = should_listen

        self.chunk_size_ms = 240  # VAD duration
        self.chunk_size = int(16000 / 1000 * self.chunk_size_ms)
        self.reply_silence_duration = 100  # Reply duration
        self.truncate_silence_duration = 1440  # Truncate duration
        self.max_audio_duration = 120000  # 120 seconds

        # 初始化VAD模型
        self.model = AutoModel(
            model="fsmn-vad",
            model_revision="v2.0.4",
            disable_pbar=True,  # 禁用进度条
            disable_update=True,
            max_end_silence_time=0  # 禁用内部的静音检测
        )
        self.reset()
        logging.info("FSMN-VAD model loaded")

    def reset(self):
        self.audio_buffer = np.array([], dtype=np.float32)
        self.audio_process_last_pos_ms = 0
        self.vad_cache = {}
        self.vad_last_pos_ms = -1
        self.vad_cached_segments = []

    def truncate(self):
        if self.audio_process_last_pos_ms < self.truncate_silence_duration:
            return
        self.audio_buffer = self.audio_buffer[-self.chunk_size_ms * 16:] # Keep the last chunk

        self.audio_process_last_pos_ms = 0 # The last chunk will be processed again
        self.vad_cache = {}

    def get_unprocessed_duration(self):
        return self.audio_buffer.shape[0] / 16 - self.audio_process_last_pos_ms

    def get_silence_duration(self):
        if self.vad_last_pos_ms == -1:
            return 0
        return self.audio_buffer.shape[0] / 16 - self.vad_last_pos_ms


    def process(self, frame: bytes) -> Generator[np.ndarray, None, None]:
        if not self.should_listen.is_set():
            return

        # 将音频数据转换为float32格式
        frame_fp32 = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768
        self.audio_buffer = np.concatenate([self.audio_buffer, frame_fp32])
        current_duration = self.audio_buffer.shape[0] / 16

        # 如果累积的音频数据足够长，进行VAD处理
        while self.get_unprocessed_duration() >= self.chunk_size_ms:
            # 提取当前chunk
            beg = self.audio_process_last_pos_ms * 16
            end = beg + self.chunk_size
            chunk = self.audio_buffer[beg:end]
            self.audio_process_last_pos_ms += self.chunk_size_ms

            # 获取VAD输出
            res = self.model.generate(
                input=chunk,
                cache=self.vad_cache,
                is_final=False,
                chunk_size=self.chunk_size_ms
            )

            # 未检测到音频
            if len(res[0]['value']) <= 0:
                if len(self.vad_cached_segments) == 0:
                    self.truncate()
                    return
            else:
                self.vad_cached_segments.extend(res[0]['value'])
                self.vad_last_pos_ms = self.vad_cached_segments[-1][1]
                logging.debug(f'VAD segments: {self.vad_cached_segments}')

                # still going
                if self.vad_last_pos_ms == -1:
                    continue

                silence_duration = self.get_silence_duration()
                if silence_duration >= self.reply_silence_duration:
                    logger.info(f'Silence detected (duration: {silence_duration:.2f}ms), {self.audio_buffer.shape[0] / 16:.2f}ms of audio data')
                    yield self.audio_buffer
                    self.cleanup()
                    break

                if current_duration >= self.max_audio_duration:
                    logger.info(f'Max audio duration reached (duration: {current_duration:.2f}ms)')
                    yield self.audio_buffer
                    self.cleanup()
                    break

        # logging.info(f'Processed {current_duration:.2f}ms of audio data')

    def cleanup(self) -> None:
        """清理资源"""
        self.cache = {}
        self.is_speaking = False
        self.current_speech = []
        self.speech_start_idx = 0
        self.vad_cached_segments = []

if __name__ == '__main__':

    # 设置日志级别为DEBUG以查看更详细的信息
    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

    chunk_size = 200 #ms

    # 创建VAD处理器
    vad_handler = VADHandler(
        stop_event=Event(),
    )
    should_listen = Event()
    vad_handler.setup(should_listen=should_listen)

    # 读取测试音频文件
    import wave

    wav_file_url = "C:\\Users\\17870\\PycharmProjects\\franco-xiaozhi\\天龙八部0107.wav"
    wav_file = wave.open(wav_file_url, "rb")
    if wav_file.getsampwidth() != 2 or wav_file.getnchannels() != 1 or wav_file.getframerate() != 16000:
        raise ValueError("WAV file must be 16kHz, 16-bit, mono")
    should_listen.set()

    # 处理音频数据
    done = False
    while not done:
        frame = wav_file.readframes(1024)
        if not frame:
            break

        for b in vad_handler.process(frame):
            if b is not None:
                done = True
                # use sf to get the wav file buffer from the audio buffer
                soundfile.write("res.ogg", b, 16000, format='ogg', subtype='OPUS')




