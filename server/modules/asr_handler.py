import logging
from asyncio import Event
from typing import Generator

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

from server.modules.base_handler import BaseHandler

class AsrHandler(BaseHandler):
    def __init__(self, stop_event: Event):
        super().__init__(stop_event)
        self.sense_model = None

    def setup(self) -> None:
        self.sense_model = AutoModel(
            model="iic/SenseVoiceSmall",
            # device="cuda",
            disable_update=True,
            disable_pbar=True,
        )
    
    def process(self, audio_buffer) -> Generator[str, None, None]:
        result = self.sense_model.generate(input=audio_buffer, cache={}, language='zh', use_itn=True)
        data = rich_transcription_postprocess(result[0]['text'])

        logging.info(f"ASR result: {data}")
        yield data


