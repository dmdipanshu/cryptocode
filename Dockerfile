# Use official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot's source code
COPY . ./

# Expose port 8000 for FastAPI Dashboard
EXPOSE 8000

# Run the backend bot as a background process using Koyeb's preferred method for running multiple things, or use a script.
# With Uvicorn, we can run the FastAPI server and have the bot loop run in a background thread inside main.py
CMD ["python", "main.py"]
