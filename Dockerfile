FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
# torch ставим отдельно из CPU-индекса, иначе pip тянет сборку с CUDA на несколько гигабайт
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Модель эмбеддингов (src/vectorization.py) скачивается при сборке, а не при каждом запуске контейнера.
# Отдельный слой до COPY . .: правки кода не вызывают повторное скачивание
ENV HF_HOME=/opt/huggingface \
    EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['EMBEDDING_MODEL'], device='cpu')"
# В рантайме модель берётся только из образа, без обращений к Hugging Face Hub
ENV HF_HUB_OFFLINE=1

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
