FROM mcr.microsoft.com/playwright/python:v1.58.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 3000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000", "--proxy-headers", "--forwarded-allow-ips=*"]
