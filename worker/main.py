#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pipeline de processamento principal para o Torbware Theater.

Este script baixa um torrent, extrai o maior arquivo de vídeo, busca
metadados no TMDb, baixa posters, converte o vídeo para HLS e processa
legendas (EN e PT‑BR). Ele foi reescrito para corrigir diversos
problemas encontrados na versão anterior:

* O arquivo de vídeo de referência para as legendas agora é sempre um
  caminho absoluto válido. O HLS final é usado quando disponível.
* Fallback explícito para legendas em português via Podnapisi quando o
  pipeline geral não encontra legendas em PT/pt‑BR.
* Normalização e deduplicação de códigos de idioma ao salvar o
  ``metadata.json``. Idiomas ``pt``, ``por`` e ``pb`` são mapeados
  para ``pt-BR``, enquanto ``en``/``eng`` tornam-se ``en``.
* Resiliência contra falhas da API Subliminal: chamadas a
  ``get_matches`` são protegidas e exceções não interrompem o fluxo.
* Correção do uso da API TMDb: o ``movie.search`` retorna lista em
  versões recentes. O script agora usa o primeiro item quando
  disponível, com fallback claro.
* Suporte a ambientes Windows sem ``python-magic``: se a detecção do
  mime falhar, a seleção do vídeo recorre à maior extensão conhecida
  (mp4/mkv/avi/mov).
* Manutenção de legendas já existentes no ``metadata.json``. O arquivo
  de metadados é carregado, atualizado e sobrescrito sem perder
  idiomas anteriores.

Para executar este script manualmente, forneça os argumentos
``--magnet``, ``--job-id`` e ``--api-url``. Em ambiente normal, ele
será invocado pelo serviço de backend.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List

import requests
try:
    import patoolib  # type: ignore
except Exception:
    # patoolib é opcional; sem ele não descompactamos arquivos
    patoolib = None  # type: ignore

try:
    import magic  # type: ignore
except Exception:
    # ``magic`` não é obrigatório em todos os ambientes.
    magic = None  # type: ignore

from babelfish import Language
from subliminal import Video, list_subtitles, download_subtitles

import config
from poster_manager import download_and_process_posters
from subtitle_manager import download_and_process_subtitles, SubtitleManager
from tmdbv3api import TMDb, Movie


# ---------------------------------------------------------------------------
# Configuração do TMDb
if not config.TMDB_API_KEY:
    print(
        "ERRO: Chave da API TMDB não encontrada. Crie um arquivo .env em /worker e defina TMDB_API_KEY.",
        file=sys.stderr,
    )
    sys.exit(1)

tmdb = TMDb()
tmdb.api_key = config.TMDB_API_KEY
tmdb.language = "pt-BR"


# ---------------------------------------------------------------------------
# Funções auxiliares

def update_status(api_url: str, job_id: str, status: str, progress: float = None, message: str = None) -> None:
    """Envia atualização de status para a API de backend."""
    payload: Dict[str, object] = {
        "status": str(status),
        "progress": float(progress) if progress is not None else None,
        "message": str(message) if message is not None else None,
    }
    try:
        requests.post(f"{api_url}/{job_id}/status", json=payload, timeout=5)
    except requests.RequestException as exc:
        print(f"AVISO: Não foi possível atualizar o status: {exc}")


