import os
import streamlit as st
import pdfplumber
import docx
from PIL import Image
import base64
import io
import json
import re
from groq import Groq

# ==========================================
# 1. CONFIGURATION & SECURE LOGIN
# ==========================================
MASTER_PIN = "7777"  # Secure PIN for Nayla

try:
    API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    API_KEY = "YOUR_API_KEY_HERE"

st.set_page_config(page_title="KANOONCHI", page_icon="⚖️", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 KANOONCHI - Secure Login")
    entered_pin = st.text_input("Enter 4-Digit PIN ", type="password")
    if st.button("Login"):
        if entered_pin == MASTER_PIN:
            st.session_state.authenticated = True
            st.success("Login Successful! Loading Kanoonchi...")
            st.rerun()
        else:
            st.error("❌ Incorrect PIN.")
    st.stop()

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
st.title("⚖️ KANOONCHI - Advanced Prep")
st.write("AIBE Preparation with Interactive Tests & Reference AI")

if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
    st.warning("⚠️ Configure your Groq API key in Streamlit Secrets.")
    st.stop()

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.convert('RGB').save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def generate_groq_response(prompt, img=None, json_mode=False):
    client = Groq(api_key=API_KEY)
    model_name = "llama-3.2-11b-vision-preview" if img else "llama-3.3-70b-versatile" 
    
    messages = [{"role": "user", "content": prompt}]
    if img:
        base64_img = pil_to_base64(img)
        messages[0]["content"] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
        ]
        
    response = client.chat.completions.create(
        model=model_name,
        messages=messages
    )
    return response.choices[0].message.content

def extract_text_from_file(uploaded_file, limit_pages=15):
    text = ""
    ext = uploaded_file.name.split('.')[-1].lower()
    if ext == "pdf":
        with pdfplumber.open(uploaded_file) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= limit_pages: break
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
    elif ext == "docx":
        doc = docx.Document(uploaded_file)
        for i, para in enumerate(doc.paragraphs):
            if i >= 200: break
            text += para.text + "\n"
    return text, ext

