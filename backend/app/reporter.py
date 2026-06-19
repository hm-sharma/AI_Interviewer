import json
import logging
from datetime import datetime
import google.generativeai as genai
from backend.app.config import DEFAULT_MODEL, GEMINI_API_KEY
from backend.app.parsers import configure_gemini

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)

def get_recommendation_label(score: float) -> str:
    """Returns the hiring recommendation based on score."""
    if score >= 8.0:
        return "Strongly Recommended"
    elif score >= 6.0:
        return "Recommended"
    else:
        return "Not Recommended"

def get_recommendation_color(rec: str) -> str:
    """Returns a hex color for the recommendation label."""
    if rec == "Strongly Recommended":
        return "#10B981" # Green
    elif rec == "Recommended":
        return "#3B82F6" # Blue
    else:
        return "#EF4444" # Red

def generate_report_summary(
    candidate_name: str,
    role_title: str,
    match_score: int,
    avg_score: float,
    qa_list: list,
    api_key: str = None
) -> dict:
    """
    Uses Gemini to analyze the interview questions/responses and generate a
    professional summary, plus aggregated lists of strengths and weaknesses.
    """
    configure_gemini(api_key)
    
    # Construct a transcript snippet for the AI to review
    transcript_lines = []
    for i, qa in enumerate(qa_list):
        transcript_lines.append(f"Q{i+1} ({qa['category'].upper()}, Diff: {qa['difficulty']}): {qa['question']}")
        transcript_lines.append(f"A{i+1}: {qa['answer']}")
        transcript_lines.append(f"Evaluator Score: {qa['score']}/10. Feedback: {qa['feedback']}")
        transcript_lines.append("-" * 30)
    transcript_text = "\n".join(transcript_lines)

    prompt = f"""
    You are a professional HR director and engineering hiring manager. Review the following details of an automated AI interview.
    
    Candidate Name: {candidate_name}
    Target Job: {role_title}
    Resume-JD Match Score: {match_score}%
    Average Interview Score: {avg_score:.1f}/10
    
    Interview Transcript:
    {transcript_text}
    
    ---
    Tasks:
    1. Write an Executive Summary (150-250 words) assessing the candidate's technical capability, communication level, responsiveness, and suitability for the role.
    2. Extract 2-4 core high-level strengths shown by the candidate in their answers.
    3. Extract 2-4 primary growth areas or weaknesses where their answers were shallow or incorrect.
    
    You MUST return ONLY a JSON object with this exact structure:
    {{
      "summary": "Executive summary text...",
      "strengths": ["Aggregate strength 1", "Aggregate strength 2"],
      "weaknesses": ["Aggregate weakness 1", "Aggregate weakness 2"]
    }}
    """
    
    try:
        model = genai.GenerativeModel(api_key=api_key or GEMINI_API_KEY, model_name=DEFAULT_MODEL)
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Error generating report summary: {e}")
        return {
            "summary": f"The candidate successfully completed the interview for the position of {role_title}. Their average score was {avg_score:.1f}/10. They demonstrated core capabilities suitable for technical review.",
            "strengths": ["Demonstrated basic programming knowledge", "Answered behavioral questions"],
            "weaknesses": ["Some answers lacked deep detail", "Requires further standard offline screening"]
        }

