#!/usr/bin/env python3
"""
Script de Debug do Sistema de Legendas
Verifica dependências e configuração
"""

import sys
import os

print("=== DEBUG DO SISTEMA DE LEGENDAS ===")
print(f"Python: {sys.version}")
print(f"Diretório atual: {os.getcwd()}")

# Testar importações uma por uma
dependencies = [
    'requests',
    'pysrt', 
    'chardet',
    'subliminal',
    'babelfish',
    'ffsubsync'
]

print("\n--- Testando dependências ---")
for dep in dependencies:
    try:
        __import__(dep)
        print(f"✓ {dep}: OK")
    except ImportError as e:
        print(f"✗ {dep}: ERRO - {e}")

# Testar módulos locais
print("\n--- Testando módulos locais ---")
worker_path = os.path.join(os.getcwd(), 'worker')
if os.path.exists(worker_path):
    print(f"✓ Pasta worker encontrada: {worker_path}")
    sys.path.insert(0, worker_path)
    
    try:
        import config
        print(f"✓ config.py: OK")
        print(f"  LIBRARY_ROOT: {getattr(config, 'LIBRARY_ROOT', 'N/A')}")
        print(f"  TEMP_ROOT: {getattr(config, 'TEMP_ROOT', 'N/A')}")
        print(f"  TMDB_API_KEY: {'Configurado' if getattr(config, 'TMDB_API_KEY', None) else 'NÃO CONFIGURADO'}")
    except ImportError as e:
        print(f"✗ config.py: ERRO - {e}")
    
    try:
        import subtitle_manager
        print(f"✓ subtitle_manager.py: OK")
    except ImportError as e:
        print(f"✗ subtitle_manager.py: ERRO - {e}")
        
else:
    print(f"✗ Pasta worker não encontrada: {worker_path}")

# Verificar estrutura de diretórios
print("\n--- Verificando estrutura ---")
dirs_to_check = ['library', 'tmp', 'worker', 'server', 'public']
for dir_name in dirs_to_check:
    dir_path = os.path.join(os.getcwd(), dir_name)
    exists = os.path.exists(dir_path)
    print(f"{'✓' if exists else '✗'} {dir_name}/: {'OK' if exists else 'NÃO ENCONTRADO'}")

# Verificar arquivos importantes
print("\n--- Verificando arquivos importantes ---")
files_to_check = [
    'worker/main.py',
    'worker/subtitle_manager.py', 
    'worker/config.py',
    'worker/requirements.txt',
    'docker-compose.yml',
    'Dockerfile'
]

for file_name in files_to_check:
    file_path = os.path.join(os.getcwd(), file_name)
    exists = os.path.exists(file_path)
    print(f"{'✓' if exists else '✗'} {file_name}: {'OK' if exists else 'NÃO ENCONTRADO'}")

print("\n=== DEBUG CONCLUÍDO ===")
