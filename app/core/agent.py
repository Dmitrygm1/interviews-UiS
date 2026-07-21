import inspect
import logging
import os
import random
import time
from core.auxiliary import (
    execute_queries, 
    fill_prompt_with_interview, 
    chat_to_string
)
from io import BytesIO
from base64 import b64decode
from openai import OpenAI

DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_REASONING_EFFORT = "none"


class LLMAgent(object):
    """ Class to manage LLM-based agents. """
    def __init__(self, api_key, timeout:int=30, max_retries:int=3):
        self.mock_openai = os.getenv("LOAD_TEST_MOCK_OPENAI", "").lower() in {"1", "true", "yes"}
        if self.mock_openai:
            self.client = None
            self._chat_create_supports_reasoning_effort = False
            logging.warning("LOAD_TEST_MOCK_OPENAI is enabled. OpenAI calls will be faked.")
        else:
            self.client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
            self._chat_create_supports_reasoning_effort = self._supports_chat_create_parameter("reasoning_effort")
            logging.info("OpenAI client instantiated. Should happen only once!")

    def _mock_delay(self, kind:str="chat") -> None:
        """Sleep to simulate OpenAI latency during explicit load tests."""
        default_delay = os.getenv("LOAD_TEST_MOCK_DELAY_SECONDS") or "0"
        delay = float(os.getenv(f"LOAD_TEST_MOCK_{kind.upper()}_DELAY_SECONDS") or default_delay)
        jitter = float(os.getenv("LOAD_TEST_MOCK_JITTER_SECONDS") or "0")
        if jitter > 0:
            delay += random.uniform(0, jitter)
        if delay > 0:
            time.sleep(delay)

    def _mock_question(self, history:list, prefix:str) -> str:
        state = history[-1] if history else {}
        topic = state.get("topic_idx", "?")
        question = state.get("question_idx", "?")
        return f"{prefix} load-test question for topic {topic}, turn {question}?"

    def _supports_chat_create_parameter(self, parameter:str) -> bool:
        """Return whether the installed SDK exposes a Chat Completions parameter."""
        try:
            return parameter in inspect.signature(self.client.chat.completions.create).parameters
        except (TypeError, ValueError):
            return False

    def load_parameters(self, parameters:dict):
        """ Load interview guidelines for prompt construction. """
        self.parameters = parameters

    def _usage_context(self, history:list) -> dict:
        """Return metadata stored with usage logs for downstream reporting."""
        state = history[-1] if history else {}
        return {
            "session_id": state.get("session_id"),
            "interview_id": self.parameters.get("_name"),
        }

    def transcribe(self, audio) -> str:
        """ Transcribe audio file. """
        if self.mock_openai:
            self._mock_delay("transcribe")
            return "Mock transcription for load testing."

        audio_file = BytesIO(b64decode(audio))
        audio_file.name = "audio.webm"

        response = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            # language="no", #norwegian transcription
            # prompt=(
            #     "Dette er et forskningsintervju på norsk. "
            #     "Transkriber talen på norsk slik den blir sagt. "
            #     "Ikke oversett til engelsk."
            # ),
        )
        return response.text

    def construct_query(self, tasks:list, history:list, user_message:str=None) -> dict:
        """ 
        Construct OpenAI API completions query, 
        defaults to `gpt-5.6-terra` model, `none` reasoning effort, 300 token answer limit,
        and temperature of 0.
        For details see https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create.
        """
        queries = {}
        for task in tasks:
            task_parameters = self.parameters[task]
            reasoning_effort = task_parameters.get("reasoning_effort", DEFAULT_REASONING_EFFORT)
            model = task_parameters.get('model', DEFAULT_MODEL)
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
                "model": model,
                # Some models reject `max_tokens`; `max_completion_tokens` is the supported replacement.
                "max_completion_tokens": task_parameters.get(
                    "max_completion_tokens",
                    task_parameters.get("max_tokens", 300),
                ),
                "temperature": task_parameters.get('temperature', 0)
            }

            extra_body = dict(task_parameters.get("extra_body", {}))

            # Interview prompts contain respondent-specific content before a reusable
            # 1,024-token prefix. Disable billable GPT-5.6 implicit cache writes unless
            # an interview configuration explicitly opts into another cache mode.
            if str(model).startswith("gpt-5.6"):
                prompt_cache_options = dict(extra_body.get("prompt_cache_options", {}))
                prompt_cache_options.setdefault("mode", "explicit")
                extra_body["prompt_cache_options"] = prompt_cache_options

            if self._chat_create_supports_reasoning_effort:
                query["reasoning_effort"] = reasoning_effort
            else:
                extra_body["reasoning_effort"] = reasoning_effort

            if extra_body:
                query["extra_body"] = extra_body

            queries[task] = query

        return queries

    def review_answer(self, message:str, history:list) -> bool:
        """ Moderate answers: Are they on topic? """
        if self.mock_openai:
            self._mock_delay("chat")
            return True

        response = execute_queries(
            self.client.chat.completions.create,
            self.construct_query(['moderator'], history, message),
            usage_context=self._usage_context(history),
        )
        return "yes" in response["moderator"].lower()

    def review_question(self, next_question:str) -> bool:
        """ Moderate questions: Are they flagged by the moderation endpoint? """
        if self.mock_openai:
            self._mock_delay("moderation")
            return False

        response = self.client.moderations.create(
            model="omni-moderation-latest",
            input=next_question,
        )
        return response.to_dict()["results"][0]["flagged"]
        
    def probe_within_topic(self, history:list) -> str:
        """ Return next 'within-topic' probing question. """
        if self.mock_openai:
            self._mock_delay("chat")
            return self._mock_question(history, "Mock follow-up")

        response = execute_queries(
            self.client.chat.completions.create,
            self.construct_query(['probe'], history),
            usage_context=self._usage_context(history),
        )
        return response['probe']

    def transition_topic(self, history:list) -> tuple[str, str]:
        """ 
        Determine next interview question transition from one topic
        cluster to the next. If have defined `summarize` model in parameters
        will also get summarization of interview thus far.
        """
        if self.mock_openai:
            self._mock_delay("chat")
            return (
                self._mock_question(history, "Mock transition"),
                "Mock running summary generated during load testing.",
            )

        summarize = self.parameters.get('summarize')
        tasks = ['summary','transition'] if summarize else ['transition']
        response = execute_queries(
            self.client.chat.completions.create,
            self.construct_query(tasks, history),
            usage_context=self._usage_context(history),
        )
        return response['transition'], response.get('summary', '')
