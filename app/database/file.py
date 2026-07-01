import logging
import os
import json
from datetime import datetime

# By default, save interview JSON data under app/data/json.
DATA_DIR = os.getenv("DATA_DIR", "./app/data/json")

class FileWriter(object):
    def __init__(self) :
        if not os.path.isdir(DATA_DIR): os.makedirs(DATA_DIR)
        logging.info(f"Will write interviews to '{DATA_DIR}'.")

    def _load_session_file(self, filepath:str) -> list:
        with open(filepath, 'r') as f:
            return json.load(f)

    def _find_session_filepath(self, session_id:str) -> str|None:
        """Find an existing session by its stored session_id, regardless of filename."""
        legacy_filepath = os.path.join(DATA_DIR, f"{session_id}.json")
        if os.path.isfile(legacy_filepath):
            return legacy_filepath

        for session_file in os.listdir(DATA_DIR):
            if not session_file.endswith('.json'):
                continue

            filepath = os.path.join(DATA_DIR, session_file)
            try:
                session = self._load_session_file(filepath)
            except (json.JSONDecodeError, OSError):
                logging.warning(f"Skipping unreadable session file '{filepath}'.")
                continue

            if session and session[-1].get('session_id') == session_id:
                return filepath

        return None

    def _timestamp_filename(self, session:list) -> str:
        """Use the interview's first recorded timestamp as a filesystem-safe name."""
        timestamp = session[0].get('time') if session else None
        try:
            dt = datetime.fromisoformat(timestamp)
            timestamp = dt.strftime("%Y-%m-%d_%H-%M-%S-%f")
        except (TypeError, ValueError):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        return f"{timestamp}.json"

    def load_remote_session(self, session_id:str) -> dict:
        """ Retrieve the interview session data from the 'database'. """
        filepath = self._find_session_filepath(session_id)
        if not filepath:
            logging.warning(f"Can't load session '{session_id}': not started!")
            return {}
        return self._load_session_file(filepath)

    def delete_remote_session(self, session_id:str):
        """ Delete session data from the 'database'. """
        filepath = self._find_session_filepath(session_id)
        if not filepath:
            logging.warning(f"Can't delete session '{session_id}': not found!")
            return
        os.remove(filepath)
        logging.info(f"Session '{session_id}' deleted!")

    def update_remote_session(self, session_id:str, session:list):
        """ Update or insert session data in the 'database'. """
        assert 'session_id' in session[-1] and session[-1]['session_id'] == session_id
        filepath = self._find_session_filepath(session_id)
        if not filepath:
            filepath = os.path.join(DATA_DIR, self._timestamp_filename(session))
        with open(filepath, 'w') as f:
            json.dump(session, f)
        logging.info(f"Session '{session_id}' updated!")

    def retrieve_sessions(self, sessions:list=None) -> list:
        """
        Retrieve chat history (list of dicts) for specified sessions
        or *all* sessions if no sessions specified in optional argument.

        Returns
            chats: (list) of "long" form data with one session-message per row, e.g.
                [
                    {'session_id':101, 'time':0, 'role':'interviewer', 'message':'Hello', ...}
                    {'session_id':101, 'time':1, 'role':'respondent', 'message':'World', ...}
                    ...
                ]
        """
        chats = []
        for session_file in os.listdir(DATA_DIR):
            if not session_file.endswith('.json'):
                continue
            filepath = os.path.join(DATA_DIR, session_file)
            session = self._load_session_file(filepath)
            if sessions and (not session or session[-1].get('session_id') not in sessions):
                continue
            # Add all messages in current interview session
            chats.extend(session)

        logging.info(f"Retrieved {len(chats)} messages!")
        return chats
