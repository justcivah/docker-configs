FROM python:3.12-slim

# prevents python from buffering, so errors are immediately shown
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy the whole code
COPY app/ .
RUN pip install --no-cache-dir -r requirements.txt

VOLUME ["/app/data"]

CMD ["python3", "main.py"]
