# Use a lightweight Python 3 base
FROM python:3.10-slim

WORKDIR /app

# Install the tech stack
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your project code into the container
COPY . .

# Default command (overridden by docker-compose)
CMD ["python", "src/node.py"]