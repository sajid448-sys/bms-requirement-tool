# Build from bms_requirement_tool directory (where Dockerfile and docker-compose.yml live)
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bms_calculator.py adv_calculator.py server.py index.html ./

EXPOSE 5000

CMD ["python", "server.py"]
