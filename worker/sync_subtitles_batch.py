#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path

# --- Bloco de Importação ---
try:
    from babelfish import Language
    from subliminal import ProviderPool
    from subliminal.video import Video
    from tmdbv3api import TMDb, Movie as TMDbMovie
    import config
except ImportError as e:
    print(f"ERRO DE IMPORTAÇÃO: {e}.\nVerifique se as dependências estão instaladas: pip install subliminal babelfish tmdbv3api python-dotenv")
    sys.exit(1)

# --- Configurações ---
PROVIDERS = ["opensubtitles", "podnapisi"]

def log(msg: str):
    """Imprime uma mensagem no console."""
    print(msg, flush=True)

def create_video_object(title: str, year: int, video_path: Path) -> Video:
    """Cria um objeto de vídeo para a busca."""
    fake_filename = f"{title}.{year}.1080p.BluRay.x264.mkv"
    video = Video.fromname(fake_filename)
    video.path = str(video_path)
    return video

def srt_to_vtt(srt_content: bytes) -> bytes:
    """Converte conteúdo SRT para VTT."""
    text = srt_content.decode("utf-8", errors="replace")
    return ("WEBVTT\n\n" + text.replace(",", ".")).encode("utf-8")

def run_sync(video_path: Path, srt_in: Path, srt_out: Path) -> bool:
    """Tenta executar o ffsubsync. Se falhar, retorna False e continua."""
    try:
        cmd = ["ffsubsync", str(video_path), "-i", str(srt_in), "-o", str(srt_out)]
        log(f"🛠️  Tentando sincronizar legenda...")
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        log("✅ Sincronização bem-sucedida.")
        return True
    except FileNotFoundError:
        log("⚠️ AVISO: 'ffsubsync' não foi encontrado. A legenda não será sincronizada.")
        return False
    except Exception as e:
        log(f"❌ Sincronização falhou. Usando legenda com tempo original. Erro: {getattr(e, 'stderr', e)}")
        return False

