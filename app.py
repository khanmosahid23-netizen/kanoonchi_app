import os
import streamlit as st
import pdfplumber
import docx
from PIL import Image
import google.generativeai as genai

# ==========================================
# 1. CONFIGURATION & MASTER PASSWORD
# ==========================================
API_KEY = "AQ.Ab8RN6IJl89zjerV51nMcnSZtjz0ybtLwSqk8qzGUBn5qY3q4g"

MASTER_PIN = "7777"  # 🔴 Yeh tumhara secure PIN hai (Isko yaad rakhna)




# Block system conflicts
os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
os.environ['GOOGLE_API_KEY'] = API_KEY

# Page Configuration
st.set_page_config(page_title="KANOONCHI", page_icon="⚖️", layout="centered")

# ==========================================
# 2. SECURE ACCESS GATE
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 KANOONCHI - Secure Login")
    st.write("Enter the secure access PIN to unlock the app for your sister.")
    
    entered_pin = st.text_input("Enter 4-Digit PIN ", type="password")
    
    if st.button("Login"):
        if entered_pin == MASTER_PIN:
            st.session_state.authenticated = True
            st.success("Login Successful! Loading Kanoonchi...")
            st.rerun()
        else:
            st.error("❌ Incorrect PIN. Try again.")
            
    st.stop() # Stops app execution until correct PIN is entered

# ==========================================
# 3. MAIN APP (Runs after login)
# ==========================================
st.title("⚖️ KANOONCHI")
st.write("Your Ultimate AIBE Preparation AI")

if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
    st.warning("👈 Please paste your actual API Key in the code (app.py) where it says 'YOUR_API_KEY_HERE'.")
    st.stop()

# Setup AI
genai.configure(api_key=API_KEY)

# Find Working Model
if "working_model" not in st.session_state:
    st.session_state.working_model = None

