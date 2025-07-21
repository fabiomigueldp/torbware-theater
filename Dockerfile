# Começamos com uma base Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# 1. Instala dependências do sistema: git, node, npm, ffmpeg e libmagic1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    ffmpeg \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Instala dependência global de Node.js (webtorrent)
RUN npm install -g webtorrent-cli

# 3. Instala dependências Python
COPY worker/requirements.txt ./worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

# 4. Instala dependências Node.js
COPY server/package.json server/package-lock.json ./server/
RUN npm install --prefix server

# 5. Copia todo o código do projeto para o diretório de trabalho
COPY . .

# Expõe a porta que o servidor Node.js usa
EXPOSE 3000

# O comando final para iniciar a aplicação (o servidor Node.js)
CMD [ "node", "server/src/index.js" ]