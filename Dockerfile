# Demand2Deal — self-hosted deployment image.
#
# This image assumes webcmd runs in CLOUD (hosted) mode: `webcmd setup`
# with a Webcmd Cloud API key, so the actual browser runs on Kernel's
# hosted infra rather than inside this container. That keeps this image
# small and avoids bundling a full Chromium + font/library stack.
#
# If you'd rather run webcmd in LOCAL mode instead (browser runs inside
# this same container), see Playwright's own Docker base images
# (https://playwright.dev/docs/docker) and layer webcmd on top of one of
# those instead of python:3.12-slim + manual Node install below.

FROM python:3.12-slim

# --- Node.js 20+ for webcmd ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @agentrhq/webcmd

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

EXPOSE 8501

# Run `webcmd setup` (hosted mode + API key) once at container start if it
# hasn't been configured yet, then launch the app. Mount a volume at
# /root/.webcmd if you want that setup to persist across restarts instead
# of re-running interactively every time.
CMD ["streamlit", "run", "app.py"]
