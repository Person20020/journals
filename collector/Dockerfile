FROM python:3.14-slim

WORKDIR /app

COPY collector.py .

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "mkdir -p /app/data && touch /app/data/journals.db && python collector.py"]
