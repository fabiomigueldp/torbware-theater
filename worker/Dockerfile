FROM python:3.10-slim

# Instala dependências do sistema: ffmpeg e webtorrent-cli (via nodejs/npm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g webtorrent-cli

WORKDIR /usr/src/app

# Instala dependências Python
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do worker
COPY worker/ .

# Este container não roda um comando por padrão, ele é chamado pelo 'server'.
# Apenas define o ponto de entrada.
ENTRYPOINT ["python", "main.py"]