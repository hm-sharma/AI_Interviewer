import os
import sys
import unittest
from datetime import datetime

# Add root folder to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.database import init_db, SessionLocal, Candidate, JobDescription, Interview, Question, Response
from backend.app import interviewer
from backend.app import reporter
from backend.app.vector_store import RAGEngine

class TestInterviewerSystem(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Initialize database
        init_db()
        cls.db = SessionLocal()
        
    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        
    def test_database_models(self):
        """Test database model creation and querying."""
        # Insert Candidate
        candidate = Candidate(
            name="Test Candidate",
            email="test_candidate@example.com",
            resume_path="dummy_path.pdf",
            skills=["Python", "FastAPI", "SQLite"],
            education=[{"degree": "BSCS"}],
            experience=[{"role": "Developer"}],
            projects=[{"title": "Test Project"}]
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        
        self.assertIsNotNone(candidate.id)
        self.assertEqual(candidate.name, "Test Candidate")
        
        # Query Candidate
        fetched = self.db.query(Candidate).filter(Candidate.email == "test_candidate@example.com").first()
        self.assertEqual(fetched.id, candidate.id)
        
        # Cleanup
        self.db.delete(candidate)
        self.db.commit()

    def test_interviewer_helpers(self):
        """Test question category selection and difficulty mapping."""
        # Category checks
        self.assertEqual(interviewer.determine_question_category(1, 5), "technical")
        self.assertEqual(interviewer.determine_question_category(2, 5), "project")
        self.assertEqual(interviewer.determine_question_category(3, 5), "technical")
        self.assertEqual(interviewer.determine_question_category(4, 5), "project")
        self.assertEqual(interviewer.determine_question_category(5, 5), "behavioral")
        
        # Difficulty adjustment checks
        self.assertEqual(interviewer.adjust_difficulty(2, 9), 3)  # score > 8 -> increase
        self.assertEqual(interviewer.adjust_difficulty(2, 3), 1)  # score < 4 -> decrease
        self.assertEqual(interviewer.adjust_difficulty(2, 6), 2)  # score 4-8 -> keep
        self.assertEqual(interviewer.adjust_difficulty(4, 10), 4) # cap at 4
        self.assertEqual(interviewer.adjust_difficulty(1, 1), 1)  # floor at 1

    def test_reporter_helpers(self):
        """Test recommendation score mapping."""
        self.assertEqual(reporter.get_recommendation_label(8.5), "Strongly Recommended")
        self.assertEqual(reporter.get_recommendation_label(7.0), "Recommended")
        self.assertEqual(reporter.get_recommendation_label(5.5), "Not Recommended")
        
        self.assertEqual(reporter.get_recommendation_color("Strongly Recommended"), "#10B981")
        self.assertEqual(reporter.get_recommendation_color("Recommended"), "#3B82F6")
        self.assertEqual(reporter.get_recommendation_color("Not Recommended"), "#EF4444")

    def test_rag_chunking(self):
        """Test the paragraph and fallback chunking methods inside RAG engine."""
        engine = RAGEngine()
        text = "Paragraph one is short.\n\nParagraph two is also short.\n\nParagraph three is a bit longer but still fine."
        chunks = engine.chunk_text(text, max_chunk_size=100)
        self.assertTrue(len(chunks) > 0)
        
        # Test long single string chunking fallback
        long_text = "A" * 600
        chunks_long = engine.chunk_text(long_text, max_chunk_size=200)
        self.assertEqual(len(chunks_long), 3)

if __name__ == "__main__":
    unittest.main()
