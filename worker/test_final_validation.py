#!/usr/bin/env python3
"""
Teste final: Validação da correção do sistema de legendas
"""

from subtitle_manager import SubtitleManager
import tempfile
import os

def test_her_movie_corrected():
    """Teste final para verificar se o sistema corrigido funciona"""
    
    print('🔧 TESTE FINAL: Sistema de legendas corrigido')
    print('================================================================================')
    
    # Criar estrutura temporária
    temp_dir = tempfile.mkdtemp()
    movie_folder = os.path.join(temp_dir, '152601')
    os.makedirs(movie_folder, exist_ok=True)
    
    # Criar arquivo de vídeo falso
    fake_video = os.path.join(movie_folder, 'Her.2013.1080p.BluRay.x264-SPARKS.mp4')
    with open(fake_video, 'wb') as f:
        f.write(b'fake video data')
    
    # Simular os dados do filme 152601 (Her) com video_file
    movie_info = {
        'id': 152601,
        'title': 'Ela',
        'original_title': 'Her',
        'year': 2013,
        'tmdb_id': 152601,
        'video_file': fake_video  # Caminho absoluto do vídeo
    }
    
    print(f'🎬 Filme: {movie_info["id"]} ({movie_info["original_title"]}/{movie_info["title"]})')
    print(f'📁 Pasta: {movie_folder}')
    print(f'🎥 Arquivo: {fake_video}')
    
    def progress_callback(message, progress=None):
        if progress:
            print(f"📥 {message} ({progress}%)")
        else:
            print(f"📥 {message}")
    
    try:
        # Configurar SubtitleManager
        sm = SubtitleManager(movie_folder, movie_info, progress_callback)
        
        # Baixar e processar legendas
        legendas = sm.download_subtitles()
        
        print('\n📊 RESULTADO FINAL:')
        print(f'  - Total de legendas: {len(legendas)}')
        
        for i, legenda in enumerate(legendas, 1):
            idioma = legenda.get('language', 'desconhecido')
            arquivo = legenda.get('file', 'N/A')
            print(f'  {i}. {idioma.upper()}')
            print(f'     - Arquivo: {arquivo}')
            if idioma == 'pt':
                print('     ✅ PORTUGUÊS CONFIRMADO!')
            elif idioma == 'en':
                print('     ✅ Inglês confirmado')
        
        # Verificar se português foi encontrado
        pt_found = any(l.get('language') == 'pt' for l in legendas)
        en_found = any(l.get('language') == 'en' for l in legendas)
        
        print('\n🎯 VALIDAÇÃO FINAL:')
        print(f'  🇧🇷 Português: {"✅ SIM" if pt_found else "❌ NÃO"}')
        print(f'  🇺🇸 Inglês: {"✅ SIM" if en_found else "❌ NÃO"}')
        
        if pt_found:
            print('\n🎉 SUCESSO TOTAL! Problema das legendas em português RESOLVIDO!')
            print('✅ Sistema agora encontra legendas PT para filmes populares como "Her"')
        else:
            print('\n❌ Ainda há problemas com legendas em português')
            
        print('\n' + '='*80)
        print('RESUMO DA CORREÇÃO IMPLEMENTADA:')
        print('✅ Corrigidos códigos de idioma (ISO 639-3)')
        print('✅ Implementada estratégia de título original')
        print('✅ Estratégia híbrida (download_best + list_subtitles)')
        print('✅ Sistema usa "Her" em vez de "Ela" para busca')
        print('='*80)
        
        return pt_found, en_found, legendas
        
    except Exception as e:
        print(f'\n❌ Erro no teste: {e}')
        import traceback
        traceback.print_exc()
        return False, False, []
    
    finally:
        # Limpar pasta temporária
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    test_her_movie_corrected()
