import streamlit as st
import google.generativeai as genai
import smtplib, json, os, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
EMAIL_ADDRESS  = os.getenv("EMAIL_ADDRESS") or st.secrets.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") or st.secrets.get("EMAIL_PASSWORD")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-lite")

# ─────────────────────────── PDF COLOURS ────────────────────────────
NAVY   = colors.HexColor("#0A0F1E")
GOLD   = colors.HexColor("#E8B84B")
CREAM  = colors.HexColor("#F7F4EE")
MUTED  = colors.HexColor("#6B7A99")
WHITE  = colors.white
BORDER = colors.HexColor("#DDD6C8")

# ────────────────────────── PDF BUILDER ─────────────────────────
def create_pdf(data: dict, filename="career_report.pdf") -> str:
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    title_s       = S("Title",    fontName="Helvetica-Bold",  fontSize=22, leading=28, textColor=NAVY, spaceAfter=4)
    subtitle_s    = S("Sub",      fontName="Helvetica",       fontSize=11, leading=16, textColor=MUTED, spaceAfter=16)
    section_s     = S("Sec",      fontName="Helvetica-Bold",  fontSize=9,  leading=12, textColor=GOLD, spaceAfter=8, spaceBefore=18, tracking=120)
    body_s        = S("Body",     fontName="Helvetica",       fontSize=10, leading=16, textColor=NAVY, spaceAfter=6)
    strong_s      = S("Strong",   fontName="Helvetica-Bold",  fontSize=10, leading=15, textColor=NAVY, spaceAfter=2)
    muted_s       = S("Muted",    fontName="Helvetica",       fontSize=9,  leading=14, textColor=MUTED, spaceAfter=8)
    week_header_s = S("WkH",      fontName="Helvetica-Bold",  fontSize=9,  leading=12, textColor=WHITE)
    day_label_s   = S("DayL",     fontName="Helvetica-Bold",  fontSize=9,  leading=13, textColor=GOLD)
    day_task_s    = S("DayT",     fontName="Helvetica",       fontSize=9,  leading=13, textColor=NAVY)

    story = []
    story.append(Paragraph("AI Career Intelligence Report", title_s))
    story.append(Paragraph(
        f"Prepared for <b>{data.get('name','')}</b> &nbsp;·&nbsp; "
        f"{data.get('interest','')} &nbsp;·&nbsp; {data.get('experience','')}",
        subtitle_s
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceAfter=4))

    story.append(Paragraph("PROFILE SUMMARY", section_s))
    story.append(Paragraph(data.get("summary", ""), body_s))

    story.append(Paragraph("KEY STRENGTHS", section_s))
    for s in data.get("strengths", []):
        story.append(Paragraph(s["title"], strong_s))
        story.append(Paragraph(s["detail"], muted_s))

    story.append(Paragraph("RECOMMENDED CAREER PATHS", section_s))
    role_rows = []
    for r in data.get("roles", []):
        role_rows.append([
            Paragraph(r["title"], strong_s),
            Paragraph(r["reason"], day_task_s)
        ])
    if role_rows:
        tbl = Table(role_rows, colWidths=[55*mm, 110*mm])
        tbl.setStyle(TableStyle([
            ("VALIGN",       (0,0),(-1,-1),"TOP"),
            ("TOPPADDING",   (0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LINEBELOW",    (0,0),(-1,-2),0.3,BORDER),
        ]))
        story.append(tbl)

    story.append(Paragraph("30-DAY ROADMAP", section_s))
    for week in data.get("weeks", []):
        header_cell = Paragraph(week["title"].upper(), week_header_s)
        week_header_tbl = Table([[header_cell]], colWidths=[165*mm])
        week_header_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(0,0),NAVY),
            ("TOPPADDING",   (0,0),(0,0),7),
            ("BOTTOMPADDING",(0,0),(0,0),7),
            ("LEFTPADDING",  (0,0),(0,0),10),
        ]))
        task_rows = []
        for t in week.get("tasks", []):
            task_rows.append([
                Paragraph(t["days"], day_label_s),
                Paragraph(t["task"], day_task_s)
            ])
        tasks_tbl = Table(task_rows, colWidths=[28*mm, 137*mm])
        tasks_tbl.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1),"TOP"),
            ("TOPPADDING",    (0,0),(-1,-1),5),
            ("BOTTOMPADDING", (0,0),(-1,-1),5),
            ("LEFTPADDING",   (0,0),(0,-1), 10),
            ("LINEBELOW",     (0,0),(-1,-2),0.3,BORDER),
            ("BACKGROUND",    (0,0),(-1,-1),CREAM),
        ]))
        story.append(KeepTogether([week_header_tbl, tasks_tbl, Spacer(1,8)]))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceBefore=16, spaceAfter=8))
    story.append(Paragraph("Generated by AI Career Mentor — for guidance purposes only.", muted_s))

    doc.build(story)
    return filename


