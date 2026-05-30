# Container image for the riptide-watergraph HTTP service.
# Build:  docker build -t riptide-watergraph .
# Serve:  docker run -p 8000:8000 riptide-watergraph
#         (then GET http://localhost:8000/healthz)
# For real models, extend with the litellm extra and pass OPENAI_API_KEY:
#         docker run -e OPENAI_API_KEY=sk-... -p 8000:8000 riptide-watergraph
FROM python:3.13-slim

WORKDIR /app

# Install the package + HTTP server extra (fastapi + uvicorn). Pure-Python build, no
# compiler needed. Copy only what the build needs first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[server]"

# Tracing is opt-in; off by default in the image.
ENV RIPTIDE_WATERGRAPH_DISABLE_TRACING=1
EXPOSE 8000

CMD ["riptide", "serve", "--host", "0.0.0.0", "--port", "8000"]
