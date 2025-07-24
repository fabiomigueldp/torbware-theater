#!/usr/bin/env python3
"""
Cria um arquivo MP4 real a partir dos segmentos HLS para sincronização de legendas
"""

import os
import subprocess
import tempfile

def create_video_from_hls():
    """Cria um arquivo MP4 a partir do HLS para sincronização"""
    
    print('🎬 CRIANDO MP4 REAL A PARTIR DO HLS')
    print('='*50)
    
    movie_folder = r'c:\Users\fabio\Projects\theater\library\152601'
    hls_playlist = os.path.join(movie_folder, 'hls', 'playlist.m3u8')
    
    if not os.path.exists(hls_playlist):
        print(f'❌ Playlist HLS não encontrada: {hls_playlist}')
        return None
    
    # Arquivo de saída temporário
    output_mp4 = os.path.join(movie_folder, 'Her.2013.converted.mp4')
    
    try:
        print(f'📥 Convertendo HLS para MP4...')
        print(f'   - Origem: {hls_playlist}')
        print(f'   - Destino: {output_mp4}')
        
        # Comando FFmpeg para converter HLS para MP4
        # -t 600 = apenas os primeiros 10 minutos (suficiente para sincronização)
        cmd = [
            'ffmpeg',
            '-i', hls_playlist,
            '-t', '600',  # Apenas 10 minutos para não demorar muito
            '-c', 'copy',  # Copia streams sem recodificar (mais rápido)
            '-y',  # Sobrescrever se existir
            output_mp4
        ]
        
        print(f'🔧 Executando: {" ".join(cmd)}')
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300  # 5 minutos de timeout
        )
        
        if result.returncode == 0 and os.path.exists(output_mp4):
            size = os.path.getsize(output_mp4)
            print(f'✅ MP4 criado com sucesso!')
            print(f'   - Arquivo: {output_mp4}')
            print(f'   - Tamanho: {size:,} bytes')
            return output_mp4
        else:
            print(f'❌ Erro na conversão:')
            print(f'   - Código de saída: {result.returncode}')
            print(f'   - Stderr: {result.stderr}')
            return None
            
    except subprocess.TimeoutExpired:
        print('❌ Conversão excedeu tempo limite (5 minutos)')
        return None
    except Exception as e:
        print(f'❌ Erro na conversão: {e}')
        return None

if __name__ == '__main__':
    create_video_from_hls()
