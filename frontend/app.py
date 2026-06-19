import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import threading
import time
import sys
import os

# Ensure project root folder is in python path for module loading
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# ----------------- BACKEND THREAD STARTUP (FOR STREAMLIT CLOUD DEPLOYMENT) -----------------
# Automatically spins up the FastAPI backend inside a background thread if not already running.
def run_backend():
    import uvicorn
    # Import uvicorn locally to prevent importing issues on start
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, log_level="warning")

# Check if backend port 8000 is open
backend_running = False
try:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    s.connect(("127.0.0.1", 8000))
    backend_running = True
    s.close()
except Exception:
    pass

if not backend_running:
    # Ensure thread is only registered once
    if not any(thread.name == "FastAPI-Backend" for thread in threading.enumerate()):
        backend_thread = threading.Thread(target=run_backend, name="FastAPI-Backend", daemon=True)
        backend_thread.start()
        # Wait a moment for database initialization
        time.sleep(2.5)

# Set page config
st.set_page_config(
    page_title="AI-Based Adaptive Interviewer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern design and typography (Outfit font, smooth gradients, cards)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

/* Main Fonts */
html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #0F172A !important;
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}
[data-testid="stSidebar"] * {
    color: #F8FAFC !important;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background-color: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
    background-color: rgba(255, 255, 255, 0.08);
}

/* Custom gradients & headers */
.main-header {
    background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 2.8rem;
    margin-bottom: 5px;
}

.sub-header {
    color: #4B5563;
    font-size: 1.2rem;
    font-weight: 300;
    margin-bottom: 25px;
}

