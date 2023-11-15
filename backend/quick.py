import aiohttp
import asyncio
import logging

API_URL = "https://api.openai.com/v1/chat/completions"

logging.basicConfig(level=logging.INFO)

async def get_answer(session, prompt, model_choice, common_instructions, api_key, temperature, seed): 
    full_prompt = f"{common_instructions}\n{prompt}" if common_instructions else prompt
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
    async with session.post(API_URL, headers=headers, json=data) as response:
        logging.info(f"Request payload: {data}")
        if response.status != 200:
            # Log non-200 responses with their text for debugging
            response_text = await response.text()
            logging.error(f"Non-200 response received: {response.status}\nResponse text: {response_text}")
            return None  # Handle non-200 responses appropriately

        try:
            response_data = await response.json()
            logging.info(f"Response data: {response_data}")
            # Extract content if the expected structure is present
            return response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except aiohttp.ClientError as client_error:
            # This will catch issues like network errors, connection errors, etc.
            logging.error(f"Client error occurred: {client_error}")
            return None

        except asyncio.TimeoutError:
            # This will catch the specific timeout error
            logging.error("Request timed out.")
            return None

        except Exception as e:
            # Catch-all for any other exceptions
            logging.error(f"Unexpected exception occurred: {e}")
            return None


async def get_answers(prompts, model_choice, common_instructions, api_key, temperature, seed, batch_size, task_id, tasks):
    results = []
    total = len(prompts)
    # Use a context manager to ensure the session is closed after use
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(prompts), batch_size):
            batch_prompts = prompts[i:i+batch_size]
            tasks = [get_answer(session, prompt, model_choice, common_instructions, api_key, temperature, seed) for prompt in batch_prompts]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            # No progress bar update needed here
            # Check if we need to wait before the next batch
            if i + batch_size < len(prompts):
                await asyncio.sleep(5)  # Adjust the delay as needed
        # Update the task status in the global dictionary
    tasks[task_id] = {"status": "completed", "results": results}
    return {"status": "completed", "results": results}