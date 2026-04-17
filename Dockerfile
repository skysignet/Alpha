FROM python:3.11-slim
# v3
RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    sqlite3 \
    gcc \
    g++ \
    make \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --no-binary pyswisseph -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "/app/main.py"]