def run_command(command: str) -> bool:
    """Executa um comando de shell e imprime a saída em tempo real."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        text=True,
        encoding="utf-8",
    )
    if process.stdout:
        for line in iter(process.stdout.readline, ""):
            print(line.strip())
    process.wait()
    return process.returncode == 0


def clean_filename_for_search(filename: str) -> str:
    """Limpa um nome de arquivo de torrent para obter um termo de busca mais útil."""
    name = os.path.splitext(filename)[0]
    patterns = [
        r"\[.*?(yts|rarbg|1337x|kickass|torrentgalaxy|eztv|limetorrents).*?\]",
        r"-\[?(yts|rarbg|1337x|kickass|torrentgalaxy|eztv|limetorrents)\]?",
        r"\b(yts|ytsmx|yts\.mx|rarbg|1337x|kickass|torrentgalaxy|eztv|limetorrents)\b",
        r"\[.*?(1080p|720p|2160p|4k|480p|brrip|bluray|blu-ray|dvdrip|webrip|web-dl|hdrip|hdtv).*?\]",
        r"\b(1080p|720p|2160p|4k|480p|brrip|bluray|blu-ray|dvdrip|webrip|web-dl|hdrip|hdtv|hdcam|cam|ts|r5)\b",
        r"\[.*?(x264|x265|h264|h265|aac|ac3|dts|5\.1|2\.0|10bit).*?\]",
        r"\b(x264|x265|h264|h265|hevc|avc|aac|ac3|dts|dd5\.1|dd2\.0|ddp5\.1|atmos|truehd|flac|mp3|10bit|aac5\.1)\b",
        r"\b(extended|unrated|directors\.cut|remastered|remux|proper|real|repack|internal|limited|mp4|mkv|avi|mov)\b",
        r"-[A-Z0-9]+$",
        r"[\.\[\]\(\)_-]",
        r"\s+",
    ]
    for pattern in patterns:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)
    cleaned = name.strip()
    year_match = re.search(r"\b(19|20)\d{2}\b", cleaned)
    if year_match:
        year = year_match.group()
        before_year = cleaned[: year_match.start()].strip()
        title_words = []
        for word in before_year.split():
            if not re.match(r"^(x26[45]|h26[45]|aac\d?|ac3|dts|bit|p|fps|mb|gb|kb)$", word, re.IGNORECASE):
                title_words.append(word)
        if title_words:
            clean_title = " ".join(title_words)
            cleaned = f"{clean_title} {year}"
    if not year_match:
        words = cleaned.split()
        meaningful_words = []
        for word in words:
            if len(word) >= 3 and not re.match(
                r"^(ddp|dts|aac\d?|ac3|h26[45]|x26[45]|bit|fps|mb|gb|kb|\d+p|\d+bit)$",
                word,
                re.IGNORECASE,
            ):
                meaningful_words.append(word)
        cleaned = " ".join(meaningful_words)
    words = cleaned.split()
    if len(words) > 6:
        final_words: List[str] = []
        for word in words[:8]:
            if re.match(r"^(19|20)\d{2}$", word):
                final_words.append(word)
                break
            final_words.append(word)
            if len(final_words) >= 5 and not re.match(
                r"^(19|20)\d{2}$",
                words[len(final_words)] if len(final_words) < len(words) else "",
            ):
                break
        cleaned = " ".join(final_words)
    return cleaned.strip()


def normalize_lang(code: str) -> str:
    """Normaliza códigos de idioma para um formato consistente."""
    if not code:
        return ""
    c = code.lower()
    if c in ("pt", "por", "pb", "pt-br"):
        return "pt-BR"
    if c in ("en", "eng"):
        return "en"
    return code


def merge_subtitles(existing: List[Dict[str, str]], new: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Combina duas listas de legendas, deduplicando por idioma e
    normalizando códigos. A lista ``new`` sobrescreve os itens de
    ``existing`` se houver conflito.
    """
    merged: Dict[str, Dict[str, str]] = {}
    for sub in existing + new:
        lang = normalize_lang(sub.get("language", ""))
        if not lang:
            continue
        file = os.path.basename(sub.get("file", sub.get("path", "")))
        name = sub.get("name") or lang
        url = sub.get("url") or f"/api/subtitles/{{id}}/{file}"
        merged[lang] = {
            "language": lang,
            "name": name,
            "file": file,
            "url": url,
        }
    # Ordenar: PT‑BR primeiro, depois EN, depois outros
    def _key(item: Dict[str, str]):
        lang = item["language"].lower()
        if lang in ("pt-br", "pt"):
            return (0, lang)
        if lang == "en":
            return (1, lang)
        return (2, lang)
    return sorted(merged.values(), key=_key)


def safe_get_matches(subtitle, video: Video) -> int:
    """Obtém a pontuação de coincidências de uma legenda de forma segura."""
    getter = getattr(subtitle, "get_matches", None)
    if callable(getter):
        try:
            return getter(video) or 0
        except Exception:
            return 0
    return 0


