# Começamos com uma base Python
FROM python:3.10-slim-bullseye

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# 1. Instala dependências do sistema
# Habilita repositórios non-free e instala pacotes essenciais
RUN sed -i 's/main/main contrib non-free/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ffmpeg \
    libmagic1 \
    unrar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Instala Node.js v18 (versão moderna e estável)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
RUN apt-get install -y nodejs

# 3. Instala dependência global de Node.js (webtorrent)
RUN npm install -g webtorrent-cli

# 4. Instala dependências Python
COPY worker/requirements.txt ./worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

# 5. Instala dependências Node.js do servidor
COPY server/package.json server/package-lock.json ./server/
RUN npm install --prefix server

# 6. Copia todo o código do projeto para o diretório de trabalho
COPY . .

# Expõe a porta que o servidor Node.js usa
EXPOSE 3000

# O comando final para iniciar a aplicação
CMD [ "sh", "-c", "chmod -R 777 /app/tmp /app/library && node server/src/index.js" ]