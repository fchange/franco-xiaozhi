import os
import wave
from datetime import datetime
from pathlib import Path
from typing import Generator, Any

from server.modules.base_handler import BaseHandler


class AudioSaverHandler(BaseHandler):
    """音频保存处理器"""
    
    def setup(self, save_dir: str = "audio_saves", sample_rate: int = 16000, channels: int = 1):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        self.channels = channels
        self.wave_file = None
        
    def _create_new_wave_file(self) -> None:
        """创建新的WAV文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.wav"
        self.current_file = self.save_dir / filename
        
        self.wave_file = wave.open(str(self.current_file), 'wb')
        self.wave_file.setnchannels(self.channels)
        self.wave_file.setsampwidth(2)  # 16-bit audio
        self.wave_file.setframerate(self.sample_rate)

    def process(self, audio_chunk: bytes) -> Generator[bytes, None, None]:
        if self.wave_file is None:
            self._create_new_wave_file()
            
        if audio_chunk and len(audio_chunk) > 0:
            self.wave_file.writeframes(audio_chunk)
            yield audio_chunk

    def cleanup(self) -> None:
        """清理资源，关闭WAV文件"""
        if self.wave_file is not None:
            self.wave_file.close()
            self.wave_file = None 