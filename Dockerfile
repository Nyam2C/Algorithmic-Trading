# ===========================================
# High-Win Survival System - Dockerfile
# Trading Bot (Background Process)
# ===========================================

FROM python:3.10-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Environment
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul

# Trading bot은 웹서버가 아니므로 헬스체크 없음
# 프로세스 실행 상태로 health 판단

CMD ["python", "-m", "src.main"]
