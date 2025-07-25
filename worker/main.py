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
from subtitle_manager import download_and_process_subtitles
from poster_manager import download_and_process_posters

# --- CONFIGURAÇÃO INICIAL ---
if not config.TMDB_API_KEY:
    print("ERRO: Chave da API TMDB não encontrada. Crie um arquivo .env em /worker e defina TMDB_API_KEY.")
    sys.exit(1)

tmdb = TMDb()
tmdb.api_key = config.TMDB_API_KEY
tmdb.language = 'en-US'

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
    # Remove extensões e termos comuns de torrents para busca mais precisa
    name = os.path.splitext(filename)[0]
    
    # Padrões para remover (em ordem de prioridade)
    patterns = [
        # Grupos de release e sites (incluindo variações entre colchetes)
        r'\[.*?(yts|rarbg|1337x|kickass|torrentgalaxy|eztv|limetorrents).*?\]',
        r'-\[?(yts|rarbg|1337x|kickass|torrentgalaxy|eztv|limetorrents)\]?',
        r'\b(yts|ytsmx|yts\.mx|rarbg|1337x|kickass|torrentgalaxy|eztv|limetorrents)\b',
        
        # Qualidade e formatos de vídeo entre colchetes ou não
        r'\[.*?(1080p|720p|2160p|4k|480p|brrip|bluray|blu-ray|dvdrip|webrip|web-dl|hdrip|hdtv).*?\]',
        r'\b(1080p|720p|2160p|4k|480p|brrip|bluray|blu-ray|dvdrip|webrip|web-dl|hdrip|hdtv|hdcam|cam|ts|r5)\b',
        
        # Codecs e áudio entre colchetes ou não - MELHORADO para pegar "10bit", "AAC5", etc.
        r'\[.*?(x264|x265|h264|h265|aac|ac3|dts|5\.1|2\.0|10bit).*?\]',
        r'\b(x264|x265|h264|h265|hevc|avc|aac|ac3|dts|dd5\.1|dd2\.0|ddp5\.1|atmos|truehd|flac|mp3|10bit|aac5\.1)\b',
        
        # Outros termos técnicos e formatos
        r'\b(extended|unrated|directors\.cut|remastered|remux|proper|real|repack|internal|limited|mp4|mkv|avi|mov)\b',
        
        # Grupos de release após hífens
        r'-[A-Z0-9]+$',  # Remove grupos como -SPARKS, -DVSUX no final
        
        # Remove caracteres especiais e substitui por espaços
        r'[\.\[\]\(\)_-]',
        
        # Remove múltiplos espaços
        r'\s+'
    ]
    
    for pattern in patterns:
        name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
    
    # Limpa espaços extras
    cleaned = name.strip()
    
    # MELHORIA: Tentar extrair título mais inteligentemente
    # Para casos como "Clown.In.A.Cornfield.2025.1080p.WEBRip.x265.10bit.AAC5.1-[YTS.MX]"
    
    # 1. Primeiro, tentar encontrar o ano
    year_match = re.search(r'\b(19|20)\d{2}\b', cleaned)
    if year_match:
        year = year_match.group()
        # Pegar tudo antes do ano como título
        before_year = cleaned[:year_match.start()].strip()
        
        # Limpar melhor o título
        title_words = []
        for word in before_year.split():
            # Ignorar palavras muito técnicas que sobrou
            if not re.match(r'^(x26[45]|h26[45]|aac\d?|ac3|dts|bit|p|fps|mb|gb|kb)$', word, re.IGNORECASE):
                title_words.append(word)
        
        if title_words:
            # Reconstruir com título limpo + ano
            clean_title = ' '.join(title_words)
            cleaned = f"{clean_title} {year}"
    
    # 2. Se não encontrou ano, tentar limpar melhor sem ano
    if not year_match:
        words = cleaned.split()
        meaningful_words = []
        for word in words:
            # Manter palavras significativas (3+ caracteres)
            if len(word) >= 3:
                # Excluir códigos técnicos específicos MAIS RÍGIDO
                if not re.match(r'^(ddp|dts|aac\d?|ac3|h26[45]|x26[45]|bit|fps|mb|gb|kb|\d+p|\d+bit)$', word, re.IGNORECASE):
                    meaningful_words.append(word)
        
        cleaned = ' '.join(meaningful_words)
    
    # 3. Último fallback: pegar apenas as primeiras palavras sensatas
    words = cleaned.split()
    if len(words) > 6:  # Se ainda tem muitas palavras, pegar apenas as primeiras
        # Tentar manter até encontrar um ano ou parar em 5 palavras
        final_words = []
        for word in words[:8]:  # Máximo 8 palavras
            if re.match(r'^(19|20)\d{2}$', word):  # Se encontrar ano
                final_words.append(word)
                break
            final_words.append(word)
            if len(final_words) >= 5 and not re.match(r'^(19|20)\d{2}$', words[len(final_words)] if len(final_words) < len(words) else ""):
                break
        cleaned = ' '.join(final_words)
    
    return cleaned.strip()

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
    
    # Variável para controlar sucesso do processamento
    processing_successful = False

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
            
            # Tentar múltiplas variações de busca para melhor resultado
            search_variations = [search_term]
            
            # Se o termo tem mais de 3 palavras, tentar versão mais curta
            words = search_term.split()
            if len(words) > 3:
                # Tentar apenas as primeiras 3-4 palavras
                short_version = ' '.join(words[:3])
                search_variations.append(short_version)
                
                # Se tem ano, tentar sem o ano primeiro
                if re.search(r'\b(19|20)\d{2}\b', search_term):
                    no_year = re.sub(r'\b(19|20)\d{2}\b', '', search_term).strip()
                    if no_year and len(no_year.split()) >= 2:
                        search_variations.insert(0, no_year)  # Tentar sem ano primeiro
            
            # Tentar também versão ainda mais limpa removendo números restantes
            clean_version = re.sub(r'\b\d+\b', '', search_term).strip()
            if clean_version and clean_version != search_term:
                search_variations.append(clean_version)
            
            print(f"Tentando variações de busca: {search_variations}")
            
            search_results = None
            successful_term = None
            
            # Tentar cada variação até encontrar resultados
            for variation in search_variations:
                print(f"Tentando busca com: '{variation}'")
                search_results = movie.search(variation)
                
                if search_results.total_results > 0:
                    successful_term = variation
                    print(f"✓ Encontrado resultados com: '{variation}' ({search_results.total_results} resultados)")
                    break
                else:
                    print(f"✗ Nenhum resultado para: '{variation}'")
            
            if not search_results or search_results.total_results == 0:
                raise Exception(f"Filme não encontrado no TMDB para nenhuma variação de '{search_term}'.")
            
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
                
                # Acesso seguro aos atributos dos detalhes - PADRONIZADO PARA INGLÊS
                final_title = getattr(movie_details, 'original_title', successful_term)
                overview = getattr(movie_details, 'overview', 'Description not available')
                release_date = getattr(movie_details, 'release_date', '')
                poster_path = getattr(movie_details, 'poster_path', None)
                year = int(release_date[:4]) if release_date else None
                
                print(f"Metadados extraídos - Título Final: {final_title}, Data: {release_date}, Ano: {year}")
                
            else:
                raise Exception(f"Filme não encontrado no TMDB para '{search_term}'.")
            
        except Exception as tmdb_error:
            print(f"Erro ao buscar metadados: {tmdb_error}")
            # Fallback com dados mínimos baseados no nome do arquivo
            final_title = search_term
            overview = 'Descrição não disponível'
            release_date = ''
            year = None
            poster_path = None
            movie_id = abs(hash(final_title)) % 1000000  # ID único baseado no hash do nome
            print(f"Usando fallback - ID: {movie_id}, Título: {final_title}")
        
        movie_library_path = os.path.join(config.LIBRARY_ROOT, str(movie_id))
        if os.path.exists(movie_library_path):
            raise Exception(f"Filme '{final_title}' já existe na biblioteca.")
        
        hls_dir = os.path.join(movie_library_path, "hls")
        os.makedirs(hls_dir)
        
        # Criar movie_info inicial para o sistema de posters
        movie_info = {
            'id': movie_id,
            'title': final_title,
            'original_title': final_title,
            'release_date': release_date,
            'year': year,
            'poster_path': poster_path,
            'video_file': video_file
        }
        
        # --- Download e Processamento de Posters (Sistema Avançado) ---
        update_status(args.api_url, args.job_id, "Processando posters", 55)
        
        def poster_progress_callback(message, progress=None):
            # Ajusta o progresso para a faixa 55-60
            adjusted_progress = 55 + (progress * 0.05) if progress else None
            update_status(args.api_url, args.job_id, message, adjusted_progress)
        
        poster_info = download_and_process_posters(
            movie_library_path, 
            movie_info, 
            poster_progress_callback
        )
        
        print(f"Posters processados: {len(poster_info)} tamanhos disponíveis")
        if poster_info:
            for size, path in poster_info.items():
                print(f"  - {size}: {path}")
        
        # Atualizar movie_info com informações de posters
        movie_info['posters'] = poster_info
        movie_info['poster_path'] = poster_info.get('large') or poster_info.get('medium') or "/poster.png"
            
        # 5. Download e Processamento de Legendas (ANTES da conversão HLS)
        update_status(args.api_url, args.job_id, "Baixando legendas", 60)
        subtitle_info = []
        print(f"\n=== INICIANDO DOWNLOAD DE LEGENDAS ===")
        
        try:
            def subtitle_progress_callback(message, progress=None):
                # Ajusta o progresso para a faixa 60-70
                adjusted_progress = 60 + (progress * 0.1) if progress else None
                update_status(args.api_url, args.job_id, message, adjusted_progress)
                print(f"Legendas: {message}")
            
            # Atualizar movie_info com informações do vídeo para o sistema de legendas
            movie_info['video_file'] = video_file  # Passa o arquivo de vídeo original (ainda na pasta temp)
            
            print(f"Informações do filme para legendas:")
            print(f"  - ID: {movie_info['id']}")
            print(f"  - Título: {movie_info['title']}")
            print(f"  - Arquivo de vídeo: {movie_info['video_file']}")
            print(f"  - Pasta de destino: {movie_library_path}")
            
            # Baixar e processar legendas usando o arquivo original ANTES da conversão HLS
            subtitle_info = download_and_process_subtitles(
                movie_library_path, 
                movie_info, 
                subtitle_progress_callback
            )
            
            print(f"Resultado do processamento de legendas: {len(subtitle_info)} encontradas")
            if subtitle_info:
                for sub in subtitle_info:
                    print(f"  - {sub.get('name', 'N/A')} ({sub.get('file', 'N/A')})")
            
        except Exception as subtitle_error:
            print(f"ERRO no processamento de legendas: {subtitle_error}")
            import traceback
            traceback.print_exc()
            subtitle_info = []  # Continua sem legendas se houver erro
        
        print(f"=== DOWNLOAD DE LEGENDAS CONCLUÍDO ===\n")
            
        # 6. Conversão inteligente para HLS (copy quando possível, recodifica só quando necessário)
        update_status(args.api_url, args.job_id, "Analisando formato do vídeo", 70)
        hls_playlist = os.path.join(hls_dir, "playlist.m3u8")
        segment_path = os.path.join(hls_dir, "segment%03d.ts")
        
        # Primeiro, analisar os codecs do arquivo de vídeo
        probe_cmd = f'ffprobe -v quiet -print_format json -show_streams "{video_file}"'
        probe_process = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
        
        can_copy = False
        bit_depth = 8  # Padrão
        pixel_format = None
        
        if probe_process.returncode == 0:
            try:
                import json
                probe_data = json.loads(probe_process.stdout)
                
                video_codec = None
                audio_codec = None
                video_profile = None
                
                for stream in probe_data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        video_codec = stream.get('codec_name', '').lower()
                        video_profile = stream.get('profile', '').lower()
                        pixel_format = stream.get('pix_fmt', '')
                        
                        # Detecção mais precisa de bit depth
                        if any(fmt in pixel_format for fmt in ['p10', '10bit', '10le', '10be', 'yuv420p10']):
                            bit_depth = 10
                        elif any(fmt in pixel_format for fmt in ['p12', '12bit', '12le', '12be', 'yuv420p12']):
                            bit_depth = 12
                        elif any(fmt in pixel_format for fmt in ['16le', '16be', '16bit']):
                            bit_depth = 16
                        else:
                            # Para formatos 8-bit ou desconhecidos, assumir 8-bit
                            bit_depth = 8
                            
                        print(f"Detecção de bit depth: {pixel_format} → {bit_depth} bits")
                            
                    elif stream.get('codec_type') == 'audio':
                        audio_codec = stream.get('codec_name', '').lower()
                
                # Verificar se os codecs são compatíveis para copy
                compatible_video = video_codec in ['h264', 'avc'] and bit_depth == 8
                compatible_audio = audio_codec in ['aac', 'mp3']
                
                # H.264 profiles compatíveis com HLS (mais rigoroso)
                compatible_profile = True
                if video_profile:
                    # Profiles problemáticos que podem causar falha no copy
                    problematic_profiles = ['high444', 'high422', 'high10']
                    compatible_profile = not any(prob in video_profile.lower() for prob in problematic_profiles)
                    if not compatible_profile:
                        print(f"AVISO: Profile H.264 {video_profile} pode ser incompatível com copy")
                
                can_copy = compatible_video and compatible_audio and compatible_profile
                
                print(f"Codecs detectados: Vídeo={video_codec} ({video_profile}), Áudio={audio_codec}")
                print(f"Pixel Format: {pixel_format}, Bit Depth: {bit_depth}")
                print(f"Compatível para segmentação rápida: {can_copy}")
                
            except Exception as probe_error:
                print(f"AVISO: Erro ao analisar codecs: {probe_error}")
                can_copy = False
        
        if can_copy:
            # Segmentação rápida sem recodificação (copy)
            update_status(args.api_url, args.job_id, "Segmentando vídeo (modo rápido)")
            print("Usando modo de segmentação rápida (copy) - isso será muito mais rápido!")
            ffmpeg_cmd = (
                f'ffmpeg -i "{video_file}" -y '
                f'-c copy '  # Copy streams sem recodificar
                f'-f hls '  # Especificar formato HLS explicitamente
                f'-hls_time 4 -hls_playlist_type vod '
                f'-hls_flags independent_segments '  # Segmentos independentes para melhor compatibilidade
                f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
            )
            
            # Tentar copy primeiro
            if not run_command(ffmpeg_cmd):
                print("AVISO: Segmentação rápida falhou, tentando estratégias intermediárias...")
                
                # Estratégia 1: Copy com flags mais conservadoras
                update_status(args.api_url, args.job_id, "Tentando segmentação conservadora")
                conservative_cmd = (
                    f'ffmpeg -i "{video_file}" -y '
                    f'-c copy '
                    f'-f hls -hls_time 4 -hls_playlist_type vod '
                    f'-hls_flags single_file '  # Flags mais simples
                    f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
                )
                
                if run_command(conservative_cmd):
                    print("✓ Segmentação conservadora funcionou!")
                else:
                    print("Segmentação conservadora falhou, tentando copy apenas do vídeo...")
                    
                    # Estratégia 2: Copy vídeo + recodificar apenas áudio
                    update_status(args.api_url, args.job_id, "Recodificando apenas áudio")
                    audio_only_cmd = (
                        f'ffmpeg -i "{video_file}" -y '
                        f'-c:v copy -c:a aac -ar 48000 -b:a 128k '
                        f'-f hls -hls_time 4 -hls_playlist_type vod '
                        f'-hls_flags independent_segments '
                        f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
                    )
                    
                    if run_command(audio_only_cmd):
                        print("✓ Copy vídeo + recodificação áudio funcionou!")
                    else:
                        print("Todas as estratégias rápidas falharam, partindo para recodificação completa...")
                        # Fallback para recodificação se copy falhar
                        update_status(args.api_url, args.job_id, "Recodificando vídeo (fallback)")
                        
                        # Escolher perfil H.264 baseado no bit depth do vídeo original
                        if bit_depth >= 10:
                            # Para vídeos de 10+ bits, converter para 8 bits para compatibilidade web
                            h264_profile = "main"
                            pixel_format_cmd = "-pix_fmt yuv420p"  # Forçar 8 bits
                            print(f"Fallback: Detectado vídeo {bit_depth}-bit, convertendo para 8-bit (yuv420p) para compatibilidade web")
                        else:
                            # Para vídeos de 8 bits, usar Main profile
                            h264_profile = "main"
                            pixel_format_cmd = ""  # Manter formato original
                            print(f"Fallback: Detectado vídeo {bit_depth}-bit, usando profile H.264 Main")
                        
                        ffmpeg_cmd = (
                            f'ffmpeg -i "{video_file}" -y '
                            f'-c:a aac -ar 48000 -b:a 128k '
                            f'-c:v h264 -profile:v {h264_profile} {pixel_format_cmd} -crf 23 -preset veryfast '
                            f'-f hls '  # Especificar formato HLS explicitamente
                            f'-hls_time 4 -hls_playlist_type vod '
                            f'-hls_flags independent_segments '  # Segmentos independentes
                            f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
                        )
                        if not run_command(ffmpeg_cmd): 
                            raise Exception("Falha na conversão do vídeo para HLS.")
        else:
            # Recodificação completa para garantir compatibilidade
            update_status(args.api_url, args.job_id, "Recodificando vídeo (necessário)")
            print("Usando modo de recodificação completa")
            
            # Escolher perfil H.264 baseado no bit depth do vídeo original
            if bit_depth >= 10:
                # Para vídeos de 10+ bits, converter para 8 bits para compatibilidade web
                h264_profile = "main"
                pixel_format_cmd = "-pix_fmt yuv420p"  # Forçar 8 bits
                print(f"Detectado vídeo {bit_depth}-bit, convertendo para 8-bit (yuv420p) para compatibilidade web")
            else:
                # Para vídeos de 8 bits, usar Main profile
                h264_profile = "main"
                pixel_format_cmd = ""  # Manter formato original
                print(f"Detectado vídeo {bit_depth}-bit, usando profile H.264 Main")
            
            ffmpeg_cmd = (
                f'ffmpeg -i "{video_file}" -y '
                f'-c:a aac -ar 48000 -b:a 128k '
                f'-c:v h264 -profile:v {h264_profile} {pixel_format_cmd} -crf 23 -preset veryfast '
                f'-force_key_frames "expr:gte(t,n_forced*4)" '  # Forçar keyframes a cada 4 segundos
                f'-f hls '  # Especificar formato HLS explicitamente
                f'-hls_time 4 -hls_playlist_type vod '
                f'-hls_flags independent_segments '  # Segmentos independentes
                f'-hls_segment_filename "{segment_path}" "{hls_playlist}"'
            )
            if not run_command(ffmpeg_cmd): 
                raise Exception("Falha na conversão do vídeo para HLS.")
        
        # 7. Verificação de Integridade das Legendas
        update_status(args.api_url, args.job_id, "Verificando legendas", 95)
        verified_subtitles = []
        
        if subtitle_info:
            print(f"Verificando integridade de {len(subtitle_info)} legendas...")
            for subtitle in subtitle_info:
                subtitle_path = os.path.join(movie_library_path, 'subtitles', subtitle['file'])
                if os.path.exists(subtitle_path):
                    verified_subtitles.append(subtitle)
                    print(f"✓ Legenda verificada: {subtitle['name']} ({subtitle['file']})")
                else:
                    print(f"✗ AVISO: Arquivo de legenda não encontrado: {subtitle_path}")
        
        print(f"Legendas finais verificadas: {len(verified_subtitles)}")
        
        # 8. Salvar Metadados Finais
        metadata = {
            "id": movie_id,
            "title": final_title,
            "original_title": final_title,
            "overview": overview,
            "release_date": release_date,
            "year": year,
            "poster_path": movie_info.get('poster_path', "/poster.png"),
            "posters": movie_info.get('posters', {}),
            "hls_playlist": "/hls/playlist.m3u8",
            "subtitles": verified_subtitles
        }
        
        metadata_path = os.path.join(movie_library_path, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(metadata, f, ensure_ascii=False, indent=4)
        
        print(f"Metadados salvos em: {metadata_path}")
        print(f"Filme processado com sucesso: {len(verified_subtitles)} legendas disponíveis")
        
        # Marcar processamento como bem-sucedido
        processing_successful = True
        update_status(args.api_url, args.job_id, "Pronto")

    except Exception as e:
        print(f"ERRO no Job {args.job_id}: {e}")
        processing_successful = False
        update_status(args.api_url, args.job_id, "Falhou", message=str(e))
    finally:
        # Limpeza condicional - só remove se processamento foi bem-sucedido
        if 'processing_successful' in locals() and processing_successful:
            print(f"Processamento concluído com sucesso. Limpando diretório temporário: {job_temp_dir}")
            shutil.rmtree(job_temp_dir, ignore_errors=True)
        else:
            print(f"Processamento falhou ou foi interrompido. Mantendo arquivos temporários para debug: {job_temp_dir}")
            print("IMPORTANTE: Limpe manualmente os arquivos temporários após investigar o problema.")

if __name__ == "__main__":
    main()