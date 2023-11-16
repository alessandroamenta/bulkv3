from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from quick import get_answers as get_answers_async
from sync import get_answers as get_answers_sync
import uuid
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

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



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": await request.json()},
    )

tasks = {}  # Dictionary to store task status and results

class PromptRequest(BaseModel):
    prompts: list
    model_choice: str
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
        results = get_answers_sync(request.prompts, request.model_choice, request.common_instructions, request.api_key, request.temperature, request.seed, task_id, tasks)
        tasks[task_id] = {"status": "completed", "results": results}
        logging.info(f"Task {task_id} completed successfully")
    except Exception as e:
        logging.error(f"Error in synchronous processing for task {task_id}: {e}")
        tasks[task_id] = {"status": "failed", "error": str(e)}

async def process_prompts_async(request: PromptRequest, task_id: str, tasks):
    try:
        logging.info(f"Starting async processing for task {task_id} with {len(request.prompts)} prompts.")
        results = await get_answers_async(request.prompts, request.model_choice, request.common_instructions, request.api_key, request.temperature, request.seed, request.batch_size, task_id, tasks)
        tasks[task_id] = {"status": "completed", "results": results}
        logging.info(f"Task {task_id} completed successfully")
        logging.info(f"Async processing completed for task {task_id}.")
    except Exception as e:
        logging.error(f"Error in asynchronous processing for task {task_id}: {e}")
        tasks[task_id] = {"status": "failed", "error": str(e)}