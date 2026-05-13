import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "knowledge.db"

# SiliconFlow API (OpenAI compatible)
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
LLM_MODEL = "deepseek-chat"

# Chunking
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 128

# Retrieval
RETRIEVAL_TOP_K = 20
RERANK_TOP_K = 5

# Ensure data dirs exist
FILES_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
