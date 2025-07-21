#!/bin/bash
# Script de Debug para Container Docker
# Execute dentro do container para verificar o sistema de legendas

echo "=== DEBUG DO SISTEMA DE LEGENDAS NO CONTAINER ==="
echo "Data/Hora: $(date)"
echo "Usuário: $(whoami)"
echo "Diretório: $(pwd)"

echo -e "\n--- Verificando Python e Dependências ---"
python3 --version
pip3 list | grep -E "(subliminal|pysrt|chardet|requests|ffsubsync|babelfish)"

echo -e "\n--- Verificando Estrutura de Diretórios ---"
ls -la /app/
echo -e "\nWorker:"
ls -la /app/worker/
echo -e "\nLibrary:"
ls -la /app/library/ 2>/dev/null || echo "Pasta library não existe"
echo -e "\nTmp:"
ls -la /app/tmp/ 2>/dev/null || echo "Pasta tmp não existe"

echo -e "\n--- Verificando Permissões ---"
echo "Library permissions:"
ls -ld /app/library/ 2>/dev/null || echo "Pasta library não existe"
echo "Tmp permissions:"  
ls -ld /app/tmp/ 2>/dev/null || echo "Pasta tmp não existe"

echo -e "\n--- Testando Importações Python ---"
python3 -c "
import sys
sys.path.insert(0, '/app/worker')

try:
    import config
    print('✓ config importado')
    print(f'  LIBRARY_ROOT: {config.LIBRARY_ROOT}')
    print(f'  TEMP_ROOT: {config.TEMP_ROOT}')
except Exception as e:
    print(f'✗ Erro ao importar config: {e}')

try:
    import subtitle_manager
    print('✓ subtitle_manager importado')
except Exception as e:
    print(f'✗ Erro ao importar subtitle_manager: {e}')

try:
    from subliminal import Video
    print('✓ subliminal importado')
except Exception as e:
    print(f'✗ Erro ao importar subliminal: {e}')
"

echo -e "\n--- Verificando Comandos Externos ---"
which ffmpeg && echo "✓ ffmpeg disponível" || echo "✗ ffmpeg não encontrado"
which webtorrent && echo "✓ webtorrent disponível" || echo "✗ webtorrent não encontrado"

echo -e "\n--- Verificando Logs Recentes ---"
echo "Últimos logs do sistema:"
tail -n 20 /var/log/syslog 2>/dev/null || echo "Logs do sistema não disponíveis"

echo -e "\n=== DEBUG CONCLUÍDO ==="
