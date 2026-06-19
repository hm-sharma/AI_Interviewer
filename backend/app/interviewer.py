import logging
import google.generativeai as genai
from backend.app.config import DEFAULT_MODEL, GEMINI_API_KEY
from backend.app.parsers import configure_gemini, retry_gemini_call

logger = logging.getLogger(__name__)

# Map difficulty levels to descriptions
DIFFICULTY_MAP = {
    1: "Level 1: Fundamentals (Core concepts, simple syntax, basic terms)",
    2: "Level 2: Intermediate (Implementation, debugging, simple trade-offs, standard patterns)",
    3: "Level 3: Advanced (Architecture, system design, optimization, edge-case handling)",
    4: "Level 4: Expert (Advanced internals, scale constraints, complex trade-offs, deep system design)"
}

def determine_question_category(q_num: int, total_qs: int) -> str:
    """Determines the category of a question based on its index and total count."""
    if q_num == total_qs:
        return "behavioral"
    elif q_num % 2 == 0:
        return "project"
    else:
        return "technical"

def generate_interview_question(
    candidate_profile: dict,
    jd_profile: dict,
    question_number: int,
    total_questions: int,
    difficulty: int,
    retrieved_context: str,
    history: list, # List of dicts with {"question": "", "answer": "", "score": 8}
    api_key: str = None
) -> str:
    """
    Generates a personalized, context-aware interview question using Gemini.
    Takes into account candidate resume details, JD details, current difficulty,
    RAG contexts, and history to prevent duplicate questions.
    """
    configure_gemini(api_key)
    
    category = determine_question_category(question_number, total_questions)
    difficulty_desc = DIFFICULTY_MAP.get(difficulty, DIFFICULTY_MAP[2])
    
    # Format history for the prompt
    history_lines = []
    for i, h in enumerate(history):
        history_lines.append(f"Q{i+1}: {h.get('question')}")
        history_lines.append(f"A{i+1}: {h.get('answer')[:150]}... (Evaluated Score: {h.get('score')}/10)")
    history_text = "\n".join(history_lines) if history_lines else "No questions asked yet."

    prompt = f"""
    You are an elite technical interviewer. Your objective is to formulate the next interview question for a candidate.
    
    Candidate Name: {candidate_profile.get("name", "Candidate")}
    Target Role: {jd_profile.get("role", "Software Engineer")}
    
    Current Progress: Question {question_number} of {total_questions}
    Current Difficulty Level: {difficulty_desc}
    Target Category: {category.upper()} (Technical, Project-based, or Behavioral)
    
    Relevant Context from Candidate Resume and JD (RAG):
    {retrieved_context}
    
    Previous Interview History:
    {history_text}
    
    ---
    Instructions:
    1. If Category is TECHNICAL: Generate a question targeting key skills or tools required in the Job Description, focusing on the candidate's declared skills. Maintain the target difficulty constraints.
    2. If Category is PROJECT: Formulate a question asking for technical details, design decisions, challenges, or architectural trade-offs on one of the projects listed on the candidate's resume (use the RAG context).
    3. If Category is BEHAVIORAL: Generate a behavioral question (STAR method) designed to assess leadership, teamwork, problem-solving, or adaptability.
    4. Keep the question professional, concise, and realistic (something a senior engineer would ask).
    5. CRITICAL: Do NOT duplicate, re-evaluate, or follow up too closely on questions already asked in the history. Ensure this is a NEW question.
    6. Return ONLY the question text. Do not output any headers, introductions ("Sure, here is...", "Next question:"), or side explanations.
    """

    try:
        model = genai.GenerativeModel(api_key=api_key or GEMINI_API_KEY, model_name=DEFAULT_MODEL)
        response = retry_gemini_call(
            model.generate_content,
            prompt
        )
        question = response.text.strip()
        
        # Clean any accidental quotes or headers
        if question.startswith('"') and question.endswith('"'):
            question = question[1:-1]
        if question.startswith("Question:"):
            question = question.replace("Question:", "").strip()
            
        return question
        
    except Exception as e:
        logger.error(f"Error generating question (falling back to dynamic offline list): {e}")
        
        # Format template values
        skills = candidate_profile.get('skills', [])
        tech = skills[0] if skills else 'your main technology'
        
        # Predefined set of fallback questions to avoid duplicates
        FALLBACK_QUESTIONS = {
            "technical": [
                "Explain the core components and life cycle of a standard system built with {tech}.",
                "What are some key optimization strategies and common performance bottlenecks in a {tech} application?",
                "Describe how you handle asynchronous processing, concurrency, or multi-threading when working with {tech}.",
                "How does memory management, garbage collection, or resource clean-up work in {tech}?",
                "Explain the difference between SQL and NoSQL databases, and how you would design a data storage layer for a high-throughput system."
            ],
            "project": [
                "Can you describe the architecture of the most challenging project you've worked on, and explain why you made those technology choices?",
                "Tell me about a major scaling bottleneck or technical challenge you encountered in a past project and how you diagnosed and resolved it.",
                "Explain how you structured the testing, CI/CD pipeline, and deployment strategy for one of your recent projects.",
                "In your resume, you listed some projects. Pick one and explain how you handled database design, data consistency, or third-party API integrations.",
                "Describe a situation in a project where you had to refactor a piece of legacy code or redesign an existing feature to support new requirements."
            ],
            "behavioral": [
                "Tell me about a time when you faced a conflict in a team or with a stakeholder, and how you went about resolving it.",
                "Describe a situation where you had to meet a tight deadline under pressure. What steps did you take to ensure a quality deliverable?",
                "Tell me about a time when you made a technical mistake or project error. How did you communicate it and what did you learn?",
                "Describe a time when you had to work with a technology you were unfamiliar with to solve a problem. How did you get up to speed?",
                "Tell me about a time when you disagreed with a technical direction chosen by your team. How did you express your view and reach alignment?"
            ]
        }
        
        asked_questions = {h.get("question", "").strip().lower() for h in history}
        candidates = FALLBACK_QUESTIONS.get(category, FALLBACK_QUESTIONS["technical"])
        
        selected_q = None
        for q_tpl in candidates:
            q_text = q_tpl.format(tech=tech)
            if q_text.strip().lower() not in asked_questions:
                selected_q = q_text
                break
                
        if not selected_q:
            selected_q = candidates[0].format(tech=tech)
            
        return selected_q

def adjust_difficulty(current_difficulty: int, last_score: int) -> int:
    """
    Adjusts the difficulty level (1 to 4) based on the score of the last answer.
    """
    if last_score > 8:
        new_diff = current_difficulty + 1
        return min(new_diff, 4)
    elif last_score < 4:
        new_diff = current_difficulty - 1
        return max(new_diff, 1)
    return current_difficulty
