FROM python:3.12-slim

# prevents python from buffering, so errors are immediately shown
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the whole project
COPY app/ .

VOLUME ["/app/data"]

CMD ["python3", "main.py"]