# ──────────────────────────── EMAIL ────────────────────────────
def send_email(to_email, subject, body, pdf_path):
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"]    = EMAIL_ADDRESS
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))
        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", 'attachment; filename="career_report.pdf"')
            msg.attach(part)
        srv = smtplib.SMTP("smtp.gmail.com", 587)
        srv.starttls()
        srv.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        srv.send_message(msg)
        srv.quit()
        return True
    except Exception as e:
        return str(e)


# ───────────────────────────── PROMPT ───────────────────────────
def build_prompt(name, interest, skills, performance, experience):
    return f"""You are a senior career strategist. Analyse this student and return a JSON object ONLY — no markdown fences, no extra text.

Student:
- Name: {name}
- Interests: {interest}
- Skills: {skills}
- Performance: {performance}
- Experience: {experience}

Return this EXACT JSON:
{{
  "summary": "3-sentence professional paragraph about the student's profile and potential",
  "strengths": [
    {{"title": "Strength area", "detail": "Why this is a strength and how to leverage it"}},
    {{"title": "Strength area", "detail": "..."}},
    {{"title": "Strength area", "detail": "..."}}
  ],
  "roles": [
    {{"title": "Job Role Title", "reason": "Why this role fits their profile specifically"}},
    {{"title": "Job Role Title", "reason": "..."}},
    {{"title": "Job Role Title", "reason": "..."}},
    {{"title": "Job Role Title", "reason": "..."}}
  ],
  "weeks": [
    {{
      "title": "Week 1: Skill Assessment & Portfolio Planning",
      "tasks": [
        {{"days": "Days 1-3", "task": "Specific actionable task"}},
        {{"days": "Days 4-5", "task": "Specific actionable task"}},
        {{"days": "Days 6-7", "task": "Specific actionable task"}}
      ]
    }},
    {{
      "title": "Week 2: Project Foundation & Skill Building",
      "tasks": [
        {{"days": "Days 8-10", "task": "..."}},
        {{"days": "Days 11-12", "task": "..."}},
        {{"days": "Days 13-14", "task": "..."}}
      ]
    }},
    {{
      "title": "Week 3: Advanced Development & Portfolio",
      "tasks": [
        {{"days": "Days 15-17", "task": "..."}},
        {{"days": "Days 18-20", "task": "..."}},
        {{"days": "Day 21", "task": "..."}}
      ]
    }},
    {{
      "title": "Week 4: Job Search & Networking",
      "tasks": [
        {{"days": "Days 22-24", "task": "..."}},
        {{"days": "Days 25-27", "task": "..."}},
        {{"days": "Days 28-30", "task": "..."}}
      ]
    }}
  ],
  "subject": "Career Development Plan for {name}",
  "emailBody": "Dear {name},\\n\\n[Professional paragraph 1: intro and purpose]\\n\\n[Professional paragraph 2: key career recommendations]\\n\\n[Professional paragraph 3: the 30-day roadmap overview]\\n\\n[Professional paragraph 4: encouragement and closing]\\n\\nWarm regards,\\nAI Career Mentor"
}}"""