def extract_json_from_text(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return json.loads(match.group(1))
    match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
    if match: return json.loads(match.group(0))
    return None

def format_long_text(text):
    """
    SPACING FIX: Automatically formats clustered text by adding double line 
    breaks and bold text for Question and Answer markers (e.g., Q1:, Ans 1:).
    """
    # Fix for Q1:, Question 1:, Q 1:
    text = re.sub(r'(Q(?:uestion)?\s*\d+\s*:)', r'\n\n**\1** ', text, flags=re.IGNORECASE)
    # Fix for Ans 1:, Answer 1:, A 1:
    text = re.sub(r'(A(?:ns)?(?:wer)?\s*\d+\s*:)', r'\n\n**\1** ', text, flags=re.IGNORECASE)
    return text.strip()

if 'mcq_answers_t1' not in st.session_state: st.session_state.mcq_answers_t1 = {}
if 'mcq_answers_t3' not in st.session_state: st.session_state.mcq_answers_t3 = {}

# ==========================================
# 3. MAIN APP TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📄 Notes to Interactive Test", "💬 AI Tutor & Library", "📝 Custom PYQ Mock Test"])

# --- TAB 1: NOTES ANALYZER ---
with tab1:
    st.header("Generate Interactive Questions")
    
    col1, col2 = st.columns(2)
    with col1:
        q_type = st.radio("Select Format:", ["Interactive MCQs", "Long Answers"])
    with col2:
        num_q = st.number_input("How many questions?", min_value=1, max_value=20, value=5)

    uploaded_file = st.file_uploader("Upload Notes (PDF, DOCX, JPG)", type=["pdf", "docx", "png", "jpg", "jpeg"], key="t1_up")

    if uploaded_file is not None:
        if st.button("Generate Test"):
            with st.spinner(f"Reading notes and crafting {num_q} {q_type}..."):
                try:
                    text_data, ext = extract_text_from_file(uploaded_file)
                    
                    if "MCQ" in q_type:
                        base_prompt = f"You are a strict law professor. Generate exactly {num_q} MCQs for AIBE from the text. You MUST return ONLY a valid JSON array in this exact format: [{{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]"
                    else:
                        base_prompt = f"Generate {num_q} Detailed Long Analytical Questions based on the text. Format exactly like this:\nQ1: ...\nQ2: ...\n===ANSWERS===\nAns 1: ...\nAns 2: ..."
                    
                    if ext in ["jpg", "jpeg", "png"]:
                        img = Image.open(uploaded_file)
                        response_text = generate_groq_response(base_prompt, img=img)
                    else:
                        response_text = generate_groq_response(base_prompt + "\n\nText:\n" + text_data[:15000])

                    if "MCQ" in q_type:
                        parsed_json = extract_json_from_text(response_text)
                        if parsed_json:
                            st.session_state.t1_mcqs = parsed_json
                            st.session_state.mcq_answers_t1 = {} # Reset answers
                        else:
                            st.error("Failed to parse JSON. Raw output:")
                            st.write(response_text)
                    else:
                        parts = response_text.split("===ANSWERS===")
                        st.session_state.t1_long_q = parts[0]
                        st.session_state.t1_long_a = parts[1] if len(parts) > 1 else response_text

                except Exception as e:
                    st.error(f"Error: {e}")

    # Interactive MCQ Rendering
    if "t1_mcqs" in st.session_state and "MCQ" in q_type:
        st.markdown("### 🎯 Your Interactive Test")
        for i, item in enumerate(st.session_state.t1_mcqs):
            st.markdown(f"**Q{i+1}: {item['question']}**")
            
            cols = st.columns(4)
            for j, option in enumerate(item['options']):
                button_key = f"t1_btn_{i}_{j}"
                if cols[j].button(option, key=button_key):
                    st.session_state.mcq_answers_t1[i] = option
            
            if i in st.session_state.mcq_answers_t1:
                user_ans = st.session_state.mcq_answers_t1[i]
                correct_ans = str(item['correct_answer']).strip()
                
                # Smart Check: Map 'A', 'B', 'C', 'D' to actual option text
                correct_text = correct_ans
                if correct_ans in ['A', 'B', 'C', 'D']:
                    idx = ord(correct_ans) - 65
                    if idx < len(item['options']):
                        correct_text = item['options'][idx]

                if user_ans == correct_text or user_ans.startswith(correct_ans):
                    st.success(f"✅ Correct! \n\n**Explanation:** {item['explanation']}")
                else:
                    st.error(f"❌ Wrong! Correct answer is: **{correct_text}** \n\n**Explanation:** {item['explanation']}")
            st.divider()

    # Long Question Rendering
    if "t1_long_q" in st.session_state and "Long" in q_type:
        st.markdown("### 📝 Long Questions")
        # Apply the spacing formatter function
        st.markdown(format_long_text(st.session_state.t1_long_q))
        with st.expander("👁️ Show Detailed Answers"):
            st.markdown(format_long_text(st.session_state.t1_long_a))

# --- TAB 2: AI TUTOR & REFERENCE LIBRARY ---
with tab2:
    st.header("Interactive Doubt Solver & Reference Library")
    
    # 📚 REFERENCE LIBRARY FEATURE (Session Based)
    with st.expander("📚 Add Reference Book (Bare Acts/Notes)"):
        ref_file = st.file_uploader("Upload a reference PDF to ground Kanoonchi's answers", type=["pdf", "docx"], key="ref_up")
        if st.button("Load Reference Book"):
            if ref_file:
                with st.spinner("Loading reference book into Kanoonchi's brain..."):
                    ref_text, _ = extract_text_from_file(ref_file, limit_pages=30) 
                    st.session_state.reference_context = ref_text
                    st.success("✅ Reference Book Loaded! Ask questions now.")
            else:
                st.warning("Please upload a file first.")

    st.divider()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message and message["image"]:
                st.image(message["image"], width=300)

    use_camera = st.checkbox("📸 Click photo from camera for doubt")
    captured_img = st.camera_input("Take a picture") if use_camera else None

    if prompt := st.chat_input("Type your legal doubt..."):
        with st.chat_message("user"):
            st.markdown(prompt)
            if captured_img: st.image(captured_img, width=300)

        st.session_state.messages.append({"role": "user", "content": prompt, "image": captured_img})

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                system_prompt = "You are Kanoonchi, an expert AI Legal Tutor for Indian law students. "
                
                if "reference_context" in st.session_state and st.session_state.reference_context:
                    system_prompt += f"\nAlways prioritize and reference this library data if relevant to the user's question:\n[LIBRARY DATA START]\n{st.session_state.reference_context[:10000]}\n[LIBRARY DATA END]\n\nUser Question: "
                else:
                    system_prompt += "User Question: "

                try:
                    if captured_img:
                        img = Image.open(captured_img)
                        response_text = generate_groq_response(system_prompt + prompt, img=img)
                    else:
                        response_text = generate_groq_response(system_prompt + prompt)
                        
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                except Exception as e:
                    st.error(f"Error: {e}")

# --- TAB 3: CUSTOM PYQ MOCK TEST ---
with tab3:
    st.header("Custom Mock Test Creator")
    
    mock_num_q = st.number_input("Number of MCQs for Mock Test", min_value=1, max_value=50, value=10)
    uploaded_pyqs = st.file_uploader("Upload Past Papers (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True, key="t3_up")
    
    if uploaded_pyqs:
        if st.button("Generate Interactive Mock Test"):
            with st.spinner(f"Analyzing past trends and creating {mock_num_q} MCQs..."):
                try:
                    combined_text = ""
                    for pyq_file in uploaded_pyqs:
                        txt, _ = extract_text_from_file(pyq_file, limit_pages=5)
                        combined_text += txt + "\n"

                    prompt = f"Act as an AIBE examiner. Based on the provided past papers, generate {mock_num_q} highly probable NEW MCQs. You MUST return ONLY a valid JSON array exactly like this: [{{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]"
                    
                    response_text = generate_groq_response(prompt + "\n\nPYQ Data:\n" + combined_text[:15000])
                    parsed_json = extract_json_from_text(response_text)
                    
                    if parsed_json:
                        st.session_state.t3_mcqs = parsed_json
                        st.session_state.mcq_answers_t3 = {}
                    else:
                        st.error("Format error from AI. Please try again.")
                        
                except Exception as e:
                    st.error(f"Error: {e}")

    # Interactive Mock Test Rendering
    if "t3_mcqs" in st.session_state:
        st.markdown("### 🎯 Your PYQ Mock Test")
        score = 0
        
        for i, item in enumerate(st.session_state.t3_mcqs):
            st.markdown(f"**Q{i+1}: {item['question']}**")
            
            cols = st.columns(4)
            for j, option in enumerate(item['options']):
                button_key = f"t3_btn_{i}_{j}"
                
                if cols[j].button(option, key=button_key):
                    st.session_state.mcq_answers_t3[i] = option
            
            if i in st.session_state.mcq_answers_t3:
                user_ans = st.session_state.mcq_answers_t3[i]
                correct_ans = str(item['correct_answer']).strip()
                
                # Smart Check: Map 'A', 'B', 'C', 'D' to actual option text
                correct_text = correct_ans
                if correct_ans in ['A', 'B', 'C', 'D']:
                    idx = ord(correct_ans) - 65
                    if idx < len(item['options']):
                        correct_text = item['options'][idx]

                if user_ans == correct_text or user_ans.startswith(correct_ans):
                    st.success(f"✅ Correct! \n\n**Explanation:** {item['explanation']}")
                    score += 1
                else:
                    st.error(f"❌ Wrong! Correct answer is: **{correct_text}** \n\n**Explanation:** {item['explanation']}")
            st.divider()
            
        # Show Score if all answered
        if len(st.session_state.mcq_answers_t3) == len(st.session_state.t3_mcqs):
            st.info(f"🏆 Your Total Score: {score} out of {len(st.session_state.t3_mcqs)}")
