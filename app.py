import streamlit as st
import pandas as pd
from io import BytesIO
import base64
import logging
import requests
import time

# Assuming your FastAPI backend is running at the specified URL
FASTAPI_BASE_URL = "https://bulk-v3-service.onrender.com"

logging.basicConfig(level=logging.INFO)

def autoplay_audio(file_path: str):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio autoplay>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)

def fetch_task_status(task_id):
    """Function to check the status of a task"""
    try:
        check_response = requests.get(f"{FASTAPI_BASE_URL}/status/{task_id}")
        if check_response.status_code == 200:
            logging.info(f"Status response for task {task_id}: {check_response.json()}")
            return check_response.json()
        else:
            return None
    except requests.RequestException as e:
        logging.error(f"Error checking task status: {e}")
        return None

def process_task(data, results_placeholder):
    """Function to process the task and handle UI updates"""
    response = requests.post(f"{FASTAPI_BASE_URL}/process/", json=data)
    if response.status_code == 200:
        task_id = response.json().get("task_id")
        st.session_state['task_id'] = task_id  # Store task_id in session state
        st.success(f"Processing started for task {task_id}. Please wait...")

        while True:
            task_info = fetch_task_status(task_id)
            if task_info and task_info.get("status") == "completed":
                response_data = task_info
                answers = response_data["results"].get("results", [])
                try:
                    df = pd.DataFrame({'Prompts': prompts, 'Answers': answers})
                    results_placeholder.write(df)
                    # Convert DataFrame to Excel and provide a download link
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False)
                    excel_data = output.getvalue()
                    b64 = base64.b64encode(excel_data).decode('utf-8')
                    st.success("🎉 Answers generated successfully!")
                    autoplay_audio('notification.mp3')  # Optional: play a notification sound
                    download_link = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="answers.xlsx">Download Excel File</a>'
                    st.markdown(download_link, unsafe_allow_html=True)
                    break  # Exit loop after successful processing
                except Exception as e:
                    st.error(f"Error creating DataFrame: {e}")
                    break
            else:
                task_progress = task_info.get("progress")
                progress_message = "GPT is processing your request. Hang tight!" if task_progress is None else f"GPT is whipping up your answers, hang tight! - {task_progress} 😎"
                results_placeholder.info(progress_message)
                time.sleep(3)  # Adjust as needed
    else:
        st.error("Failed to start processing. Please try again.")

# Sidebar configuration
st.sidebar.title("🛠️ Settings")
API_KEY = st.sidebar.text_input("🔑 OpenAI API Key", value='', type='password')
ai_model_choice = st.sidebar.selectbox("🤖 Choose model:", ["gpt-3.5-turbo-16k", "gpt-4", "gpt-4-1106-preview"])
temperature = st.sidebar.slider("🌡️ Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
seed = 12345  # Fixed seed value
processing_mode = st.sidebar.selectbox("Select Processing Mode:", ["Quick Mode", "High Accuracy Mode"], index=1)
batch_size_options = [1] + list(range(5, 51, 5))
if processing_mode == "Quick Mode":
    batch_size = st.sidebar.select_slider("Batch Size for Processing", options=batch_size_options, value=10)
with st.sidebar.expander("📝 Custom Instructions"):
    common_instructions = st.text_area("Enter instructions to apply to all prompts", '')

# Main App
st.title("🧠 GPT Answer Generator")
st.write("Generate answers for a bulk of prompts using OpenAI.")
st.warning(
    "Heads-up: The number of prompts you can smoothly process depends on how complex they are, your chosen AI model, and the set batch size. If you hit the rate limits, you might get less accurate answers, or sometimes, none at all. So, remember to adjust your batch size, pick a suitable model, and manage your prompts accordingly to get the best results."
)

# Input method selection
input_method = st.selectbox("📥 Choose input method:", ["Text Box", "File Upload"])
if input_method == "Text Box":
    user_input = st.text_area("Enter prompts:", height=300)
    prompts = user_input.split('\n\n')
elif input_method == "File Upload":
    uploaded_file = st.file_uploader("📂 Upload a CSV or Excel file", type=["csv", "xlsx"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        prompts = df.iloc[:, 0].tolist()
else:
    prompts = []

# Button to start processing
results_placeholder = st.empty()
if st.button("🚀 Generate Answers") and API_KEY:
    data = {"prompts": prompts, "ai_model_choice": ai_model_choice, "common_instructions": common_instructions, "api_key": API_KEY, "temperature": temperature, "seed": seed, "processing_mode": processing_mode}
    if processing_mode == "Quick Mode":
        data["batch_size"] = batch_size
    process_task(data, results_placeholder)

# Check if a task is already in progress when the page is loaded/refreshed
if 'task_id' in st.session_state:
    process_task(None, results_placeholder)  # Call with None data to just check status