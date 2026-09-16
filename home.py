import streamlit as st
from pypdf import PdfReader
from docx import Document
import os
import math
import json 
from openai import OpenAI
from dotenv import load_dotenv

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

# Offer

def analyze_offer(full_text, client):
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether a valid legal OFFER was made.

An offer is a definite promise to be bound on specified terms, communicated to the other party. It must be distinguished from a mere invitation to treat, a statement of willingness to negotiate, or a non-committal or conditional statement (e.g. "I might consider", "no promises").

Read the contract below and determine whether a valid, definite offer was made.

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if "chunks" in st.session_state:
    full_text = "".join(st.session_state.chunks)

    if st.button("Check for a Legal Offer"):
        with st.spinner("Analysing the offer..."):
            progress_bar = st.progress(0)
            try:
                progress_bar.progress(30)
                st.session_state.offer_result = analyze_offer(full_text, client)
                progress_bar.progress(100)
            except Exception as e:
                st.error(f"Something went wrong calling the API: {e}")
            finally:
                progress_bar.empty()

    if "offer_result" in st.session_state:
        result = st.session_state.offer_result
        if result.get("valid"):
            st.markdown("### :green[✅ A legal offer was made]")
            st.write(result.get("explanation", ""))
        else:
            st.markdown("### :red[⚠️ Possible legal error]")
            st.write(result.get("explanation", ""))
            with st.expander("Show the relevant part of the contract"):
                st.write(result.get("problem_quote", "(no specific passage identified)"))

# Acceptance

def analyze_acceptance(full_text, client):
    legal_reference = """
Acceptance occurs when the person receiving an offer agrees to it, either by a clear
statement of acceptance or through their conduct. Acceptance must be unequivocal, and it
must be communicated to the person who made the offer -- silence or inaction is not
enough; the law does not treat a person as having accepted merely because they failed to
expressly reject. Acceptance must match precisely what was offered. If the response
introduces new, different, or additional terms, it is not a valid acceptance but a
counter-offer, and it is then up to the original offeror to decide whether to accept
that counter-offer.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether a valid legal ACCEPTANCE was made, applying the following legal test:

{legal_reference}

Read the contract below and apply this test to determine whether a valid acceptance occurred, matching precisely what was offered.

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if st.button("Check for Acceptance"):
    with st.spinner("Analysing acceptance..."):
        progress_bar = st.progress(0)
        try:
            progress_bar.progress(30)
            st.session_state.acceptance_result = analyze_acceptance(full_text, client)
            progress_bar.progress(100)
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

if "acceptance_result" in st.session_state:
    result = st.session_state.acceptance_result
    if result.get("valid"):
        st.markdown("### :green[✅ A valid acceptance was made]")
        st.write(result.get("explanation", ""))
    else:
        st.markdown("### :red[⚠️ Possible legal error]")
        st.write(result.get("explanation", ""))
        with st.expander("Show the relevant part of the contract"):
            st.write(result.get("problem_quote", "(no specific passage identified)"))

#Contractual Intention

def analyze_intention(full_text, client):
    legal_reference = """
Intention to create legal relations is judged objectively -- not by what the parties
subjectively felt, but by what a reasonable person would consider they intended, given
the circumstances in which the agreement was reached. Where parties are dealing at arm's
length in a commercial context, courts generally presume they intended to create a
binding legal relationship. Where an agreement is between family members or friends and
has the character of a domestic or social arrangement, courts generally presume the
opposite -- that no legally binding relationship was intended -- unless there is clear
evidence to the contrary. A bare statement in the document asserting that the parties
intend to be legally bound does not, on its own, overcome objective circumstances
suggesting an informal, domestic, or social arrangement.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether the parties had a genuine INTENTION TO CREATE LEGAL RELATIONS, applying the following legal test:

{legal_reference}

Read the contract below and apply this test. Do not rely solely on any clause that simply asserts the parties intended to be bound -- weigh that against the actual objective circumstances described in the document (the relationship between the parties, how the agreement arose, and its overall character).

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if st.button("Check for Intention to Create Legal Relations"):
    with st.spinner("Analysing intention..."):
        progress_bar = st.progress(0)
        try:
            progress_bar.progress(30)
            st.session_state.intention_result = analyze_intention(full_text, client)
            progress_bar.progress(100)
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

