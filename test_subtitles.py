#!/usr/bin/env python3
"""
Script de Teste do Sistema de Legendas
Testa o download e processamento de legendas isoladamente
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Adiciona o diretório worker ao path para importar os módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'worker'))

try:
    from subtitle_manager import download_and_process_subtitles
    import config
except ImportError as e:
    print(f"ERRO: Não foi possível importar módulos necessários: {e}")
    print("Certifique-se de que está executando no diretório correto e que as dependências estão instaladas.")
    sys.exit(1)

def test_subtitle_system():
    """Testa o sistema de legendas com um arquivo de exemplo"""
    
    print("=== TESTE DO SISTEMA DE LEGENDAS ===")
    
    # Criar diretórios temporários para teste
    test_root = tempfile.mkdtemp(prefix='subtitle_test_')
    print(f"Diretório de teste: {test_root}")
    
    try:
        # Simular estrutura de diretórios
        movie_folder = os.path.join(test_root, "test_movie")
        video_file = os.path.join(test_root, "sample_video.mp4")
        
        os.makedirs(movie_folder, exist_ok=True)
        
        # Criar arquivo de vídeo falso para teste
        with open(video_file, 'w') as f:
            f.write("fake video content for testing")
        
        print(f"Pasta do filme: {movie_folder}")
        print(f"Arquivo de vídeo simulado: {video_file}")
        
        # Informações do filme para teste
        movie_info = {
            'id': 123456,
            'title': 'Test Movie 2023',
            'release_date': '2023-01-01',
            'video_file': video_file
        }
        
        def progress_callback(message, progress=None):
            print(f"[{progress or '?'}%] {message}")
        
        print("\n--- Iniciando teste de download de legendas ---")
        
        # Testar o sistema de legendas
        subtitle_info = download_and_process_subtitles(
            movie_folder, 
            movie_info, 
            progress_callback
        )
        
        print(f"\n--- Resultado do teste ---")
        print(f"Legendas processadas: {len(subtitle_info)}")
        
        if subtitle_info:
            print("Legendas encontradas:")
            for sub in subtitle_info:
                print(f"  - {sub.get('name', 'N/A')} ({sub.get('language', 'N/A')})")
                print(f"    Arquivo: {sub.get('file', 'N/A')}")
                print(f"    URL: {sub.get('url', 'N/A')}")
                
                # Verificar se arquivo existe
                subtitle_path = os.path.join(movie_folder, 'subtitles', sub.get('file', ''))
                exists = os.path.exists(subtitle_path)
                print(f"    Arquivo existe: {exists}")
                if exists:
                    size = os.path.getsize(subtitle_path)
                    print(f"    Tamanho: {size} bytes")
        else:
            print("Nenhuma legenda foi processada.")
        
        # Verificar pasta de legendas
        subtitles_folder = os.path.join(movie_folder, 'subtitles')
        if os.path.exists(subtitles_folder):
            files = os.listdir(subtitles_folder)
            print(f"\nArquivos na pasta de legendas: {files}")
        else:
            print("\nPasta de legendas não foi criada.")
            
    except Exception as e:
        print(f"ERRO durante o teste: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Limpeza
        print(f"\nLimpando diretório de teste: {test_root}")
        shutil.rmtree(test_root, ignore_errors=True)
        
    print("=== TESTE CONCLUÍDO ===")

if __name__ == "__main__":
    test_subtitle_system()
