from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
import re
import time
import logging 

USAGE_DIR = os.getenv("USAGE_DIR", "./app/data/usage")


def chat_to_string(chat:list, only_topic:int=None, until_topic:int=None) -> str:
    """ Convert messages from chat into one string. """
    topic_history = ""
    for message in chat:
        # If desire specific topic's chat history:
        if only_topic and message['topic_idx'] != only_topic: 
            continue
        if until_topic and message['topic_idx'] == until_topic:
            break
        if message["type"] == "question":
            topic_history += f'Interviewer: "{message["content"]}"\n'
        if message["type"] == "answer":
            topic_history += f'Interviewee: "{message["content"]}"\n'
    return topic_history.strip()

def fill_prompt_with_interview(template:str, topics:list, history:list, user_message:str=None) -> str:
    """ Fill the prompt template with parameters from current interview. """
    state = history[-1]
    current_topic_idx = min(int(state['topic_idx']), len(topics))
    next_topic_idx = min(current_topic_idx + 1, len(topics))
    current_topic_chat = chat_to_string(history, only_topic=current_topic_idx)
    prompt = template.format(
        topics='\n'.join([topic['topic'] for topic in topics]),
        question=state["content"],
        answer=user_message,
        summary=state['summary'] or chat_to_string(history, until_topic=current_topic_idx),
        current_topic=topics[current_topic_idx - 1]["topic"],
        next_interview_topic=topics[next_topic_idx - 1]["topic"],
        current_topic_history=current_topic_chat
    )
    logging.debug(f"Prompt to GPT:\n{prompt}")
    assert not re.findall(r"\{[^{}]+\}", prompt)
    return prompt 


def _plain_dict(value) -> dict:
    """Convert SDK response objects to plain dictionaries where possible."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _safe_usage_filename(session_id:str|None) -> str:
    safe_session_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(session_id or "unknown"))
    return f"{safe_session_id}.jsonl"


def log_openai_usage(task:str, request_args:dict, response, usage_context:dict|None=None) -> None:
    """Append exact token usage for one OpenAI response to a per-session JSONL file."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    usage_context = usage_context or {}
    usage_data = _plain_dict(usage)
    session_id = usage_context.get("session_id")
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "interview_id": usage_context.get("interview_id"),
        "task": task,
        "request_model": request_args.get("model"),
        "response_model": getattr(response, "model", None),
        "prompt_tokens": usage_data.get("prompt_tokens"),
        "completion_tokens": usage_data.get("completion_tokens"),
        "total_tokens": usage_data.get("total_tokens"),
        "usage": usage_data,
    }

    os.makedirs(USAGE_DIR, exist_ok=True)
    usage_path = os.path.join(USAGE_DIR, _safe_usage_filename(session_id))
    with open(usage_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def execute_queries(query, task_args:dict, usage_context:dict|None=None) -> dict:
    """ 
    Execute queries (concurrently if multiple).

    Args:
        query: function to execute
        task_args: (dict) of arguments for each task's query
    Returns:
        suggestions (dict): {task: output} 
    """
    st = time.time()
    suggestions = {}
    with ThreadPoolExecutor(max_workers=len(task_args)) as executor:
        futures = {
            executor.submit(query, **kwargs): task 
                for task, kwargs in task_args.items()
        }
        for future in as_completed(futures):
            task = futures[future]
            response = future.result()
            resp = response.choices[0].message.content.strip("\n\" '''")
            suggestions[task] = resp
            try:
                log_openai_usage(task, task_args[task], response, usage_context)
            except Exception as exc:  # pragma: no cover - logging must not break interviews
                logging.warning(f"Could not write OpenAI usage log for task '{task}': {exc}")

    logging.info("OpenAI query took {:.2f} seconds".format(time.time() - st))
    logging.info(f"OpenAI query returned: {suggestions}")
    return suggestions
