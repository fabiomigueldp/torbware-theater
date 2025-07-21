import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

TMDB_API_KEY = os.getenv("6121534d2816e223b0f6d2b021d341da")

# Diretórios (relativos à raiz do projeto)
# Usamos `..` para subir um nível a partir do diretório do worker
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
LIBRARY_ROOT = os.path.join(PROJECT_ROOT, "library")
TEMP_ROOT = os.path.join(PROJECT_ROOT, "tmp")