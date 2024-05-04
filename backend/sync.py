import requests
import logging
import time

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

logging.basicConfig(level=logging.INFO)

def get_answer(prompt, ai_model_choice, common_instructions, api_key, temperature, seed, ai_provider):
    full_prompt = f"{common_instructions}\n{prompt}" if common_instructions else prompt
    logging.info(f"Sending request with prompt: {prompt[:50]}...")
    headers = {
        "Content-Type": "application/json",
    }
    if ai_provider == "Anthropic":
        headers["X-API-Key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        data = {
            "model": ai_model_choice,
            "max_tokens": 4000,
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
            "temperature": temperature,
        }
        url = ANTHROPIC_API_URL
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["User-Agent"] = "OpenAI Python v0.27.3"
        data = {
            "model": ai_model_choice,
            "messages": [{"role": "user", "content": full_prompt}],
            "temperature": temperature,
            "top_p": 1,
            "seed": seed,
        }
        url = OPENAI_API_URL
    attempts = 0
    max_attempts = 5  # maximum number of retries
    while attempts < max_attempts:
        try:
            response = requests.post(url, headers=headers, json=data)
            logging.info(f"Response Status: {response.status_code}, Response Time: {response.elapsed.total_seconds()} seconds")

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60)) # Default to 60 seconds
                logging.error(f"Rate limit exceeded. Will retry after {retry_after} seconds.")
                time.sleep(retry_after)
                attempts += 1
            elif response.status_code != 200:
                logging.error(f"Non-200 response received: {response.status_code}\nResponse body: {response.text}")
                return None, None
            else:
                response_data = response.json()
                if ai_provider == "Anthropic":
                    answer = response_data.get('content', [{}])[0].get('text', '')
                    system_fingerprint = 'Not available'
                else:
                    answer = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    system_fingerprint = response_data.get('system_fingerprint', 'Not available')
                logging.info(f"Received answer for prompt: {prompt[:50]}...")
                return answer, system_fingerprint
        except requests.RequestException as e:
            logging.error(f"HTTP Request Exception: {e}")
            attempts += 1
        except Exception as e:
            logging.error(f"Exception in API Response Parsing: {e}")
            return None, None
    logging.error("Maximum retry attempts reached.")
    return None, None

def get_answers(prompts, ai_model_choice, common_instructions, api_key, temperature, seed, ai_provider, task_id, tasks):
    results = []
    total = len(prompts)
    for index, prompt in enumerate(prompts):
        answer, system_fingerprint = get_answer(prompt, ai_model_choice, common_instructions, api_key, temperature, seed, ai_provider)
        results.append(answer)
        logging.info(f"Processing prompt {index+1}/{total}: {prompt[:50]}... System Fingerprint: {system_fingerprint}")
        progress = f"Processing prompt {index + 1} of {total}"
        tasks[task_id]['progress'] = progress
        time.sleep(2)

    # Update the task status in the global dictionary
    tasks[task_id] = {"status": "completed", "results": results}
    return {"status": "completed", "results": results}
