import requests
import re
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_title_slug(url):
    match = re.search(r"https://leetcode\.com/problems/([^/]+)/?", url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid LeetCode problem URL")

def fetch_leetcode_problem(title_slug):
    url = "https://leetcode.com/graphql"
    query = """
    query getQuestionDetail($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            title
            content
            exampleTestcases
            metaData
        }
    }
    """
    variables = {"titleSlug": title_slug}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        question_data = data.get("data", {}).get("question", {})
        
        problem_statement = question_data.get("content", "Problem description not found")
        problem_statement = re.sub(r"<p><strong>Follow up:</strong>.*?</p>", "", problem_statement, flags=re.DOTALL)
        problem_statement = re.sub(r"Examples:.*?Constraints:.*", "", problem_statement, flags=re.DOTALL)
        
        return {
            "title": question_data.get("title", "Title not found"),
            "problem_statement": problem_statement.strip(),
            "examples": question_data.get("exampleTestcases", "Examples not found"),
            "constraints": question_data.get("metaData", "Constraints not available")
        }
    else:
        return {"error": f"Failed to fetch problem: {response.status_code}"}

def get_gpt_response(chat_history):
    system_message = {
        "role": "system",
        "content": "You are an AI tutor helping users understand coding problems. "
                   "Your responses should be structured with the following subheadings: "
                   "1. Intuition, 2. Approach Discussion In Points with Subpoints Using Example For Each Approach, 3. Example In Tabular Format, 4. Time & Space Complexity. "
                   "Do not provide direct answers. Instead, focus on guiding questions, related examples, "
                   "and thought-provoking hints to help the user think through the problem."
    }
    
    guided_chat_history = [system_message] + chat_history
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=guided_chat_history
    )
    return response.choices[0].message.content

def format_response(response):
    formatted_response = ""
    sections = response.split("\n\n")
    
    for section in sections:
        if section.startswith("Intuition:"):
            formatted_response += "## **Intuition**\n"
            formatted_response += section.replace("Intuition:", "").strip() + "\n\n"
        elif section.startswith("Approach Discussion:"):
            formatted_response += "## **Approach Discussion**\n"
            formatted_response += section.replace("Approach Discussion:", "").strip() + "\n\n"
        elif section.startswith("Example:"):
            formatted_response += "## **Example**\n"
            formatted_response += section.replace("Example:", "").strip() + "\n\n"
        elif section.startswith("Time & Space Complexity:"):
            formatted_response += "## **Time & Space Complexity**\n"
            formatted_response += section.replace("Time & Space Complexity:", "").strip() + "\n\n"
        else:
            formatted_response += section.strip() + "\n\n"
    
    return formatted_response

# Streamlit UI Integration
st.title("LeetCode GPT Assistant")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "show_chat" not in st.session_state:
    st.session_state.show_chat = False

if "problem_data" not in st.session_state:
    st.session_state.problem_data = None

leetcode_url = st.text_input("Enter LeetCode Problem URL:")

if st.button("Fetch Problem Details"):
    try:
        title_slug = extract_title_slug(leetcode_url)
        problem_data = fetch_leetcode_problem(title_slug)
        
        if "error" in problem_data:
            st.error(problem_data["error"])
        else:
            st.subheader(problem_data["title"])
            st.write("**Problem Statement:**", problem_data["problem_statement"], unsafe_allow_html=True)
            st.write("**Examples:**", problem_data["examples"])
            st.write("**Constraints:**", problem_data["constraints"])
            
            st.session_state.problem_data = problem_data
            
            st.session_state.chat_history = [
                {"role": "system", "content": "You are an AI tutor helping users understand coding problems."},
                {"role": "user", "content": f"Help me understand this problem: {problem_data['title']}.\n"
                                            f"Problem Statement: {problem_data['problem_statement']}\n"
                                            f"Examples: {problem_data['examples']}\n"
                                            f"Constraints: {problem_data['constraints']}"}
            ]
            
            gpt_response = get_gpt_response(st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "assistant", "content": gpt_response})
            st.subheader("AI Guidance")
            
            formatted_response = format_response(gpt_response)
            st.markdown(formatted_response, unsafe_allow_html=True)
            
            st.session_state.show_chat = True
    except ValueError as e:
        st.error(str(e))

if st.session_state.show_chat:
    st.subheader("Chat History")
    for i, message in enumerate(st.session_state.chat_history[2:]):
        if message["role"] == "user":
            st.write(f"👤 **You:** {message['content']}")
        elif message["role"] == "assistant":
            st.markdown(format_response(message["content"]), unsafe_allow_html=True)
        
        if i < len(st.session_state.chat_history[2:]) - 1:
            st.write("")

    st.subheader("Chat with AI")
    user_input = st.text_input("Ask a follow-up question:")
    if st.button("Send") and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        gpt_response = get_gpt_response(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": gpt_response})
        
        st.rerun()