if "intention_result" in st.session_state:
    result = st.session_state.intention_result
    if result.get("valid"):
        st.markdown("### :green[✅ Intention to create legal relations was present]")
        st.write(result.get("explanation", ""))
    else:
        st.markdown("### :red[⚠️ Possible legal error]")
        st.write(result.get("explanation", ""))
        with st.expander("Show the relevant part of the contract"):
            st.write(result.get("problem_quote", "(no specific passage identified)"))

# Consideration

def analyze_consideration(full_text, client):
    legal_reference = """
Consideration is the price paid for a promise -- something of value given, done, or
promised by one party in exchange for the other party's promise. It does not have to be
money; it can be a right, benefit, or interest given, or a detriment or loss undertaken.
Courts do not weigh whether the consideration given is adequate, so long as it is real
and has some value. Love, affection, or a purely voluntary gift, with nothing given in
return, is not valid consideration. A promise that leaves the promisor with complete
discretion over whether to perform at all -- with no genuine binding commitment -- is
not real consideration. The consideration must also not be illegal or impossible to
perform. An exception applies to documents properly executed as a deed: a valid deed
does not require consideration to be binding, provided it is genuinely signed, sealed
(or expressed to be sealed), and delivered in accordance with the applicable
formalities.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether valid CONSIDERATION was present, applying the following legal test:

{legal_reference}

Read the contract below and apply this test. If the document is styled or executed as a deed, consider whether it genuinely satisfies the formalities for a valid deed (properly signed, sealed or expressed to be sealed, and delivered) before concluding that the deed exception applies -- do not assume the exception applies merely because the document is labelled a "deed".

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if st.button("Check for Consideration"):
    with st.spinner("Analysing consideration..."):
        progress_bar = st.progress(0)
        try:
            progress_bar.progress(30)
            st.session_state.consideration_result = analyze_consideration(full_text, client)
            progress_bar.progress(100)
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

if "consideration_result" in st.session_state:
    result = st.session_state.consideration_result
    if result.get("valid"):
        st.markdown("### :green[✅ Valid consideration was present]")
        st.write(result.get("explanation", ""))
    else:
        st.markdown("### :red[⚠️ Possible legal error]")
        st.write(result.get("explanation", ""))
        with st.expander("Show the relevant part of the contract"):
            st.write(result.get("problem_quote", "(no specific passage identified)"))

#Capacity

def analyze_capacity(full_text, client):
    legal_reference = """
Legal capacity refers to a person's legal ability to enter into a binding contract.
Certain categories of people have limited capacity, including: people with a mental
impairment (a contract is not valid unless the person had the capacity to genuinely
understand the general nature of the contract); young people under 18 years of age
(minors) -- contracts with a minor for goods that are not "necessaries" (such as food,
clothing, shelter, medicine, or things connected with their education or apprenticeship)
are generally not binding on the minor, and contracts for credit or borrowed money are
also not binding on a minor regardless of the goods involved; bankrupts (who retain
general contractual capacity but face some statutory restrictions); and corporations
(which have capacity to contract through persons acting with actual or apparent
authority). Where a party lacks legal capacity, a contract with that party may be void
or unenforceable against them.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether all parties had valid LEGAL CAPACITY, applying the following legal test:

{legal_reference}

Read the contract below and apply this test. Pay particular attention to the actual ages, roles, and circumstances of the parties as described anywhere in the document -- including in background or recital sections -- rather than relying solely on any clause that simply asserts the parties have capacity. If a party is a minor, consider whether the subject matter of the contract would count as a "necessary" for that minor.

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if st.button("Check for Legal Capacity"):
    with st.spinner("Analysing legal capacity..."):
        progress_bar = st.progress(0)
        try:
            progress_bar.progress(30)
            st.session_state.capacity_result = analyze_capacity(full_text, client)
            progress_bar.progress(100)
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

if "capacity_result" in st.session_state:
    result = st.session_state.capacity_result
    if result.get("valid"):
        st.markdown("### :green[✅ All parties had valid legal capacity]")
        st.write(result.get("explanation", ""))
    else:
        st.markdown("### :red[⚠️ Possible legal error]")
        st.write(result.get("explanation", ""))
        with st.expander("Show the relevant part of the contract"):
            st.write(result.get("problem_quote", "(no specific passage identified)"))

#Consent