def force_pt_with_podnapisi(movie_info: Dict[str, object], hls_path: str, movie_folder: str, progress_callback) -> List[Dict[str, str]]:
    """
    Busca uma legenda PT/pt‑BR diretamente do provedor Podnapisi como
    fallback. Retorna uma lista contendo um único dicionário no padrão
    usado pelo pipeline.
    """
    # Instanciar SubtitleManager para reutilizar métodos de conversão
    sm = SubtitleManager(movie_folder, movie_info, progress_callback)

    # Configurar o objeto Video para busca. O título original tende a
    # corresponder ao banco do Podnapisi, e definimos o ano explicitamente.
    video = Video.fromname(hls_path)
    if movie_info.get("original_title"):
        video.name = movie_info["original_title"]
    elif movie_info.get("title"):
        video.name = movie_info["title"]
    # preencher ano
    if movie_info.get("year"):
        try:
            video.year = int(movie_info["year"])
        except Exception:
            pass

    languages = {Language("por")}
    providers = ["podnapisi"]
    try:
        progress_callback("Buscando legendas PT em Podnapisi...", 0)
        subs_map = list_subtitles([video], languages, providers=providers)
    except Exception as exc:
        progress_callback(f"Erro ao listar legendas no Podnapisi: {str(exc)[:50]}", 0)
        return []
    pt_subs = subs_map.get(video, []) if subs_map else []
    if not pt_subs:
        progress_callback("Nenhuma legenda PT encontrada em Podnapisi", 0)
        return []
    # Selecionar a melhor legenda com base em get_matches, quando disponível
    best = max(pt_subs, key=lambda s: safe_get_matches(s, video))
    try:
        # Fazer o download do conteúdo da legenda
        download_subtitles([best])
    except Exception as exc:
        progress_callback(f"Falha ao baixar legenda PT: {str(exc)[:50]}", 0)
        return []
    if not getattr(best, "content", None):
        progress_callback("Legenda PT baixada está vazia", 0)
        return []
    # Usar método público de SubtitleManager para converter conteúdo
    try:
        result = sm.process_subtitle_content(best, "pt-BR")
    except AttributeError:
        # Em versões antigas, process_subtitle_content pode não existir. Nesse
        # caso, escrever o conteúdo diretamente em VTT.
        filename = "subtitle_pt-BR.vtt"
        out_path = os.path.join(movie_folder, "subtitles", filename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # simples conversão: adiciona cabeçalho WEBVTT e substitui vírgulas
        content = best.content.decode("utf-8", errors="replace")
        if "WEBVTT" not in content[:20].upper():
            content = "WEBVTT\n\n" + content.replace(",", ".")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        result = {
            "language": "pt-BR",
            "name": "Português (Brasil)",
            "file": filename,
            "url": f"/api/subtitles/{movie_info['id']}/{filename}",
        }
    if result:
        progress_callback("Legenda PT via Podnapisi processada", 100)
        return [result]
    return []


# ---------------------------------------------------------------------------
# Função principal

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--magnet", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--api-url", required=True)
    args = parser.parse_args()

    # Preparar diretórios
    job_temp_dir = os.path.join(config.TEMP_ROOT, args.job_id)
    download_dir = os.path.join(job_temp_dir, "download")
    unpacked_dir = os.path.join(job_temp_dir, "unpacked")
    os.makedirs(unpacked_dir, exist_ok=True)
    os.makedirs(config.LIBRARY_ROOT, exist_ok=True)

    processing_successful = False

    try:
        # -------------------------------------------------------------------
        # Passo 1 – Download
        update_status(args.api_url, args.job_id, "Baixando")
        if not run_command(f'webtorrent download "{args.magnet}" --out "{download_dir}"'):
            raise Exception("Falha no download do torrent.")

        # -------------------------------------------------------------------
        # Passo 2 – Descompressão
        update_status(args.api_url, args.job_id, "Descompactando")
        archive_found = False
        for item in os.listdir(download_dir):
            item_path = os.path.join(download_dir, item)
            try:
                # Verificar se patoolib está disponível e se o item é um arquivo compactado
                if patoolib and hasattr(patoolib, 'is_archive') and patoolib.is_archive(item_path):
                    print(f"Descompactando {item}...")
                    patoolib.extract_archive(item_path, outdir=unpacked_dir)
                    archive_found = True
            except Exception as exc:
                print(f"AVISO: Não foi possível extrair {item}. Erro: {exc}")
        if not archive_found:
            print("Nenhum arquivo compactado encontrado, copiando todos os arquivos.")
            for item in os.listdir(download_dir):
                src_path = os.path.join(download_dir, item)
                dest_path = os.path.join(unpacked_dir, item)
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dest_path)

        # -------------------------------------------------------------------
        # Passo 3 – Identificação do maior arquivo de vídeo
        update_status(args.api_url, args.job_id, "Analisando arquivos")
        video_file: str = None
        max_size = 0
        supported_ext = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".mpg", ".mpeg"}
        for root, _, files in os.walk(unpacked_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    if magic:
                        try:
                            mime_type = magic.from_file(filepath, mime=True)
                        except Exception:
                            mime_type = ""
                    else:
                        mime_type = ""
                    is_video = mime_type.startswith("video/") if mime_type else False
                    if not is_video:
                        # Fallback: verifica pela extensão
                        ext = os.path.splitext(file)[1].lower()
                        if ext in supported_ext:
                            is_video = True
                    if is_video:
                        size = os.path.getsize(filepath)
                        if size > max_size:
                            max_size = size
                            video_file = filepath
                except Exception:
                    continue
        if not video_file:
            raise Exception("Nenhum arquivo de vídeo válido encontrado.")

        # -------------------------------------------------------------------
        # Passo 4 – Metadados via TMDb
        update_status(args.api_url, args.job_id, "Buscando metadados")
        search_term = clean_filename_for_search(os.path.basename(video_file))
        print(f"Buscando metadados para: '{search_term}'")
        movie = Movie()
        search_variations = [search_term]
        words = search_term.split()
        if len(words) > 3:
            short_version = " ".join(words[:3])
            search_variations.append(short_version)
            if re.search(r"\b(19|20)\d{2}\b", search_term):
                no_year = re.sub(r"\b(19|20)\d{2}\b", "", search_term).strip()
                if no_year and len(no_year.split()) >= 2:
                    search_variations.insert(0, no_year)
        clean_version = re.sub(r"\b\d+\b", "", search_term).strip()
        if clean_version and clean_version != search_term:
            search_variations.append(clean_version)
        search_results = None
        successful_term = None
        movie_id = None
        title = search_term
        original_title = search_term
        overview = "Descrição não disponível"
        release_date = ""
        for variation in search_variations:
            try:
                results = movie.search(variation)
            except Exception as exc:
                print(f"Erro na busca TMDb com '{variation}': {exc}")
                continue
            # A API recente retorna lista de objetos. Se vazia, tente próximo.
            if results and isinstance(results, list):
                first = results[0]
                try:
                    movie_id = getattr(first, "id", None)
                except Exception:
                    movie_id = None
                if movie_id:
                    try:
                        details = movie.details(movie_id)
                        title = getattr(details, "title", variation)
                        original_title = getattr(details, "original_title", title)
                        overview = getattr(details, "overview", overview)
                        release_date = getattr(details, "release_date", release_date)
                    except Exception:
                        pass
                    successful_term = variation
                    break
        if not movie_id:
            # Fallback com hash para ID único
            movie_id = abs(hash(search_term)) % 1000000
            print(f"Filme não encontrado no TMDb para '{search_term}', usando fallback ID: {movie_id}")

        # Pasta na biblioteca para este filme
        movie_library_path = os.path.join(config.LIBRARY_ROOT, str(movie_id))
        if os.path.exists(movie_library_path):
            raise Exception(f"Filme '{title}' já existe na biblioteca.")
        os.makedirs(movie_library_path, exist_ok=True)
        hls_dir = os.path.join(movie_library_path, "hls")
        os.makedirs(hls_dir, exist_ok=True)

        # Construir movie_info inicial
        year = None
        if release_date:
            try:
                year = int(str(release_date)[:4])
            except Exception:
                year = None
        movie_info: Dict[str, object] = {
            "id": movie_id,
            "title": title,
            "original_title": original_title,
            "overview": overview,
            "release_date": release_date,
            "year": year,
            "poster_path": None,
        }

        # -------------------------------------------------------------------
        # Passo 5 – Download e processamento de posters
        update_status(args.api_url, args.job_id, "Processando posters", 55)
        def poster_progress_callback(message: str, progress: float = None) -> None:
            adjusted = 55 + (progress * 0.05) if progress is not None else None
            update_status(args.api_url, args.job_id, message, adjusted)
        poster_info = download_and_process_posters(movie_library_path, movie_info, poster_progress_callback)
        movie_info["posters"] = poster_info
        movie_info["poster_path"] = poster_info.get("large") or poster_info.get("medium") or "/poster.png"

        # -------------------------------------------------------------------
        # Passo 6 – Conversão para HLS (inteligente)
        update_status(args.api_url, args.job_id, "Analisando formato do vídeo", 70)
        hls_playlist = os.path.join(hls_dir, "playlist.m3u8")
        segment_path = os.path.join(hls_dir, "segment%03d.ts")
        # Analisar codecs
        probe_cmd = f'ffprobe -v quiet -print_format json -show_streams "{video_file}"'
        probe_process = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
        can_copy = False
        bit_depth = 8
        pixel_format = None
        if probe_process.returncode == 0:
            try:
                probe_data = json.loads(probe_process.stdout)
                video_codec = None
                audio_codec = None
                video_profile = None
                for stream in probe_data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        video_codec = stream.get("codec_name", "").lower()
                        video_profile = stream.get("profile", "").lower()
                        pixel_format = stream.get("pix_fmt", "")
                        if any(fmt in pixel_format for fmt in ["p10", "10bit", "10le", "10be", "yuv420p10"]):
                            bit_depth = 10
                        elif any(fmt in pixel_format for fmt in ["p12", "12bit", "12le", "12be", "yuv420p12"]):
                            bit_depth = 12
                        elif any(fmt in pixel_format for fmt in ["16le", "16be", "16bit"]):
                            bit_depth = 16
                        else:
                            bit_depth = 8
                    elif stream.get("codec_type") == "audio":
                        audio_codec = stream.get("codec_name", "").lower()
                compatible_video = video_codec in ["h264", "avc"] and bit_depth == 8
                compatible_audio = audio_codec in ["aac", "mp3"]
                compatible_profile = True
                if video_profile:
                    problematic = ["high444", "high422", "high10"]
                    compatible_profile = not any(prob in video_profile.lower() for prob in problematic)
                can_copy = compatible_video and compatible_audio and compatible_profile
                print(
                    f"Codecs detectados: Vídeo={video_codec} ({video_profile}), Áudio={audio_codec};"
                    f" Pixel Format={pixel_format}, Bit Depth={bit_depth}; Copy={can_copy}"
                )
            except Exception as exc:
                print(f"AVISO: Erro ao analisar codecs: {exc}")
                can_copy = False
        ffmpeg_cmd = None
        if can_copy:
            update_status(args.api_url, args.job_id, "Segmentando vídeo (modo rápido)")
            ffmpeg_cmd = (
                f'ffmpeg -i "{video_file}" -y -c copy -f hls -hls_time 4 '
                f'-hls_playlist_type vod -hls_flags independent_segments '
                f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
            )
            if not run_command(ffmpeg_cmd):
                # tentar fallback com copy conservador
                update_status(args.api_url, args.job_id, "Tentando segmentação conservadora")
                ffmpeg_cmd = (
                    f'ffmpeg -i "{video_file}" -y -c copy -f hls -hls_time 4 '
                    f'-hls_playlist_type vod -hls_flags single_file '
                    f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
                )
                if not run_command(ffmpeg_cmd):
                    print("Segmentação rápida falhou, recodificando áudio apenas...")
                    update_status(args.api_url, args.job_id, "Recodificando apenas áudio")
                    ffmpeg_cmd = (
                        f'ffmpeg -i "{video_file}" -y -c:v copy -c:a aac -ar 48000 -b:a 128k '
                        f'-f hls -hls_time 4 -hls_playlist_type vod -hls_flags independent_segments '
                        f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
                    )
                    if not run_command(ffmpeg_cmd):
                        can_copy = False
        if not can_copy:
            update_status(args.api_url, args.job_id, "Recodificando vídeo (necessário)")
            # Escolher profile e pixel format
            if bit_depth >= 10:
                h264_profile = "main"
                pixel_format_cmd = "-pix_fmt yuv420p"
                print(
                    f"Fallback: Detectado vídeo {bit_depth}-bit, convertendo para 8-bit (yuv420p) para compatibilidade web"
                )
            else:
                h264_profile = "main"
                pixel_format_cmd = ""
                print(f"Fallback: Detectado vídeo {bit_depth}-bit, usando profile H.264 Main")
            ffmpeg_cmd = (
                f'ffmpeg -i "{video_file}" -y '
                f'-c:a aac -ar 48000 -b:a 128k '
                f'-c:v h264 -profile:v {h264_profile} {pixel_format_cmd} -crf 23 -preset veryfast '
                f'-f hls -hls_time 4 -hls_playlist_type vod -hls_flags independent_segments '
                f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
            )
            if not run_command(ffmpeg_cmd):
                raise Exception("Falha na conversão do vídeo para HLS.")

        # -------------------------------------------------------------------
        # Passo 7 – Download e processamento de legendas
        update_status(args.api_url, args.job_id, "Baixando legendas", 80)
        subtitle_info: List[Dict[str, str]] = []
        print("\n=== INICIANDO DOWNLOAD DE LEGENDAS ===")
        def subtitle_progress_callback(message: str, progress: float = None) -> None:
            adjusted = 80 + (progress * 0.1) if progress is not None else None
            update_status(args.api_url, args.job_id, message, adjusted)
            print(f"Legendas: {message}")
        try:
            # Usar o HLS final como arquivo de referência para as legendas
            movie_info['video_file'] = hls_playlist
            subtitle_info = download_and_process_subtitles(movie_library_path, movie_info, subtitle_progress_callback)
            print(f"Resultado do processamento de legendas: {len(subtitle_info)} encontradas")
        except Exception as sub_exc:
            print(f"ERRO no processamento de legendas: {sub_exc}")
            subtitle_info = []
        # Fallback via Podnapisi se não houver PT/pt‑BR
        has_pt = any(normalize_lang(sub.get('language')) in ('pt-BR', 'pt') for sub in subtitle_info)
        if not has_pt:
            try:
                fallback_subs = force_pt_with_podnapisi(movie_info, hls_playlist, movie_library_path, subtitle_progress_callback)
                if fallback_subs:
                    subtitle_info.extend(fallback_subs)
            except Exception as exc:
                print(f"Erro tentando buscar PT via Podnapisi: {exc}")
        print(f"=== DOWNLOAD DE LEGENDAS CONCLUÍDO ===\n")

        # -------------------------------------------------------------------
        # Passo 8 – Verificação de integridade das legendas
        update_status(args.api_url, args.job_id, "Verificando legendas", 95)
        verified_subtitles: List[Dict[str, str]] = []
        for sub in subtitle_info:
            lang = normalize_lang(sub.get('language'))
            file_name = sub.get('file')
            if not file_name:
                continue
            subtitle_path = os.path.join(movie_library_path, 'subtitles', file_name)
            if os.path.exists(subtitle_path):
                # Ajusta o idioma normalizado e nome amigável
                verified_subtitles.append({
                    'language': lang,
                    'name': sub.get('name') or lang,
                    'file': file_name,
                    'url': f"/api/subtitles/{movie_id}/{file_name}",
                })
                print(f"✓ Legenda verificada: {sub.get('name', 'N/A')} ({file_name})")
            else:
                print(f"✗ AVISO: Arquivo de legenda não encontrado: {subtitle_path}")
        print(f"Legendas finais verificadas: {len(verified_subtitles)}")

        # -------------------------------------------------------------------
        # Passo 9 – Montar metadados e salvar no disco
        metadata_path = os.path.join(movie_library_path, "metadata.json")
        existing_metadata = {}
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    existing_metadata = json.load(f)
            except Exception:
                existing_metadata = {}
        # Merge de legendas antigas com as novas
        existing_subs = existing_metadata.get('subtitles', []) if existing_metadata else []
        merged_subs = merge_subtitles(existing_subs, verified_subtitles)
        # Construir metadados finais
        metadata = {
            'id': movie_id,
            'title': title,
            'original_title': original_title,
            'overview': overview,
            'release_date': release_date,
            'poster_path': movie_info.get('poster_path', '/poster.png'),
            'posters': movie_info.get('posters', {}),
            'hls_playlist': '/hls/playlist.m3u8',
            'subtitles': merged_subs,
        }
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
        print(f"Metadados salvos em: {metadata_path}")
        print(f"Filme processado com sucesso: {len(merged_subs)} legendas disponíveis")
        processing_successful = True
        update_status(args.api_url, args.job_id, "Pronto")

    except Exception as exc:
        print(f"ERRO no Job {args.job_id}: {exc}")
        update_status(args.api_url, args.job_id, "Falhou", message=str(exc))
        processing_successful = False
    finally:
        # Limpeza condicional de arquivos temporários
        if processing_successful:
            print(f"Processamento concluído com sucesso. Limpando diretório temporário: {job_temp_dir}")
            shutil.rmtree(job_temp_dir, ignore_errors=True)
        else:
            print(
                f"Processamento falhou ou foi interrompido. Mantendo arquivos temporários para debug: {job_temp_dir}"
            )
            print("IMPORTANTE: Limpe manualmente os arquivos temporários após investigar o problema.")


if __name__ == "__main__":
    main()