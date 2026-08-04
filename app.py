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

# --- HIDE STREAMLIT BRANDING, GITHUB LINK & HEADER/FOOTER ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stDeployButton {display:none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

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
st.title("⚖️ KANOONCHI - Advanced Legal Prep")
st.markdown("---")

if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
    st.warning("⚠️ Configure your Groq API key in Streamlit Secrets.")
    st.stop()

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.convert('RGB').save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def generate_groq_response(prompt, img=None, json_mode=False):
    client = Groq(api_key=API_KEY)
    model_name = "llama-3.3-70b-versatile" 
    
    if img:
        base64_img = pil_to_base64(img)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]
        
    response = client.chat.completions.create(
        model=model_name,
        messages=messages
    )
    return response.choices[0].message.content

def extract_text(file_input, start_page=1, end_page=30, process_mode="First X Pages", x_pages=15):
    text = ""
    is_path = isinstance(file_input, str)
    ext = file_input.split('.')[-1].lower() if is_path else file_input.name.split('.')[-1].lower()
    
    try:
        if ext == "pdf":
            with pdfplumber.open(file_input) as pdf:
                total_pages = len(pdf.pages)
                if process_mode == "Custom Range":
                    s_idx = max(0, start_page - 1)
                    e_idx = min(total_pages, end_page)
                elif process_mode == "Last X Pages":
                    s_idx = max(0, total_pages - x_pages)
                    e_idx = total_pages
                else: 
                    s_idx = 0
                    e_idx = min(total_pages, x_pages)
                
                selected_pages = pdf.pages[s_idx:e_idx]
                for page in selected_pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
                        
        elif ext == "docx":
            doc = docx.Document(file_input)
            for i, para in enumerate(doc.paragraphs):
                if i >= 300: break
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
# 3. CLEAN MULTI-PAGE NAVIGATION SETUP
# ==========================================
page = st.sidebar.selectbox("📂 Choose Section", ["📄 Notes to Test Generator", "💬 AI Tutor & Library Chat", "📝 Custom PYQ Mock Test"])

# ==========================================
# PAGE 1: NOTES TO TEST GENERATOR
# ==========================================
if page == "📄 Notes to Test Generator":
    st.header("📄 Notes to Interactive Test Generator")
    st.write("Upload your study notes, bare acts, or chapters and generate smart interactive tests.")

    col1, col2 = st.columns(2)
    with col1:
        q_type = st.radio("Select Test Format:", ["Interactive MCQs", "Long Answers"])
    with col2:
        num_q = st.number_input("Number of Questions", min_value=1, max_value=20, value=5)

    uploaded_file = st.file_uploader("Upload Document (PDF, DOCX, JPG)", type=["pdf", "docx", "png", "jpg", "jpeg"], key="t1_up")

    with st.expander("✂️ Advanced: Smart Page Range Extractor (For Large PDFs)"):
        p_mode = st.radio("Scan Mode:", ["First X Pages", "Last X Pages", "Custom Range"], horizontal=True, key="t1_pmode")
        start_p, end_p, x_p = 1, 30, 15
        if p_mode == "Custom Range":
            cp1, cp2 = st.columns(2)
            start_p = cp1.number_input("Start Page", min_value=1, value=1)
            end_p = cp2.number_input("End Page", min_value=1, value=30)
        else:
            x_p = st.number_input("Number of pages to scan", min_value=1, max_value=200, value=15, key="t1_xp")

    if uploaded_file is not None:
        if st.button("🚀 Generate Test"):
            with st.spinner(f"Processing document & crafting {num_q} {q_type}..."):
                try:
                    ext = uploaded_file.name.split('.')[-1].lower()
                    if ext in ["jpg", "jpeg", "png"]:
                        img = Image.open(uploaded_file)
                        base_prompt = f"You are a strict law professor. Generate exactly {num_q} MCQs for AIBE from the image. Each option must include full description text. Return ONLY a valid JSON array: [{{\"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]" if "MCQ" in q_type else f"Generate {num_q} Detailed Long Questions based on image.\nQ1: ...\n===ANSWERS===\nAns 1: ..."
                        response_text = generate_groq_response(base_prompt, img=img)
                    else:
                        text_data, _ = extract_text(uploaded_file, start_page=start_p, end_page=end_p, process_mode=p_mode, x_pages=x_p)
                        if not text_data.strip():
                            st.error("❌ No text extracted from the specified pages.")
                        else:
                            base_prompt = f"You are a strict law professor. Generate exactly {num_q} MCQs for AIBE from the text. Each option must include full description text. Return ONLY a valid JSON array: [{{\"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]" if "MCQ" in q_type else f"Generate {num_q} Detailed Long Questions based on text.\nQ1: ...\n===ANSWERS===\nAns 1: ..."
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
        st.markdown("### 🎯 Interactive Test Session")
        for i, item in enumerate(st.session_state.t1_mcqs):
            st.markdown(f"**Q{i+1}: {item['question']}**")
            cols = st.columns(4)
            for j, option in enumerate(item['options']):
                if cols[j].button(option, key=f"t1_btn_{i}_{j}"):
                    st.session_state.mcq_answers_t1[i] = option
            
            if i in st.session_state.mcq_answers_t1:
                user_ans = st.session_state.mcq_answers_t1[i]
                correct_ans = str(item['correct_answer']).strip().upper()
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
        st.markdown("### 📝 Long Analytical Questions")
        st.markdown(format_long_text(st.session_state.t1_long_q))
        with st.expander("👁️ Show Detailed Answers"):
            st.markdown(format_long_text(st.session_state.t1_long_a))

