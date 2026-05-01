FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY index.html /app/index.html
COPY css /app/css
COPY js /app/js
COPY pages /app/pages
COPY docs /app/docs
COPY README.md /app/README.md

RUN mkdir -p /app/data/uploads/avatars /app/data/uploads/posts /app/data/uploads/thumbs /app/data/exports/backups /app/data/logs

ENV OMNIFORUM_HOST=0.0.0.0 \
    OMNIFORUM_PORT=8000

EXPOSE 8000

CMD ["python3", "app.py"]