def analyze_consent(full_text, client):
    legal_reference = """
Consent to a contract must be genuine, involving free will and proper understanding by
each party of what they are doing. Genuine consent can be undermined by: (a) mistake --
but only where the mistake goes to the very basis of the agreement; (b) misrepresentation
or misleading conduct that induced a party to enter the contract; (c) duress -- actual or
threatened harm, including economic duress (threats to a person's business or
livelihood), that deprives a party of their free will to decide; (d) undue influence --
taking unfair and improper advantage of another party's weakness or vulnerability such
that they did not voluntarily enter the contract. This can arise even without a formally
recognised relationship (such as solicitor-client or doctor-patient) wherever one party
has a position of trust, dependency, or authority over the other -- for example, where
one party has taken on responsibility for managing the other's day-to-day affairs. Where
such a relationship of trust and dependency exists, a presumption of undue influence
arises, and it falls to the stronger party to show that the weaker party received
independent advice or otherwise entered the contract free of that influence; and (e)
unfair contract terms in standard form contracts. If any of these matters affected a
party's consent, the contract may not be binding on that party.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether genuine CONSENT was given by all parties, applying the following legal test:

{legal_reference}

Read the contract below and apply this test. Look closely at the actual relationship, circumstances, and vulnerabilities of the parties described anywhere in the document -- including background or recital sections -- rather than relying solely on any clause that simply asserts consent was genuine or that independent advice was obtained. Consider in particular whether a relationship of trust or dependency existed, and whether the document itself indicates that independent advice was actually obtained.

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if st.button("Check for Consent"):
    with st.spinner("Analysing consent..."):
        progress_bar = st.progress(0)
        try:
            progress_bar.progress(30)
            st.session_state.consent_result = analyze_consent(full_text, client)
            progress_bar.progress(100)
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

if "consent_result" in st.session_state:
    result = st.session_state.consent_result
    if result.get("valid"):
        st.markdown("### :green[✅ Genuine consent was present]")
        st.write(result.get("explanation", ""))
    else:
        st.markdown("### :red[⚠️ Possible legal error]")
        st.write(result.get("explanation", ""))
        with st.expander("Show the relevant part of the contract"):
            st.write(result.get("problem_quote", "(no specific passage identified)"))

def analyze_legality(full_text, client):
    legal_reference = """
A contract, or a term of a contract, that involves illegal conduct may be void and
unenforceable. Certain contracts are illegal at common law because they are contrary to
public policy, including contracts to commit a crime, tort, or fraud; contracts to
defraud the revenue (for example, deliberately misstating a transaction's true value in
order to reduce tax or duty payable); contracts that prejudice public safety or the
administration of justice; contracts that tend to promote corruption; and contracts in
unreasonable restraint of trade. An illegally formed contract is generally void and
unenforceable by either party. Where a contract that was legally formed is performed in
an illegal manner, the contract itself is not necessarily void, but the party
responsible for the illegal performance cannot claim remedies, though the innocent party
retains its rights.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": f"""You are analysing a contract to determine whether its subject matter and terms are LEGAL, applying the following legal test:

{legal_reference}

Read the contract below and apply this test, checking in particular for any term whose purpose is to misstate a transaction's true value, evade tax or duty, or otherwise achieve an illegal or public-policy-contrary outcome, even if that term is presented as routine administrative or valuation language.

Respond only in valid JSON with three keys:
"valid" (true or false),
"explanation" (a short, plain-English explanation of your reasoning, referring to the test above),
"problem_quote" (if valid is false, the exact sentence(s) from the contract, copied word-for-word, that show the problem; otherwise an empty string).