if st.session_state.working_model is None:
    with st.spinner("Connecting to Google AI... Please wait..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            for m_name in available_models:
                try:
                    test_model = genai.GenerativeModel(m_name)
                    test_model.generate_content("hi")
                    st.session_state.working_model = m_name
                    break 
                except Exception:
                    continue
        except Exception:
            st.error("Could not connect to Google API. Please check your internet.")
            st.stop()

if not st.session_state.working_model:
    st.error("❌ Error: No working models found for this API Key.")
    st.stop()

working_model_name = st.session_state.working_model

# Session States
if "t1_q" not in st.session_state: st.session_state.t1_q = None
if "t1_a" not in st.session_state: st.session_state.t1_a = None
if "t1_show" not in st.session_state: st.session_state.t1_show = False

if "t3_q" not in st.session_state: st.session_state.t3_q = None
if "t3_a" not in st.session_state: st.session_state.t3_a = None
if "t3_show" not in st.session_state: st.session_state.t3_show = False

def extract_text_from_file(uploaded_file):
    text = ""
    ext = uploaded_file.name.split('.')[-1].lower()
    if ext == "pdf":
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages: 
                text += page.extract_text() + "\n"
    elif ext == "docx":
        doc = docx.Document(uploaded_file)
        text = "\n".join([para.text for para in doc.paragraphs])
    return text, ext

# App Tabs
tab1, tab2, tab3 = st.tabs(["📄 Notes Analyzer", "💬 AI Legal Tutor + Camera", "📝 PYQ Analyzer"])

# TAB 1: Notes Analyzer
with tab1:
    st.header("Generate Questions from Notes")
    q_type = st.radio("What type of questions do you want?", ["MCQs (Multiple Choice)", "Long Analytical Questions"])
    uploaded_file = st.file_uploader("Upload Law notes (PDF, DOCX, JPG, PNG)", type=["pdf", "docx", "png", "jpg", "jpeg"], key="t1_up")

    if uploaded_file is not None:
        if st.button("Generate Test"):
            with st.spinner(f"Reading notes and generating {q_type}..."):
                try:
                    text_data, ext = extract_text_from_file(uploaded_file)
                    model = genai.GenerativeModel(working_model_name)
                    
                    if "MCQ" in q_type:
                        base_prompt = "You are an expert Law professor. Based on the provided text, generate 5 MCQs for AIBE prep. Format EXACTLY like this:\nWrite the 5 questions with 4 options each.\nThen, write exactly the word '===ANSWERS===' on a new line.\nThen, provide the correct answers with explanations."
                    else:
                        base_prompt = "You are an expert Law professor. Based on the provided text, generate 3 detailed Long Analytical Questions. Format EXACTLY like this:\nWrite the 3 questions.\nThen, write exactly the word '===ANSWERS===' on a new line.\nThen, provide the detailed model answers for each question."
                    
                    if ext in ["jpg", "jpeg", "png"]:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([base_prompt, img])
                    else:
                        response = model.generate_content(base_prompt + "\n\nText Data:\n" + text_data[:20000])

                    parts = response.text.split("===ANSWERS===")
                    st.session_state.t1_q = parts[0].strip()
                    st.session_state.t1_a = parts[1].strip() if len(parts) > 1 else "Answer formatting error. Raw output:\n" + response.text
                    st.session_state.t1_show = False
                    
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state.t1_q:
        st.markdown("### 📝 Generated Questions")
        st.write(st.session_state.t1_q)
        
        if not st.session_state.t1_show:
            if st.button("👁️ Show Answers"):
                st.session_state.t1_show = True
                st.rerun()
                
        if st.session_state.t1_show:
            st.markdown("### ✅ Answers & Explanations")
            st.write(st.session_state.t1_a)

# TAB 2: AI LEGAL TUTOR + PHONE CAMERA INTEGRATION
with tab2:
    st.header("Interactive Doubt Solver & Book Reader")
    st.write("Ask any legal concept or **click a picture of your book/bare act** using your phone camera to explain it instantly.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message and message["image"]:
                st.image(message["image"], caption="Uploaded Book Snapshot", width=300)

    use_camera = st.checkbox("📸 Click photo from phone/laptop camera for doubt")
    captured_img = None
    if use_camera:
        captured_img = st.camera_input("Take a picture of the book page or legal text")

    if prompt := st.chat_input("Type your legal doubt or ask about the photo..."):
        with st.chat_message("user"):
            st.markdown(prompt)
            if captured_img:
                st.image(captured_img, caption="Captured Book Snapshot", width=300)

        st.session_state.messages.append({"role": "user", "content": prompt, "image": captured_img})

        with st.chat_message("assistant"):
            with st.spinner("Analyzing legal concept and book context..."):
                try:
                    model = genai.GenerativeModel(working_model_name)
                    system_prompt = "You are Kanoonchi, an expert AI Legal Tutor for Indian law students preparing for AIBE. Explain concepts clearly and simply. User's question: "
                    
                    if captured_img:
                        img = Image.open(captured_img)
                        response = model.generate_content([system_prompt + prompt, img])
                    else:
                        response = model.generate_content(system_prompt + prompt)
                        
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Chat Error: {e}")

# TAB 3: PYQ Analyzer
with tab3:
    st.header("PYQ Analyzer & Mock Test Creator")
    st.write("Upload past AIBE question papers. AI will analyze trends and create a fresh new mock test.")
    
    uploaded_pyqs = st.file_uploader("Upload Previous Year Papers (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True, key="t3_up")
    
    if uploaded_pyqs:
        if st.button("Analyze Trends & Generate New Paper"):
            with st.spinner("Deep analyzing past papers and crafting a new Mock Test..."):
                try:
                    combined_text = ""
                    for pyq_file in uploaded_pyqs:
                        txt, _ = extract_text_from_file(pyq_file)
                        combined_text += txt + "\n"

                    model = genai.GenerativeModel(working_model_name)
                    prompt = "You are an expert AIBE examiner. I am providing text from past year AIBE question papers. Analyze the trends, important topics, and difficulty level. Based on this analysis, generate a NEW Mock Test containing 10 high-quality MCQs that have a high probability of being asked. Format EXACTLY like this:\nWrite the 10 questions with 4 options each.\nThen, write exactly the word '===ANSWERS===' on a new line.\nThen, provide the answer key with detailed explanations."
                    
                    response = model.generate_content(prompt + "\n\nPYQ Data:\n" + combined_text[:30000])
                    
                    parts = response.text.split("===ANSWERS===")
                    st.session_state.t3_q = parts[0].strip()
                    st.session_state.t3_a = parts[1].strip() if len(parts) > 1 else "Answer formatting error. Raw output:\n" + response.text
                    st.session_state.t3_show = False
                    
                except Exception as e:
                    st.error(f"Error generating Mock Test: {e}")

    if st.session_state.t3_q:
        st.markdown("### 🎯 Your Custom Mock Test")
        st.write(st.session_state.t3_q)
        
        if not st.session_state.t3_show:
            if st.button("👁️ Show Answer Key"):
                st.session_state.t3_show = True
                st.rerun()
                
        if st.session_state.t3_show:
            st.markdown("### ✅ Answer Key & Explanations")
            st.write(st.session_state.t3_a)
