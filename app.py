import os
import json
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from google import genai


# --------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is not configured.")

# Create Gemini client
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Current Gemini model
MODEL_NAME = "gemini-3.8-flash"


# --------------------------------------------------
# FLASK APP
# --------------------------------------------------

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"

UPLOAD_FOLDER.mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


ALLOWED_EXTENSIONS = {
    "pdf",
    "txt"
}


# --------------------------------------------------
# TEMPORARY DOCUMENT MEMORY
# --------------------------------------------------

document_text = ""
document_name = ""


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def allowed_file(filename):
    """Check whether the uploaded file type is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""

    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n\n".join(pages)


def extract_text_from_txt(file_path):
    """Read text file."""

    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def ask_gemini(prompt):
    """Send a prompt to Gemini."""

    if client is None:
        raise RuntimeError(
            "Gemini API key is missing. Please add GEMINI_API_KEY to .env"
        )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/use-sample")
def use_sample():
    global document_text, document_name
    sample_path = BASE_DIR / "sample.txt"
    if not sample_path.exists():
        sample_path = BASE_DIR / "uploads" / "sample.txt"
    try:
        document_text = sample_path.read_text(encoding="utf-8")
        document_name = "sample.txt"
        return jsonify({"success": True, "message": "Sample loaded! Ready to generate."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/quick-summary")
def quick_summary():
    global document_text, document_name
    if not document_text:
        return "<h2>No document. Go to /use-sample first</h2><a href='/use-sample'>Load</a>"
    try:
        from google import genai
        client = genai.Client()
        txt = document_text[:5000]
        prompt = "Summarize for TNPSC exam in simple points: " + txt
        response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
        return "<h1>EduGenie Summary</h1><b>" + document_name + "</b><hr><div style='font-size:18px; padding:20px; white-space: pre-wrap'>" + response.text + "</div><br><a href='/'>Home</a><br><a href='/quick-quiz'>Next: Quiz</a>"
    except Exception as e:
        return "<h2>Error: " + str(e) + "</h2>"

@app.route("/quick-quiz")
def quick_quiz():
    global document_text
    if not document_text:
        return "<h2>No document. Go to /use-sample</h2>"
    try:
        from google import genai
        client = genai.Client()
        txt = document_text[:5000]
        prompt = "Create 5 MCQ quiz with answers from: " + txt
        response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
        return "<h1>EduGenie Quiz</h1><hr><div style='font-size:18px; padding:20px; white-space: pre-wrap'>" + response.text + "</div><br><a href='/'>Home</a>"
    except Exception as e:
        return "<h2>Error: " + str(e) + "</h2>"

# ------------------------
# UPLOAD DOCUMENT
# ------------------------
@app.route("/upload", methods=["POST"])
def upload_document():

    global document_text
    global document_name

    if "file" not in request.files:
        return jsonify({
            "success": False,
            "message": "No file selected."
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "message": "Please select a file."
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "message": "Only PDF and TXT files are supported."
        }), 400

    filename = secure_filename(file.filename)

    file_path = UPLOAD_FOLDER / filename

    file.save(file_path)

    try:

        extension = filename.rsplit(".", 1)[1].lower()

        if extension == "pdf":
            extracted_text = extract_text_from_pdf(file_path)

        else:
            extracted_text = extract_text_from_txt(file_path)

        if not extracted_text.strip():

            return jsonify({
                "success": False,
                "message": "Could not extract any text from the document."
            }), 400

        # Save current document in memory
        document_text = extracted_text
        document_name = filename

        return jsonify({
            "success": True,
            "message": "Document uploaded successfully!",
            "filename": filename,
            "characters": len(document_text)
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "message": f"Error reading document: {str(error)}"
        }), 500


# --------------------------------------------------
# CHAT WITH GEMINI
# --------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "success": False,
            "message": "Please enter a question."
        }), 400

    context = ""

    if document_text:

        # Limit context to avoid sending extremely large documents
        context = document_text[:50000]

    prompt = f"""
You are EduGenie, an AI-powered learning assistant.

Your goal is to help students understand academic concepts
in simple and clear language.

IMPORTANT RULES:

1. Explain concepts step-by-step.
2. Use simple English.
3. Give examples whenever useful.
4. If the student asks a difficult question, explain it like a beginner.
5. If a document is provided, use the document as the main context.
6. Do not invent information from the document.
7. If the answer is not available in the document, clearly say that.
8. Use headings and bullet points when appropriate.
9. For programming questions, provide working examples.
10. Encourage learning rather than simply giving unexplained answers.

CURRENT DOCUMENT:
{document_name if document_name else "No document uploaded"}

DOCUMENT CONTENT:
{context if context else "No document has been uploaded."}

STUDENT QUESTION:
{user_message}

Provide a helpful educational answer.
"""

    try:

        answer = ask_gemini(prompt)

        return jsonify({
            "success": True,
            "answer": answer
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# --------------------------------------------------
# DOCUMENT SUMMARY
# --------------------------------------------------

@app.route("/summary", methods=["POST"])
def summary():

    if not document_text:

        return jsonify({
            "success": False,
            "message": "Please upload a document first."
        }), 400

    prompt = f"""
You are EduGenie, an AI learning assistant.

Create a clear and student-friendly summary of the following document.

Requirements:

- Give a short overview.
- List the important concepts.
- Explain important terms.
- Highlight important points.
- Keep the language simple.
- Use headings and bullet points.
- Do not add information that is not present in the document.

DOCUMENT:

{document_text[:50000]}
"""

    try:

        result = ask_gemini(prompt)

        return jsonify({
            "success": True,
            "summary": result
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# --------------------------------------------------
# GENERATE QUIZ
# --------------------------------------------------

@app.route("/quiz", methods=["POST"])
def quiz():

    if not document_text:

        return jsonify({
            "success": False,
            "message": "Please upload a document first."
        }), 400

    prompt = f"""
You are EduGenie, an educational quiz generator.

Create a quiz based ONLY on the following document.

Generate 5 multiple-choice questions.

Each question must have:

- question
- four options
- correct_answer
- explanation

Return ONLY valid JSON.

Use exactly this structure:

[
    {{
        "question": "Question here",
        "options": [
            "Option A",
            "Option B",
            "Option C",
            "Option D"
        ],
        "correct_answer": "Option A",
        "explanation": "Short explanation"
    }}
]

DOCUMENT:

{document_text[:50000]}
"""

    try:

        result = ask_gemini(prompt)

        # Remove possible markdown code fences
        result = result.strip()

        if result.startswith("```"):
            result = result.replace("```json", "")
            result = result.replace("```", "")
            result = result.strip()

        quiz_data = json.loads(result)

        return jsonify({
            "success": True,
            "quiz": quiz_data
        })

    except json.JSONDecodeError:

        return jsonify({
            "success": False,
            "message": "Gemini returned an invalid quiz format. Please try again."
        }), 500

    except Exception as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# --------------------------------------------------
# CLEAR DOCUMENT
# --------------------------------------------------

@app.route("/clear", methods=["POST"])
def clear_document():

    global document_text
    global document_name

    document_text = ""
    document_name = ""

    return jsonify({
        "success": True,
        "message": "Document cleared."
    })


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():

    return jsonify({
        "status": "running",
        "gemini_configured": bool(GEMINI_API_KEY)
    })


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    print("\n======================================")
    print("       EduGenie AI Learning Assistant")
    print("======================================")

    print("Server: http://127.0.0.1:5000")

    if GEMINI_API_KEY:
        print("Gemini API: Configured")
    else:
        print("Gemini API: NOT configured")

    print("======================================\n")

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )