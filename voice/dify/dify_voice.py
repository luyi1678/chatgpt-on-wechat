"""
google voice service
"""
import random
import requests
from voice import audio_convert
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf
from voice.voice import Voice
from common import const
import os
import datetime
import openai
import speech_recognition
from gtts import gTTS


class DifyVoice(Voice):
    def __init__(self):
        self.api_key = conf().get("dify_api_key")
        self.api_url = conf().get("dify_api_url")
        openai.api_key = conf().get("open_ai_api_key")
        self.conversation_id = None
        pass

    def voiceToText(self, voice_file):
        logger.debug("[DifyVoice] voice file name={}".format(voice_file))
        try:
            file = open(voice_file, "rb")
            result = openai.Audio.transcribe("whisper-1", file)
            text = result["text"]
            reply = Reply(ReplyType.TEXT, text)
            logger.info("[Dify-openai] voiceToText text={} voice file name={}".format(text, voice_file))

        except Exception as e:
            reply = Reply(ReplyType.ERROR, "我暂时还无法听清您的语音，请稍后再试吧~")
        finally:
            return reply

    def textToVoice(self, text):
        try:
            # Avoid the same filename under multithreading
            mp3File = "tmp/" + datetime.datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(0, 1000)) + ".mp3"
            tts = gTTS(text=text, lang="zh")
            tts.save(mp3File)
            logger.info("[Dify-Google] textToVoice text={} voice file name={}".format(text, mp3File))
            reply = Reply(ReplyType.VOICE, mp3File)
        except Exception as e:
            reply = Reply(ReplyType.ERROR, str(e))
        finally:
            return reply