import logging
from asyncio import Event
from typing import Generator
from server.modules.base_handler import BaseHandler
from server.modules.chat import Chat
from openai import OpenAI

from server.modules.tts_handler import TTSMessage, TTSMessageType


class LLMHandler(BaseHandler):

    def __init__(self, stop_event: Event):
        super().__init__(stop_event)

    def setup(
            self,
            model_name="",
            device="cuda",
            gen_kwargs={},
            base_url=None,
            api_key=None,
            stream=False,
            user_role="user",
            chat_size=1,
            init_chat_role="system",
            init_chat_prompt="You are a helpful AI assistant, Please reply to my message in chinese.",
    ):
        self.model_name = model_name
        self.stream = stream
        self.chat = Chat(chat_size)
        if init_chat_role:
            if not init_chat_prompt:
                raise ValueError(
                    "An initial prompt needs to be specified when setting init_chat_role."
                )
            self.chat.init_chat({"role": init_chat_role, "content": init_chat_prompt})
        self.user_role = user_role
        self.client = OpenAI(api_key=api_key, base_url=base_url)

        # TODO
        # self.warmup()

    def process(self, prompt) -> Generator[str, None, None]:
        logging.debug("call api language model...")
        self.chat.append({"role": self.user_role, "content": prompt})
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": self.user_role, "content": prompt},
            ],
            stream=self.stream
        )
        if self.stream:
            yield TTSMessage(type=TTSMessageType.START)
            generated_text, printable_text = "", ""
            for chunk in response:
                new_text = chunk.choices[0].delta.content or ""
                generated_text += new_text
                sentences = printable_text
                # sentences = sent_tokenize(printable_text)
                # if len(sentences) > 1:
                #     yield TTSMessage(sentences[0])
                #     printable_text = new_text
            self.chat.append({"role": "assistant", "content": generated_text})
            logging.info("assistant: " + generated_text)
            # don't forget last sentence
            yield TTSMessage(text=generated_text, type=TTSMessageType.TXT)
            yield TTSMessage(type=TTSMessageType.END)
        else:
            generated_text = response.choices[0].message.content
            self.chat.append({"role": "assistant", "content": generated_text})
            yield generated_text
            