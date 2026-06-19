import os
import shutil
import uuid
import logging
from typing import Optional
from fastapi import FastAPI, Depends, UploadFile, File, Form, Header, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app.config import RESUME_DIR, JD_DIR, DEFAULT_QUESTION_COUNT, DB_PATH, GEMINI_API_KEY
from backend.app.database import init_db, get_db, Candidate, JobDescription, Interview, Question, Response
from backend.app import parsers
from backend.app import matcher
from backend.app import interviewer
from backend.app import evaluator
from backend.app import reporter
from backend.app.vector_store import RAGEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")

# Initialize DB
init_db()

app = FastAPI(title="AI-Based Adaptive Interviewer API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for active RAG engines to avoid rebuilding on every call
# Keys are interview_ids, values are RAGEngine instances
RAG_CACHE = {}

def get_or_create_rag(interview: Interview, db: Session, api_key: str = None) -> RAGEngine:
    """Retrieves cached RAGEngine or builds a new one from database records."""
    if interview.id in RAG_CACHE:
        return RAG_CACHE[interview.id]
        
    logger.info(f"Rebuilding RAGEngine for Interview {interview.id}")
    rag = RAGEngine(api_key=api_key)
    
    # Retrieve raw texts
    candidate = interview.candidate
    jd = interview.jd
    
    # Extract candidate resume text
    try:
        resume_text = parsers.extract_text_from_pdf(candidate.resume_path)
    except Exception as e:
        logger.error(f"Failed to extract text for RAG rebuild: {e}")
        resume_text = ""
        
    rag.add_documents(resume_text, jd.raw_text)
    RAG_CACHE[interview.id] = rag
    return rag

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "AI-Based Adaptive Interviewer API",
        "api_key_configured": bool(GEMINI_API_KEY)
    }

