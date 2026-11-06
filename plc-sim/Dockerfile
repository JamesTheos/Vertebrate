FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir asyncua==2.0.1
COPY plc_sim.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 4840 8081
CMD ["python", "plc_sim.py"]
