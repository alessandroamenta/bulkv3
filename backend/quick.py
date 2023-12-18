import aiohttp
import asyncio
import logging

API_URL = "https://api.openai.com/v1/chat/completions"

logging.basicConfig(level=logging.INFO)


async def get_answer(session, prompt, ai_model_choice, common_instructions, api_key, temperature, seed): 
    full_prompt = f"{common_instructions}\n{prompt}" if common_instructions else prompt
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OpenAI Python v0.27.3"
    }
    data = {
        "model": ai_model_choice,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": temperature,
        "top_p": 1,
        "seed": seed 
    }
    
    logging.info(f"Sending request for prompt: {prompt[:50]}")
    retry_delay = 10  # Initial delay before retrying in seconds
    max_retries = 3  # Maximum number of retries
    timeout_duration = 1000  # Timeout duration in seconds

    for attempt in range(max_retries):
        try:
            async with session.post(API_URL, headers=headers, json=data, timeout=timeout_duration) as response:
                if response.status == 429:
                    logging.error("Rate limit exceeded. Retrying after a delay.")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Increase delay for next retry
                    continue  # Retry the request

                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"Non-200 response received: {response.status}\nResponse text: {response_text}")
                    return None

                response_data = await response.json()
                return response_data.get('choices', [{}])[0].get('message', {}).get('content', '')

        except aiohttp.ClientError as client_error:
            logging.error(f"Client error occurred: {client_error}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                return None

        except asyncio.TimeoutError:
            logging.error("Request timed out. Retrying.")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                return None

        except Exception as e:
            logging.error(f"Unexpected exception occurred: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                return None

    logging.error("Maximum retry attempts reached.")
    return None


async def get_answers(prompts, ai_model_choice, common_instructions, api_key, temperature, seed, batch_size, task_id, tasks):
    results = []
    total = len(prompts)
    # Use a context manager to ensure the session is closed after use
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(prompts), batch_size):
            batch_prompts = prompts[i:i+batch_size]
            tasks_list = [get_answer(session, prompt, ai_model_choice, common_instructions, api_key, temperature, seed) for prompt in batch_prompts]
            batch_results = await asyncio.gather(*tasks_list)
            logging.info(f"Batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} processed.")
            results.extend(batch_results)

            # Update progress
            progress = f"Processing prompt {min(i + batch_size, total)} of {total}"
            tasks[task_id]['progress'] = progress

            # Check if we need to wait before the next batch
            if i + batch_size < total:
                await asyncio.sleep(3)  # Adjust the delay as needed

    # Update the task status in the global dictionary
    tasks[task_id] = {"status": "completed", "results": results}
    return {"status": "completed", "results": results}