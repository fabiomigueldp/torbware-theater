#!/usr/bin/env python3
"""
Processamento de legendas usando o arquivo HLS real do filme Her
"""

import os
import sys
sys.path.append('.')

from subtitle_manager import download_and_process_subtitles
import json

def process_her_subtitles_with_hls():
    """Processa legendas para o filme Her usando o HLS real"""
    
    print('🎬 PROCESSAMENTO COM HLS REAL: Legendas para Her (152601)')
    print('='*70)
    
    # Caminho real do filme na biblioteca
    movie_folder = r'c:\Users\fabio\Projects\theater\library\152601'
    
    # Usar o arquivo HLS real como referência de vídeo
    hls_playlist = os.path.join(movie_folder, 'hls', 'playlist.m3u8')
    
    if not os.path.exists(hls_playlist):
        print(f'❌ Playlist HLS não encontrada: {hls_playlist}')
        return
    
    print(f'📁 Pasta do filme: {movie_folder}')
    print(f'🎥 Arquivo HLS: {hls_playlist}')
    
    # Verificar se o playlist existe e tem conteúdo
    with open(hls_playlist, 'r') as f:
        playlist_content = f.read()
        print(f'📺 Playlist contém: {len(playlist_content)} caracteres')
        print('📺 Primeiras linhas:')
        for i, line in enumerate(playlist_content.split('\n')[:5]):
            print(f'   {i+1}: {line}')
    
    # Preparar informações do filme usando HLS
    movie_info = {
        'id': 152601,
        'title': 'Ela',  # Título localizado
        'original_title': 'Her',  # Título original (inglês)
        'year': 2013,
        'tmdb_id': 152601,
        'video_file': hls_playlist  # Usar HLS como arquivo de vídeo
    }
    
    print(f'\n🔧 Informações do filme:')
    print(f'   - ID: {movie_info["id"]}')
    print(f'   - Título: {movie_info["title"]}')
    print(f'   - Original: {movie_info["original_title"]}')
    print(f'   - Ano: {movie_info["year"]}')
    print(f'   - Arquivo HLS: {movie_info["video_file"]}')
    
    def progress_callback(message, progress=None):
        if progress:
            print(f'📥 {message} ({progress}%)')
        else:
            print(f'📥 {message}')
    
    try:
        print('\n🚀 Iniciando processamento com HLS real...')
        print('-' * 50)
        
        # Processar legendas usando o HLS
        subtitle_info = download_and_process_subtitles(
            movie_folder,
            movie_info,
            progress_callback
        )
        
        print('\n📊 RESULTADO FINAL:')
        print(f'   - Total de legendas processadas: {len(subtitle_info)}')
        
        if subtitle_info:
            for i, sub in enumerate(subtitle_info, 1):
                language = sub.get('language', 'desconhecido')
                name = sub.get('name', 'N/A')
                file = sub.get('file', 'N/A')
                print(f'   {i}. {name} ({language})')
                print(f'      - Arquivo: {file}')
                
                # Verificar se o arquivo foi criado
                subtitle_path = os.path.join(movie_folder, 'subtitles', file)
                if os.path.exists(subtitle_path):
                    size = os.path.getsize(subtitle_path)
                    print(f'      ✅ Arquivo criado: {size} bytes')
                else:
                    print(f'      ❌ Arquivo não encontrado: {subtitle_path}')
        
        return subtitle_info
        
    except Exception as e:
        print(f'\n❌ ERRO no processamento: {e}')
        import traceback
        traceback.print_exc()
        return []

if __name__ == '__main__':
    process_her_subtitles_with_hls()
