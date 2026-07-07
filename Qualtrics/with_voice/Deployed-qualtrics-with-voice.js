Qualtrics.SurveyEngine.addOnload(function () {

    ////////////////////////////////////////////////////////////////
    // Embedded data from Survey Flow
    ////////////////////////////////////////////////////////////////
    // console.log("This question ID is:", this.questionId);

	//var userID = "test_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
	var userID = "${e://Field/ResponseID}";
    Qualtrics.SurveyEngine.setEmbeddedData("user_id", userID);
	var interviewID = "GENAI_WORKPLACE";
    var endpoint = "https://ai-interview.uis.no/";

    //console.log("CHATBOT endpoint value is:", endpoint);
    //console.log("userID:", userID);
    //console.log("interviewID:", interviewID);

    ////////////////////////////////////////////////////////////////
    // HTML elements
    ////////////////////////////////////////////////////////////////
    var chatArea = document.getElementById("chatArea");
    var submitButton = document.getElementById("submitButton");
    var inputField = document.getElementById("inputBox");
    var recordButton = document.getElementById("recordButton");

    ////////////////////////////////////////////////////////////////
    // Safety check
    ////////////////////////////////////////////////////////////////
    if (!chatArea || !submitButton || !inputField || !recordButton) {
        console.error("One or more required HTML elements are missing.");
        return;
    }

    ////////////////////////////////////////////////////////////////
    // Helper: add chatbot message
    ////////////////////////////////////////////////////////////////
    function appendChatbotMessage(message, chatArea, status) {
        var messageContent = document.createElement('div');

        messageContent.style.cssText =
            "word-wrap: break-word;" +
            "width: 80%;" +
            "border: 1px solid #F6F6F6;" +
            "border-radius: 5px;" +
            "padding: 5px;" +
            "margin-bottom: 10px;" +
            "background-color: #F6F6F6;" +
            "display: block;" +
            "margin-right: auto;" +
            "font-size: 18px;" +
            "line-height: 1.5;";

        if (status === "waiting") {
            messageContent.innerHTML = `
                <div>
                    <div id="wave" style="position:relative; text-align:left;">
                        <span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite;"></span>
                        <span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite; animation-delay: -1.1s;"></span>
                        <span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite; animation-delay: -0.9s;"></span>
                    </div>
                    <style>
                        @keyframes wave {
                            0%, 60%, 100% { transform: initial; }
                            30% { transform: translateY(-7px); }
                        }
                    </style>
                </div>
            `;
            messageContent.id = "dancingDots";
        } else if (status === "response") {
            var existingDots = document.getElementById("dancingDots");

            if (existingDots) {
                existingDots.innerText = message.trim();
                existingDots.removeAttribute('id');
                chatArea.scrollTop = chatArea.scrollHeight;
                return;
            } else {
                messageContent.innerText = message.trim();
            }
        }

        chatArea.appendChild(messageContent);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    ////////////////////////////////////////////////////////////////
    // Helper: add participant message
    ////////////////////////////////////////////////////////////////
    function appendUserMessage(message) {
        var messageContent = document.createElement('div');

        messageContent.style.cssText =
            "display: inline-block;" +
            "max-width: 80%;" +
            "border: 1px solid #ddd;" +
            "border-radius: 5px;" +
            "padding: 5px;" +
            "margin-bottom: 10px;" +
            "background-color: #ddd;" +
            "word-wrap: break-word;" +
            "white-space: pre-wrap;" +
            "box-sizing: border-box;" +
            "font-size: 18px;" +
            "text-align: left;" +
            "line-height: 1.5;";

        messageContent.innerText = message;
        chatArea.appendChild(messageContent);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    ////////////////////////////////////////////////////////////////
    // Helper: call interview API
    ////////////////////////////////////////////////////////////////
    function callInterviewAPI(userMessage) {
        return fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                route: "next",
                payload: {
                    user_message: userMessage,
                    session_id: userID,
                    interview_id: interviewID
                }
            })
        })
        .then(function (response) {
            if (!response.ok) {
                throw new Error("Server returned status " + response.status);
            }
            return response.json();
        });
    }

    ////////////////////////////////////////////////////////////////
    // Get first chatbot question
    ////////////////////////////////////////////////////////////////
    submitButton.disabled = true;
    recordButton.disabled = true;

    callInterviewAPI("")
        .then(function (data) {
            var question = data.message.trim();
            appendChatbotMessage(question, chatArea, "response");

            if (Qualtrics.SurveyEngine.setJSEmbeddedData) {
                Qualtrics.SurveyEngine.setJSEmbeddedData('first_question', question);
            } else {
                Qualtrics.SurveyEngine.setEmbeddedData('first_question', question);
            }

            submitButton.disabled = false;
            recordButton.disabled = false;
        })
        .catch(function (error) {
            console.error("Error getting first question:", error);
            appendChatbotMessage(
                "Det oppstod en teknisk feil. Oppdater siden eller fortsett i undersøkelsen.",
                chatArea,
                "response"
            );

            submitButton.disabled = false;
            recordButton.disabled = false;
        });

    ////////////////////////////////////////////////////////////////
    // Submit typed response
    ////////////////////////////////////////////////////////////////
    submitButton.addEventListener("click", function () {
        var userMessage = inputField.value.trim();

        if (!userMessage) {
            return;
        }

        inputField.value = "";

        submitButton.disabled = true;
        submitButton.style.backgroundColor = '#ccc';
        submitButton.innerText = "Venter på svar...";
        recordButton.disabled = true;

        appendUserMessage(userMessage);
        appendChatbotMessage("", chatArea, "waiting");

        callInterviewAPI(userMessage)
            .then(function (data) {
                var next_question = data.message.trim();

                var endInterviewIndex = next_question.indexOf("---END---");

                if (endInterviewIndex !== -1) {
                    next_question = next_question.replace("---END---", "").trim();

                    submitButton.disabled = true;
                    submitButton.innerText = "Intervjuet er avsluttet";
                    recordButton.disabled = true;
                } else {
                    submitButton.disabled = false;
                    submitButton.innerText = "Send svar";
                    submitButton.style.backgroundColor = '#007BFF';
                    recordButton.disabled = false;
                }

                appendChatbotMessage(next_question, chatArea, "response");
            })
            .catch(function (error) {
                console.error("Error submitting response:", error);

                appendChatbotMessage(
                    "Det oppstod en teknisk feil. Prøv igjen.",
                    chatArea,
                    "response"
                );

                submitButton.disabled = false;
                submitButton.style.backgroundColor = '#007BFF';
                submitButton.innerText = "Send svar";
                recordButton.disabled = false;
            });
    });

    ////////////////////////////////////////////////////////////////
    // Audio recording and transcription
    ////////////////////////////////////////////////////////////////
    var mediaRecorder;
    var audioChunks = [];
    var stream;

    recordButton.addEventListener("click", async function () {
        if (recordButton.textContent === "Ta opp svar") {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                recordButton.textContent = "Stopp opptak";
                submitButton.disabled = true;

                mediaRecorder.start();

                mediaRecorder.ondataavailable = function (event) {
                    audioChunks.push(event.data);
                };

            } catch (err) {
                console.error("Microphone error:", err);
                alert("Feil ved tilgang til mikrofon: " + err.message);
                submitButton.disabled = false;
            }

        } else if (recordButton.textContent === "Stopp opptak") {
            recordButton.textContent = "Transkriberer lyd...";
            recordButton.disabled = true;

            mediaRecorder.stop();

            mediaRecorder.onstop = async function () {
                var audioBlob = new Blob(audioChunks, { type: "audio/webm" });
                var reader = new FileReader();

                reader.onloadend = function () {
                    var audioBase64 = reader.result.split(",")[1];

                    fetch(endpoint, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            route: "transcribe",
                            payload: {
                                audio: audioBase64
                            }
                        })
                    })
                    .then(function (response) {
                        if (!response.ok) {
                            throw new Error("Server returned status " + response.status);
                        }
                        return response.json();
                    })
                    .then(function (data) {
                        var transcript = data.transcription || "Transkriberingen mislyktes. Prøv igjen.";
                        inputField.value = transcript;
                    })
                    .catch(function (error) {
                        console.error("Transcription error:", error);
                        alert("Noe gikk galt med transkriberingen. Prøv igjen.");
                    })
                    .finally(function () {
                        audioChunks = [];

                        if (stream) {
                            stream.getTracks().forEach(function (track) {
                                track.stop();
                            });
                        }

                        recordButton.textContent = "Ta opp svar";
                        recordButton.disabled = false;
                        submitButton.disabled = false;
                    });
                };

                reader.readAsDataURL(audioBlob);
            };
        }
    });

    ////////////////////////////////////////////////////////////////
    // Prevent copy, cut, and paste
    ////////////////////////////////////////////////////////////////
    ["copy", "cut", "paste"].forEach(function (eventType) {
        [chatArea, inputField].forEach(function (element) {
            element.addEventListener(eventType, function (event) {
                event.preventDefault();
            });
        });
    });

});

Qualtrics.SurveyEngine.addOnReady(function () {
    // Runs when the page is fully displayed
});

Qualtrics.SurveyEngine.addOnUnload(function () {
    // Runs when the page is unloaded
});
