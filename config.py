import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

if os.getenv("HF_OFFLINE", "1") == "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Caminhos
BASE_DIR = Path(__file__).resolve().parent
EDITAIS_DIR = BASE_DIR / "editais"
CHROMA_DIR = BASE_DIR / "data" / "chroma_db"

# NVIDIA API
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
# Pode ser trocado no .env com: LLM_MODEL=nvidia/nome-do-modelo
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))  # segundos

# Embeddings
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
PREFIXO_DOCUMENTO = "passage: "
PREFIXO_PERGUNTA = "query: "

# Chunking 
CHUNK_TOKENS = 300
CHUNK_OVERLAP = 50

# Recuperação
TOP_K = 5

# Geração (chat)
TEMPERATURA = 0.2
MAX_TOKENS_RESPOSTA = int(os.getenv("MAX_TOKENS_RESPOSTA", "1024"))

# Análise (resumo e compatibilidade)
K_POR_CONSULTA = 3       # trechos recuperados por consulta na análise
MAX_TOKENS_ANALISE = int(os.getenv("MAX_TOKENS_ANALISE", "2048"))

DESATIVAR_RACIOCINIO = os.getenv("DESATIVAR_RACIOCINIO", "0") == "1"