@app.post("/upload-resume")
def upload_resume(
    file: UploadFile = File(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
    x_gemini_key: Optional[str] = Header(None)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
        
    # Generate unique file path
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    dest_path = RESUME_DIR / unique_filename
    
    # Save PDF
    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume: {e}")
        
    # Extract and parse structured resume
    try:
        parsed_data = parsers.parse_resume(str(dest_path), api_key=x_gemini_key)
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
        
    # Check if candidate already exists
    candidate = db.query(Candidate).filter(Candidate.email == email).first()
    if candidate:
        # Update existing candidate
        candidate.name = parsed_data.get("name", "Unknown")
        candidate.resume_path = str(dest_path)
        candidate.skills = parsed_data.get("skills", [])
        candidate.education = parsed_data.get("education", [])
        candidate.experience = parsed_data.get("experience", [])
        candidate.projects = parsed_data.get("projects", [])
    else:
        # Create new candidate
        candidate = Candidate(
            name=parsed_data.get("name", "Unknown"),
            email=email,
            resume_path=str(dest_path),
            skills=parsed_data.get("skills", []),
            education=parsed_data.get("education", []),
            experience=parsed_data.get("experience", []),
            projects=parsed_data.get("projects", [])
        )
        db.add(candidate)
        
    db.commit()
    db.refresh(candidate)
    
    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "skills": candidate.skills,
        "education": candidate.education,
        "experience": candidate.experience,
        "projects": candidate.projects
    }

@app.post("/upload-jd")
def upload_jd(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    x_gemini_key: Optional[str] = Header(None)
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only text (.txt) Job Descriptions are supported.")
        
    # Save file
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    dest_path = JD_DIR / unique_filename
    
    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save Job Description: {e}")
        
    # Extract and parse structured JD
    try:
        parsed_data = parsers.parse_jd(str(dest_path), api_key=x_gemini_key)
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
        
    # Save to database
    jd = JobDescription(
        role=parsed_data.get("role", "Unknown"),
        required_skills=parsed_data.get("required_skills", []),
        experience=parsed_data.get("experience", "Not specified"),
        responsibilities=parsed_data.get("responsibilities", []),
        raw_text=parsed_data.get("raw_text", "")
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    
    return {
        "jd_id": jd.id,
        "role": jd.role,
        "required_skills": jd.required_skills,
        "experience": jd.experience,
        "responsibilities": jd.responsibilities
    }

@app.post("/match-candidate")
def match_candidate(
    candidate_id: int,
    jd_id: int,
    db: Session = Depends(get_db),
    x_gemini_key: Optional[str] = Header(None)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    
    if not candidate or not jd:
        raise HTTPException(status_code=404, detail="Candidate or Job Description not found.")
        
    cand_data = {
        "skills": candidate.skills,
        "experience": candidate.experience,
        "projects": candidate.projects
    }
    jd_data = {
        "required_skills": jd.required_skills,
        "experience": jd.experience,
        "responsibilities": jd.responsibilities,
        "raw_text": jd.raw_text
    }
    
    match_result = matcher.match_candidate_to_jd(cand_data, jd_data, api_key=x_gemini_key)
    return match_result

@app.post("/start-interview")
def start_interview(
    candidate_id: int,
    jd_id: int,
    question_count: int = DEFAULT_QUESTION_COUNT,
    db: Session = Depends(get_db),
    x_gemini_key: Optional[str] = Header(None)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    
    if not candidate or not jd:
        raise HTTPException(status_code=404, detail="Candidate or Job Description not found.")
        
    # Check if there's already an ongoing interview for this pair
    interview = db.query(Interview).filter(
        Interview.candidate_id == candidate_id,
        Interview.jd_id == jd_id,
        Interview.status == "ongoing"
    ).first()
    
    if not interview:
        # Create new interview, start at level 1 difficulty
        interview = Interview(
            candidate_id=candidate_id,
            jd_id=jd_id,
            status="ongoing",
            current_difficulty=1,
            current_question_number=1
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)
        
    # Initialize RAG and cache it
    rag = get_or_create_rag(interview, db, api_key=x_gemini_key)
    
    # Check if first question is already generated
    first_q = db.query(Question).filter(
        Question.interview_id == interview.id,
        Question.difficulty == interview.current_difficulty,
        Question.category == "technical"
    ).first()
    
    if not first_q:
        # Retrieve context for technical evaluation
        retrieved_context = rag.retrieve("core skills and technical competencies required", k=3)
        
        cand_profile = {
            "name": candidate.name,
            "skills": candidate.skills,
            "projects": candidate.projects,
            "experience": candidate.experience
        }
        jd_profile = {
            "role": jd.role,
            "required_skills": jd.required_skills,
            "responsibilities": jd.responsibilities
        }
        
        question_text = interviewer.generate_interview_question(
            candidate_profile=cand_profile,
            jd_profile=jd_profile,
            question_number=1,
            total_questions=question_count,
            difficulty=interview.current_difficulty,
            retrieved_context=retrieved_context,
            history=[],
            api_key=x_gemini_key
        )
        
        first_q = Question(
            interview_id=interview.id,
            question_text=question_text,
            category="technical",
            difficulty=interview.current_difficulty
        )
        db.add(first_q)
        db.commit()
        db.refresh(first_q)
        
    return {
        "interview_id": interview.id,
        "question_id": first_q.id,
        "question_text": first_q.question_text,
        "question_number": interview.current_question_number,
        "total_questions": question_count,
        "difficulty": interview.current_difficulty
    }

@app.post("/submit-answer")
def submit_answer(
    interview_id: int,
    question_id: int,
    answer: str,
    question_count: int = DEFAULT_QUESTION_COUNT,
    db: Session = Depends(get_db),
    x_gemini_key: Optional[str] = Header(None)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    question = db.query(Question).filter(Question.id == question_id).first()
    
    if not interview or not question:
        raise HTTPException(status_code=404, detail="Interview or Question not found.")
        
    if interview.status == "completed":
        raise HTTPException(status_code=400, detail="This interview has already completed.")
        
    candidate = interview.candidate
    jd = interview.jd
    rag = get_or_create_rag(interview, db, api_key=x_gemini_key)
    
    # 1. Retrieve context to evaluate
    retrieved_context = rag.retrieve(question.question_text, k=2)
    
    # 2. Evaluate answer
    eval_result = evaluator.evaluate_candidate_answer(
        question_text=question.question_text,
        answer_text=answer,
        retrieved_context=retrieved_context,
        role_title=jd.role,
        api_key=x_gemini_key
    )
    
    # 3. Save Response
    response = Response(
        question_id=question.id,
        answer_text=answer,
        score=eval_result["score"],
        feedback=eval_result["feedback"],
        strengths=eval_result["strengths"],
        weaknesses=eval_result["weaknesses"]
    )
    db.add(response)
    db.commit()
    
    # 4. Adaptive Difficulty Logic
    prev_difficulty = interview.current_difficulty
    new_difficulty = interviewer.adjust_difficulty(prev_difficulty, eval_result["score"])
    
    # Check if interview is over
    next_question_number = interview.current_question_number + 1
    
    if next_question_number > question_count:
        # Interview is complete! Let's build the final assessment.
        interview.status = "completed"
        db.commit()
        
        # Load all QAs for report generator
        all_questions = db.query(Question).filter(Question.interview_id == interview.id).all()
        qa_list = []
        scores = []
        for q in all_questions:
            res = db.query(Response).filter(Response.question_id == q.id).first()
            if res:
                scores.append(res.score)
                qa_list.append({
                    "question": q.question_text,
                    "answer": res.answer_text,
                    "score": res.score,
                    "feedback": res.feedback,
                    "category": q.category,
                    "difficulty": q.difficulty
                })
                
        avg_score = sum(scores) / len(scores) if scores else 0.0
        recommendation = reporter.get_recommendation_label(avg_score)
        
        # Perform matching to extract match score
        cand_data = {"skills": candidate.skills, "experience": candidate.experience, "projects": candidate.projects}
        jd_data = {"required_skills": jd.required_skills, "experience": jd.experience, "responsibilities": jd.responsibilities, "raw_text": jd.raw_text}
        match_res = matcher.match_candidate_to_jd(cand_data, jd_data, api_key=x_gemini_key)
        
        # Generate executive summary using Gemini
        report_summary = reporter.generate_report_summary(
            candidate_name=candidate.name,
            role_title=jd.role,
            match_score=match_res["match_score"],
            avg_score=avg_score,
            qa_list=qa_list,
            api_key=x_gemini_key
        )
        
        # Save to DB
        interview.score = avg_score
        interview.recommendation = recommendation
        interview.summary = report_summary.get("summary")
        interview.strengths = report_summary.get("strengths")
        interview.weaknesses = report_summary.get("weaknesses")
        db.commit()
        
        # Clean RAG cache
        RAG_CACHE.pop(interview.id, None)
        
        return {
            "status": "completed",
            "evaluation": eval_result,
            "average_score": avg_score,
            "recommendation": recommendation,
            "summary": report_summary.get("summary")
        }
        
    else:
        # Generate NEXT question
        interview.current_question_number = next_question_number
        interview.current_difficulty = new_difficulty
        db.commit()
        
        # Determine Category
        next_category = interviewer.determine_question_category(next_question_number, question_count)
        
        # Fetch RAG context for the category
        retrieved_context = rag.retrieve(f"Question about {next_category} skills", k=3)
        
        # Fetch question history
        all_questions = db.query(Question).filter(Question.interview_id == interview.id).all()
        history = []
        for q in all_questions:
            res = db.query(Response).filter(Response.question_id == q.id).first()
            if res:
                history.append({
                    "question": q.question_text,
                    "answer": res.answer_text,
                    "score": res.score
                })
                
        cand_profile = {
            "name": candidate.name,
            "skills": candidate.skills,
            "projects": candidate.projects,
            "experience": candidate.experience
        }
        jd_profile = {
            "role": jd.role,
            "required_skills": jd.required_skills,
            "responsibilities": jd.responsibilities
        }
        
        next_q_text = interviewer.generate_interview_question(
            candidate_profile=cand_profile,
            jd_profile=jd_profile,
            question_number=next_question_number,
            total_questions=question_count,
            difficulty=new_difficulty,
            retrieved_context=retrieved_context,
            history=history,
            api_key=x_gemini_key
        )
        
        next_q = Question(
            interview_id=interview.id,
            question_text=next_q_text,
            category=next_category,
            difficulty=new_difficulty
        )
        db.add(next_q)
        db.commit()
        db.refresh(next_q)
        
        return {
            "status": "ongoing",
            "evaluation": eval_result,
            "next_question_id": next_q.id,
            "next_question_text": next_q.question_text,
            "next_question_number": next_question_number,
            "difficulty": new_difficulty
        }

@app.get("/get-report/{interview_id}")
def get_report(interview_id: int, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
        
    if interview.status == "ongoing":
        return {
            "status": "ongoing",
            "current_question_number": interview.current_question_number,
            "candidate_name": interview.candidate.name,
            "role": interview.jd.role
        }
        
    all_questions = db.query(Question).filter(Question.interview_id == interview.id).all()
    qa_list = []
    for q in all_questions:
        res = db.query(Response).filter(Response.question_id == q.id).first()
        qa_list.append({
            "question": q.question_text,
            "answer": res.answer_text if res else "",
            "score": res.score if res else 0,
            "feedback": res.feedback if res else "No answer submitted",
            "strengths": res.strengths if res else [],
            "weaknesses": res.weaknesses if res else [],
            "category": q.category,
            "difficulty": q.difficulty
        })
        
    return {
        "status": "completed",
        "interview_id": interview.id,
        "candidate": {
            "name": interview.candidate.name,
            "email": interview.candidate.email,
            "skills": interview.candidate.skills
        },
        "jd": {
            "role": interview.jd.role,
            "required_skills": interview.jd.required_skills
        },
        "score": interview.score,
        "recommendation": interview.recommendation,
        "summary": interview.summary,
        "strengths": interview.strengths,
        "weaknesses": interview.weaknesses,
        "qa": qa_list,
        "created_at": interview.created_at.isoformat()
    }

@app.get("/download-report/{interview_id}")
def download_report(interview_id: int, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
        
    if interview.status == "ongoing":
        raise HTTPException(status_code=400, detail="Cannot download a report for an ongoing interview.")
        
    pdf_filename = f"report_{interview.id}_{uuid.uuid4().hex[:8]}.pdf"
    pdf_path = RESUME_DIR / pdf_filename  # Temp save in resumes/uploads dir
    
    # Retrieve data
    candidate_profile = {
        "name": interview.candidate.name,
        "email": interview.candidate.email,
        "skills": interview.candidate.skills
    }
    jd_profile = {
        "role": interview.jd.role,
        "required_skills": interview.jd.required_skills
    }
    interview_data = {
        "score": interview.score,
        "recommendation": interview.recommendation,
        "summary": interview.summary,
        "strengths": interview.strengths,
        "weaknesses": interview.weaknesses,
        "created_at": interview.created_at.isoformat()
    }
    
    all_questions = db.query(Question).filter(Question.interview_id == interview.id).all()
    qa_list = []
    for q in all_questions:
        res = db.query(Response).filter(Response.question_id == q.id).first()
        qa_list.append({
            "question": q.question_text,
            "answer": res.answer_text if res else "No response",
            "score": res.score if res else 0,
            "feedback": res.feedback if res else "No feedback",
            "category": q.category,
            "difficulty": q.difficulty
        })
        
    try:
        # Build PDF using reporter helper
        reporter.build_pdf_report(
            candidate_profile=candidate_profile,
            jd_profile=jd_profile,
            interview_data=interview_data,
            qa_list=qa_list,
            output_path=str(pdf_path)
        )
        
        # Return response streaming and remove the file afterwards
        response = FileResponse(
            path=str(pdf_path),
            filename=f"{candidate_profile['name']}_Interview_Report.pdf",
            media_type="application/pdf"
        )
        return response
    except Exception as e:
        logger.error(f"Failed to generate report PDF file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")

@app.get("/interviews")
def list_interviews(db: Session = Depends(get_db)):
    """List all interviews in the database."""
    interviews = db.query(Interview).order_by(Interview.created_at.desc()).all()
    results = []
    for i in interviews:
        results.append({
            "interview_id": i.id,
            "candidate_name": i.candidate.name,
            "candidate_email": i.candidate.email,
            "role": i.jd.role,
            "score": i.score,
            "recommendation": i.recommendation,
            "status": i.status,
            "created_at": i.created_at.isoformat()
        })
    return results

@app.get("/jds")
def list_jds(db: Session = Depends(get_db)):
    """List all job descriptions in the database."""
    jds = db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()
    return [{
        "jd_id": j.id,
        "role": j.role,
        "required_skills": j.required_skills,
        "experience": j.experience,
        "created_at": j.created_at.isoformat()
    } for j in jds]
