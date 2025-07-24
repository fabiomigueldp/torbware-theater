#!/usr/bin/env python3
"""
Processamento direto de legendas para o filme 152601 (Her) no diretório real da biblioteca
"""

import os
import sys
sys.path.append('.')

from subtitle_manager import download_and_process_subtitles
import json

def process_her_subtitles():
    """Processa legendas para o filme Her (152601) no diretório real"""
    
    print('🎬 PROCESSAMENTO DIRETO: Legendas para Her (152601)')
    print('='*70)
    
    # Caminho real do filme na biblioteca
    movie_folder = r'c:\Users\fabio\Projects\theater\library\152601'
    
    # Verificar se a pasta existe
    if not os.path.exists(movie_folder):
        print(f'❌ Pasta do filme não encontrada: {movie_folder}')
        return
    
    # Carregar informações do metadata.json existente
    metadata_file = os.path.join(movie_folder, 'metadata.json')
    if not os.path.exists(metadata_file):
        print(f'❌ Arquivo metadata.json não encontrado: {metadata_file}')
        return
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        existing_metadata = json.load(f)
    
    print(f'📁 Pasta do filme: {movie_folder}')
    print(f'🎭 Título atual: {existing_metadata.get("title")}')
    print(f'📅 Data de lançamento: {existing_metadata.get("release_date")}')
    
    # Procurar por arquivo de vídeo na pasta (caso exista)
    video_file = None
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.m4v']
    
    for file in os.listdir(movie_folder):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            video_file = os.path.join(movie_folder, file)
            break
    
    if not video_file:
        print('⚠️  Nenhum arquivo de vídeo encontrado na pasta do filme')
        print('💡 Criando arquivo de vídeo temporário para processamento...')
        # Criar um arquivo de vídeo temporário para o processamento
        video_file = os.path.join(movie_folder, 'Her.2013.temp.mp4')
        with open(video_file, 'wb') as f:
            f.write(b'temporary video file for subtitle processing')
        print(f'📹 Arquivo temporário criado: {video_file}')
    else:
        print(f'📹 Arquivo de vídeo encontrado: {video_file}')
    
    # Preparar informações do filme para o SubtitleManager
    movie_info = {
        'id': 152601,
        'title': 'Ela',  # Título localizado
        'original_title': 'Her',  # Título original (inglês)
        'year': 2013,
        'tmdb_id': 152601,
        'video_file': video_file
    }
    
    print(f'🔧 Informações do filme:')
    print(f'   - ID: {movie_info["id"]}')
    print(f'   - Título: {movie_info["title"]}')
    print(f'   - Original: {movie_info["original_title"]}')
    print(f'   - Ano: {movie_info["year"]}')
    print(f'   - Arquivo: {movie_info["video_file"]}')
    
    def progress_callback(message, progress=None):
        if progress:
            print(f'📥 {message} ({progress}%)')
        else:
            print(f'📥 {message}')
    
    try:
        print('\n🚀 Iniciando processamento de legendas...')
        print('-' * 50)
        
        # Processar legendas usando a função principal
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
        else:
            print('   ❌ Nenhuma legenda foi processada')
        
        print('\n📁 VERIFICAÇÃO DOS ARQUIVOS:')
        subtitles_folder = os.path.join(movie_folder, 'subtitles')
        if os.path.exists(subtitles_folder):
            subtitle_files = os.listdir(subtitles_folder)
            if subtitle_files:
                print(f'   ✅ Pasta de legendas contém {len(subtitle_files)} arquivo(s):')
                for file in subtitle_files:
                    file_path = os.path.join(subtitles_folder, file)
                    size = os.path.getsize(file_path)
                    print(f'      - {file} ({size} bytes)')
            else:
                print('   ❌ Pasta de legendas está vazia')
        else:
            print('   ❌ Pasta de legendas não existe')
        
        return subtitle_info
        
    except Exception as e:
        print(f'\n❌ ERRO no processamento: {e}')
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        # Limpar arquivo temporário se foi criado
        if video_file and video_file.endswith('.temp.mp4') and os.path.exists(video_file):
            try:
                os.remove(video_file)
                print(f'\n🧹 Arquivo temporário removido: {video_file}')
            except:
                pass

if __name__ == '__main__':
    process_her_subtitles()