def build_pdf_report(
    candidate_profile: dict,
    jd_profile: dict,
    interview_data: dict,  # score, recommendation, summary, strengths, weaknesses, created_at
    qa_list: list,         # List of dicts with question, answer, score, feedback, strengths, weaknesses, category, difficulty
    output_path: str
):
    """
    Builds a beautifully styled PDF document using ReportLab.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles to look extremely premium
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4B5563'),
        spaceAfter=15
    )
    
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=12,
        spaceAfter=8,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#374151'),
        spaceAfter=6
    )
    
    label_style = ParagraphStyle(
        'Label',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1F2937')
    )
    
    score_badge_style = ParagraphStyle(
        'ScoreBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1 # Center
    )
    
    rec_badge_style = ParagraphStyle(
        'RecBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.white,
        alignment=1 # Center
    )
    
    story = []
    
    # 1. Header (Title, Subtitle & Metadata Table)
    story.append(Paragraph("AI INTERVIEW ASSESSMENT REPORT", title_style))
    created_date = datetime.strptime(interview_data['created_at'], "%Y-%m-%dT%H:%M:%S.%f").strftime("%B %d, %Y at %I:%M %p") if 'created_at' in interview_data else datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Generated by Adaptive Interviewer System on {created_date}", subtitle_style))
    story.append(Spacer(1, 10))
    
    # Metadata Dashboard layout
    rec = interview_data['recommendation']
    rec_color = get_recommendation_color(rec)
    
    meta_data = [
        [
            Paragraph("Candidate Details", label_style),
            Paragraph("Interview Performance", label_style)
        ],
        [
            Paragraph(f"<b>Name:</b> {candidate_profile.get('name')}<br/><b>Email:</b> {candidate_profile.get('email')}<br/><b>Target Role:</b> {jd_profile.get('role')}", body_style),
            Table([
                [Paragraph("OVERALL SCORE", ParagraphStyle('CenterLabel', parent=label_style, alignment=1)), 
                 Paragraph("RECOMMENDATION", ParagraphStyle('CenterLabel2', parent=label_style, alignment=1))],
                [Paragraph(f"{interview_data['score']:.1f} / 10", score_badge_style),
                 Paragraph(rec.upper(), rec_badge_style)]
            ], colWidths=[110, 150], style=TableStyle([
                ('BACKGROUND', (1, 1), (1, 1), colors.HexColor(rec_color)),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
        ]
    ]
    
    meta_table = Table(meta_data, colWidths=[240, 280])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # 2. Executive Summary
    story.append(Paragraph("Executive Summary", section_title))
    story.append(Paragraph(interview_data['summary'], body_style))
    story.append(Spacer(1, 10))
    
    # 3. Strengths & Weaknesses (Two Column Layout)
    sw_data = [
        [Paragraph("Key Strengths", label_style), Paragraph("Areas of Improvement", label_style)],
        [
            Paragraph("<br/>".join([f"• {s}" for s in interview_data.get('strengths', [])]), body_style),
            Paragraph("<br/>".join([f"• {w}" for w in interview_data.get('weaknesses', [])]), body_style)
        ]
    ]
    sw_table = Table(sw_data, colWidths=[260, 260])
    sw_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#F3F4F6')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#F3F4F6')),
        ('BOX', (0,0), (0,1), 1, colors.HexColor('#E5E7EB')),
        ('BOX', (1,0), (1,1), 1, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(sw_table)
    story.append(Spacer(1, 15))
    
    # Page Break for Question Details
    story.append(PageBreak())
    
    # 4. Question & Response Details
    story.append(Paragraph("Detailed Interview Transcript", section_title))
    
    for idx, qa in enumerate(qa_list):
        q_elements = []
        q_elements.append(Paragraph(f"Question {idx+1} ({qa['category'].capitalize()} - Difficulty Level {qa['difficulty']})", label_style))
        q_elements.append(Paragraph(f"<b>Q:</b> {qa['question']}", body_style))
        q_elements.append(Paragraph(f"<b>A:</b> {qa['answer']}", ParagraphStyle('AnswerText', parent=body_style, fontName='Helvetica-Oblique')))
        
        # Scoring Row
        score_val = qa['score']
        score_color = '#10B981' if score_val >= 8 else ('#F59E0B' if score_val >= 5 else '#EF4444')
        
        q_elements.append(Table([
            [
                Paragraph(f"<b>Score:</b> <font color='{score_color}'><b>{score_val}/10</b></font>", body_style),
                Paragraph(f"<b>Feedback:</b> {qa['feedback']}", body_style)
            ]
        ], colWidths=[80, 420], style=TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ])))
        
        q_elements.append(Spacer(1, 10))
        
        # Draw borders around each QA block
        qa_block_table = Table([[q_elements]], colWidths=[510])
        qa_block_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAFBFD')),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        
        story.append(KeepTogether(qa_block_table))
        story.append(Spacer(1, 12))
        
    doc.build(story)
