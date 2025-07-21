import os
from dotenv import load_dotenv

# No ambiente Docker, as variáveis são passadas diretamente.
# Para desenvolvimento local, ele lê do arquivo .env.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# CORREÇÃO: Lê a variável de ambiente chamada "TMDB_API_KEY"
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Os caminhos agora são relativos ao WORKDIR do Docker (/app)
LIBRARY_ROOT = "/app/library"
TEMP_ROOT = "/app/tmp"