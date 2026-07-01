import inspect
import logging
from core.auxiliary import (
    execute_queries, 
    fill_prompt_with_interview, 
    chat_to_string
)
from io import BytesIO
from base64 import b64decode
from openai import OpenAI

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "none"


class LLMAgent(object):
    """ Class to manage LLM-based agents. """
    def __init__(self, api_key, timeout:int=30, max_retries:int=3):
        self.client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._chat_create_supports_reasoning_effort = self._supports_chat_create_parameter("reasoning_effort")
        logging.info("OpenAI client instantiated. Should happen only once!")

    def _supports_chat_create_parameter(self, parameter:str) -> bool:
        """Return whether the installed SDK exposes a Chat Completions parameter."""
        try:
            return parameter in inspect.signature(self.client.chat.completions.create).parameters
        except (TypeError, ValueError):
            return False

    def load_parameters(self, parameters:dict):
        """ Load interview guidelines for prompt construction. """
        self.parameters = parameters

    def transcribe(self, audio) -> str:
        """ Transcribe audio file. """
        audio_file = BytesIO(b64decode(audio))
        audio_file.name = "audio.webm"

        response = self.client.audio.transcriptions.create(
          model="whisper-1", 
          file=audio_file,
          language="en" # English language input
        )
        return response.text

    def construct_query(self, tasks:list, history:list, user_message:str=None) -> dict:
        """ 
        Construct OpenAI API completions query, 
        defaults to `gpt-5.5` model, `none` reasoning effort, 300 token answer limit,
        and temperature of 0.
        For details see https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create.
        """
        queries = {}
        for task in tasks:
            task_parameters = self.parameters[task]
            reasoning_effort = task_parameters.get("reasoning_effort", DEFAULT_REASONING_EFFORT)
            query = {
                "messages": [{
                    "role":"user", 
                    "content": fill_prompt_with_interview(
                        task_parameters['prompt'], 
                        self.parameters['interview_plan'],
                        history,
                        user_message=user_message
                    )
                }],
                "model": task_parameters.get('model', DEFAULT_MODEL),
                # Some models reject `max_tokens`; `max_completion_tokens` is the supported replacement.
                "max_completion_tokens": task_parameters.get(
                    "max_completion_tokens",
                    task_parameters.get("max_tokens", 300),
                ),
                "temperature": task_parameters.get('temperature', 0)
            }

            if self._chat_create_supports_reasoning_effort:
                query["reasoning_effort"] = reasoning_effort
            else:
                extra_body = dict(task_parameters.get("extra_body", {}))
                extra_body["reasoning_effort"] = reasoning_effort
                query["extra_body"] = extra_body

            queries[task] = query

        return queries

    def review_answer(self, message:str, history:list) -> bool:
        """ Moderate answers: Are they on topic? """
        response = execute_queries(
            self.client.chat.completions.create,
            self.construct_query(['moderator'], history, message)
        )
        return "yes" in response["moderator"].lower()

    def review_question(self, next_question:str) -> bool:
        """ Moderate questions: Are they flagged by the moderation endpoint? """
        response = self.client.moderations.create(
            model="omni-moderation-latest",
            input=next_question,
        )
        return response.to_dict()["results"][0]["flagged"]
        
    def probe_within_topic(self, history:list) -> str:
        """ Return next 'within-topic' probing question. """
        response = execute_queries(
            self.client.chat.completions.create,
            self.construct_query(['probe'], history)
        )
        return response['probe']

    def transition_topic(self, history:list) -> tuple[str, str]:
        """ 
        Determine next interview question transition from one topic
        cluster to the next. If have defined `summarize` model in parameters
        will also get summarization of interview thus far.
        """
        summarize = self.parameters.get('summarize')
        tasks = ['summary','transition'] if summarize else ['transition']
        response = execute_queries(
            self.client.chat.completions.create,
            self.construct_query(tasks, history)
        )
        return response['transition'], response.get('summary', '')
