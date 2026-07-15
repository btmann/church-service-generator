FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Streamlit config is in .streamlit/config.toml; these are belt-and-suspenders
    # overrides that survive any config-file parse error on Cloud Run.
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# LibreOffice provides PPTX -> PDF conversion support.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-core \
    libreoffice-impress \
    libreoffice-writer \
    fonts-dejavu-core \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-ui.txt ./
RUN pip install --upgrade pip && pip install -r requirements-ui.txt

COPY . .

# Cloud Run supplies PORT.  Use exec form so signals reach Streamlit cleanly.
CMD ["sh", "-c", "exec streamlit run ui.py --server.address=0.0.0.0 --server.port=${PORT:-8080}"]
