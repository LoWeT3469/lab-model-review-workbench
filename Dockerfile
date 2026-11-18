FROM python:3.11.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY .streamlit/ .streamlit/
RUN python -m lab_workbench.train && mkdir -p data
CMD ["uvicorn", "lab_workbench.api:app", "--host", "0.0.0.0", "--port", "8000"]
