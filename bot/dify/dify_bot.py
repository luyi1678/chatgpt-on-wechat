# encoding:utf-8

import time

import openai
import openai.error

from bot.bot import Bot
from bot.dify.dify_session import DifySession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf
import requests
import json
import sseclient

user_session = dict()


class DifyBot(Bot):
    def __init__(self):
        super().__init__()
        self.api_key = conf().get("dify_api_key")
        self.api_url = conf().get("dify_api_url")
        self.conversation_id = None
        logger.info("[DIFY] url={}".format(self.api_url))
        self.model = conf().get("model") or "text-davinci-003"
        self.args = {}
        self.sessions = SessionManager(DifySession, model=conf().get("model") or "text-davinci-003")


    def reply(self, query, context=None):
        logger.info(f"[DIFY] Received query from user: {query}")
        # acquire reply content
        if context and context.type:
            print("context:", context)
            logger.info("[OPEN_AI] query={}".format(query))
            session_id = context["session_id"]
            logger.info(f"[DIFY] Session ID: {session_id}")
            logger.info(f"[DIFY] Context: {context}")
            reply = None
            if context.type == ContextType.TEXT:
                logger.info("[DIFY] query={}".format(query))
                # Get from_user_id from context
                receiver = context.kwargs.get('receiver')
                reply = None
                if query == "#清除记忆":
                    self.conversation_id = None
                    self.sessions.clear_session(session_id)
                    reply = Reply(ReplyType.INFO, "记忆已清除")
                elif query == "#清除所有":
                    self.conversation_id = None
                    self.sessions.clear_session(session_id)
                    reply = Reply(ReplyType.INFO, "所有人记忆已清除")
                elif "/new" in query.lower():
                    # User is creating a new conversation
                    self.conversation_id = None
                    self.sessions.clear_session(session_id)
                    reply = Reply(ReplyType.TEXT, '新建成功，开始新的对话吧~~')
                else:
                    session = self.sessions.session_query(query, session_id)
                    # session.conversation_id = self.conversation_id
                    logger.info(f"[DIFY] Session after query processing: {session}")
                    # Use the new streaming method
                    # for partial_reply_content in self.reply_text_streaming(query, receiver):
                    #     # For each chunk of the message, create a Reply and send it
                    #     if partial_reply_content:  # Ensure there's content to send
                    #         reply = Reply(ReplyType.TEXT, partial_reply_content)

                    # result = self.reply_text(query, receiver)
                    logger.info(
                        f"[DIFY] Current conversation_id: {self.conversation_id}, Receiver: {context.get('receiver')}")
                    result = self.reply_text(session,query,receiver)
                    logger.info(f"[DIFY] Result before accessing total_tokens: {result}")
                    if isinstance(result, dict) and "total_tokens" in result:
                        total_tokens, completion_tokens, total_price, reply_content = (
                            result["total_tokens"],
                            result["completion_tokens"],
                            result["total_price"],
                            result["content"],
                        )
                        logger.debug(
                            "[DIFY] new_query={}, conversation_id={}, reply_cont={}, completion_tokens={}".format(
                                query, self.conversation_id, reply_content, completion_tokens
                            )
                        )

                        if total_tokens == 0:
                            reply = Reply(ReplyType.ERROR, reply_content)
                        else:
                            self.sessions.session_reply(reply_content, session_id, total_tokens)
                            session.conversation_id = result.get('conversation_id', self.conversation_id)
                            reply = Reply(ReplyType.TEXT, reply_content)
                    else:
                        logger.error(f"[DIFY] Unexpected result format or missing keys: {result}")
                        reply = Reply(ReplyType.ERROR, "Unexpected result format or missing keys")
                return reply
            elif context.type == ContextType.IMAGE_CREATE:
                ok, retstring = self.create_img(query, 0)
                reply = None
                if ok:
                    reply = Reply(ReplyType.IMAGE_URL, retstring)
                else:
                    reply = Reply(ReplyType.ERROR, retstring)
                return reply
    # blocking mode
    # def reply_text(self, query, receiver, retry_count=0):
    #     logger.info("[DIFY] model={}".format(self.model))
    #     print("query:", query)
    #
    #     # Check if the user's query is "/new" to update conversation_id
    #     if "/new" in query.lower():
    #         conversation_id = None  # Set to None to request a new conversation_id
    #     else:
    #         conversation_id = self.conversation_id
    #
    #     print("conversation_id:", conversation_id)
    #     headers = {
    #         'Authorization': f'Bearer {self.api_key}',
    #         'Content-Type': 'application/json'
    #     }
    #     data = {
    #         "inputs": {},
    #         "response_mode": "blocking",
    #         "query": query,
    #         "user": receiver,
    #         "conversation_id": conversation_id
    #     }
    #     response = requests.post(self.api_url, json=data, headers=headers)
    #
    #     if response.status_code == 200:
    #         answer = response.json()['answer']
    #         logger.info(f"[DIFY] answer={answer}")
    #         total_tokens = response.json()['metadata']['usage']['total_tokens']
    #         completion_tokens = response.json()['metadata']['usage']['completion_tokens']
    #         total_price = response.json()['metadata']['usage']['total_price']
    #
    #         # Update the conversation_id if a new one is received
    #         new_conversation_id = response.json().get('conversation_id')
    #         if new_conversation_id:
    #             self.conversation_id = new_conversation_id
    #
    #         logger.info("[DIFY] reply={}".format(answer))
    #         return {
    #             "total_tokens": total_tokens,
    #             "completion_tokens": completion_tokens,
    #             "total_price": total_price,
    #             "content": answer,
    #             "conversation_id": self.conversation_id  # Include the conversation_id in the result
    #         }
    #     else:
    #         return "Sorry, there was an error processing your message."

        # streaming mode
    def reply_text(self, session: DifySession,query, receiver, retry_count=0):
        try:
            logger.info("[DIFY] model={}".format(self.model))
            # query = str(session)
            print("query:", query)

            # Check if the user's query is "/new" to update conversation_id
            if session.is_new or "/new" in query.lower():
                session.conversation_id = None
                session.mark_as_used()# Set to None to request a new conversation_id

            print("conversation_id:", session.conversation_id)
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                "inputs": {},
                "response_mode": "streaming",
                "query": query,
                "user": receiver,
                "conversation_id": session.conversation_id
            }
            logger.error(f"[DIFY] data before query '{data}'")
            response = requests.post(self.api_url, json=data, headers=headers, stream=True)
            logger.error(f"[DIFY] API response for query '{query}': {response.status_code}, Body: {response.text}")

            if response.status_code == 200:
                client = sseclient.SSEClient(response)
                all_answers = []  # List to accumulate all answers
                total_tokens = completion_tokens = total_price = 0
                for event in client.events():
                    event_data = json.loads(event.data)
                    if event_data.get('event') == 'message':
                        # This block executes for message events
                        if 'answer' in event_data:
                            all_answers.append(event_data['answer'])  # Accumulate the answer part
                    elif event_data.get('event') == 'message_end':
                        # This block executes for the message_end event
                        metadata = event_data.get('metadata', {})
                        usage = metadata.get('usage', {})
                        total_tokens = usage.get('total_tokens', 0)
                        completion_tokens = usage.get('completion_tokens', 0)
                        total_price = usage.get('total_price', 0)

                        # Update the conversation_id if a new one is received
                        new_conversation_id = event_data.get('conversation_id')
                        if new_conversation_id:
                            session.conversation_id = new_conversation_id

                complete_answer = ''.join(all_answers)
                logger.info(f"[DIFY] answer={complete_answer}")
                logger.info("[DIFY] reply={}".format(complete_answer))

                return {
                    "total_tokens": total_tokens,
                    "completion_tokens": completion_tokens,
                    "total_price": total_price,
                    "content": complete_answer,
                    "conversation_id": session.conversation_id  # Include the conversation_id in the result
                }
            else:
                logger.error("[DIFY] Error in streaming response: Status code {}".format(response.status_code))
                return "Sorry, there was an error processing your message."
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[DIFY_AI] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[DIFY_AI] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIConnectionError):
                logger.warn("[DIFY_AI] APIConnectionError: {}".format(e))
                need_retry = False
                result["content"] = "我连接不到你的网络"
            else:
                logger.warn("[DIFY_AI] Exception: {}".format(e))
                need_retry = False
                self.sessions.clear_session(session.session_id)

            if need_retry:
                logger.warn("[DIFY_AI] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:
                return result

    # def reply_text_streaming(self, query, receiver):
    #     # Check for commands like before
    #     # Set up headers and data payload with "response_mode": "streaming"
    #     logger.info("[DIFY] model={}".format(self.model))
    #     print("query:", query)
    #
    #     # Check if the user's query is "/new" to update conversation_id
    #     if "/new" in query.lower():
    #         conversation_id = None  # Set to None to request a new conversation_id
    #     else:
    #         conversation_id = self.conversation_id
    #
    #     print("conversation_id:", conversation_id)
    #     headers = {
    #         'Authorization': f'Bearer {self.api_key}',
    #         'Content-Type': 'application/json'
    #     }
    #     data = {
    #         "inputs": {},
    #         "response_mode": "streaming",
    #         "query": query,
    #         "user": receiver,
    #         "conversation_id": conversation_id
    #     }
    #
    #     response = requests.post(self.api_url, json=data, headers=headers, stream=True)
    #
    #     if response.status_code == 200:
    #         client = sseclient.SSEClient(response)
    #         sentence_accumulator = ''  # Accumulate sentences here
    #
    #         for event in client.events():
    #             event_data = json.loads(event.data)
    #             if event_data.get('event') == 'message':
    #                 # Append each piece of the message to the accumulator
    #                 sentence_accumulator += event_data.get('answer', '')
    #                 # Check if you have complete sentences
    #                 sentences = sentence_accumulator.split(
    #                     '.')  # Simple split, you may need more sophisticated splitting
    #                 if len(sentences) > 1:  # More than one sentence available
    #                     for i in range(len(sentences) - 1):  # Yield all but the last (possibly incomplete) sentence
    #                         yield sentences[i] + '.'  # Re-add the delimiter for clarity
    #                     sentence_accumulator = sentences[-1]  # Keep the last part for further accumulation
    #             elif event_data.get('event') == 'message_end':
    #                 # Handle the end of the message
    #                 yield sentence_accumulator  # Yield any remaining text
    #                 break  # Exit the loop as the message is complete
    #     else:
    #         yield "Sorry, there was an error processing your message."



