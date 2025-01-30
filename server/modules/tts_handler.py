import logging
from asyncio import Event
from dataclasses import dataclass
from enum import Enum

import pyaudio
import dashscope
from dashscope.audio.tts_v2 import *
from server.modules.base_handler import BaseHandler

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

# 对接文档
# https://help.aliyun.com/zh/model-studio/developer-reference/cosyvoice-large-model-for-speech-synthesis/
class TTSHandler(BaseHandler):
    def __init__(self, stop_event: Event):
        super().__init__(stop_event, is_async=True)
        self.synthesizer = None

    def setup(self, api_key, should_listen:Event, model = "cosyvoice-v1", voice = "longxiang"):
        dashscope.api_key = api_key
        self.should_listen = should_listen

        self.model = model
        self.voice = voice


    def async_process(self, message:TTSMessage):
        if message.type == TTSMessageType.START:
            self.synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=self.voice,
                format=AudioFormat.PCM_16000HZ_MONO_16BIT,
                callback=Callback(self),
            )
        elif message.type == TTSMessageType.TXT:
            self.synthesizer.streaming_call(message.text)
        elif message.type == TTSMessageType.END:
            self.synthesizer.streaming_complete()

class Callback(ResultCallback):
    handler = None

    def __init__(self, handler):
        self.handler = handler

    def on_complete(self):
        logging.debug("speech synthesis task complete successfully.")
        self.handler.should_listen.set()

    def on_error(self, message: str):
        logging.debug(f"speech synthesis task failed, {message}")

    def on_close(self):
        logging.debug("websocket is closed.")

    def on_event(self, message):
        logging.debug(f"recv speech synthsis message {message}")

    def on_data(self, data: bytes) -> None:
        self.handler.put_output(data)
