import logging
from asyncio import Event

import requests

from server.modules.base_handler import BaseHandler
from server.modules.tts_handler import TTSMessage, TTSMessageType


# 对接文档
# https://docs.siliconflow.cn/api-reference/audio/create-speech
class TTSSiliconflowHandler(BaseHandler):
    def __init__(self, stop_event: Event):
        super().__init__(stop_event, is_async=True)
        self.synthesizer = None

    def setup(self, should_listen: Event, api_key: str):
        self.should_listen = should_listen
        self.api_key = api_key

    def async_process(self, message: TTSMessage):
        if message.type == TTSMessageType.START:
            self.input = ""
        elif message.type == TTSMessageType.TXT:
            self.input += message.text
        elif message.type == TTSMessageType.END:
            url = "https://api.siliconflow.cn/v1/audio/speech"
            payload = {
                "model": "FunAudioLLM/CosyVoice2-0.5B",
                "input": self.input,
                "voice": "FunAudioLLM/CosyVoice2-0.5B:alex",
                "response_format": "pcm",
                "sample_rate": 16000,
                "stream": True,
                "speed": 1,
                "gain": 0
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            spoken_response = requests.request("POST", url, json=payload, headers=headers)
            if spoken_response.status_code == 200:
                for chunk in spoken_response.iter_content(chunk_size=4096):
                    self.put_output(chunk)

            # 等待output清空，再继续
            while self.output_queues[0].qsize() > 0:
                pass
            logging.info("=============================should_listen=============================")
            self.should_listen.set()


if __name__ == '__main__':
    handler = TTSSiliconflowHandler(Event())
    handler.async_process(TTSMessage(type=TTSMessageType.START))
    handler.async_process(TTSMessage("您好"))
    handler.async_process(TTSMessage(type=TTSMessageType.END))
