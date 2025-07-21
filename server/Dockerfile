FROM node:18-alpine

WORKDIR /usr/src/app

# Copia package.json para o diretório de trabalho
COPY server/package*.json ./

# Instala as dependências
RUN npm install

# Copia o restante do código do servidor
COPY server/ .

# Expõe a porta que o app vai rodar
EXPOSE 3000

# Comando para iniciar a aplicação
CMD [ "node", "src/index.js" ]