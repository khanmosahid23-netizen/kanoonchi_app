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
st.write("AIBE Preparation with Interactive Tests & Permanent Library")

if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
    st.warning("⚠️ Configure your Groq API key in Streamlit Secrets.")
    st.stop()

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.convert('RGB').save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def generate_groq_response(prompt, img=None, json_mode=False):
    client = Groq(api_key=API_KEY)
    # Updated to use versatile model for both text and images to avoid decommissioning error
    model_name = "llama-3.3-70b-versatile" 
    
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

def extract_text(file_input, limit_pages=15):
    text = ""
    is_path = isinstance(file_input, str)
    ext = file_input.split('.')[-1].lower() if is_path else file_input.name.split('.')[-1].lower()
    
    try:
        if ext == "pdf":
            with pdfplumber.open(file_input) as pdf:
                for i, page in enumerate(pdf.pages):
                    if i >= limit_pages: break
                    extracted = page.extract_text()
                    if extracted: text += extracted + "\n"
        elif ext == "docx":
            doc = docx.Document(file_input)
            for i, para in enumerate(doc.paragraphs):
                if i >= 200: break
                text += para.text + "\n"
    except Exception as e:
        return f"Error reading file: {e}", ext
        
    return text, ext

def extract_json_from_text(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: return json.loads(match.group(1))
    
    match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
    if match: return json.loads(match.group(0))
    return None

def format_long_text(text):
    text = re.sub(r'(Q(?:uestion)?\s*\d+\s*:)', r'\n\n**\1** ', text, flags=re.IGNORECASE)
    text = re.sub(r'(A(?:ns)?(?:wer)?\s*\d+\s*:)', r'\n\n**\1** ', text, flags=re.IGNORECASE)
    return text.strip()

if 'mcq_answers_t1' not in st.session_state: st.session_state.mcq_answers_t1 = {}
if 'mcq_answers_t3' not in st.session_state: st.session_state.mcq_answers_t3 = {}

LIB_FOLDER = "kanoonchi_library"
if not os.path.exists(LIB_FOLDER):
    os.makedirs(LIB_FOLDER)

# ==========================================
# 3. MAIN APP TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📄 Notes to Interactive Test", "💬 AI Tutor & Permanent Library", "📝 Custom PYQ Mock Test"])

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
                    if uploaded_file.name.split('.')[-1].lower() in ["jpg", "jpeg", "png"]:
                        img = Image.open(uploaded_file)
                        base_prompt = f"You are a strict law professor. Generate exactly {num_q} MCQs for AIBE from the image. Return ONLY a valid JSON array: [{{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]" if "MCQ" in q_type else f"Generate {num_q} Detailed Long Analytical Questions based on the image.\nQ1: ...\n===ANSWERS===\nAns 1: ..."
                        response_text = generate_groq_response(base_prompt, img=img)
                    else:
                        text_data, _ = extract_text(uploaded_file)
                        base_prompt = f"You are a strict law professor. Generate exactly {num_q} MCQs for AIBE from the text. Return ONLY a valid JSON array: [{{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]" if "MCQ" in q_type else f"Generate {num_q} Detailed Long Analytical Questions based on the text.\nQ1: ...\n===ANSWERS===\nAns 1: ..."
                        response_text = generate_groq_response(base_prompt + "\n\nText:\n" + text_data[:15000])

                    if "MCQ" in q_type:
                        parsed_json = extract_json_from_text(response_text)
                        if parsed_json:
                            st.session_state.t1_mcqs = parsed_json
                            st.session_state.mcq_answers_t1 = {} 
                        else:
                            st.error("Failed to parse JSON. Raw output:")
                            st.write(response_text)
                    else:
                        parts = response_text.split("===ANSWERS===")
                        st.session_state.t1_long_q = parts[0]
                        st.session_state.t1_long_a = parts[1] if len(parts) > 1 else response_text

                except Exception as e:
                    st.error(f"Error: {e}")

    if "t1_mcqs" in st.session_state and "MCQ" in q_type:
        st.markdown("### 🎯 Your Interactive Test")
        for i, item in enumerate(st.session_state.t1_mcqs):
            st.markdown(f"**Q{i+1}: {item['question']}**")
            cols = st.columns(4)
            for j, option in enumerate(item['options']):
                if cols[j].button(option, key=f"t1_btn_{i}_{j}"):
                    st.session_state.mcq_answers_t1[i] = option
            
            if i in st.session_state.mcq_answers_t1:
                user_ans = st.session_state.mcq_answers_t1[i]
                correct_ans = str(item['correct_answer']).strip()
                correct_text = correct_ans
                if correct_ans in ['A', 'B', 'C', 'D']:
                    idx = ord(correct_ans) - 65
                    if idx < len(item['options']):
                        correct_text = item['options'][idx]

                if user_ans == correct_text or user_ans.startswith(correct_text):
                    st.success(f"✅ Correct! \n\n**Explanation:** {item['explanation']}")
                else:
                    st.error(f"❌ Wrong! Correct answer is: **{correct_text}** \n\n**Explanation:** {item['explanation']}")
            st.divider()

    if "t1_long_q" in st.session_state and "Long" in q_type:
        st.markdown("### 📝 Long Questions")
        st.markdown(format_long_text(st.session_state.t1_long_q))
        with st.expander("👁️ Show Detailed Answers"):
            st.markdown(format_long_text(st.session_state.t1_long_a))

# --- TAB 2: AI TUTOR & PERMANENT LIBRARY ---
with tab2:
    st.header("Interactive Doubt Solver & Library")
    
    st.markdown("### 🏛️ Kanoonchi Master Library & Direct Upload")
    
    available_books = []
    if os.path.exists(LIB_FOLDER):
        available_books.extend([os.path.join(LIB_FOLDER, f) for f in os.listdir(LIB_FOLDER) if f.endswith(('.pdf', '.docx'))])
    
    root_files = [f for f in os.listdir('.') if f.endswith(('.pdf', '.docx')) and f != "requirements.txt"]
    for rf in root_files:
        if rf not in available_books:
            available_books.append(rf)

    if available_books:
        book_names = [os.path.basename(b) for b in available_books]
        selection_mode = st.radio("Choose Library Mode:", ["Select Specific Book", "Reference from All Books"])
        
        if selection_mode == "Select Specific Book":
            selected_book_name = st.selectbox("Choose a specific book/case file:", book_names)
            selected_book_path = next((b for b in available_books if os.path.basename(b) == selected_book_name), available_books[0])
            
            if st.button(f"Load '{selected_book_name}' into AI Brain"):
                with st.spinner(f"Loading '{selected_book_name}'..."):
                    ref_text, _ = extract_text(selected_book_path, limit_pages=30) 
                    st.session_state.reference_context = ref_text
                    st.success(f"✅ '{selected_book_name}' Loaded successfully into AI Brain!")
        else:
            if st.button("Load & Reference ALL Library Books"):
                with st.spinner("Compiling and loading all books..."):
                    combined_all_text = ""
                    for b_path in available_books:
                        b_name = os.path.basename(b_path)
                        txt, _ = extract_text(b_path, limit_pages=15)
                        combined_all_text += f"\n--- [BOOK: {b_name}] ---\n" + txt
                    st.session_state.reference_context = combined_all_text
                    st.success("✅ All books loaded together into AI Brain!")

    st.markdown("---")
    st.markdown("### 📂 Or Directly Upload Book Here")
    direct_book = st.file_uploader("Upload PDF/DOCX for instant reference", type=["pdf", "docx"], key="direct_lib_up")
    if direct_book:
        if st.button("Load Uploaded Book into AI Brain"):
            with st.spinner("Reading uploaded file..."):
                ref_text, _ = extract_text(direct_book, limit_pages=30)
                st.session_state.reference_context = ref_text
                st.success(f"✅ '{direct_book.name}' Loaded successfully into AI Brain!")

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
                    system_prompt += f"\nAlways prioritize and reference this library data if relevant to the user's question:\n[LIBRARY DATA START]\n{st.session_state.reference_context[:15000]}\n[LIBRARY DATA END]\n\nUser Question: "
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
                        txt, _ = extract_text(pyq_file, limit_pages=5)
                        combined_text += txt + "\n"

                    prompt = f"Act as an AIBE examiner. Based on the provided past papers, generate {mock_num_q} highly probable NEW MCQs. Return ONLY a valid JSON array: [{{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]"
                    
                    response_text = generate_groq_response(prompt + "\n\nPYQ Data:\n" + combined_text[:15000])
                    parsed_json = extract_json_from_text(response_text)
                    
                    if parsed_json:
                        st.session_state.t3_mcqs = parsed_json
                        st.session_state.mcq_answers_t3 = {}
                    else:
                        st.error("Format error from AI. Please try again.")
                        
                except Exception as e:
                    st.error(f"Error: {e}")

    if "t3_mcqs" in st.session_state:
        st.markdown("### 🎯 Your PYQ Mock Test")
        score = 0
        
        for i, item in enumerate(st.session_state.t3_mcqs):
            st.markdown(f"**Q{i+1}: {item['question']}**")
            
            cols = st.columns(4)
            for j, option in enumerate(item['options']):
                if cols[j].button(option, key=f"t3_btn_{i}_{j}"):
                    st.session_state.mcq_answers_t3[i] = option
            
            if i in st.session_state.mcq_answers_t3:
                user_ans = st.session_state.mcq_answers_t3[i]
                correct_ans = str(item['correct_answer']).strip()
                correct_text = correct_ans
                if correct_ans in ['A', 'B', 'C', 'D']:
                    idx = ord(correct_ans) - 65
                    if idx < len(item['options']):
                        correct_text = item['options'][idx]

                if user_ans == correct_text or user_ans.startswith(correct_text):
                    st.success(f"✅ Correct! \n\n**Explanation:** {item['explanation']}")
                    score += 1
                else:
                    st.error(f"❌ Wrong! Correct answer is: **{correct_text}** \n\n**Explanation:** {item['explanation']}")
            st.divider()
            
        if len(st.session_state.mcq_answers_t3) == len(st.session_state.t3_mcqs):
            st.info(f"🏆 Your Total Score: {score} out of {len(st.session_state.t3_mcqs)}")
