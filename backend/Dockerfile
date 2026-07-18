# RankPilot AI — Backend image (ใช้ได้ทั้ง api / worker / beat)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ติดตั้ง dependency ก่อน (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ด
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# ค่าเริ่มต้น = API server (worker/beat override command ใน compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
