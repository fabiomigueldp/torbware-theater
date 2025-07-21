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
    # Garantir que status é uma string
    if not isinstance(status, str):
        status = str(status)
    
    # Garantir que progress é None ou número
    if progress is not None and not isinstance(progress, (int, float)):
        try:
            progress = float(progress)
        except (ValueError, TypeError):
            progress = None
    
    # Garantir que message é None ou string
    if message is not None and not isinstance(message, str):
        message = str(message)
    
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
        for item in os.listdir(download_dir):
            item_path = os.path.join(download_dir, item)
            try:
                if patoolib.is_archive(item_path):
                    print(f"Descompactando {item}...")
                    patoolib.extract_archive(item_path, outdir=unpacked_dir)
                    archive_found = True
            except Exception as e:
                print(f"AVISO: Não foi possível extrair {item}. Erro: {e}")

        if not archive_found:
            print("Nenhum arquivo compactado encontrado, copiando todos os arquivos.")
            for item in os.listdir(download_dir):
                src_path = os.path.join(download_dir, item)
                dest_path = os.path.join(unpacked_dir, item)
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dest_path)

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
        print(f"Buscando metadados para: '{search_term}'")
        
        try:
            # Busca por filmes usando a API do TMDB - sintaxe corrigida
            movie = Movie()
            search_results = movie.search(search_term)
            
            print(f"Resultado da busca: Total de resultados: {search_results.total_results}")
            
            # Acesso correto aos resultados da busca
            if search_results.total_results > 0 and hasattr(search_results, 'results'):
                results_list = search_results.results
                print(f"Acessando lista de resultados, tipo: {type(results_list)}")
                
                # O objeto AsObj funciona como uma lista, então podemos iterar
                first_result = None
                try:
                    # Tentar acessar primeiro item
                    if hasattr(results_list, '__getitem__'):
                        first_result = results_list[0]
                    elif hasattr(results_list, '__iter__'):
                        for item in results_list:
                            first_result = item
                            break
                    
                    if not first_result:
                        raise Exception("Não foi possível acessar primeiro resultado")
                        
                except Exception as access_error:
                    print(f"Erro ao acessar primeiro resultado: {access_error}")
                    raise Exception("Formato de resultados não suportado")
                
                print(f"Primeiro resultado obtido: {type(first_result)}")
                
                # Extrair ID do primeiro resultado
                movie_id = None
                if hasattr(first_result, 'id'):
                    movie_id = first_result.id
                elif isinstance(first_result, dict) and 'id' in first_result:
                    movie_id = first_result['id']
                else:
                    print(f"Estrutura do primeiro resultado: {first_result}")
                    raise Exception("Não foi possível extrair ID do resultado")
                    
                print(f"Filme encontrado - ID: {movie_id}")
                
                # Busca detalhes do filme
                movie_details = movie.details(movie_id)
                print(f"Detalhes obtidos: {type(movie_details)}")
                
                # Acesso seguro aos atributos dos detalhes
                title = getattr(movie_details, 'title', search_term)
                overview = getattr(movie_details, 'overview', 'Descrição não disponível')
                release_date = getattr(movie_details, 'release_date', '')
                poster_path = getattr(movie_details, 'poster_path', None)
                
                print(f"Metadados extraídos - Título: {title}, Data: {release_date}")
                
            else:
                raise Exception(f"Filme não encontrado no TMDB para '{search_term}'.")
            
        except Exception as tmdb_error:
            print(f"Erro ao buscar metadados: {tmdb_error}")
            # Fallback com dados mínimos baseados no nome do arquivo
            title = search_term
            overview = 'Descrição não disponível'
            release_date = ''
            poster_path = None
            movie_id = abs(hash(search_term)) % 1000000  # ID único baseado no hash do nome
            print(f"Usando fallback - ID: {movie_id}, Título: {title}")
        
        movie_library_path = os.path.join(config.LIBRARY_ROOT, str(movie_id))
        if os.path.exists(movie_library_path):
            raise Exception(f"Filme '{title}' já existe na biblioteca.")
        
        hls_dir = os.path.join(movie_library_path, "hls")
        os.makedirs(hls_dir)
        
        # --- Download do Poster (Lógica Melhorada e à Prova de Falhas) ---
        poster_filename = "poster.png" # Nome padrão do arquivo
        
        # Verifica se o filme tem um poster antes de tentar baixar
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            try:
                poster_res = requests.get(poster_url, stream=True)
                poster_res.raise_for_status() # Lança um erro se a requisição falhar
                with open(os.path.join(movie_library_path, poster_filename), 'wb') as f:
                    shutil.copyfileobj(poster_res.raw, f)
                print(f"Poster para '{title}' baixado com sucesso.")
            except requests.exceptions.RequestException as e:
                print(f"AVISO: Falha ao baixar o poster. Um placeholder será usado. Erro: {e}")
                # Aqui você pode copiar um poster padrão, se tiver um.
                # Ex: shutil.copyfile('caminho/do/placeholder.png', os.path.join(movie_library_path, poster_filename))
        else:
            print("AVISO: Nenhum poster encontrado no TMDB. Um placeholder será usado.")
            # Lógica para criar/copiar um poster padrão (placeholder)
            # Por simplicidade, vamos apenas pular a criação do arquivo. O frontend não vai quebrar.
            pass
            
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
            "title": title,
            "overview": overview,
            "release_date": release_date,
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