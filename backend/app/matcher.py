import json
import logging
import google.generativeai as genai
from backend.app.config import DEFAULT_MODEL, GEMINI_API_KEY
from backend.app.parsers import configure_gemini

logger = logging.getLogger(__name__)

def match_candidate_to_jd(candidate_data: dict, jd_data: dict, api_key: str = None) -> dict:
    """
    Compares a candidate's profile against a Job Description to compute a match score,
    matched skills, and missing skills. Uses Gemini for semantic matching, falling back
    to exact token matching if needed.
    """
    # 1. Try Gemini semantic matching
    try:
        configure_gemini(api_key)
        
        # Strip raw_text from jd_data to keep prompt size reasonable
        jd_data_clean = {k: v for k, v in jd_data.items() if k != "raw_text"}
        
        prompt = f"""
        You are an expert recruiter AI. Compare the candidate's resume details and the job description (JD) below.
        
        Calculate:
        1. A match score from 0 to 100 based on how well the candidate's skills, experience, and projects align with the job requirements.
        2. "matched_skills": A list of skills from the JD that the candidate possesses (match synonyms semantically, e.g., 'React.js' matches 'React', 'AI/ML' matches 'Machine Learning').
        3. "missing_skills": A list of key required skills from the JD that the candidate appears to be missing or lacks experience in.

        Candidate Resume JSON:
        {json.dumps(candidate_data, indent=2)}

        Job Description JSON:
        {json.dumps(jd_data_clean, indent=2)}

        Return ONLY a JSON object with this exact structure:
        {{
          "match_score": 82,
          "matched_skills": ["skill1", "skill2"],
          "missing_skills": ["skill3", "skill4"]
        }}
        """
        
        model = genai.GenerativeModel(api_key=api_key or GEMINI_API_KEY, model_name=DEFAULT_MODEL)
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
        
    except Exception as e:
        logger.warning(f"Gemini matching failed, using fallback matcher: {e}")
        return fallback_matching(candidate_data, jd_data)

def fallback_matching(candidate_data: dict, jd_data: dict) -> dict:
    """
    A local fallback matcher that does basic case-insensitive string intersection matching
    of skills.
    """
    candidate_skills = [s.lower().strip() for s in candidate_data.get("skills", [])]
    required_skills = [s.lower().strip() for s in jd_data.get("required_skills", [])]
    
    if not required_skills:
        return {
            "match_score": 50,
            "matched_skills": [],
            "missing_skills": []
        }
        
    matched = []
    missing = []
    
    # We do a basic substring check
    for req in required_skills:
        found = False
        for cand in candidate_skills:
            if req in cand or cand in req:
                matched.append(req)
                found = True
                break
        if not found:
            missing.append(req)
            
    # Clean up display casing by mapping back to original JD skills
    orig_req_skills = jd_data.get("required_skills", [])
    matched_skills_orig = [s for s in orig_req_skills if s.lower().strip() in matched]
    missing_skills_orig = [s for s in orig_req_skills if s.lower().strip() in missing]
    
    # Calculate score
    pct = len(matched_skills_orig) / len(orig_req_skills) if orig_req_skills else 0
    # Experience factor (simplistic fallback)
    match_score = int(pct * 100)
    
    return {
        "match_score": match_score,
        "matched_skills": matched_skills_orig,
        "missing_skills": missing_skills_orig
    }
