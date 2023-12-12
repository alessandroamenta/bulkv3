from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from quick import get_answers as get_answers_async
from sync import get_answers as get_answers_sync
import uuid
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import redis

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize Redis client
redis_client = redis.Redis(
  host='redis-11690.c323.us-east-1-2.ec2.cloud.redislabs.com',
  port=11690,
  password='AcXaA835oSUqdTNkDtSVGwTHyXw97WGZ'
)

# Replace these with your actual Dropbox app credentials
DROPBOX_APP_KEY = "npvcigoarpi9ftu"
DROPBOX_APP_SECRET = "vzhjh9kqojfoipr"
# Securely store and retrieve your refresh token
REDIRECT_URI = "https://bulk-v3-service.onrender.com/auth"
#REDIRECT_URI = "http://localhost:8000/auth"


@app.get("/auth/redirect")
async def auth_redirect():
    return RedirectResponse(
        url=f"https://www.dropbox.com/oauth2/authorize?client_id={DROPBOX_APP_KEY}&response_type=code&redirect_uri={REDIRECT_URI}&token_access_type=offline"
    )

@app.get("/auth")
async def auth(request: Request):
    code = request.query_params.get("code")
    if code:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.dropbox.com/oauth2/token",
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": DROPBOX_APP_KEY,
                    "client_secret": DROPBOX_APP_SECRET,
                    "redirect_uri": REDIRECT_URI,
                },
            )
        if response.status_code == 200:
            token_data = response.json()
            # Store tokens in Redis
            redis_client.set("dropbox_refresh_token", token_data["refresh_token"])
            redis_client.set("dropbox_access_token", token_data["access_token"])
            # Return an HTML response indicating successful authentication
            html_content = """
            <html>
                <head>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            background-color: #f4f4f4;
                            text-align: center;
                            padding: 50px;
                        }
                        h2 {
                            color: #4CAF50;
                        }
                        p {
                            color: #555;
                        }
                    </style>
                </head>
                <body>
                    <h2>Authentication Successful!</h2>
                    <p>Please return to the app and refresh the page once to use Dropbox.</p>
                </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        else:
            return JSONResponse(status_code=400, content={"message": "Failed to authenticate"})
    else:
        raise HTTPException(status_code=400, detail="Missing authorization code")

@app.get("/refresh_token")
async def refresh_token():
    refresh_token = redis_client.get("dropbox_refresh_token").decode("utf-8") if redis_client.get("dropbox_refresh_token") else None
    if refresh_token:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.dropbox.com/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": DROPBOX_APP_KEY,
                    "client_secret": DROPBOX_APP_SECRET,
                },
            )
        if response.status_code == 200:
            new_tokens = response.json()
            redis_client.set("dropbox_access_token", new_tokens["access_token"])
            return {"access_token": new_tokens["access_token"]}
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to refresh token")
    else:
        raise HTTPException(status_code=400, detail="Refresh token not available")

@app.get("/check_authentication")
async def check_authentication():
    access_token = redis_client.get("dropbox_access_token").decode("utf-8") if redis_client.get("dropbox_access_token") else None
    if access_token:
        return {"authenticated": True, "access_token": access_token}
    else:
        return {"authenticated": False}

# Endpoint to clear authentication (logout)
@app.get("/clear_authentication")
async def clear_authentication():
    redis_client.delete("dropbox_refresh_token")
    redis_client.delete("dropbox_access_token")
    return {"message": "Dropbox authentication cleared"}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": await request.json()},
    )

tasks = {}  # Dictionary to store task status and results

class PromptRequest(BaseModel):
    prompts: list
    ai_model_choice: str
    common_instructions: str = "" 
    api_key: str
    temperature: float
    seed: int
    processing_mode: str
    batch_size: Optional[int] = None   # Optional, used only in Quick Mode

@app.get("/test/")
async def test_endpoint():
    logging.info("Test endpoint hit")
    return {"message": "Test endpoint is working!"}

@app.post("/process/")
async def process_prompts(request: PromptRequest, background_tasks: BackgroundTasks):
    print(f"Received request: {request}")
    logging.info(f"Received request: {request}")
    task_id = str(uuid.uuid4())  # Generate a unique task ID
    tasks[task_id] = {"status": "processing"}

    if request.processing_mode == "Quick Mode":
        background_tasks.add_task(process_prompts_async, request, task_id, tasks)
    else:
        background_tasks.add_task(process_prompts_sync, request, task_id, tasks)

    return {"message": "Processing started", "task_id": task_id}

@app.get("/status/{task_id}")
async def check_status(task_id: str):
    task = tasks.get(task_id)
    if task:
        logging.info(f"Returning status for task {task_id}: {task['status']}")
        return task
    raise HTTPException(status_code=404, detail="Task not found")

def process_prompts_sync(request: PromptRequest, task_id: str, tasks):
    logging.info("Received request in process_prompts")
    try:
        logging.info(f"Starting synchronous processing for task {task_id}")
        results = get_answers_sync(request.prompts, request.ai_model_choice, request.common_instructions, request.api_key, request.temperature, request.seed, task_id, tasks)
        tasks[task_id] = {"status": "completed", "results": results}
        logging.info(f"Task {task_id} completed successfully")
    except Exception as e:
        logging.error(f"Error in synchronous processing for task {task_id}: {e}")
        tasks[task_id] = {"status": "failed", "error": str(e)}

async def process_prompts_async(request: PromptRequest, task_id: str, tasks):
    try:
        logging.info(f"Starting async processing for task {task_id} with {len(request.prompts)} prompts.")
        results = await get_answers_async(request.prompts, request.ai_model_choice, request.common_instructions, request.api_key, request.temperature, request.seed, request.batch_size, task_id, tasks)
        tasks[task_id] = {"status": "completed", "results": results}
        logging.info(f"Task {task_id} completed successfully")
        logging.info(f"Async processing completed for task {task_id}.")
    except Exception as e:
        logging.error(f"Error in asynchronous processing for task {task_id}: {e}")
        tasks[task_id] = {"status": "failed", "error": str(e)}