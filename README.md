# AI-Based Adaptive Interviewer System

An intelligent, context-aware recruitment platform that automates candidate screening. The system parses PDF resumes and text job descriptions (JDs), performs semantic compatibility matching, conducts an interactive interview session that adapts question difficulty in real-time, and yields a detailed hiring PDF report.

## 🚀 Key Features

- **Automated Parsing**: PyMuPDF-based text extraction of PDF resumes, native text reading of Job Descriptions, and Gemini-driven structured parsing.
- **RAG Knowledge Engine**: Context retrieval via local FAISS indexing of document text using Gemini's state-of-the-art embedding API (`text-embedding-004`).
- **Semantic Profile Matching**: Compare resume experience and skills against the job requirements using LLM evaluations with local fallbacks.
- **Real-time Adaptive Interview**: Session engine that tracks question categories (Technical, Project, Behavioral) and dynamically adjusts difficulty (Levels 1 to 4) depending on candidate scores.
- **Automated Score Evaluations**: Question-by-question grading (0 to 10 scale), constructive feedback, strengths, and weaknesses.
- **Professional PDF Assessment Reports**: Generates elegant assessment sheets with ReportLab containing executive summaries, score charts, recommendations, and full transcripts.

---

## 🛠️ Architecture

- **Backend**: FastAPI (Python), SQLite (SQLAlchemy ORM), FAISS (Vector Index), and Google Generative AI (Gemini model: `gemini-1.5-flash`).
- **Frontend**: Streamlit with custom CSS injector styling for premium look & feel, dynamic Plotly indicator gauges, and charts.

---

## 💻 Installation

### Prerequisites
- Python 3.9+
- Pip package manager

### 1. Clone & Set Up Directory
Navigate to the project directory:
```bash
cd Ai_interviewer
```

### 2. Install Dependencies
You can install dependencies for both components:
```bash
# Install backend requirements
pip install -r backend/requirements.txt

# Install frontend requirements
pip install -r frontend/requirements.txt
```

---

## ⚙️ Configuration

Create a `.env` file in the project root folder or set environment variables:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

---

## 🏃 Running the Application

To launch both the FastAPI backend and Streamlit frontend concurrently, run:

```bash
python run.py
```

- **Candidate Portal**: `http://127.0.0.1:8501` (by default)
- **Recruiter Dashboard**: Select from the Navigation radio in the Streamlit sidebar
- **API Swagger Documentation**: `http://127.0.0.1:8000/docs`
