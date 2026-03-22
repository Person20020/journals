FROM python:3.14-slim

WORKDIR /app

COPY scraper.py .

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "scraper.py"]
