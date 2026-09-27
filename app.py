import os
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types
import PyPDF2
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None
MODEL = "gemini-1.5-flash"

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent
(UPLOAD_FOLDER := BASE_DIR / "uploads").mkdir(exist_ok=True)

doc_text = ""
doc_name = ""

def extract_pdf(path):
    txt=""
    try:
        r=PyPDF2.PdfReader(open(path,"rb"))
        for p in r.pages:
            t=p.extract_text()
            if t: txt+=t+"\n"
    except Exception as e:
        print(e)
    return txt

def extract_txt(path):
    for enc in ['utf-8','latin-1']:
        try:
            return open(path,'r',encoding=enc).read()
        except: continue
    return ""

def ask_gemini(prompt):
    if not client:
        return "API Key missing"
    try:
        res = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=2048)
        )
        return res.text
    except Exception as e:
        err=str(e)
        if "503" in err or "overload" in err.lower():
            return "⚠️ Google AI busy, 30 sec kazhichu try pannu"
        return f"Error: {err}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global doc_text, doc_name
    if 'file' not in request.files:
        return jsonify({"success":False,"message":"No file"})
    f=request.files['file']
    if not f.filename:
        return jsonify({"success":False,"message":"No filename"})
    path=os.path.join(UPLOAD_FOLDER, f.filename)
    f.save(path)
    if path.endswith(".pdf"):
        doc_text=extract_pdf(path)
    else:
        doc_text=extract_txt(path)
    doc_name=f.filename
    if len(doc_text)<10:
        return jsonify({"success":False,"message":"Text extract panna mudiyala"})
    return jsonify({"success":True,"message":f"{f.filename} uploaded!","filename":f.filename})

@app.route('/chat', methods=['POST'])
def chat():
    data=request.get_json()
    q=data.get('message','').strip()
    if not q:
        return jsonify({"response":"Question enter pannu"})
    if doc_text:
        prompt=f"Document ({doc_name}):\n{doc_text[:7000]}\n\nQuestion: {q}\nAnswer simply:"
    else:
        prompt=f"You are EduGenie AI assistant. Answer: {q}"
    ans=ask_gemini(prompt)
    return jsonify({"response":ans,"answer":ans})

@app.route('/quiz', methods=['POST'])
def quiz():
    if doc_text:
        prompt=f"From this:\n{doc_text[:5000]}\nCreate 5 MCQ with answer"
    else:
        prompt="Create 5 TNPSC GK MCQ with 4 options and answer"
    return jsonify({"quiz":ask_gemini(prompt),"response":ask_gemini(prompt)})

@app.route('/summary', methods=['POST'])
def summary():
    if not doc_text:
        return jsonify({"summary":"Upload document first"})
    prompt=f"Summarize in points:\n{doc_text[:7000]}"
    return jsonify({"summary":ask_gemini(prompt)})

@app.route('/health')
def health():
    return jsonify({"status":"ok","model":MODEL,"has_doc":bool(doc_text)})

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT",5000)))
