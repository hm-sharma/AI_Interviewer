import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from backend.app.config import DATABASE_URL

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    resume_path = Column(String, nullable=False)
    skills = Column(JSON, default=[])       # List of skills
    education = Column(JSON, default=[])    # List of education records
    experience = Column(JSON, default=[])   # List of experience records
    projects = Column(JSON, default=[])     # List of projects
    created_at = Column(DateTime, default=utc_now)

    interviews = relationship("Interview", back_populates="candidate")

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False)
    required_skills = Column(JSON, default=[])   # List of required skills
    experience = Column(String, nullable=True)     # Required experience (e.g. "3+ years")
    responsibilities = Column(JSON, default=[])  # List of responsibilities
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    interviews = relationship("Interview", back_populates="jd")

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    jd_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    status = Column(String, default="ongoing")  # 'ongoing' or 'completed'
    current_difficulty = Column(Integer, default=2)  # Level 1 to 4
    current_question_number = Column(Integer, default=0)
    score = Column(Float, nullable=True)  # Final/average score out of 10
    recommendation = Column(String, nullable=True) # Strong Recommendation, Recommended, Not Recommended
    summary = Column(Text, nullable=True)
    strengths = Column(JSON, default=[])
    weaknesses = Column(JSON, default=[])
    created_at = Column(DateTime, default=utc_now)

    candidate = relationship("Candidate", back_populates="interviews")
    jd = relationship("JobDescription", back_populates="interviews")
    questions = relationship("Question", back_populates="interview")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    category = Column(String, nullable=False)  # technical, project, behavioral
    difficulty = Column(Integer, nullable=False) # 1 to 4
    created_at = Column(DateTime, default=utc_now)

    interview = relationship("Interview", back_populates="questions")
    responses = relationship("Response", back_populates="question")

class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    score = Column(Integer, nullable=True)  # 0 to 10
    feedback = Column(Text, nullable=True)
    strengths = Column(JSON, default=[])
    weaknesses = Column(JSON, default=[])
    created_at = Column(DateTime, default=utc_now)

    question = relationship("Question", back_populates="responses")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
