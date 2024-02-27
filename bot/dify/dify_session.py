from bot.session_manager import Session
from common.log import logger
from config import conf

"""
    e.g.  [
        {"role": "user", "content": "Who won the world series in 2020?"},
        {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        {"role": "user", "content": "Where was it played?"}
    ]
"""
system_prompt = "you are an AI assistant, please answer user's questions with language the same as the user's"

class DifySession(Session):
    def __init__(self, session_id, system_prompt=system_prompt, model=conf().get("model") or "text-davinci-003"):
        super().__init__(session_id, system_prompt)
        self.model = model
        self.conversation_id = None  # Add this line
        self.is_new = True  # Initialize the is_new attribute here
        self.reset()

    def __str__(self):
        return f"Session(id={self.session_id}, model={self.model}, messages={self.messages})"

    def mark_as_used(self):
        self.is_new = False  # The session is no longer new

    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True
        try:
            cur_tokens = self.calc_tokens()
        except Exception as e:
            precise = False
            if cur_tokens is None:
                raise e
            logger.debug("Exception when counting tokens precisely for query: {}".format(e))
        while cur_tokens > max_tokens:
            if len(self.messages) >= 2:
                self.messages.pop(0)
                self.messages.pop(0)
            else:
                logger.debug("max_tokens={}, total_tokens={}, len(messages)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break
            if precise:
                cur_tokens = self.calc_tokens()
            else:
                cur_tokens = cur_tokens - max_tokens
        return cur_tokens

    def calc_tokens(self):
        return num_tokens_from_messages(self.messages, self.model)


def num_tokens_from_messages(messages, model):
    """Returns the number of tokens used by a list of messages."""
    tokens = 0
    for msg in messages:
        tokens += len(msg["content"])
    return tokens
