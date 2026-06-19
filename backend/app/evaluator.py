import json
import logging
import google.generativeai as genai
from backend.app.config import DEFAULT_MODEL, GEMINI_API_KEY
from backend.app.parsers import configure_gemini, retry_gemini_call

logger = logging.getLogger(__name__)

def evaluate_candidate_answer(
    question_text: str,
    answer_text: str,
    retrieved_context: str,
    role_title: str = "Software Engineer",
    api_key: str = None
) -> dict:
    """
    Evaluates a candidate's answer to a specific question using Gemini.
    Returns a score out of 10, general feedback, and lists of strengths/weaknesses.
    """
    configure_gemini(api_key)
    
    prompt = f"""
    You are an expert technical interviewer and evaluator. Evaluate the candidate's response to the question below.
    
    Target Role: {role_title}
    Question: {question_text}
    Candidate's Answer: {answer_text}
    
    Reference / Expected Context:
    {retrieved_context}
    
    ---
    Evaluation Guidelines:
    1. Score the answer out of 10. Be objective and fair:
       - 0-3: Answer is incorrect, empty, or demonstrates lack of basic understanding.
       - 4-6: Answer is partially correct, but lacks detail, misses core concepts, or is vague.
       - 7-8: Answer is correct, demonstrates solid understanding, handles key aspects well.
       - 9-10: Answer is highly detailed, correct, discusses trade-offs, shows deep expertise.
     2. Provide constructive, direct feedback to the candidate.
     3. Identify specific strengths (what was explained well or correctly).
     4. Identify specific weaknesses (what was missing, incorrect, or requires more detail).
    
    You MUST return ONLY a JSON object with the following structure:
    {{
      "score": 8,
      "feedback": "Constructive explanation of the score and the answer's quality.",
      "strengths": ["Key strength 1", "Key strength 2"],
      "weaknesses": ["Key weakness 1", "Key weakness 2"]
    }}
    """
    
    try:
        model = genai.GenerativeModel(api_key=api_key or GEMINI_API_KEY, model_name=DEFAULT_MODEL)
        response = retry_gemini_call(
            model.generate_content,
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        result = json.loads(response.text)
        
        # Ensure score is an integer within bounds
        score = result.get("score", 5)
        try:
            score = int(score)
            score = max(0, min(10, score))
        except ValueError:
            score = 5
        result["score"] = score
        
        # Ensure lists are lists of strings
        for list_key in ["strengths", "weaknesses"]:
            if not isinstance(result.get(list_key), list):
                result[list_key] = [str(result.get(list_key))] if result.get(list_key) else []
                
        return result
        
    except Exception as e:
        logger.error(f"Error evaluating candidate answer (using offline heuristic grading): {e}")
        
        clean_ans = answer_text.strip().lower()
        word_count = len(clean_ans.split())
        
        # Heuristic rules for offline grading
        if not clean_ans or len(clean_ans) < 12:
            return {
                "score": 1,
                "feedback": "The answer is empty or too short to demonstrate any understanding of the question.",
                "strengths": [],
                "weaknesses": ["Response was too brief or empty."]
            }
        elif any(phrase in clean_ans for phrase in ["i don't know", "i dont know", "no idea", "unsure", "dont know", "skip"]):
            return {
                "score": 1,
                "feedback": "The candidate indicated that they do not know the answer or wish to skip this question.",
                "strengths": [],
                "weaknesses": ["No conceptual explanation was attempted."]
            }
        else:
            # Baseline scoring depending on description length
            if word_count > 60:
                score = 6
                feedback = "Heuristic Grading (API Offline): Detailed attempt provided. Baseline credit applied."
                strengths = ["Detailed response length indicating technical explanation attempt"]
                weaknesses = ["Detailed AI evaluation is unavailable due to rate limits."]
            elif word_count > 25:
                score = 5
                feedback = "Heuristic Grading (API Offline): Brief explanation attempted."
                strengths = ["Attempted to answer the question"]
                weaknesses = ["Detailed AI evaluation is unavailable due to rate limits. Response is somewhat short."]
            else:
                score = 3
                feedback = "Heuristic Grading (API Offline): Response is very short and lacks conceptual depth."
                strengths = ["Attempted answer"]
                weaknesses = ["Detailed AI evaluation is unavailable. Response length is extremely short."]
                
            return {
                "score": score,
                "feedback": feedback,
                "strengths": strengths,
                "weaknesses": weaknesses
            }
