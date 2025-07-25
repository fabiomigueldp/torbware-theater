#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script único para:
- Baixar/sincronizar/convertar legendas (EN/PT-BR) para Captain America: Brave New World (id 822119)
- Garantir PT-BR via Podnapisi se o pipeline geral falhar
- Atualizar o metadata.json com as legendas encontradas

Baseado nos dois scripts que você usou para "Her" (152601)
"""

import os
import sys
import json
from pathlib import Path

# Para importar seu módulo local
sys.path.append('.')

# Imports vindos do seu projeto
from subtitle_manager import download_and_process_subtitles, SubtitleManager

# Imports do subliminal se precisarmos forçar Podnapisi/PT
from subliminal import Video, list_subtitles, download_subtitles
from babelfish import Language

# ---------------------------------------------------------------------------

MOVIE_ID = 822119
MOVIE_FOLDER = Path(r'C:\Users\fabio\Projects\theater\library') / str(MOVIE_ID)
METADATA_PATH = MOVIE_FOLDER / 'metadata.json'
SUBTITLES_DIR = MOVIE_FOLDER / 'subtitles'

# Nome interno que usaremos no arquivo final
LANG_ALIASES = {
    'pt': 'pt-BR',     # caso venha 'pt' do provider, vamos padronizar como pt-BR
    'por': 'pt-BR',
    'pb': 'pt-BR',
    'en': 'en',
    'eng': 'en'
}

# ---------------------------------------------------------------------------

def progress_callback(message, progress=None):
    if progress is not None:
        print(f'📥 {message} ({progress}%)')
    else:
        print(f'📥 {message}')

def load_metadata():
    if not METADATA_PATH.exists():
        raise FileNotFoundError(f'metadata.json não encontrado em: {METADATA_PATH}')
    with METADATA_PATH.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def save_metadata(metadata):
    with METADATA_PATH.open('w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    print(f'💾 metadata.json atualizado em {METADATA_PATH}')

def normalize_lang(code: str) -> str:
    code = (code or '').lower()
    return LANG_ALIASES.get(code, code)

def build_hls_path(metadata):
    """
    Seu metadata guarda "/hls/playlist.m3u8". Vamos removê-la da raiz e
    apontar para dentro da pasta do filme.
    """
    rel = metadata.get('hls_playlist', '/hls/playlist.m3u8').lstrip('/')
    return MOVIE_FOLDER / rel

def build_subtitle_url(movie_id: int, filename: str) -> str:
    return f'/api/subtitles/{movie_id}/{filename}'

def ensure_dirs():
    SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)

def already_has_pt(subs_info):
    for s in subs_info:
        lang = normalize_lang(s.get('language'))
        if lang in ('pt', 'pt-br'):
            return True
    return False

def run_general_pipeline(movie_info):
    """
    Usa o pipeline normal (download_and_process_subtitles),
    que já funcionou para EN no outro script.
    """
    print('\n🚀 Rodando pipeline geral com download_and_process_subtitles...')
    subs_info = download_and_process_subtitles(
        str(MOVIE_FOLDER),
        movie_info,
        progress_callback
    )
    print(f'📊 Pipeline geral retornou {len(subs_info)} legendas')
    for i, sub in enumerate(subs_info, 1):
        print(f'  {i}. {sub.get("name", "N/A")} ({sub.get("language", "??")}) -> {sub.get("file")}')
    return subs_info

def try_force_pt_with_podnapisi(movie_info, hls_playlist):
    """
    Reimplementa a lógica do seu script que *funcionou* para PT em "Her":
    - Força providers = ['podnapisi']
    - languages = {Language('por')}
    - Usa SubtitleManager._process_subtitle_content para salvar a legenda
    """
    print('\n🇧🇷 Tentando reforçar PT usando apenas Podnapisi...')
    sm = SubtitleManager(str(MOVIE_FOLDER), movie_info, progress_callback)

    # Configurar vídeo a partir do HLS
    video = Video.fromname(str(hls_playlist))
    video.name = movie_info['original_title']  # título inglês tende a casar com DB do Podnapisi
    video.year = movie_info['year']

    languages = {Language('por')}
    providers = ['podnapisi']

    print(f'🔍 Buscando legendas PT em {providers} para: {video} ({video.year})')
    subs_map = list_subtitles([video], languages, providers=providers)
    pt_subs = subs_map.get(video, [])

    print(f'📊 Encontradas {len(pt_subs)} legendas em português (Podnapisi)')
    for i, sub in enumerate(pt_subs, 1):
        score = getattr(sub, 'get_matches', None)
        score = score(video) if score else 'N/A'
        print(f'  {i}. {sub} (Score: {score})')

    if not pt_subs:
        print('❌ Nenhuma legenda PT encontrada no Podnapisi')
        return []

    # Escolher a "melhor"
    def _score(s):
        return s.get_matches(video) if hasattr(s, 'get_matches') else 0

    best = max(pt_subs, key=_score)
    print(f'🎯 Melhor PT: {best}')
    download_subtitles([best])

    if not getattr(best, 'content', None):
        print('❌ Legenda baixada está vazia')
        return []

    print(f'✅ Conteúdo PT baixado: {len(best.content)} bytes')

    # Processar com o SubtitleManager
    try:
        result = sm._process_subtitle_content(best, 'pt')  # internal method que você já usou
    except AttributeError:
        # Fallback: se seu SubtitleManager não tiver mais esse método,
        # escrevemos manualmente o arquivo VTT (assumindo já vir em srt)
        print('⚠️ _process_subtitle_content não existe. Salvando manualmente como .vtt')
        filename = 'subtitle_pt.vtt'
        out_path = SUBTITLES_DIR / filename
        # Se vier srt, converta para vtt (simplesmente trocando a vírgula por ponto? depende do seu pipeline)
        content = best.content.decode('utf-8', errors='replace')
        if 'WEBVTT' not in content[:20].upper():
            # Conversão bem simples; use a sua função real se existir
            content = 'WEBVTT\n\n' + content.replace(',', '.')
        out_path.write_text(content, encoding='utf-8')
        result = {
            'language': 'pt-BR',
            'name': 'Português (Brasil)',
            'file': filename
        }

    if result:
        print(f'🎉 SUCESSO! Legenda PT processada: {result["file"]}')
        return [result]

    print('❌ Falha ao processar legenda PT (Podnapisi)')
    return []

def merge_and_write_to_metadata(metadata, subs_found):
    """
    subs_found: lista de dicts no padrão do seu pipeline:
      {
        "language": "...",
        "name": "...",
        "file": "..."
      }
    Atualiza metadata["subtitles"] com url e garante códigos normalizados.
    """
    # Deduplicar por idioma (último vence)
    merged_by_lang = {}
    for s in subs_found:
        lang = normalize_lang(s.get('language', ''))
        file = s.get('file')
        name = s.get('name') or lang
        if not file:
            # às vezes pode vir path absoluto; trate
            file = Path(s.get('path', '')).name or f'subtitle_{lang}.vtt'
        merged_by_lang[lang] = {
            'language': 'pt-BR' if lang == 'pt-br' else lang,
            'name': name,
            'file': file,
            'url': build_subtitle_url(MOVIE_ID, file)
        }

    final_list = list(merged_by_lang.values())
    # Ordena PT-BR primeiro, depois EN, depois demais
    def _key(item):
        if item['language'].lower() in ('pt-br', 'pt'):
            return (0, item['language'])
        if item['language'].lower() == 'en':
            return (1, item['language'])
        return (2, item['language'])
    final_list.sort(key=_key)

    metadata['subtitles'] = final_list
    return metadata

def validate_created_files(subs_found):
    for s in subs_found:
        f = s.get('file')
        if not f:
            continue
        path = SUBTITLES_DIR / f
        if path.exists():
            size = path.stat().st_size
            print(f'✅ {f} criado ({size} bytes)')
        else:
            print(f'❌ Arquivo não encontrado: {path}')

def main():
    print('🎬 PROCESSAMENTO ÚNICO: Capitão América: Admirável Mundo Novo (822119)')
    print('=' * 80)

    ensure_dirs()

    metadata = load_metadata()

    # Montar movie_info coerente com seus módulos
    hls_path = build_hls_path(metadata)
    if not hls_path.exists():
        print(f'❌ HLS não encontrado: {hls_path}')
        return

    print(f'📁 Pasta do filme: {MOVIE_FOLDER}')
    print(f'🎥 HLS: {hls_path}')

    # Exibir um preview do playlist
    try:
        with hls_path.open('r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        print(f'📺 Playlist contém: {len(content)} caracteres')
        print('📺 Primeiras linhas:')
        for i, line in enumerate(content.splitlines()[:5], start=1):
            print(f'  {i}: {line}')
    except Exception as e:
        print(f'⚠️ Não consegui ler a playlist: {e}')

    movie_info = {
        'id': MOVIE_ID,
        'title': metadata.get('title', 'Capitão América: Admirável Mundo Novo'),
        'original_title': 'Captain America: Brave New World',
        'year': 2025,
        'tmdb_id': MOVIE_ID,
        'video_file': str(hls_path)
    }

    # 1) Pipeline geral
    subs_general = []
    try:
        subs_general = run_general_pipeline(movie_info)
    except Exception as e:
        print(f'⚠️ Erro no pipeline geral: {e}')
        import traceback
        traceback.print_exc()

    # 2) Garante PT
    subs_pt_force = []
    if not already_has_pt(subs_general):
        try:
            subs_pt_force = try_force_pt_with_podnapisi(movie_info, hls_path)
        except Exception as e:
            print(f'⚠️ Erro tentando PT no Podnapisi: {e}')
            import traceback
            traceback.print_exc()

    # 3) Junta resultados
    all_subs = []
    if subs_general:
        all_subs.extend(subs_general)
    if subs_pt_force:
        all_subs.extend(subs_pt_force)

    print('\n📊 RESULTADO FINAL')
    print(f'  Total de legendas processadas: {len(all_subs)}')
    for i, s in enumerate(all_subs, 1):
        print(f'  {i}. {s.get("name", "N/A")} ({s.get("language", "??")}) -> {s.get("file")}')

    # 4) Atualiza metadata.json
    metadata = merge_and_write_to_metadata(metadata, all_subs)
    save_metadata(metadata)

    # 5) Valida criação de arquivos
    validate_created_files(metadata.get('subtitles', []))

    print('\n🏁 Fim.')

if __name__ == '__main__':
    main()
