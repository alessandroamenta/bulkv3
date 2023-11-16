import requests
import logging
import time

API_URL = "https://api.openai.com/v1/chat/completions"

logging.basicConfig(level=logging.INFO)

def get_answer(prompt, model_choice, common_instructions, api_key, temperature, seed):
    full_prompt = f"{common_instructions}\n{prompt}" if common_instructions else prompt
    logging.info(f"Sending request with prompt: {prompt[:50]}...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OpenAI Python v0.27.3"
    }
    data = {
        "model": model_choice,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": temperature,
        "top_p": 1,
        "seed": seed 
    }
    attempts = 0
    max_attempts = 5  # maximum number of retries
    backoff_factor = 1  # initial delay in seconds

    while attempts < max_attempts:
        try:
            response = requests.post(API_URL, headers=headers, json=data)
            logging.info(f"Response Status: {response.status_code}, Response Time: {response.elapsed.total_seconds()} seconds")

            if response.status_code == 429:
                logging.error("Rate limit exceeded. Will retry after a delay.")
                time.sleep(backoff_factor)
                backoff_factor *= 2  # double the delay for next retry
                attempts += 1
            elif response.status_code != 200:
                logging.error(f"Non-200 response received: {response.status_code}\nResponse body: {response.text}")
                return None, None
            else:
                # Process successful response
                response_data = response.json()
                answer = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                system_fingerprint = response_data.get('system_fingerprint', 'Not available')
                return answer, system_fingerprint
        except Exception as e:
            logging.error(f"Exception in API Response Parsing: {e}")
            logging.error(f"API Response: {response.text}")
            return None, None
    logging.error("Maximum retry attempts reached.")
    return None, None

def get_answers(prompts, model_choice, common_instructions, api_key, temperature, seed, task_id, tasks):
    results = []
    total = len(prompts)
    for index, prompt in enumerate(prompts):
        answer, system_fingerprint = get_answer(prompt, model_choice, common_instructions, api_key, temperature, seed)
        results.append(answer)
        logging.info(f"Processing prompt {index+1}/{total}: {prompt[:50]}... System Fingerprint: {system_fingerprint}")
        progress = f"Processing prompt {index + 1} of {total}"
        tasks[task_id]['progress'] = progress
        time.sleep(2)

    # Update the task status in the global dictionary
    tasks[task_id] = {"status": "completed", "results": results}
    return {"status": "completed", "results": results}