import streamlit as st
import pandas as pd
from io import BytesIO
import base64
import logging
import requests
import time
import dropbox

# Assuming your FastAPI backend is running at the specified URL
FASTAPI_BASE_URL = "https://shark-app-829tg.ondigitalocean.app"
#FASTAPI_BASE_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO)

# Dropbox Upload Function
def upload_to_dropbox(file_bytes, dropbox_folder, file_name):
    # Request new access token from backend
    response = requests.get(f"{FASTAPI_BASE_URL}/refresh_token")
    if response.status_code == 200:
        access_token = response.json().get("access_token")
        dbx = dropbox.Dropbox(access_token)
        dropbox_path = f'/{dropbox_folder}/{file_name}'
        try:
            dbx.files_upload(file_bytes, dropbox_path, mode=dropbox.files.WriteMode.overwrite)
            return True
        except Exception as e:
            print(f"Error uploading to Dropbox: {e}")
            return False
    else:
        print("Failed to refresh Dropbox token")
        return False


def check_dropbox_authentication():
    response = requests.get(f"{FASTAPI_BASE_URL}/check_authentication")
    if response.status_code == 200:
        st.session_state['dropbox_authenticated'] = response.json().get("authenticated", False)
        st.session_state['dropbox_token'] = response.json().get("access_token", None)
    else:
        st.session_state['dropbox_authenticated'] = False
        st.session_state['dropbox_token'] = None

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

def process_task(data, results_placeholder, output_file_name):
    """Function to process the task and handle UI updates"""
    dropbox_folder = st.session_state.get('dropbox_folder', '')
    if data:
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
                        
                        # Convert DataFrame to Excel
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df.to_excel(writer, index=False)
                        excel_data = output.getvalue()
                        b64 = base64.b64encode(excel_data).decode('utf-8')

                        # Provide download link
                        download_link = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{output_file_name}">Download Excel File</a>'

                        st.markdown(download_link, unsafe_allow_html=True)
                        st.success("🎉 Answers generated successfully!")
                        autoplay_audio('notification.mp3')

                        # Upload to Dropbox if authenticated
                        if 'dropbox_token' in st.session_state and st.session_state['dropbox_token']:
                            if upload_to_dropbox(excel_data, dropbox_folder, output_file_name):
                                st.success(f"File uploaded to Dropbox successfully at /{dropbox_folder}/{output_file_name}!")
                            else:
                                st.error("Failed to upload the file to Dropbox.")
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

# Ensure Dropbox authentication check is performed on every page load
check_dropbox_authentication()

# Sidebar configuration
st.sidebar.title("🛠️ Settings")
ai_provider_toggle = st.sidebar.toggle("Select AI Provider", value=True, key="ai_provider_toggle")
if ai_provider_toggle:
    ai_provider = "Anthropic"
    ai_provider_emoji = "🦜"
else:
    ai_provider = "OpenAI"
    ai_provider_emoji = "🤖"
st.sidebar.write(f"You have selected {ai_provider} {ai_provider_emoji}")
api_key = st.sidebar.text_input("Enter your API key:", type="password")

# Dropbox Integration
if 'dropbox_authenticated' not in st.session_state:
    st.session_state['dropbox_authenticated'] = check_dropbox_authentication()

if st.session_state['dropbox_authenticated']:
    st.sidebar.success("✅ Authenticated with Dropbox")
    dropbox_folder = st.sidebar.text_input("Dropbox Folder", value='bulk')
    st.session_state['dropbox_folder'] = dropbox_folder

    # Add Log Out button here
    if st.sidebar.button("Log Out from Dropbox"):
        response = requests.get(f"{FASTAPI_BASE_URL}/clear_authentication")
        if response.status_code == 200:
            st.session_state.pop('dropbox_authenticated', None)
            st.session_state.pop('dropbox_token', None)
            st.sidebar.success("Logged out from Dropbox")
        else:
            st.sidebar.error("Failed to log out from Dropbox")
else:
    if st.sidebar.button("Connect to Dropbox"):
        st.sidebar.markdown(f"[Authenticate with Dropbox]({FASTAPI_BASE_URL}/auth/redirect)", unsafe_allow_html=True)

# Input for custom output file name
custom_output_name = st.sidebar.text_input("Name Output File (without extension - optional!)")

ai_model_choice = st.sidebar.selectbox("🤖 Choose model:", [
    "gpt-4-turbo-preview", "gpt-3.5-turbo-0125", "gpt-4", "gpt-4-1106-preview",
    "claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-haiku-20240307"
])
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
st.warning("⚠️ Dropbox Notes:\n"
            "- File Overwriting: If a file with the same name already exists in your specified Dropbox folder, it will be overwritten.\n"
            "- Folder Creation: If the specified folder doesn't exist, Dropbox will automatically create it during the file upload.")

# Input method selection
input_method = st.selectbox("📥 Choose input method:", ["Text Box", "File Upload"])
if input_method == "Text Box":
    user_input = st.text_area("Enter prompts:", height=300)
    prompts = user_input.split('\n\n')
    default_output_file_name = "answers.xlsx"
elif input_method == "File Upload":
    uploaded_file = st.file_uploader("📂 Upload a CSV or Excel file", type=["csv", "xlsx"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        prompts = df.iloc[:, 0].tolist()
        default_output_file_name = uploaded_file.name
    else:
        prompts = []
        default_output_file_name = "answers.xlsx"

# Button to start processing
results_placeholder = st.empty()
if st.button("🚀 Generate Answers"):
    if not api_key:
        st.sidebar.error("🚨 Please enter a valid API key to use the app.")
        st.stop()
    else:
        output_file_name = f"{custom_output_name}.xlsx" if custom_output_name else default_output_file_name
        data = {
            "prompts": prompts, 
            "ai_model_choice": ai_model_choice, 
            "common_instructions": common_instructions, 
            "api_key": api_key, 
            "temperature": temperature, 
            "seed": seed, 
            "processing_mode": processing_mode,
            "ai_provider": ai_provider
        }    
    if processing_mode == "Quick Mode":
        data["batch_size"] = batch_size
            # Determine the output file name based on user input or default logic
    if custom_output_name:
        output_file_name = f"{custom_output_name}.xlsx"
    else:
        output_file_name = uploaded_file.name if input_method == "File Upload" and uploaded_file is not None else "answers.xlsx"

    # Call process_task with the determined file name
    process_task(data, results_placeholder, output_file_name)

# Check if a task is already in progress when the page is loaded/refreshed
if 'task_id' in st.session_state:
    process_task(None, results_placeholder, default_output_file_name)  # Call with None data to just check status
