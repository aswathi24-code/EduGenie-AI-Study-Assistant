# EduGenie - AI Study Assistant - Full Version
# Fixed for Render Deployment + JSON Error + Model Error
import os
import re
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Google Generative AI - New SDK
from google import genai
from google.genai import types

# For File Reading
import PyPDF2
try:
    import docx
except ImportError:
    docs = None

# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FLASK_SECRET = os.getenv("FLASK_SECRET_KEY", "edugenie-secret-2024")

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================================================
# GEMINI CLIENT SETUP - FIXED MODEL NAME
# =========================================================
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini Client Initialized Successfully")
    except Exception as e:
        logger.error(f"Failed to init Gemini Client: {e}")
        client = None
else:
    logger.warning("GEMINI_API_KEY is missing in.env")

# *** IMPORTANT FIX - This was the 503 error ***
# Old model: gemini-3.8-Flash (does not exist)
# New Fixed Models - Try in order
MODEL_PRIMARY = "gemini-1.5-flash"
MODEL_FALLBACK = "gemini-1.5-flash-latest"
MODEL_BACKUP = "gemini-2.0-flash-exp"

def get_model_name():
    """Return working model name"""
    return MODEL_PRIMARY

# =========================================================
# FLASK APP SETUP
# =========================================================
app = Flask(__name__)
app.secret_key = FLASK_SECRET
CORS(app, resources={r"/*": {"origins": "*"}})

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'doc'}

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB

# Global variable to store document context
document_store = {
    "text": "",
    "filename": "",
    "upload_time": "",
    "chunks": []
}

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                except Exception as e:
                    logger.warning(f"Failed to extract page {page_num}: {e}")
                    continue
        return text
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return ""

def extract_text_from_txt(file_path):
    """Extract text from TXT file"""
    text = ""
    try:
        # Try multiple encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    text = f.read()
                break
            except UnicodeDecodeError:
                continue
        return text
    except Exception as e:
        logger.error(f"TXT extraction error: {e}")
        return ""

def extract_text_from_file(file_path):
    """Main extractor - detects file type"""
    file_path = str
