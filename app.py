import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import google.generativeai as genai
import PyPDF2
from pathlib import Path

# Setup
import dotenv
dotenv.load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-3.8-flash")
else:
    model = None

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

doc_text = ""
doc_name = ""

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global doc_text, doc_name
    f = request.files.get('file')
    if not f:
        return jsonify({"success": False, "message": "No file"})
    path = UPLOAD_DIR / f.filename
    f.save(path)
    # extract
    text = ""
    try:
        if str(path).endswith(".pdf"):
            reader = PyPDF2.PdfReader(open(path, "rb"))
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        else:
            text = open(path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as e:
        text = ""
    doc_text = text
    doc_name = f.filename
    return jsonify({"success": True, "message": f"{f.filename} uploaded {len(text)} chars"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    q = data.get('message', '')
    if not q:
        return jsonify({"response": "Enter question"})
    if not model:
        return jsonify({"response": "API Key missing on server"})
    try:
        if doc_text:
            prompt = f"Document {doc_name}:\n{doc_text[:7000]}\n\nQ: {q}\nAnswer:"
        else:
            prompt = q
        resp = model.generate_content(prompt)
        return jsonify({"response": resp.text})
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})

@app.route('/quiz', methods=['POST'])
def quiz():
    try:
        p = f"Make 5 MCQ from:\n{doc_text[:5000]}" if doc_text else "Make 5 TNPSC GK MCQ with answers"
        r = model.generate_content(p)
        return jsonify({"quiz": r.text})
    except Exception as e:
        return jsonify({"quiz": str(e)})

@app.route('/summary', methods=['POST'])
def summary():
    if not doc_text:
        return jsonify({"summary": "Upload file first"})
    try:
        r = model.generate_content(f"Summarize:\n{doc_text[:7000]}")
        return jsonify({"summary": r.text})
    except Exception as e:
        return jsonify({"summary": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
