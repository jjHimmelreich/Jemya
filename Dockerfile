# Use an official Python runtime as a parent image
#FROM python:3.8-slim
FROM python:3

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app
RUN mkdir /app/tmp

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5050
EXPOSE 5555

# Run the python script
CMD ["python", "./server.py"]
