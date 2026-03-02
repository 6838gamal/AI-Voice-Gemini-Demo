import os
import requests
import json
import tempfile
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise Exception("Set GEMINI_API_KEY environment variable!")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

app = FastAPI()
chat_history = []

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Gemini Voice Chat</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 40px auto; }
        #recordBtn { padding: 10px 20px; font-size:16px; }
        #status { color: red; font-weight:bold; margin-left:10px; }
        #chatBox p { margin:5px 0; }
    </style>
</head>
<body>
<h2>Gemini Voice Chat</h2>

<button id="recordBtn">تسجيل صوتك</button>
<span id="status"></span>
<div id="chatBox" style="margin-top:20px;"></div>
<audio id="voiceReply" controls></audio>

<script>
let mediaRecorder;
let audioChunks = [];
let recording = false;

document.getElementById("recordBtn").onclick = async function() {
    const status = document.getElementById("status");

    if(!mediaRecorder){
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = async () => {
            recording = false;
            status.innerText = "";
            const blob = new Blob(audioChunks, {type:'audio/webm'});
            audioChunks = [];

            const formData = new FormData();
            formData.append("audio", blob, "voice.webm");

            const chatBox = document.getElementById("chatBox");
            chatBox.innerHTML += "<p><b>أنت: (صوت)</b></p>";

            const response = await fetch("/voice", { method:"POST", body: formData });
            const replyBlob = await response.blob();
            const audioURL = URL.createObjectURL(replyBlob);
            const audioElem = document.getElementById("voiceReply");
            audioElem.src = audioURL;
            audioElem.play();

            chatBox.innerHTML += "<p><b>Gemini:</b> (استمع للصوت)</p>";
        };
    }

    if(!recording){
        mediaRecorder.start();
        recording = true;
        status.innerText = "التسجيل جاري 🔴";
    } else {
        mediaRecorder.stop();
    }
};
</script>
</body>
</html>
"""

# -----------------------------
# دوال التطبيق
# -----------------------------
def ask_gemini(text: str) -> str:
    global chat_history
    full_prompt = "\n".join(chat_history + [f"You: {text}"])
    data = {"contents":[{"parts":[{"text": full_prompt}]}]}
    r = requests.post(GEMINI_URL, headers={"Content-Type":"application/json"}, data=json.dumps(data))
    res = r.json()
    try:
        reply = res["candidates"][0]["content"]["parts"][0]["text"]
    except:
        reply = "حدث خطأ في Gemini: " + str(res)
    chat_history.append(f"You: {text}")
    chat_history.append(f"Gemini: {reply}")
    return reply

def text_to_speech(text: str, filename: str, lang="en"):
    tts = gTTS(text=text, lang=lang)
    tts.save(filename)

def speech_to_text(file_path: str) -> str:
    # تحويل WebM إلى WAV
    wav_file = file_path.replace(".webm", ".wav")
    AudioSegment.from_file(file_path).export(wav_file, format="wav")

    r = sr.Recognizer()
    with sr.AudioFile(wav_file) as source:
        audio_data = r.record(source)
        try:
            return r.recognize_google(audio_data, language="ar-EG")  # Arabic
        except:
            return ""

# -----------------------------
# مسارات FastAPI
# -----------------------------
@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE

@app.post("/voice")
async def voice(audio: UploadFile = File(...)):
    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    tmp_audio.write(await audio.read())
    tmp_audio.close()

    user_text = speech_to_text(tmp_audio.name)
    if not user_text:
        user_text = "لم أفهم الصوت"

    reply_text = ask_gemini(user_text)

    tmp_reply = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    text_to_speech(reply_text, tmp_reply.name, lang="ar")
    tmp_reply.close()

    return FileResponse(tmp_reply.name, media_type="audio/mpeg")

# -----------------------------
# نقطة البداية main
# -----------------------------
def main():
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