Contract:
{full_text}"""}
        ]
    )
    return json.loads(response.choices[0].message.content)

if st.button("Check for Legality"):
    with st.spinner("Analysing legality..."):
        progress_bar = st.progress(0)
        try:
            progress_bar.progress(30)
            st.session_state.legality_result = analyze_legality(full_text, client)
            progress_bar.progress(100)
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

if "legality_result" in st.session_state:
    result = st.session_state.legality_result
    if result.get("valid"):
        st.markdown("### :green[✅ The contract's terms are legal]")
        st.write(result.get("explanation", ""))
    else:
        st.markdown("### :red[⚠️ Possible legal error]")
        st.write(result.get("explanation", ""))
        with st.expander("Show the relevant part of the contract"):
            st.write(result.get("problem_quote", "(no specific passage identified)"))

#Summary of Elements

ELEMENTS = [
    ("Offer", analyze_offer, "offer_result"),
    ("Acceptance", analyze_acceptance, "acceptance_result"),
    ("Intention to Create Legal Relations", analyze_intention, "intention_result"),
    ("Consideration", analyze_consideration, "consideration_result"),
    ("Legal Capacity", analyze_capacity, "capacity_result"),
    ("Consent", analyze_consent, "consent_result"),
    ("Legality", analyze_legality, "legality_result"),
]

if "chunks" in st.session_state:
    full_text = "".join(st.session_state.chunks)

    if st.button("Run Full Contract Formation Analysis"):
        progress_bar = st.progress(0)
        total = len(ELEMENTS)
        try:
            for i, (label, func, key) in enumerate(ELEMENTS):
                with st.spinner(f"Analysing {label}... ({i + 1}/{total})"):
                    st.session_state[key] = func(full_text, client)
                progress_bar.progress(int((i + 1) / total * 100))
            st.session_state.full_analysis_run = True
        except Exception as e:
            st.error(f"Something went wrong calling the API: {e}")
        finally:
            progress_bar.empty()

    if st.session_state.get("full_analysis_run"):
        results = [(label, st.session_state[key]) for label, _, key in ELEMENTS]
        all_valid = all(r.get("valid") for _, r in results)
        failed_labels = [label for label, r in results if not r.get("valid")]

        st.write("---")

        if all_valid:
            st.markdown("## :green[✅ Contract Formation Confirmed]")
            st.write("All seven elements of contract formation are satisfied.")
        else:
            st.markdown("## :red[⚠️ Contract Formation Issues Found]")
            st.write(f"The following element(s) need attention: **{', '.join(failed_labels)}**.")

        st.write("### Summary")
        for label, result in results:
            if result.get("valid"):
                st.markdown(f"**{label}:** :green[✅ Valid]")
                st.caption(result.get("explanation", ""))
            else:
                st.markdown(f"**{label}:** :red[⚠️ Needs attention]")
                st.caption(result.get("explanation", ""))
                with st.expander(f"Show the relevant part of the contract — {label}"):
                    st.write(result.get("problem_quote", "(no specific passage identified)"))

# If the user provided feedback for a regeneration, include it in the prompt
def generate_contract_fixes(full_text, failed_issues, feedback, client):
    """
    Asks the LLM to rewrite the contract or specific clauses to fix the identified legal errors.
    Takes optional user feedback to guide the rewrite if the user didn't like the first attempt.
    """
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

# Only show the fix UI if the full analysis ran and there are errors
if st.session_state.get("full_analysis_run") and not all_valid:
    st.write("---")
    st.markdown("## 🛠️ Fix Contract Issues")
    
    # State 1: We haven't generated anything yet
    if "proposed_fixes" not in st.session_state:
        st.write("Would you like our AI to draft the necessary changes to make this contract legally valid?")
        
        if st.button("Generate Fixes"):
            with st.spinner("Drafting legally valid revisions..."):
                failed_dict = {label: res for label, res in results if not res.get("valid")}
                st.session_state.proposed_fixes = generate_contract_fixes(full_text, failed_dict, "", client)
                st.session_state.user_feedback = "" 
            st.rerun() # Refresh the page to load State 2
            
    # State 2: We have generated fixes, show feedback loop on top, results below
    else:
        st.markdown("### Proposed Revisions")
        st.write("Not quite right? Tell us what to change (e.g., 'Make it more formal', 'Change the consideration to $10') and generate a new version.")
        
        # Feedback input and regenerate button go ABOVE the text area now
        feedback_input = st.text_input("Enter your feedback here:")
        
        if st.button("Regenerate Alternative Fix"):
            if feedback_input:
                with st.spinner("Drafting an alternative valid version..."):
                    failed_dict = {label: res for label, res in results if not res.get("valid")}
                    st.session_state.proposed_fixes = generate_contract_fixes(
                        full_text, 
                        failed_dict, 
                        feedback_input, 
                        client
                    )
                    st.rerun() # Refresh to show the newly generated text
            else:
                st.warning("Please enter some feedback before regenerating.")
                
        # The text area is now rendered below the button
        st.text_area(
            "Here is the legally valid alternative:", 
            st.session_state.proposed_fixes, 
            height=300
        )