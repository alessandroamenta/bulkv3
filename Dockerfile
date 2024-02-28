# Use a Python base image from Docker Hub
FROM python:3.9

# Set a directory for the app
WORKDIR /usr/src/app

# Copy the backend directory contents into the container at /usr/src/app/backend
COPY backend /usr/src/app/backend

# Install the Python dependencies from backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Change to the backend directory
WORKDIR /usr/src/app/backend

# Tell the container that when it starts up, it should run your FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]