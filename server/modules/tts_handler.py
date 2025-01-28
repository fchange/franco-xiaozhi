import logging
from asyncio import Event
from dataclasses import dataclass
from enum import Enum

import pyaudio
import dashscope
from dashscope.audio.tts_v2 import *
from server.modules.base_handler import BaseHandler

dashscope.api_key = "TODO"


class TTSMessageType(Enum):
    START = 1
    END = 2
    TXT = 3


@dataclass
class TTSMessage:
    type: TTSMessageType = TTSMessageType.TXT
    text: str = None

    def __init__(self, text=None, type=TTSMessageType.TXT):
        self.type = type
        self.text = text

class TTSHandler(BaseHandler):
    def __init__(self, stop_event: Event):
        super().__init__(stop_event, is_async=True)
        self.model = "cosyvoice-v1"
        self.voice = "longxiang"
        self.synthesizer = None
        self._player = None
        self._stream = None

    def setup(self):
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(
            format=pyaudio.paInt16, channels=1, rate=16000, output=True
        )


    def async_process(self, message:TTSMessage):
        if message.type == TTSMessageType.START:
            self.synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=self.voice,
                format=AudioFormat.PCM_22050HZ_MONO_16BIT,
                callback=Callback(self),
            )
        elif message.type == TTSMessageType.TXT:
            self.synthesizer.streaming_call(message.text)
        elif message.type == TTSMessageType.END:
            self.synthesizer.streaming_complete()

    def cleanup(self):
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
        if self._player is not None:
            self._player.terminate()

class Callback(ResultCallback):
    handler = None

    def __init__(self, handler):
        self.handler = handler

    def on_complete(self):
        logging.debug("speech synthesis task complete successfully.")

    def on_error(self, message: str):
        logging.debug(f"speech synthesis task failed, {message}")

    def on_close(self):
        logging.debug("websocket is closed.")

    def on_event(self, message):
        logging.debug(f"recv speech synthsis message {message}")

    def on_data(self, data: bytes) -> None:
        self.handler.put_output(data)
