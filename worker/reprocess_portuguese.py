#!/usr/bin/env python3
"""
Reprocessar apenas legendas em português usando Podnapisi
"""

import os
import sys
sys.path.append('.')

from subtitle_manager import SubtitleManager
import json

def reprocess_portuguese_subtitles():
    """Reprocessa apenas legendas em português"""
    
    print('🇧🇷 REPROCESSAMENTO: Legendas PT para Her (152601)')
    print('='*60)
    
    movie_folder = r'c:\Users\fabio\Projects\theater\library\152601'
    hls_playlist = os.path.join(movie_folder, 'hls', 'playlist.m3u8')
    
    # Informações do filme
    movie_info = {
        'id': 152601,
        'title': 'Ela',
        'original_title': 'Her',
        'year': 2013,
        'tmdb_id': 152601,
        'video_file': hls_playlist
    }
    
    def progress_callback(message, progress=None):
        if progress:
            print(f'📥 {message} ({progress}%)')
        else:
            print(f'📥 {message}')
    
    try:
        # Criar SubtitleManager diretamente
        sm = SubtitleManager(movie_folder, movie_info, progress_callback)
        
        print('🔧 Configurando busca apenas para português...')
        
        # Vamos tentar baixar legendas manualmente focando no Podnapisi
        from subliminal import Video, list_subtitles
        from babelfish import Language
        
        # Configurar vídeo
        video = Video.fromname(hls_playlist)
        video.name = movie_info['original_title']
        video.year = movie_info['year']
        
        # Buscar legendas apenas em português usando Podnapisi
        languages = {Language('por')}  # Português apenas
        providers = ['podnapisi']  # Apenas Podnapisi
        
        print(f'🔍 Buscando legendas PT em: {providers}')
        print(f'📹 Vídeo: {video}')
        
        subtitles = list_subtitles([video], languages, providers=providers)
        pt_subtitles = subtitles[video]
        
        print(f'📊 Encontradas {len(pt_subtitles)} legendas em português:')
        for i, sub in enumerate(pt_subtitles, 1):
            print(f'   {i}. {sub} (Score: {sub.get_matches(video) if hasattr(sub, "get_matches") else "N/A"})')
        
        if pt_subtitles:
            # Pegar a melhor legenda
            best_pt = max(pt_subtitles, key=lambda s: s.get_matches(video) if hasattr(s, "get_matches") else 0)
            print(f'🎯 Melhor legenda PT: {best_pt}')
            
            # Baixar usando o método interno
            from subliminal import download_subtitles
            download_subtitles([best_pt])
            
            if best_pt.content:
                print(f'✅ Conteúdo baixado: {len(best_pt.content)} bytes')
                
                # Processar usando o método interno do SubtitleManager
                result = sm._process_subtitle_content(best_pt, 'pt')
                
                if result:
                    print(f'🎉 SUCESSO! Legenda PT processada: {result["file"]}')
                    return [result]
                else:
                    print('❌ Falha no processamento da legenda PT')
            else:
                print('❌ Legenda baixada está vazia')
        else:
            print('❌ Nenhuma legenda em português encontrada')
        
        return []
        
    except Exception as e:
        print(f'❌ ERRO: {e}')
        import traceback
        traceback.print_exc()
        return []

if __name__ == '__main__':
    reprocess_portuguese_subtitles()
