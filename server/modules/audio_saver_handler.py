from asyncio import Event
from datetime import datetime
from pathlib import Path
from typing import Generator

import soundfile
from numpy import ndarray

from server.modules.base_handler import BaseHandler


class AudioSaverHandler(BaseHandler):
    """音频保存处理器"""

    def __init__(self, stop_event: Event):
        super().__init__(stop_event)
        self.channels = None
        self.sample_rate = None
        self.save_dir = None

    def setup(self, save_dir: str = "audio_saves", sample_rate: int = 16000, channels: int = 1):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        self.channels = channels
        
    def new_file(self) -> str:
        """创建新的WAV文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.ogg"
        return self.save_dir / filename

    def process(self, audio_chunk) -> Generator[ndarray, None, None]:
        soundfile.write(self.new_file(), audio_chunk, self.sample_rate, format='ogg', subtype='OPUS')
        yield audio_chunk