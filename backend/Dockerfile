FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install all dependencies (torch will be pulled from PyPI by sentence-transformers)
RUN pip install --no-cache-dir --default-timeout=300 -r requirements.txt

COPY . .

# Create storage directories
RUN mkdir -p storage/uploads storage/generated storage/chroma_db storage/faiss_laws

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
