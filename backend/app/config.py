import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Resume and JD subdirectories
RESUME_DIR = UPLOAD_DIR / "resumes"
JD_DIR = UPLOAD_DIR / "jds"
RESUME_DIR.mkdir(exist_ok=True)
JD_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = BASE_DIR / "interviewer.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Gemini Model settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCrgfzH5r_SmhQsfCbkrJxqFExkY4lWW0Q")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-3.5-flash")
EMBEDDING_MODEL = "models/gemini-embedding-001"

# Interview settings
DEFAULT_QUESTION_COUNT = 5  # Total questions per interview
