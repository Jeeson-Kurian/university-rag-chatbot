# Hugging Face Space (Docker SDK) for the public Course Compass demo.
FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
USER user
ENV HOME=/home/user PYTHONUNBUFFERED=1 UNIVERSITY_CACHE_DIR=/tmp/course-compass-cache \
    DAILY_BUDGET_USD=2 SESSION_AI_LIMIT=25
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
