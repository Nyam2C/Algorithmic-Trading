# ===========================================
# High-Win Survival System - Dockerfile
# Trading Bot (Background Process)
# ===========================================

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Environment
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul

# 통합 서버 (Bot + API + Discord) 실행
# healthcheck는 docker-compose.yml에서 정의

EXPOSE 8000

CMD ["python", "-m", "src.main"]