def find_correct_movie_info(title: str, year: int) -> dict:
    """Busca no TMDB os metadados corretos."""
    log(f"🔄 Buscando metadados no TMDB para '{title}' ({year})...")
    try:
        tmdb = TMDb()
        tmdb.api_key = config.TMDB_API_KEY
        if not tmdb.api_key: raise ValueError("Chave da API do TMDB não configurada")
        tmdb.language = 'pt-BR'
        movie_api = TMDbMovie()
        results = movie_api.search(title)
        
        for movie in results:
            release_year = int(movie.release_date.split('-')[0]) if hasattr(movie, 'release_date') and movie.release_date else 0
            if movie.title.lower() == title.lower() and release_year == year:
                log(f"✅ Metadados encontrados: '{movie.title}' (ID: {movie.id})")
                return movie_api.details(movie.id)
        return None
    except Exception as e:
        log(f"❌ Erro ao buscar dados no TMDB: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Busca, baixa e processa legendas de forma direta para um filme.")
    parser.add_argument("--movie-dir", required=True, help="Caminho completo para o diretório do filme.")
    parser.add_argument("--correct-title", required=True, help="O título original e correto do filme.")
    parser.add_argument("--correct-year", required=True, type=int, help="O ano de lançamento correto do filme.")
    args = parser.parse_args()

    movie_dir = Path(args.movie_dir).resolve()
    hls_path = movie_dir / "hls" / "playlist.m3u8"
    if not hls_path.exists(): raise FileNotFoundError(f"Arquivo HLS não encontrado em: {hls_path}")

    correct_info = find_correct_movie_info(args.correct_title, args.correct_year)
    if not correct_info:
        log("Encerrando: não foi possível encontrar metadados válidos.")
        return

    # --- FASE 1: UMA ÚNICA BUSCA DIRETA ---
    log("-" * 50)
    log("FASE 1: Realizando busca única e direta por legendas")
    video = create_video_object(args.correct_title, args.correct_year, hls_path)
    languages = {Language("eng"), Language("por", "BR")}
    
    with ProviderPool(providers=PROVIDERS) as pool:
        all_subtitles = pool.list_subtitles(video, languages)
    
    log(f"📊 Total de legendas encontradas na busca: {len(all_subtitles)}")
    if not all_subtitles:
        log("❌ Nenhuma legenda encontrada para este filme. Verifique o título e o ano.")
        return

    # --- FASE 2: SELECIONAR MANUALMENTE A MELHOR DE CADA IDIOMA ---
    log("-" * 50)
    log("FASE 2: Selecionando as melhores legendas de cada idioma")
    best_english = None
    best_portuguese = None
    max_en_score = -1
    max_pt_score = -1

    for sub in all_subtitles:
        score = sub.get_matches(video)
        lang = sub.language
        
        if lang.alpha3 == 'eng' and score > max_en_score:
            max_en_score = score
            best_english = sub
        
        if lang.alpha3 == 'por' and score > max_pt_score:
            max_pt_score = score
            best_portuguese = sub

    # --- FASE 3: PROCESSAR AS LEGENDAS SELECIONADAS ---
    log("-" * 50)
    log("FASE 3: Baixando e processando as legendas selecionadas")
    subtitles_dir = movie_dir / "subtitles"
    subtitles_dir.mkdir(exist_ok=True)
    final_results = []
    
    subtitles_to_process = [s for s in [best_english, best_portuguese] if s is not None]

    if not subtitles_to_process:
        log("❌ Nenhuma legenda com pontuação válida foi selecionada.")
        return

    with ProviderPool(providers=PROVIDERS) as pool:
        for sub in subtitles_to_process:
            lang_code = "en" if sub.language.alpha3 == 'eng' else "pt-BR"
            log(f"\n⬇️  Processando legenda para '{lang_code}' (Score: {sub.get_matches(video)})...")
            pool.download_subtitle(sub)

            if not sub.content: continue

            srt_path = subtitles_dir / f"temp_{lang_code}.srt"
            with open(srt_path, "wb") as f: f.write(sub.content)

            sync_srt_path = subtitles_dir / f"temp_{lang_code}.synced.srt"
            was_synced = run_sync(hls_path, srt_path, sync_srt_path)
            final_srt_path = sync_srt_path if was_synced else srt_path
            
            vtt_filename = f"subtitle_{'en' if lang_code == 'en' else 'pt'}.vtt"
            vtt_path = movie_dir / vtt_filename
            with open(final_srt_path, "rb") as f:
                vtt_content = srt_to_vtt(f.read())
            with open(vtt_path, "wb") as f:
                f.write(vtt_content)
            
            log(f"✅ Legenda final salva em: {vtt_path.name}")
            final_results.append({"language": lang_code, "file": vtt_path.name})
            
            srt_path.unlink(missing_ok=True)
            sync_srt_path.unlink(missing_ok=True)

    # --- FASE 4: ATUALIZAR METADADOS ---
    if final_results:
        log("-" * 50)
        log("FASE 4: Corrigindo o arquivo metadata.json")
        correct_info_dict = {
            "id": correct_info.id, "title": correct_info.title,
            "original_title": correct_info.original_title, "overview": correct_info.overview,
            "release_date": correct_info.release_date, "poster_path": correct_info.poster_path,
            "hls_playlist": "/hls/playlist.m3u8", "subtitles": []
        }
        for res in final_results:
            correct_info_dict["subtitles"].append({
                "language": res["language"],
                "name": "English" if res["language"] == "en" else "Português (Brasil)",
                "file": res["file"],
                "url": f"/api/subtitles/{correct_info.id}/{res['file']}"
            })
        
        with open(movie_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(correct_info_dict, f, ensure_ascii=False, indent=4)
        log("📝 metadata.json foi permanentemente CORRIGIDO.")
    
    log("\n🎉 Processo concluído!")

if __name__ == "__main__":
    main()