/* Styled Cards (Glassmorphism look with interactive hover effects) */
.glass-card {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 22px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    margin-bottom: 15px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.glass-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

/* Login Container styles */
.login-container {
    max-width: 480px;
    margin: 60px auto;
    padding: 35px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -2px rgba(0, 0, 0, 0.05);
    backdrop-filter: blur(10px);
}

.login-title {
    text-align: center;
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 25px;
}

/* Question Banner */
.question-box {
    background-color: rgba(128, 128, 128, 0.08);
    border-left: 5px solid #3B82F6;
    border-radius: 0 8px 8px 0;
    padding: 18px;
    margin: 15px 0;
    font-size: 1.15rem;
    font-weight: 500;
}

/* Difficulty Stars / Labels */
.diff-badge {
    background-color: #E0E7FF;
    color: #4338CA;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}

.category-badge {
    background-color: #FEF3C7;
    color: #D97706;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}

/* Score displays */
.score-big {
    font-size: 3rem;
    font-weight: 700;
    color: #1E3A8A;
    line-height: 1;
}

/* Status Badges */
.badge-rec-strong {
    background-color: #D1FAE5;
    color: #065F46;
    padding: 6px 12px;
    border-radius: 30px;
    font-weight: 700;
    display: inline-block;
}

.badge-rec-normal {
    background-color: #DBEAFE;
    color: #1E40AF;
    padding: 6px 12px;
    border-radius: 30px;
    font-weight: 700;
    display: inline-block;
}

.badge-rec-not {
    background-color: #FEE2E2;
    color: #991B1B;
    padding: 6px 12px;
    border-radius: 30px;
    font-weight: 700;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE INITS -----------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'candidate_email' not in st.session_state:
    st.session_state.candidate_email = ""
if 'api_key_configured' not in st.session_state:
    st.session_state.api_key_configured = True
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'backend_url' not in st.session_state:
    st.session_state.backend_url = "http://127.0.0.1:8000"
if 'candidate_id' not in st.session_state:
    st.session_state.candidate_id = None
if 'candidate_name' not in st.session_state:
    st.session_state.candidate_name = ""
if 'jd_id' not in st.session_state:
    st.session_state.jd_id = None
if 'jd_role' not in st.session_state:
    st.session_state.jd_role = ""
if 'match_details' not in st.session_state:
    st.session_state.match_details = None
if 'interview_id' not in st.session_state:
    st.session_state.interview_id = None
if 'current_question_id' not in st.session_state:
    st.session_state.current_question_id = None
if 'current_question_text' not in st.session_state:
    st.session_state.current_question_text = ""
if 'current_question_number' not in st.session_state:
    st.session_state.current_question_number = 0
if 'total_questions' not in st.session_state:
    st.session_state.total_questions = 5
if 'difficulty' not in st.session_state:
    st.session_state.difficulty = 2
if 'interview_status' not in st.session_state:
    st.session_state.interview_status = "idle" # idle, match_preview, ongoing, completed
if 'latest_evaluation' not in st.session_state:
    st.session_state.latest_evaluation = None
if 'last_answer' not in st.session_state:
    st.session_state.last_answer = ""
if 'refresh_list' not in st.session_state:
    st.session_state.refresh_list = True

# Helper header dict
def get_headers():
    headers = {}
    if st.session_state.api_key:
        headers["x-gemini-key"] = st.session_state.api_key
    return headers

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("frontend/ai_interviewer_logo.png", use_container_width=True)
    st.markdown("<h3 style='text-align: center; margin-top: -5px; font-family: Outfit;'>AI Interviewer</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    if st.session_state.get("logged_in", False):
        st.markdown(f"**Role:** `{st.session_state.user_role.capitalize()}`")
        if st.session_state.user_role == "candidate":
            st.markdown(f"👤 **{st.session_state.candidate_name}**")
            st.markdown(f"<small style='word-break: break-all;'>{st.session_state.candidate_email}</small>", unsafe_allow_html=True)
            mode = "Candidate Portal"
        else:
            mode = st.radio("Navigation", ["Recruiter Dashboard", "Candidate Portal"], index=0)
            
        st.markdown("---")
        st.markdown("### System Configuration")
        total_qs_input = st.number_input("Question Count", min_value=3, max_value=10, value=st.session_state.total_questions)
        st.session_state.total_questions = total_qs_input
        
        st.markdown("---")
        if st.button("Logout", use_container_width=True, type="secondary"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.candidate_email = ""
            st.session_state.candidate_name = ""
            st.session_state.interview_status = "idle"
            st.session_state.candidate_id = None
            st.session_state.jd_id = None
            st.session_state.interview_id = None
            st.rerun()
    else:
        st.info("🔒 Please authenticate in the main portal to proceed.")
        mode = "Candidate Portal"
        
    st.markdown("---")
    st.markdown("<small style='color: gray;'>Powered by Gemini & FAISS RAG</small>", unsafe_allow_html=True)


# ----------------- BACKEND STATUS CHECK -----------------
try:
    health_check = requests.get(f"{st.session_state.backend_url}/")
    is_online = health_check.status_code == 200
    api_key_configured = health_check.json().get("api_key_configured", True) if is_online else False
except Exception:
    is_online = False
    api_key_configured = False

if not is_online:
    st.error(f"⚠️ Unable to connect to the backend server at `{st.session_state.backend_url}`. Please make sure the backend server is running.")
    st.stop()

st.session_state.api_key_configured = api_key_configured


# ----------------- LOGIN PORTAL -----------------
if not st.session_state.get("logged_in", False):
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 class='login-title'>AI Interviewer Portal</h2>", unsafe_allow_html=True)
    
    login_tabs = st.tabs(["Candidate Sign In", "Recruiter Login"])
    
    with login_tabs[0]:
        c_name = st.text_input("Your Full Name", placeholder="e.g. Jane Doe", key="login_c_name")
        c_email = st.text_input("Your Email Address", placeholder="e.g. jane.doe@example.com", key="login_c_email")
        if st.button("Enter Candidate Portal", type="primary", use_container_width=True, key="login_c_btn"):
            if not c_name.strip() or not c_email.strip():
                st.error("Please enter both your name and email to proceed.")
            else:
                st.session_state.logged_in = True
                st.session_state.user_role = "candidate"
                st.session_state.candidate_name = c_name.strip()
                st.session_state.candidate_email = c_email.strip()
                st.rerun()
                
    with login_tabs[1]:
        r_user = st.text_input("Recruiter Username", placeholder="admin", key="login_r_user")
        r_pass = st.text_input("Passcode", type="password", placeholder="Enter recruiter password", key="login_r_pass")
        if st.button("Login as Recruiter", type="primary", use_container_width=True, key="login_r_btn"):
            if r_user.strip() == "admin" and r_pass == "recruiter123":
                st.session_state.logged_in = True
                st.session_state.user_role = "recruiter"
                st.rerun()
            else:
                st.error("Invalid recruiter credentials.")
                
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ----------------- MAIN TITLE -----------------
st.markdown("<h1 class='main-header'>AI-Based Adaptive Interviewer</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Conducting context-rich, objective recruitment screening at scale</p>", unsafe_allow_html=True)

if not st.session_state.api_key_configured:
    st.warning("⚠️ **API Key Config Notice**: The backend did not find a valid `GEMINI_API_KEY` in environment variables or your `.env` file. The application is running using a fallback key or offline mock mode. If API requests fail, please make sure your `.env` file is set up correctly in the project root directory and restart the backend.")


# ----------------- CANDIDATE PORTAL -----------------
if mode == "Candidate Portal":
    
    # CASE 1: IDLE / NOT STARTED
    if st.session_state.interview_status == "idle":
        st.markdown("### Welcome Candidate! Let's get started.")
        st.info("To start, please upload your resume and select/upload the Job Description (JD) you are applying for.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.subheader("Step 1: Your Resume")
            if st.session_state.user_role == "candidate":
                st.markdown(f"**Email Address:** `{st.session_state.candidate_email}`")
                candidate_email = st.session_state.candidate_email
            else:
                candidate_email = st.text_input("Your Email Address", value=st.session_state.candidate_email, placeholder="candidate@example.com")
            resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col2:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.subheader("Step 2: Job Description")
            
            # Fetch existing JDs
            existing_jds = []
            try:
                jds_res = requests.get(f"{st.session_state.backend_url}/jds")
                if jds_res.status_code == 200:
                    existing_jds = jds_res.json()
            except Exception as e:
                st.warning("Could not fetch pre-existing JDs.")
                
            jd_options = ["-- Upload New Job Description --"] + [f"{j['role']} (ID: {j['jd_id']})" for j in existing_jds]
            selected_jd_opt = st.selectbox("Select target Job Description", jd_options)
            
            uploaded_jd_file = None
            if selected_jd_opt == "-- Upload New Job Description --":
                uploaded_jd_file = st.file_uploader("Upload Job Description (TXT)", type=["txt"])
            st.markdown("</div>", unsafe_allow_html=True)
            
        # Processing uploads
        if st.button("Parse Documents & Analyze Profile", type="primary"):
            if not candidate_email or not resume_file:
                st.error("Please provide both your email and resume PDF.")
            elif selected_jd_opt == "-- Upload New Job Description --" and not uploaded_jd_file:
                st.error("Please upload a Job Description TXT or select a pre-loaded one.")
            else:
                with st.spinner("Parsing documents and initializing AI engine..."):
                    # 1. Upload Resume
                    files_resume = {"file": (resume_file.name, resume_file.getvalue(), "application/pdf")}
                    data_resume = {"email": candidate_email}
                    
                    try:
                        res_resume = requests.post(
                            f"{st.session_state.backend_url}/upload-resume",
                            files=files_resume,
                            data=data_resume,
                            headers=get_headers()
                        )
                        if res_resume.status_code != 200:
                            st.error(f"Resume parser error: {res_resume.json().get('detail')}")
                            st.stop()
                            
                        res_data = res_resume.json()
                        st.session_state.candidate_id = res_data["candidate_id"]
                        parsed_name = res_data.get("name", "Unknown")
                        if parsed_name != "Unknown":
                            st.session_state.candidate_name = parsed_name
                        
                        # 2. Setup JD
                        if selected_jd_opt == "-- Upload New Job Description --":
                            files_jd = {"file": (uploaded_jd_file.name, uploaded_jd_file.getvalue(), "text/plain")}
                            res_jd = requests.post(
                                f"{st.session_state.backend_url}/upload-jd",
                                files=files_jd,
                                headers=get_headers()
                            )
                            if res_jd.status_code != 200:
                                st.error(f"JD parser error: {res_jd.json().get('detail')}")
                                st.stop()
                            jd_data = res_jd.json()
                            st.session_state.jd_id = jd_data["jd_id"]
                            st.session_state.jd_role = jd_data["role"]
                        else:
                            # Parse ID
                            selected_id = int(selected_jd_opt.split("ID: ")[1][:-1])
                            matching_jd = next(j for j in existing_jds if j["jd_id"] == selected_id)
                            st.session_state.jd_id = matching_jd["jd_id"]
                            st.session_state.jd_role = matching_jd["role"]
                            
                        # 3. Match candidate to JD
                        res_match = requests.post(
                            f"{st.session_state.backend_url}/match-candidate",
                            params={"candidate_id": st.session_state.candidate_id, "jd_id": st.session_state.jd_id},
                            headers=get_headers()
                        )
                        if res_match.status_code == 200:
                            st.session_state.match_details = res_match.json()
                            
                        st.session_state.interview_status = "match_preview"
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Failed to communicate with parsing service: {e}")
                        
    # CASE 2: DOCUMENT MATCH PREVIEW
    elif st.session_state.interview_status == "match_preview":
        st.markdown(f"### Profile Analysis: {st.session_state.candidate_name} &rarr; {st.session_state.jd_role}")
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        
        with col1:
            match_score = st.session_state.match_details.get("match_score", 0)
            
            # Simple Gauge chart
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = match_score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Resume-JD Match Score", 'font': {'size': 18, 'family': 'Outfit'}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "#3B82F6"},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, 50], 'color': '#FEE2E2'},
                        {'range': [50, 80], 'color': '#FEF3C7'},
                        {'range': [80, 100], 'color': '#D1FAE5'}
                    ],
                }
            ))
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.markdown("#### Competency Breakdown")
            
            matched_skills = st.session_state.match_details.get("matched_skills", [])
            missing_skills = st.session_state.match_details.get("missing_skills", [])
            
            st.markdown("**Matched Skills/Competencies:**")
            if matched_skills:
                # Render badges
                badges_html = " ".join([f"<span class='badge-rec-normal' style='margin: 3px; font-size: 0.8rem; padding: 3px 8px;'>{s}</span>" for s in matched_skills])
                st.markdown(badges_html, unsafe_allow_html=True)
            else:
                st.write("*No skills matched automatically.*")
                
            st.markdown("<br/>**Missing/Underrepresented Skills:**", unsafe_allow_html=True)
            if missing_skills:
                badges_html = " ".join([f"<span class='badge-rec-not' style='margin: 3px; font-size: 0.8rem; padding: 3px 8px;'>{s}</span>" for s in missing_skills])
                st.markdown(badges_html, unsafe_allow_html=True)
            else:
                st.write("*Your profile meets all explicit skills requirements!*")
                
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("#### Ready to begin your Interview?")
        st.write("The interview comprises **5 dynamically adjusted questions** covering: **Technical skills**, **past projects**, and **behavioral aspects**.")
        st.write("Difficulty adapts in real-time based on your responses. You can write your answer and submit. There is no time limit, but please provide complete explanations.")
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("Start Interview", type="primary", use_container_width=True):
                with st.spinner("Generating initial question..."):
                    try:
                        res = requests.post(
                            f"{st.session_state.backend_url}/start-interview",
                            params={
                                "candidate_id": st.session_state.candidate_id, 
                                "jd_id": st.session_state.jd_id,
                                "question_count": st.session_state.total_questions
                            },
                            headers=get_headers()
                        )
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state.interview_id = data["interview_id"]
                            st.session_state.current_question_id = data["question_id"]
                            st.session_state.current_question_text = data["question_text"]
                            st.session_state.current_question_number = data["question_number"]
                            st.session_state.difficulty = data["difficulty"]
                            st.session_state.interview_status = "ongoing"
                            st.rerun()
                        else:
                            st.error(f"Failed to start interview: {res.json().get('detail')}")
                    except Exception as e:
                        st.error(f"Network error starting interview: {e}")
        with col_btn2:
            if st.button("Cancel & Start Over", type="secondary"):
                st.session_state.interview_status = "idle"
                st.rerun()

    # CASE 3: ONGOING INTERVIEW
    elif st.session_state.interview_status == "ongoing":
        q_num = st.session_state.current_question_number
        tot_q = st.session_state.total_questions
        
        # Header showing progress
        col_h1, col_h2 = st.columns([4, 1])
        with col_h1:
            st.markdown(f"### Question {q_num} of {tot_q}")
            st.progress(float(q_num) / float(tot_q))
        with col_h2:
            # Map diff level
            stars = "⭐️" * st.session_state.difficulty
            st.markdown(f"<div style='text-align: right;'><span class='diff-badge'>{stars} Level {st.session_state.difficulty}</span></div>", unsafe_allow_html=True)
            
        # Display latest evaluation feedback if available (showing what was scored on last answer)
        if st.session_state.latest_evaluation:
            st.markdown("<div class='glass-card' style='background-color: #F9FAFB; border-left: 5px solid #10B981;'>", unsafe_allow_html=True)
            st.markdown(f"**Previous Question Feedback (Score: {st.session_state.latest_evaluation['score']}/10):**")
            st.write(st.session_state.latest_evaluation['feedback'])
            st.markdown("</div>", unsafe_allow_html=True)
            st.session_state.latest_evaluation = None # clear so it only shows once
            
        # Display current question
        st.markdown(f"<div class='question-box'>{st.session_state.current_question_text}</div>", unsafe_allow_html=True)
        
        # User answer text area
        # We key it by question ID to ensure it clears/resets when the question changes
        ans_input = st.text_area(
            "Write your response here:", 
            key=f"ans_text_q_{st.session_state.current_question_id}", 
            height=180,
            placeholder="Type your explanation, coding concepts, or behavioral scenarios in detail..."
        )
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("Submit Answer", type="primary", use_container_width=True):
                if not ans_input.strip():
                    st.warning("Please type an answer before submitting.")
                else:
                    with st.spinner("Submitting and evaluating response..."):
                        try:
                            payload = {
                                "interview_id": st.session_state.interview_id,
                                "question_id": st.session_state.current_question_id,
                                "answer": ans_input,
                                "question_count": st.session_state.total_questions
                            }
                            res = requests.post(
                                f"{st.session_state.backend_url}/submit-answer",
                                params=payload,
                                headers=get_headers()
                            )
                            if res.status_code == 200:
                                data = res.json()
                                # Track evaluation
                                st.session_state.latest_evaluation = data["evaluation"]
                                
                                if data["status"] == "completed":
                                    st.session_state.interview_status = "completed"
                                    st.success("🎉 Interview Completed! Compiling report...")
                                    st.rerun()
                                else:
                                    # Setup next question
                                    st.session_state.current_question_id = data["next_question_id"]
                                    st.session_state.current_question_text = data["next_question_text"]
                                    st.session_state.current_question_number = data["next_question_number"]
                                    st.session_state.difficulty = data["difficulty"]
                                    st.rerun()
                            else:
                                st.error(f"Failed to submit answer: {res.json().get('detail')}")
                        except Exception as e:
                            st.error(f"Network error submitting answer: {e}")
        with col_btn2:
            st.markdown("<small style='line-height: 2.5; color: gray;'>Submitting will adapt the next question's difficulty.</small>", unsafe_allow_html=True)

    # CASE 4: COMPLETED & VIEWING REPORT
    elif st.session_state.interview_status == "completed":
        st.balloons()
        st.markdown("## Interview Assessment Completed")
        st.write("Thank you for attending the interview. Your results have been automatically processed and compiled.")
        
        with st.spinner("Fetching report details..."):
            try:
                res = requests.get(f"{st.session_state.backend_url}/get-report/{st.session_state.interview_id}")
                if res.status_code == 200:
                    report = res.json()
                    
                    # Score and recommendation layout
                    rec_label = report["recommendation"]
                    rec_color = "#10B981" if rec_label == "Strongly Recommended" else ("#3B82F6" if rec_label == "Recommended" else "#EF4444")
                    
                    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.markdown("<p style='margin: 0; color: gray; font-size: 0.9rem;'>OVERALL PERFORMANCE SCORE</p>", unsafe_allow_html=True)
                        st.markdown(f"<p class='score-big'>{report['score']:.1f} <span style='font-size: 1.5rem; color: gray;'>/ 10</span></p>", unsafe_allow_html=True)
                        st.markdown(f"<span class='badge-rec-normal' style='background-color: {rec_color}30; color: {rec_color}; font-size: 1.1rem; padding: 6px 16px;'>{rec_label}</span>", unsafe_allow_html=True)
                    with col2:
                        st.markdown("#### Executive Summary")
                        st.write(report["summary"])
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Strengths and Weaknesses
                    col_s, col_w = st.columns(2)
                    with col_s:
                        st.markdown("<div class='glass-card' style='border-left: 5px solid #10B981;'>", unsafe_allow_html=True)
                        st.markdown("##### 🟢 Core Strengths")
                        for s in report.get("strengths", []):
                            st.markdown(f"- {s}")
                        st.markdown("</div>", unsafe_allow_html=True)
                    with col_w:
                        st.markdown("<div class='glass-card' style='border-left: 5px solid #EF4444;'>", unsafe_allow_html=True)
                        st.markdown("##### 🔴 Areas of Improvement")
                        for w in report.get("weaknesses", []):
                            st.markdown(f"- {w}")
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    # Transcript & Questions
                    st.markdown("### Detailed Interview Transcript")
                    for idx, qa in enumerate(report["qa"]):
                        with st.expander(f"Q{idx+1}: {qa['question'][:80]}... (Score: {qa['score']}/10)"):
                            st.markdown(f"**Category:** <span class='category-badge'>{qa['category'].upper()}</span> &nbsp; **Difficulty:** <span class='diff-badge'>Level {qa['difficulty']}</span>", unsafe_allow_html=True)
                            st.markdown(f"<br/>**Question:**<br/>{qa['question']}", unsafe_allow_html=True)
                            st.markdown(f"**Candidate Answer:**<br/><p style='font-style: italic; color: #4B5563;'>{qa['answer']}</p>", unsafe_allow_html=True)
                            st.markdown(f"**AI Score:** **{qa['score']}/10**")
                            st.markdown(f"**AI Feedback:** {qa['feedback']}")
                            
                    # Download Link
                    pdf_url = f"{st.session_state.backend_url}/download-report/{st.session_state.interview_id}"
                    st.markdown("---")
                    
                    # Setup download button triggering FastAPI file streaming
                    try:
                        pdf_res = requests.get(pdf_url)
                        if pdf_res.status_code == 200:
                            st.download_button(
                                label="Download Full PDF Report",
                                data=pdf_res.content,
                                file_name=f"{report['candidate']['name']}_Hiring_Report.pdf",
                                mime="application/pdf",
                                type="primary"
                            )
                    except Exception as e:
                        st.error("Failed to prepare PDF download file.")
                        
                else:
                    st.error("Failed to load interview report details.")
            except Exception as e:
                st.error(f"Error loading final report: {e}")
                
        if st.button("Start a New Interview / Reset"):
            st.session_state.interview_status = "idle"
            st.session_state.candidate_id = None
            st.session_state.jd_id = None
            st.session_state.interview_id = None
            st.rerun()


# ----------------- RECRUITER DASHBOARD -----------------
else:
    st.markdown("### Recruiter Administration & Analytics")
    
    tab_interviews, tab_jds = st.tabs(["Candidate Interview Reports", "Job Descriptions (JDs)"])
    
    with tab_interviews:
        # Fetch interviews
        interviews = []
        try:
            res_int = requests.get(f"{st.session_state.backend_url}/interviews")
            if res_int.status_code == 200:
                interviews = res_int.json()
        except Exception:
            st.error("Failed to connect to backend database.")
            
        if not interviews:
            st.info("No interview records found in the database. Instruct candidates to apply or run a mock session.")
        else:
            # Create a nice dashboard list
            df = pd.DataFrame(interviews)
            
            # Simple Chart of scores
            completed_interviews = df[df["status"] == "completed"]
            
            if not completed_interviews.empty:
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    st.markdown("##### Candidate Score Distribution")
                    fig = px.bar(
                        completed_interviews,
                        x="candidate_name",
                        y="score",
                        color="recommendation",
                        color_discrete_map={
                            "Strongly Recommended": "#10B981",
                            "Recommended": "#3B82F6",
                            "Not Recommended": "#EF4444"
                        },
                        labels={"candidate_name": "Candidate", "score": "Interview Score (Avg)"},
                        height=300
                    )
                    fig.update_layout(font_family="Outfit")
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col_chart2:
                    st.markdown("##### Recommendation Breakdown")
                    rec_counts = completed_interviews["recommendation"].value_counts().reset_index()
                    rec_counts.columns = ["Recommendation", "Count"]
                    fig_pie = px.pie(
                        rec_counts,
                        values="Count",
                        names="Recommendation",
                        color="Recommendation",
                        color_discrete_map={
                            "Strongly Recommended": "#10B981",
                            "Recommended": "#3B82F6",
                            "Not Recommended": "#EF4444"
                        },
                        hole=0.4,
                        height=300
                    )
                    fig_pie.update_layout(font_family="Outfit")
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
            st.markdown("##### All Interviews List")
            # Format dataframe for display
            df_display = df.copy()
            df_display["created_at"] = df_display["created_at"].apply(lambda x: datetime.fromisoformat(x).strftime("%Y-%m-%d %H:%M"))
            df_display["score"] = df_display["score"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
            df_display.columns = ["Interview ID", "Candidate Name", "Email", "Target Role", "Score", "Recommendation", "Status", "Date"]
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Select specific interview to inspect details
            st.markdown("##### Detailed Candidate Report Inspector")
            selected_int_id = st.selectbox(
                "Select Candidate Interview ID to view assessment report details:", 
                df["interview_id"].unique(),
                format_func=lambda x: f"Interview #{x} - {df[df['interview_id'] == x]['candidate_name'].values[0]} ({df[df['interview_id'] == x]['role'].values[0]})"
            )
            
            if selected_int_id:
                # Load report details
                with st.spinner("Loading candidate details..."):
                    try:
                        res_rep = requests.get(f"{st.session_state.backend_url}/get-report/{selected_int_id}")
                        if res_rep.status_code == 200:
                            report = res_rep.json()
                            
                            if report["status"] == "ongoing":
                                st.warning(f"This interview is currently ONGOING. Currently on question {report['current_question_number']}.")
                            else:
                                rec_label = report["recommendation"]
                                rec_color = "#10B981" if rec_label == "Strongly Recommended" else ("#3B82F6" if rec_label == "Recommended" else "#EF4444")
                                
                                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                                col1, col2 = st.columns([1, 2])
                                with col1:
                                    st.markdown("<p style='margin: 0; color: gray; font-size: 0.9rem;'>OVERALL PERFORMANCE SCORE</p>", unsafe_allow_html=True)
                                    st.markdown(f"<p class='score-big'>{report['score']:.1f} <span style='font-size: 1.5rem; color: gray;'>/ 10</span></p>", unsafe_allow_html=True)
                                    st.markdown(f"<span class='badge-rec-normal' style='background-color: {rec_color}30; color: {rec_color}; font-size: 1.1rem; padding: 6px 16px;'>{rec_label}</span>", unsafe_allow_html=True)
                                with col2:
                                    st.markdown("#### Executive Summary")
                                    st.write(report["summary"])
                                st.markdown("</div>", unsafe_allow_html=True)
                                
                                # Strengths and Weaknesses
                                col_s, col_w = st.columns(2)
                                with col_s:
                                    st.markdown("<div class='glass-card' style='border-left: 5px solid #10B981;'>", unsafe_allow_html=True)
                                    st.markdown("##### 🟢 Core Strengths")
                                    for s in report.get("strengths", []):
                                        st.markdown(f"- {s}")
                                    st.markdown("</div>", unsafe_allow_html=True)
                                with col_w:
                                    st.markdown("<div class='glass-card' style='border-left: 5px solid #EF4444;'>", unsafe_allow_html=True)
                                    st.markdown("##### 🔴 Areas of Improvement")
                                    for w in report.get("weaknesses", []):
                                        st.markdown(f"- {w}")
                                    st.markdown("</div>", unsafe_allow_html=True)
                                    
                                # Detailed Question & Answers
                                st.markdown("#### Detailed Interview Transcript")
                                for idx, qa in enumerate(report["qa"]):
                                    with st.expander(f"Q{idx+1}: {qa['question'][:80]}... (Score: {qa['score']}/10)"):
                                        st.markdown(f"**Category:** <span class='category-badge'>{qa['category'].upper()}</span> &nbsp; **Difficulty:** <span class='diff-badge'>Level {qa['difficulty']}</span>", unsafe_allow_html=True)
                                        st.markdown(f"<br/>**Question:**<br/>{qa['question']}", unsafe_allow_html=True)
                                        st.markdown(f"**Candidate Answer:**<br/><p style='font-style: italic; color: #4B5563;'>{qa['answer']}</p>", unsafe_allow_html=True)
                                        st.markdown(f"**AI Score:** **{qa['score']}/10**")
                                        st.markdown(f"**AI Feedback:** {qa['feedback']}")
                                        
                                # PDF Download Button
                                pdf_url = f"{st.session_state.backend_url}/download-report/{selected_int_id}"
                                try:
                                    pdf_res = requests.get(pdf_url)
                                    if pdf_res.status_code == 200:
                                        st.download_button(
                                            label=f"Download {report['candidate']['name']}'s PDF Report",
                                            data=pdf_res.content,
                                            file_name=f"{report['candidate']['name']}_Interview_Report.pdf",
                                            mime="application/pdf",
                                            key=f"dl_btn_{selected_int_id}"
                                        )
                                except Exception as e:
                                    st.error("Failed to prepare PDF download stream.")
                        else:
                            st.error("Could not fetch interview report.")
                    except Exception as e:
                        st.error(f"Error fetching report: {e}")
                        
    with tab_jds:
        st.markdown("##### Upload a New Job Description")
        
        col_jd1, col_jd2 = st.columns([1, 1])
        with col_jd1:
            jd_file_rec = st.file_uploader("Upload Job Description TXT", type=["txt"], key="recruiter_jd_upload")
            if st.button("Parse and Save JD", type="primary"):
                if not jd_file_rec:
                    st.error("Please select a TXT file first.")
                else:
                    with st.spinner("Uploading and parsing JD..."):
                        try:
                            files_jd = {"file": (jd_file_rec.name, jd_file_rec.getvalue(), "text/plain")}
                            res_jd = requests.post(
                                f"{st.session_state.backend_url}/upload-jd",
                                files=files_jd,
                                headers=get_headers()
                            )
                            if res_jd.status_code == 200:
                                st.success("Job Description parsed and added to Database successfully!")
                                st.rerun()
                            else:
                                st.error(f"Failed to parse JD: {res_jd.json().get('detail')}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
                            
        with col_jd2:
            st.markdown("##### Available Job Roles in Database")
            jds = []
            try:
                res_jd_list = requests.get(f"{st.session_state.backend_url}/jds")
                if res_jd_list.status_code == 200:
                    jds = res_jd_list.json()
            except Exception:
                pass
                
            if not jds:
                st.info("No JDs uploaded yet.")
            else:
                for j in jds:
                    with st.expander(f"{j['role']} (ID: {j['jd_id']})"):
                        st.markdown(f"**Required Experience:** {j['experience']}")
                        st.markdown("**Key Required Skills:**")
                        st.markdown(" ".join([f"`{s}`" for s in j['required_skills']]))