# ==========================================
# PAGE 2: AI TUTOR & LIBRARY CHAT
# ==========================================
elif page == "💬 AI Tutor & Library Chat":
    st.header("💬 AI Legal Tutor & Library Chat")
    st.write("Chat with your permanent library books or attach files/photos instantly.")

    available_books = []
    if os.path.exists(LIB_FOLDER):
        available_books.extend([os.path.join(LIB_FOLDER, f) for f in os.listdir(LIB_FOLDER) if f.endswith(('.pdf', '.docx'))])
    
    root_files = [f for f in os.listdir('.') if f.endswith(('.pdf', '.docx')) and f != "requirements.txt"]
    for rf in root_files:
        if rf not in available_books:
            available_books.append(rf)

    if available_books:
        with st.expander("🏛️ Permanent Library Book Loader"):
            book_names = [os.path.basename(b) for b in available_books]
            selected_book_name = st.selectbox("Choose book:", book_names)
            selected_book_path = next((b for b in available_books if os.path.basename(b) == selected_book_name), available_books[0])
            
            lc1, lc2 = st.columns(2)
            lib_s = lc1.number_input("Start Page", min_value=1, value=1, key="lib_s")
            lib_e = lc2.number_input("End Page", min_value=1, value=50, key="lib_e")
            
            if st.button("📥 Load Pages into AI Brain"):
                with st.spinner("Loading library pages..."):
                    ref_text, _ = extract_text(selected_book_path, start_page=lib_s, end_page=lib_e, process_mode="Custom Range") 
                    st.session_state.reference_context = ref_text
                    st.success(f"✅ Loaded Pages {lib_s}-{lib_e} of '{selected_book_name}'!")

    with st.expander("📎 Direct Chat Attachments (PDF / Photo / Camera)"):
        chat_file = st.file_uploader("Upload PDF, DOCX or Image", type=["pdf", "docx", "png", "jpg", "jpeg"], key="chat_file_up")
        use_camera = st.checkbox("📸 Click live photo from camera")
        captured_img = st.camera_input("Take a picture") if use_camera else None

    st.markdown("---")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message and message["image"]:
                st.image(message["image"], width=300)

    if prompt := st.chat_input("Ask your legal doubt..."):
        with st.chat_message("user"):
            st.markdown(prompt)
            if captured_img: st.image(captured_img, width=300)
            if chat_file: st.write(f"📁 Attached: {chat_file.name}")

        attachment_text = ""
        attachment_img = None

        if captured_img:
            attachment_img = Image.open(captured_img)
        elif chat_file:
            ext = chat_file.name.split('.')[-1].lower()
            if ext in ["jpg", "jpeg", "png"]:
                attachment_img = Image.open(chat_file)
            else:
                attachment_text, _ = extract_text(chat_file, process_mode="First X Pages", x_pages=20)

        st.session_state.messages.append({
            "role": "user", 
            "content": prompt, 
            "image": captured_img if captured_img else (attachment_img if chat_file and chat_file.name.split('.')[-1].lower() in ["jpg", "jpeg", "png"] else None)
        })

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                system_prompt = "You are Kanoonchi, an expert AI Legal Tutor for Indian law students. "
                if "reference_context" in st.session_state and st.session_state.reference_context:
                    system_prompt += f"\nLibrary Data:\n{st.session_state.reference_context[:10000]}\n"
                if attachment_text:
                    system_prompt += f"\nAttached File Data:\n{attachment_text[:10000]}\n"
                system_prompt += f"\nUser Question: {prompt}"

                try:
                    if attachment_img:
                        response_text = generate_groq_response(system_prompt, img=attachment_img)
                    else:
                        response_text = generate_groq_response(system_prompt)
                        
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# PAGE 3: CUSTOM PYQ MOCK TEST
# ==========================================
elif page == "📝 Custom PYQ Mock Test":
    st.header("📝 Custom PYQ Mock Test Generator")
    st.write("Upload past exam papers and generate probable mock tests with automatic score tracking.")
    
    mock_num_q = st.number_input("Number of MCQs for Mock Test", min_value=1, max_value=50, value=10)
    uploaded_pyqs = st.file_uploader("Upload Past Papers (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True, key="t3_up")
    
    if uploaded_pyqs:
        if st.button("🚀 Generate Mock Test"):
            with st.spinner("Analyzing past trends & generating test..."):
                try:
                    combined_text = ""
                    for pyq_file in uploaded_pyqs:
                        txt, _ = extract_text(pyq_file, process_mode="First X Pages", x_pages=10)
                        combined_text += txt + "\n"

                    prompt = f"Act as an AIBE examiner. Based on the provided past papers, generate {mock_num_q} highly probable NEW MCQs. Each option must include full description text. Return ONLY a valid JSON array: [{{\"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"correct_answer\": \"A\", \"explanation\": \"...\"}}]"
                    
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
        st.markdown("### 🎯 Mock Test Session")
        score = 0
        
        for i, item in enumerate(st.session_state.t3_mcqs):
            st.markdown(f"**Q{i+1}: {item['question']}**")
            
            cols = st.columns(4)
            for j, option in enumerate(item['options']):
                if cols[j].button(option, key=f"t3_btn_{i}_{j}"):
                    st.session_state.mcq_answers_t3[i] = option
            
            if i in st.session_state.mcq_answers_t3:
                user_ans = st.session_state.mcq_answers_t3[i]
                correct_ans = str(item['correct_answer']).strip().upper()
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
