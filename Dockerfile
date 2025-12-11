FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

# Expose port
EXPOSE 8000

# Run the API
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
