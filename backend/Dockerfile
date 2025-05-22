# Build stage
FROM python:alpine AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --cache-dir /tmp/pip-cache -r requirements.txt

# Runtime stage
FROM python:alpine
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

CMD ["fastapi", "run", "app/main.py"]
