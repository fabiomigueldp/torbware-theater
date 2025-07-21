#!/bin/bash

echo "Instalando dependências de legendas..."

# Atualiza o sistema
apt-get update

# Instala dependências do sistema para subliminal e ffsubsync
apt-get install -y \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    ffmpeg

# Instala ffsubsync via pip
pip install ffsubsync

# Instala outras dependências Python
pip install -r requirements.txt

echo "Dependências de legendas instaladas com sucesso!"
echo ""
echo "Funcionalidades disponíveis:"
echo "- Download automático de legendas em inglês e português"
echo "- Conversão automática para WebVTT (compatível com HLS.js)"
echo "- Sincronização automática com ffsubsync"
echo "- Interface de usuário para seleção de legendas"
echo "- Sincronização de legendas entre membros da party"