# ──────────────────────────── STREAMLIT UI ───────────────────────
st.set_page_config(
    page_title="AI Career Mentor",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* ── Page background ── */
.stApp {
    background: linear-gradient(135deg, #0A0F1E 0%, #111827 50%, #0D1520 100%);
    min-height: 100vh;
}

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 2.5rem 3rem 3rem 3rem;
    max-width: 1100px;
}

/* ── Hero header ── */
.hero-wrap {
    text-align: center;
    padding: 3rem 1rem 2.5rem 1rem;
    position: relative;
}
.hero-badge {
    display: inline-block;
    background: linear-gradient(90deg, rgba(232,184,75,0.15), rgba(232,184,75,0.05));
    border: 1px solid rgba(232,184,75,0.35);
    color: #E8B84B;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 6px 18px;
    border-radius: 50px;
    margin-bottom: 1.4rem;
}
.hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 3.2rem;
    font-weight: 700;
    color: #FFFFFF;
    line-height: 1.15;
    margin-bottom: 0.8rem;
    letter-spacing: -0.5px;
}
.hero-title span {
    background: linear-gradient(135deg, #E8B84B 0%, #F5D37A 50%, #C99A2E 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    font-size: 1.0rem;
    color: #8A9BBF;
    font-weight: 300;
    max-width: 520px;
    margin: 0 auto 2.5rem auto;
    line-height: 1.7;
}

/* ── Divider ── */
.gold-rule {
    height: 1px;
    background: linear-gradient(90deg, transparent, #E8B84B55, #E8B84B, #E8B84B55, transparent);
    border: none;
    margin: 0 auto 2.5rem auto;
    width: 60%;
}

/* ── Form card ── */
.form-card {
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 2.4rem 2.8rem;
    backdrop-filter: blur(10px);
    box-shadow: 0 24px 64px rgba(0,0,0,0.4);
    margin-bottom: 2rem;
}
.form-section-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #E8B84B;
    margin-bottom: 1.2rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(232,184,75,0.2);
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    color: #E8EDF5 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1rem !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(232,184,75,0.6) !important;
    box-shadow: 0 0 0 3px rgba(232,184,75,0.1) !important;
    outline: none !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder {
    color: #4A5568 !important;
}
label[data-testid="stWidgetLabel"] p {
    color: #A8B5CC !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    margin-bottom: 0.3rem !important;
}

/* ── Submit button ── */
.stFormSubmitButton > button {
    background: linear-gradient(135deg, #E8B84B 0%, #F5D37A 50%, #C99A2E 100%) !important;
    color: #0A0F1E !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.05em !important;
    padding: 0.85rem 2rem !important;
    border-radius: 12px !important;
    border: none !important;
    width: 100% !important;
    margin-top: 1rem !important;
    cursor: pointer !important;
    transition: opacity 0.2s, transform 0.15s !important;
    box-shadow: 0 8px 24px rgba(232,184,75,0.3) !important;
}
.stFormSubmitButton > button:hover {
    opacity: 0.9 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 12px 32px rgba(232,184,75,0.4) !important;
}

/* ── Download button ── */
.stDownloadButton > button {
    background: transparent !important;
    border: 1.5px solid rgba(232,184,75,0.5) !important;
    color: #E8B84B !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border-radius: 10px !important;
    padding: 0.7rem 1.5rem !important;
    width: 100% !important;
    transition: background 0.2s, border-color 0.2s !important;
}
.stDownloadButton > button:hover {
    background: rgba(232,184,75,0.1) !important;
    border-color: #E8B84B !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 9px !important;
    color: #6B7A99 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 8px 20px !important;
    transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(232,184,75,0.15) !important;
    color: #E8B84B !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem !important;
}

/* ── Section heading inside tabs ── */
.sec-label {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #E8B84B;
    margin: 1.8rem 0 1rem 0;
    display: flex;
    align-items: center;
    gap: 10px;
}
.sec-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: rgba(232,184,75,0.2);
}

/* ── Summary card ── */
.summary-card {
    background: rgba(232,184,75,0.06);
    border: 1px solid rgba(232,184,75,0.2);
    border-left: 3px solid #E8B84B;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    color: #C8D3E8;
    font-size: 0.93rem;
    line-height: 1.8;
    margin-bottom: 1.2rem;
}

/* ── Strength / Role cards ── */
.item-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s, background 0.2s;
}
.item-card:hover {
    border-color: rgba(232,184,75,0.3);
    background: rgba(232,184,75,0.04);
}
.item-card-title {
    font-weight: 600;
    color: #E8EDF5;
    font-size: 0.95rem;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.item-card-title::before {
    content: '✦';
    color: #E8B84B;
    font-size: 0.6rem;
}
.item-card-detail {
    color: #7A8FA8;
    font-size: 0.85rem;
    line-height: 1.65;
}

/* ── Role number badge ── */
.role-num {
    background: linear-gradient(135deg, #E8B84B, #C99A2E);
    color: #0A0F1E;
    font-size: 0.65rem;
    font-weight: 700;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-right: 8px;
    flex-shrink: 0;
}

/* ── Week block ── */
.week-block { margin-bottom: 1.2rem; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.07); }
.week-header {
    background: linear-gradient(90deg, #0A0F1E, #111E35);
    border-bottom: 1px solid rgba(232,184,75,0.25);
    padding: 0.9rem 1.3rem;
    display: flex;
    align-items: center;
    gap: 10px;
}
.week-header-num {
    background: #E8B84B;
    color: #0A0F1E;
    font-size: 0.65rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 50px;
    letter-spacing: 0.05em;
}
.week-header-title {
    color: #D4C5A0;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}
.week-body { background: rgba(255,255,255,0.025); padding: 0.5rem 0; }
.day-row {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 0.65rem 1.3rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    transition: background 0.15s;
}
.day-row:last-child { border-bottom: none; }
.day-row:hover { background: rgba(232,184,75,0.04); }
.day-lbl {
    color: #E8B84B;
    font-size: 0.78rem;
    font-weight: 700;
    min-width: 78px;
    padding-top: 2px;
    letter-spacing: 0.02em;
}
.day-task { color: #B0BDD0; font-size: 0.88rem; line-height: 1.6; }

/* ── Email preview ── */
.email-meta { margin-bottom: 1.2rem; }
.email-meta-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0.55rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    font-size: 0.87rem;
}
.email-meta-row:last-child { border-bottom: none; }
.email-meta-key { color: #5A6A88; min-width: 70px; font-weight: 500; }
.email-meta-val { color: #C0CCDF; }
.email-body-box {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.5rem 1.8rem;
    font-size: 0.88rem;
    line-height: 1.9;
    white-space: pre-wrap;
    color: #A8B5CC;
    font-family: 'DM Sans', sans-serif;
}

/* ── Alerts ── */
.stSuccess, .stWarning, .stError, .stInfo {
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: #E8B84B !important; }

/* ── Selectbox dropdown ── */
.stSelectbox [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    color: #E8EDF5 !important;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.08) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(232,184,75,0.3); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrap">
  <div class="hero-badge">✦ AI-Powered Career Intelligence</div>
  <div class="hero-title">Shape Your <span>Career Path</span><br>with Precision</div>
  <div class="hero-sub">Enter your profile below and receive a personalised career analysis, role recommendations, and a 30-day action roadmap — delivered instantly.</div>
  <div class="gold-rule"></div>
</div>
""", unsafe_allow_html=True)

# ── Form card ────────────────────────────────────────────────────
st.markdown('<div class="form-card">', unsafe_allow_html=True)
st.markdown('<div class="form-section-label">✦ Your Profile</div>', unsafe_allow_html=True)

with st.form("career_form"):
    c1, c2 = st.columns(2, gap="large")
    name  = c1.text_input("Full Name", placeholder="e.g. Arjun Sharma")
    email = c2.text_input("Email Address", placeholder="arjun@example.com")

    interest = st.text_input("Domain / Interests", placeholder="e.g. AIML, Data Science, NLP, Cybersecurity")
    skills   = st.text_area("Current Skills", placeholder="e.g. Python, Machine Learning, Deep Learning, SQL, Power BI", height=90)

    c3, c4 = st.columns(2, gap="large")
    performance = c3.selectbox("Academic Performance", ["Low", "Average", "Good", "Excellent"])
    experience  = c4.selectbox("Experience Level", [
        "Student (no experience)", "Fresher (0-1 year)",
        "Junior (1-2 years)", "Mid-level (3+ years)"
    ])

    submitted = st.form_submit_button("✦ Generate My Career Report", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# ── Processing ───────────────────────────────────────────────────
if submitted:
    if not name or not interest or not skills:
        st.warning("⚠️  Please fill in your Name, Interests, and Skills to continue.")
    else:
        with st.spinner("Crafting your personalised career intelligence report…"):
            prompt   = build_prompt(name, interest, skills, performance, experience)
            response = model.generate_content(prompt)
            raw      = response.text.strip()
            clean    = re.sub(r"```json|```", "", raw).strip()
            data     = json.loads(clean)
            data["name"]       = name
            data["interest"]   = interest
            data["experience"] = experience

        st.markdown("---")
        st.markdown(f"""
        <div style="text-align:center; padding: 1rem 0 0.5rem 0;">
            <div style="font-family:'Playfair Display',serif; font-size:1.5rem; color:#E8EDF5; font-weight:600;">
                Report Ready for <span style="color:#E8B84B;">{name}</span>
            </div>
            <div style="color:#6B7A99; font-size:0.85rem; margin-top:6px;">
                {interest} &nbsp;·&nbsp; {experience}
            </div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊  Profile Analysis",
            "💼  Career Paths",
            "🗓  30-Day Roadmap",
            "📧  Email Draft"
        ])

        # ── Tab 1: Profile ──────────────────────────────────────
        with tab1:
            st.markdown('<div class="sec-label">Profile Summary</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="summary-card">{data["summary"]}</div>', unsafe_allow_html=True)

            st.markdown('<div class="sec-label">Key Strengths</div>', unsafe_allow_html=True)
            for s in data.get("strengths", []):
                st.markdown(f"""
                <div class="item-card">
                    <div class="item-card-title">{s['title']}</div>
                    <div class="item-card-detail">{s['detail']}</div>
                </div>
                """, unsafe_allow_html=True)

        # ── Tab 2: Roles ────────────────────────────────────────
        with tab2:
            st.markdown('<div class="sec-label">Recommended Career Paths</div>', unsafe_allow_html=True)
            for i, r in enumerate(data.get("roles", []), 1):
                st.markdown(f"""
                <div class="item-card">
                    <div class="item-card-title">
                        <span class="role-num">{i}</span>{r['title']}
                    </div>
                    <div class="item-card-detail">{r['reason']}</div>
                </div>
                """, unsafe_allow_html=True)

        # ── Tab 3: Roadmap ──────────────────────────────────────
        with tab3:
            st.markdown('<div class="sec-label">Your 30-Day Action Plan</div>', unsafe_allow_html=True)
            week_emojis = ["🔍", "🏗️", "🚀", "🌐"]
            for i, week in enumerate(data.get("weeks", [])):
                title_parts = week["title"].split(":", 1)
                week_num    = title_parts[0].strip() if len(title_parts) > 1 else f"Week {i+1}"
                week_title  = title_parts[1].strip() if len(title_parts) > 1 else week["title"]
                emoji       = week_emojis[i] if i < len(week_emojis) else "📌"

                rows_html = "".join(
                    f'<div class="day-row"><span class="day-lbl">{t["days"]}</span><span class="day-task">{t["task"]}</span></div>'
                    for t in week.get("tasks", [])
                )
                st.markdown(f"""
                <div class="week-block">
                    <div class="week-header">
                        <span class="week-header-num">{emoji} {week_num}</span>
                        <span class="week-header-title">{week_title}</span>
                    </div>
                    <div class="week-body">{rows_html}</div>
                </div>
                """, unsafe_allow_html=True)

        # ── Tab 4: Email ────────────────────────────────────────
        with tab4:
            st.markdown('<div class="sec-label">Email Preview</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="email-meta">
                <div class="email-meta-row">
                    <span class="email-meta-key">To</span>
                    <span class="email-meta-val">{email if email else '—'}</span>
                </div>
                <div class="email-meta-row">
                    <span class="email-meta-key">Subject</span>
                    <span class="email-meta-val">{data.get('subject','')}</span>
                </div>
            </div>
            <div class="email-body-box">{data.get('emailBody','').replace(chr(10),'<br>')}</div>
            """, unsafe_allow_html=True)

        # ── PDF & Email actions ─────────────────────────────────
        st.markdown("---")
        col_dl, col_status = st.columns([1, 2], gap="large")

        pdf_path = create_pdf(data)

        with col_dl:
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇  Download Career Report PDF",
                    data=f.read(),
                    file_name="career_report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        with col_status:
            if email:
                with st.spinner("Sending report to your inbox…"):
                    result = send_email(email, data["subject"], data["emailBody"], pdf_path)
                if result is True:
                    st.success("📧  Report emailed successfully with PDF attached!")
                else:
                    st.error(f"Email failed: {result}")
            else:
                st.info("💡  Add your email address in the form to receive the report in your inbox.")