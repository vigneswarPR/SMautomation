
FROM python:3.9-slim-buster


WORKDIR /app


COPY streamlit_requirements.txt ./
RUN pip install --no-cache-dir -r streamlit_requirements.txt

COPY app.py ./


EXPOSE 8501


CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
