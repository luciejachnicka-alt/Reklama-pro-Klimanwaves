FROM python:3.12-slim-bookworm@sha256:7753c33391fc9f01d1984375bf375eb6686d52ba10db6043a86634a5ccf90dcf
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 APP_DATA_DIR=/data
WORKDIR /app
RUN groupadd --gid 10001 klimanwaves && useradd --uid 10001 --gid 10001 --no-create-home klimanwaves \
    && mkdir /data && chown 10001:10001 /data && chmod 700 /data
COPY app/ ./app/
COPY scripts/hosting_start.py ./scripts/hosting_start.py
RUN chmod -R a+rX /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health',timeout=4)" || exit 1
# Bootstrap fixes only the volume directory owner, then drops root before running the app.
ENTRYPOINT ["python", "scripts/hosting_start.py"]
