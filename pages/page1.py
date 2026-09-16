import streamlit as st
from pypdf import PdfReader
from docx import Document
import os
import math
import json 
from openai import OpenAI
from dotenv import load_dotenv

# Import our legal text definitions from the new file
from legal_tests import LEGAL_REFERENCES 

load_dotenv()
client = OpenAI()

st.title("Lab 1: Hypothetical Answering Tool")

def chunk_text(text, chunk_size=500):
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)
    return chunks

def chunk_text_max(text, max_chunks=20):
    chunk_size = math.ceil(len(text) / max_chunks)
    return chunk_text(text, chunk_size=chunk_size)

def get_chunk_folder(uploaded_file):
    base_name = os.path.splitext(uploaded_file.name)[0]
    return os.path.join("chunks", base_name)

def save_chunks(chunks, folder):
    os.makedirs(folder, exist_ok=True)
    for i, chunk in enumerate(chunks):
        filepath = os.path.join(folder, f"chunk_{i + 1}.txt")
        with open(filepath, "w") as f:
            f.write(chunk)

def read_document_as_text(uploaded_file):
    if uploaded_file.type == "application/pdf":
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = Document(uploaded_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    else:
        return None

# --- FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload your contract", type=["pdf", "docx"])

if uploaded_file is not None:
    if st.session_state.get("last_processed_file") != uploaded_file.name:
        with st.spinner("Processing your document..."):
            progress_bar = st.progress(0)
            content = read_document_as_text(uploaded_file)
            progress_bar.progress(25)

            if content is not None:
                chunks = chunk_text_max(content, max_chunks=20)
                progress_bar.progress(60)

                chunk_folder = get_chunk_folder(uploaded_file)
                save_chunks(chunks, chunk_folder)
                progress_bar.progress(100)

                st.session_state.chunks = chunks
                st.session_state.chunk_folder = chunk_folder
                st.session_state.last_processed_file = uploaded_file.name
            else:
                st.error("Could not read this file type.")
            progress_bar.empty()

    if st.session_state.get("last_processed_file") == uploaded_file.name:
        st.success("File Uploaded Successfully.")

# --- ONE FUNCTION TO RULE THEM ALL ---
def analyze_element(full_text, element_name, legal_reference, client):
    """
    A single generalized function to analyze any contract element using the provided legal reference text.
    """
    prompt = f"""You are analysing a contract to determine whether the element of {element_name.upper()} is satisfied, applying the following legal test:

{legal_reference}

Read the contract below and apply this test to determine whether this element is legally sound based on the text.

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

# --- RUNNING THE ANALYSIS ---
if "chunks" in st.session_state:
    full_text = "".join(st.session_state.chunks)
    
    st.write("---")
    st.markdown("## Individual Element Checks")
    st.write("Check each element of contract formation independently below:")

    # 1. LOOP FOR INDIVIDUAL BUTTONS
    for element_name, legal_text in LEGAL_REFERENCES.items():
        # Create a unique button for each element
        if st.button(f"Check for {element_name}", key=f"btn_{element_name}"):
            with st.spinner(f"Analysing {element_name}..."):
                try:
                    result = analyze_element(full_text, element_name, legal_text, client)
                    st.session_state[f"{element_name}_result"] = result
                except Exception as e:
                    st.error(f"Something went wrong calling the API: {e}")

        # If we have a result for this element (either from individual check or full run), display it
        if f"{element_name}_result" in st.session_state:
            result = st.session_state[f"{element_name}_result"]
            if result.get("valid"):
                st.markdown(f"### :green[✅ {element_name} is satisfied]")
                st.write(result.get("explanation", ""))
            else:
                st.markdown(f"### :red[⚠️ {element_name} - Possible legal error]")
                st.write(result.get("explanation", ""))
                with st.expander(f"Show the relevant part of the contract — {element_name}"):
                    st.write(result.get("problem_quote", "(no specific passage identified)"))
        st.write("---") # Add a divider between elements

    # 2. FULL ANALYSIS BUTTON
    st.markdown("## Full Contract Check")
    if st.button("Run Full Contract Formation Analysis"):
        progress_bar = st.progress(0)
        total_elements = len(LEGAL_REFERENCES)
        
        try:
            for i, (element_name, legal_text) in enumerate(LEGAL_REFERENCES.items()):
                with st.spinner(f"Analysing {element_name}... ({i + 1}/{total_elements})"):
                    st.session_state[f"{element_name}_result"] = analyze_element(full_text, element_name, legal_text, client)
                progress_bar.progress(int((i + 1) / total_elements * 100))
            
            st.session_state.full_analysis_run = True
            st.rerun() # Refresh the page to show all results at once
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

    # --- FIX CONTRACT ISSUES UI (WITH FEEDBACK LOOP) ---
    def generate_contract_fixes(full_text, failed_issues, feedback, client):
        issues_json = json.dumps(failed_issues, indent=2)
        
        feedback_instruction = ""
        if feedback:
            feedback_instruction = (
                f"\n\nThe user did not like the previous proposed revision and provided this feedback:\n"
                f"'{feedback}'\n"
                f"Please generate an ALTERNATIVE legally valid revision that accommodates this feedback "
                f"while still ensuring all legal formation issues are fixed."
            )

        prompt = f"""You are an expert contract lawyer. The following contract has been analyzed and found to have legal formation issues.
        
        Original Contract:
        {full_text}
        
        Issues identified (JSON format):
        {issues_json}
        {feedback_instruction}
        
        Please rewrite the problematic clauses (or add necessary clauses) to make the contract legally valid, addressing all the identified issues. 
        Ensure the revised text maintains the original intent of the parties as much as possible while complying with the law. 
        Output ONLY the revised text (either the specific rewritten clauses or the full revised text, whichever is clearer). Do not include markdown blocks like ``` or introductory pleasantries.
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    # Check if a full analysis was run, and if there are any errors to fix
    if st.session_state.get("full_analysis_run"):
        # Gather all current results
        results = [(element, st.session_state.get(f"{element}_result", {})) for element in LEGAL_REFERENCES.keys()]
        all_valid = all(r.get("valid") for _, r in results if r)
        
        if not all_valid:
            st.markdown("## 🛠️ Fix Contract Issues")
            
            # State 1: We haven't generated anything yet
            if "proposed_fixes" not in st.session_state:
                st.write("Would you like our AI to draft the necessary changes to make this contract legally valid?")
                
                if st.button("Generate Fixes"):
                    with st.spinner("Drafting legally valid revisions..."):
                        failed_dict = {label: res for label, res in results if res and not res.get("valid")}
                        st.session_state.proposed_fixes = generate_contract_fixes(full_text, failed_dict, "", client)
                        st.session_state.user_feedback = "" 
                    st.rerun() 
                    
            # State 2: We have generated fixes, show feedback loop on top, results below
            else:
                st.markdown("### Proposed Revisions")
                st.write("Not quite right? Tell us what to change (e.g., 'Make it more formal', 'Change the consideration to $10') and generate a new version.")
                
                feedback_input = st.text_input("Enter your feedback here:")
                
                if st.button("Regenerate Alternative Fix"):
                    if feedback_input:
                        with st.spinner("Drafting an alternative valid version..."):
                            failed_dict = {label: res for label, res in results if res and not res.get("valid")}
                            st.session_state.proposed_fixes = generate_contract_fixes(
                                full_text, 
                                failed_dict, 
                                feedback_input, 
                                client
                            )
                            st.rerun() 
                    else:
                        st.warning("Please enter some feedback before regenerating.")
                        
                st.text_area(
                    "Here is the legally valid alternative:", 
                    st.session_state.proposed_fixes, 
                    height=300
                )