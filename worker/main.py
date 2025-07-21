import os
import sys
import shutil
import subprocess
import argparse
import requests
import magic
import patoolib
import re
from tmdbv3api import TMDb, Movie, Search
import config

# --- CONFIGURAÇÃO INICIAL ---
if not config.TMDB_API_KEY:
    print("ERRO: Chave da API TMDB não encontrada. Crie um arquivo .env em /worker e adicione TMDB_API_KEY.")
    sys.exit(1)

tmdb = TMDb()
tmdb.api_key = config.TMDB_API_KEY
tmdb.language = 'pt-BR'

# --- FUNÇÕES HELPER ---
def update_status(api_url, job_id, status, progress=None, message=None):
    payload = {"status": status, "progress": progress, "message": message}
    try:
        requests.post(f"{api_url}/{job_id}/status", json=payload, timeout=5)
    except requests.RequestException as e:
        print(f"AVISO: Não foi possível atualizar o status: {e}")

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, text=True, encoding='utf-8')
    for line in iter(process.stdout.readline, ''):
        print(line.strip())
    process.wait()
    return process.returncode == 0

def clean_filename_for_search(filename):
    # Remove extensões e termos comuns de torrents
    name = os.path.splitext(filename)[0]
    patterns = [
        r'\b(1080p|720p|2160p|4k|brrip|bluray|dvdrip|webrip|web-dl|hdrip|x264|x265|h264|aac|dts)\b',
        r'[\.\[\]\(\)-]', # Substitui ., [], (), - por espaços
        r'\s+' # Substitui múltiplos espaços por um só
    ]
    for p in patterns:
        name = re.sub(p, ' ', name, flags=re.IGNORECASE)
    return name.strip()

# --- PIPELINE ---
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--magnet', required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--api-url', required=True)
    args = parser.parse_args()

    job_temp_dir = os.path.join(config.TEMP_ROOT, args.job_id)
    download_dir = os.path.join(job_temp_dir, "download")
    unpacked_dir = os.path.join(job_temp_dir, "unpacked")
    os.makedirs(unpacked_dir, exist_ok=True)
    os.makedirs(config.LIBRARY_ROOT, exist_ok=True)

    try:
        # 1. Download
        update_status(args.api_url, args.job_id, "Baixando")
        if not run_command(f'webtorrent download "{args.magnet}" --out "{download_dir}"'):
            raise Exception("Falha no download do torrent.")

        # 2. Descompressão
        update_status(args.api_url, args.job_id, "Descompactando")
        archive_found = False
        for f in os.listdir(download_dir):
            filepath = os.path.join(download_dir, f)
            if patoolib.is_archive(filepath):
                patoolib.extract_archive(filepath, outdir=unpacked_dir)
                archive_found = True
        if not archive_found:
            # Se não houver arquivo, o conteúdo já está na pasta de download
            shutil.copytree(download_dir, unpacked_dir, dirs_exist_ok=True)

        # 3. Identificação
        update_status(args.api_url, args.job_id, "Analisando arquivos")
        video_file = None
        max_size = 0
        for root, _, files in os.walk(unpacked_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    if 'video' in magic.from_file(filepath, mime=True):
                        size = os.path.getsize(filepath)
                        if size > max_size:
                            max_size = size
                            video_file = filepath
                except Exception: continue
        if not video_file: raise Exception("Nenhum arquivo de vídeo válido encontrado.")

        # 4. Metadados
        update_status(args.api_url, args.job_id, "Buscando metadados")
        search_term = clean_filename_for_search(os.path.basename(video_file))
        results = Search().movie(search_term)
        if not results: raise Exception(f"Filme não encontrado no TMDB para '{search_term}'.")
        
        movie_id = results[0].id
        movie_details = Movie().details(movie_id)
        
        movie_library_path = os.path.join(config.LIBRARY_ROOT, str(movie_id))
        if os.path.exists(movie_library_path): raise Exception(f"Filme '{movie_details.title}' já existe na biblioteca.")
        
        hls_dir = os.path.join(movie_library_path, "hls")
        os.makedirs(hls_dir)
        
        # Download do Poster
        poster_url = f"https://image.tmdb.org/t/p/w500{movie_details.poster_path}"
        poster_res = requests.get(poster_url)
        with open(os.path.join(movie_library_path, "poster.png"), 'wb') as f:
            f.write(poster_res.content)
            
        # 5. Transcodificação
        update_status(args.api_url, args.job_id, "Convertendo para HLS")
        hls_playlist = os.path.join(hls_dir, "playlist.m3u8")
        segment_path = os.path.join(hls_dir, "segment%03d.ts")
        ffmpeg_cmd = (
            f'ffmpeg -i "{video_file}" -y '
            f'-c:a aac -ar 48000 -b:a 128k '
            f'-c:v h264 -profile:v main -crf 23 -preset veryfast '
            f'-hls_time 4 -hls_playlist_type vod '
            f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
        )
        if not run_command(ffmpeg_cmd): raise Exception("Falha na transcodificação do vídeo.")
        
        # 6. Salvar Metadados Finais
        metadata = {
            "id": movie_id,
            "title": movie_details.title,
            "overview": movie_details.overview,
            "release_date": movie_details.release_date,
            "poster_path": "/poster.png",
            "hls_playlist": "/hls/playlist.m3u8"
        }
        with open(os.path.join(movie_library_path, "metadata.json"), 'w', encoding='utf-8') as f:
            import json
            json.dump(metadata, f, ensure_ascii=False, indent=4)

        update_status(args.api_url, args.job_id, "Pronto")

    except Exception as e:
        print(f"ERRO no Job {args.job_id}: {e}")
        update_status(args.api_url, args.job_id, "Falhou", message=str(e))
    finally:
        print(f"Limpando diretório temporário: {job_temp_dir}")
        shutil.rmtree(job_temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()