"""This Flask application provides several endpoints to manage and interact with interview sessions. Each endpoint serves a specific purpose, such as starting an interview session, continuing with the next question, transcribing an audio message from interviewees, loading, deleting, or retrieving stored interviews sessions. Below is a detailed documentation for each endpoint."""

from flask import (
	Flask, 
	request,
	jsonify, 
	render_template, 
	make_response
)
from core import decorators, logic
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)
app.add_url_rule('/healthcheck', 'healthcheck', lambda: ('', 200))

@app.route('/', methods=['GET', 'POST', 'OPTIONS'])
@decorators.handle_500
def index():
	"""For verifying that the app is running or routing Qualtrics API requests."""
	if request.method == 'GET':
		return 'Running!'
	if request.method == 'OPTIONS':
		response = make_response('', 204)
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
		response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
		return response
	body = request.get_json(force=True, silent=True) or {}
	route = body.get('route')
	payload = body.get('payload', {}) or {}
	if route == 'next':
		required = [key for key in ('session_id', 'interview_id') if key not in payload]
		if required:
			raise ValueError(f"Missing required fields for 'next': {', '.join(required)}")
		response = logic.next_question(
			payload['session_id'],
			payload['interview_id'],
			payload.get('user_message')
		)
	elif route == 'transcribe':
		if 'audio' not in payload:
			raise ValueError("Missing audio payload for transcription.")
		response = logic.transcribe(payload['audio'])
	elif route == 'retrieve':
		sessions = payload.get('sessions')
		response = logic.retrieve_sessions(sessions)
	else:
		raise ValueError("Invalid request. Please try again.")
	return jsonify(response)

@app.route('/<interview_id>/<session_id>', methods=['GET'])
@decorators.handle_500
def landing(interview_id:str, session_id:str):
	"""Endpoint: /<interview_id>/<session_id> (GET)
	----------------------------------
	Description:
		This endpoint serves as the landing (start) page for a given interview session. It initializes the interview session and renders the chat page with the session data. To start an interview, simply navigate to the following URL:
		http://http://127.0.0.1:8000/<interview_id>/<session_id>
		and replace the placeholders with the interview ID and session ID. Note that the interview_id must be a valid key in the INTERVIEW_PARAMETERS dictionary in app/parameters.py.

	Input Arguments:
		- interview_id (str): The unique identifier for the interview parameters to be used (from app/parameters.py).
		- session_id (str): A unique identifier for the session.

	Example Query:
		Using Python's requests package:
			```
			response = requests.get('http://127.0.0.1:8000/INTERVIEW_ID/SESSION_ID')
			```

		Using the command line with curl:
			```
			curl http://127.0.0.1:8000/INTERVIEW_ID/SESSION_ID
			```
	"""
	response = logic.begin_interview_session(session_id, interview_id)
	return render_template('chat.html', data=response)

@app.route('/next', methods=['POST'])
@decorators.handle_500
def next():
	"""Endpoint: /next/ (POST)
	----------------------------------
	Description:
		This endpoint is called internally by the app to continue the interview with the next question. It returns the next interview question to be shown to the interviewee.

	Input Arguments:
		- JSON payload containing the session_id (str), interview_id (str) and user_message (str).

	Example Query:
	Using Python's requests package:
		```
		payload = {
			"session_id": "67890",
			"interview_id": "STOCK_MARKET",
			"user_message": "I don't like risky investments"
		}
		response = requests.post('http://127.0.0.1:8000/next', json=payload)
		```
	Using the command line with curl:
		```
		curl -X POST -H "Content-Type: application/json" -d '{"session_id": "67890", "interview_id": "STOCK_MARKET", "response": "I don't like risky investments"}' http://127.0.0.1:8000/next
		```
	"""
	payload = request.get_json(force=True)
	response = logic.next_question(**payload)
	return jsonify(response)

@app.route('/transcribe', methods=['POST'])
@decorators.handle_500
def transcribe():
	"""Endpoint: /transcribe (POST)
	----------------------------------
	Description:
		This endpoint is called to transcribe an audio message recorded by the interviewee. It processes the audio input and returns the transcribed text.
	
	Input Arguments:
		JSON payload containing the audio (str) to be transcribed.
	
	Example Query:
		Using Python's requests package:
		```
		payload = {
			"audio": "base64_encoded_audio_string"
		}
		response = requests.post('http://127.0.0.1:8000/transcribe', json=payload)
		```

	Using the command line with curl:
		```
		curl -X POST -H "Content-Type: application/json" -d '{"audio": "base64_encoded_audio_string"}' http://127.0.0.1:8000/transcribe
		```
	"""
	payload = request.get_json(force=True)
	response = logic.transcribe(**payload)
	return jsonify(response)

@app.route('/load/<session_id>', methods=['GET'])
@decorators.handle_500
def load(session_id:str):
	"""Endpoint: /load/<session_id> (GET)
	----------------------------------
	Description:
		This endpoint loads a specific interview session from the database based on the provided session ID.

	Input Arguments:
		- session_id (str): The unique identifier for the interview session.

	Example Query:
		Using Python's requests package:
			```
			response = requests.get('http://127.0.0.1:8000/load/67890')
			```

		Using the command line with curl:
			```
			curl http://127.0.0.1:8000/load/67890
			```
	"""
	session = logic.load_interview_session(session_id)
	return jsonify(session)

@app.route('/delete/<session_id>', methods=['GET'])
@decorators.handle_500
def delete(session_id:str):
	"""Endpoint: /delete/<session_id> (GET)
	------------------------------------
	Description:
		This endpoint deletes a specific interview session from the database using the session ID.

	Input Arguments:
		- session_id (str): The unique identifier for the session.

	Example Query:
		Using Python's requests package:
			```
			response = requests.get('http://127.0.0.1:8000/delete/67890')
			```

		Using the command line with curl:
			```
			curl http://127.0.0.1:8000/delete/67890
			```
	"""
	logic.delete_interview_session(session_id)
	return make_response(f"Successfully deleted session '{session_id}'.")

@app.route('/retrieve', methods=['GET'])
@decorators.handle_500
def retrieve():
	""" Endpoint: /retrieve (GET)
	-------------------------
	Description:
		This endpoint retrieves all stored interview sessions from the database and returns them.

	Input Arguments:
		None

	Example Query:
		Using requests package:
			```
			response = requests.get('http://127.0.0.1:8000/retrieve')
			```

		Using curl:
			```
			curl http://127.0.0.1:8000/retrieve
			```
	"""
	response = logic.retrieve_sessions()
	return jsonify(response)


if __name__ == "__main__":
	# Only for debugging while developing!
	app.run(host="0.0.0.0", port=8000, debug=True)
