# Script de instalação para Windows

Write-Host "Instalando dependências de legendas para Windows..." -ForegroundColor Green

# Verifica se Python está instalado
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERRO: Python não encontrado. Instale Python 3.8+ antes de continuar." -ForegroundColor Red
    exit 1
}

# Verifica se pip está disponível
try {
    pip --version | Out-Null
    Write-Host "pip encontrado" -ForegroundColor Green
} catch {
    Write-Host "ERRO: pip não encontrado. Reinstale Python com pip incluído." -ForegroundColor Red
    exit 1
}

# Instala ffmpeg (requer Chocolatey ou instalação manual)
Write-Host "Verificando ffmpeg..." -ForegroundColor Yellow
try {
    ffmpeg -version | Out-Null
    Write-Host "ffmpeg encontrado" -ForegroundColor Green
} catch {
    Write-Host "AVISO: ffmpeg não encontrado." -ForegroundColor Yellow
    Write-Host "Para instalar ffmpeg:" -ForegroundColor Yellow
    Write-Host "1. Via Chocolatey: choco install ffmpeg" -ForegroundColor Cyan
    Write-Host "2. Baixe de: https://ffmpeg.org/download.html" -ForegroundColor Cyan
    Write-Host "3. Adicione ao PATH do sistema" -ForegroundColor Cyan
}

# Instala dependências Python
Write-Host "Instalando dependências Python..." -ForegroundColor Yellow

try {
    # Atualiza pip
    python -m pip install --upgrade pip

    # Instala ffsubsync
    pip install ffsubsync

    # Instala outras dependências
    pip install -r requirements.txt

    Write-Host "Dependências instaladas com sucesso!" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Funcionalidades disponíveis:" -ForegroundColor Cyan
    Write-Host "- Download automático de legendas em inglês e português" -ForegroundColor White
    Write-Host "- Conversão automática para WebVTT (compatível com HLS.js)" -ForegroundColor White
    Write-Host "- Sincronização automática com ffsubsync" -ForegroundColor White
    Write-Host "- Interface de usuário para seleção de legendas" -ForegroundColor White
    Write-Host "- Sincronização de legendas entre membros da party" -ForegroundColor White
    
} catch {
    Write-Host "ERRO na instalação: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Tente executar como Administrador ou instale manualmente:" -ForegroundColor Yellow
    Write-Host "pip install ffsubsync subliminal pysrt chardet" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Instalação concluída!" -ForegroundColor Green
