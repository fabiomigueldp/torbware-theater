import os
import json
import subprocess
import requests
import pysrt
import chardet
from subliminal import Video, download_best_subtitles, save_subtitles
from subliminal.subtitle import get_subtitle_path
from babelfish import Language
import logging
import tempfile
import shutil

# Verifica se ffsubsync está disponível
try:
    import ffsubsync
    FFSUBSYNC_AVAILABLE = True
except ImportError:
    FFSUBSYNC_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class SubtitleManager:
    def __init__(self, movie_folder, movie_info, progress_callback=None):
        self.movie_folder = movie_folder
        self.movie_info = movie_info
        self.progress_callback = progress_callback
        self.subtitles_folder = os.path.join(movie_folder, 'subtitles')
        os.makedirs(self.subtitles_folder, exist_ok=True)
        
        # Cria um diretório temporário específico para este processamento
        self.temp_folder = tempfile.mkdtemp(prefix='subtitles_')
        
    def report_progress(self, message, progress=None):
        """Reporta progresso das legendas"""
        if self.progress_callback:
            self.progress_callback(f"Legendas: {message}", progress)
        logger.info(f"Legendas: {message}")
        print(f"Legendas: {message}")
    
    def cleanup_temp(self):
        """Limpa arquivos temporários"""
        try:
            if os.path.exists(self.temp_folder):
                print(f"Limpando pasta temporária de legendas: {self.temp_folder}")
                # Listar arquivos antes de apagar para debug
                temp_files = os.listdir(self.temp_folder)
                if temp_files:
                    print(f"Arquivos a serem removidos: {temp_files}")
                shutil.rmtree(self.temp_folder, ignore_errors=True)
                print("Limpeza de arquivos temporários de legendas concluída")
            else:
                print("Pasta temporária de legendas não existe ou já foi removida")
        except Exception as e:
            print(f"AVISO: Erro ao limpar temporários de legendas: {e}")
            logger.warning(f"Erro ao limpar temporários de legendas: {e}")
    
    def download_subtitles(self):
        """Baixa legendas em inglês e português com retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self._download_subtitles_attempt()
            except Exception as e:
                self.report_progress(f"Tentativa {attempt + 1} falhou: {str(e)[:50]}")
                if attempt == max_retries - 1:
                    self.report_progress("Todas as tentativas de download falharam")
                    return []
                import time
                time.sleep(2)  # Aguarda antes de tentar novamente
        
        return []
    
    def _download_subtitles_attempt(self):
        """Tentativa única de download de legendas com múltiplos providers"""
        self.report_progress("Iniciando download de legendas", 10)
        
        # Usa o arquivo de vídeo especificado no movie_info (que está na pasta temporária)
        video_file = self.movie_info.get('video_file')
        if not video_file or not os.path.exists(video_file):
            raise Exception("Arquivo de vídeo não encontrado para download de legendas")
        
        self.report_progress(f"Usando arquivo: {os.path.basename(video_file)}", 20)
        
        # Configura o vídeo para o Subliminal
        video = Video.fromname(video_file)
        if self.movie_info.get('title'):
            video.title = self.movie_info['title']
        if self.movie_info.get('release_date'):
            try:
                video.year = int(self.movie_info['release_date'][:4])
            except:
                pass
        
        # Define as linguagens desejadas (usando códigos alpha3)
        languages = {
            Language('eng'),  # Inglês (alpha3)
            Language('por', country='BR'),  # Português brasileiro
            Language('por')   # Português genérico
        }
        
        self.report_progress("Procurando legendas online", 30)
        
        # Lista de providers para tentar (em ordem de prioridade)
        providers_to_try = [
            ['podnapisi'],           # Provider mais confiável
            ['tvsubtitles'],         # Alternative provider
            ['argenteam'],           # Provider para português
            ['subdivx'],             # Outro provider
            ['opensubtitles'],       # OpenSubtitles por último (problemas conhecidos)
        ]
        
        subtitles = {}
        for provider_list in providers_to_try:
            try:
                self.report_progress(f"Tentando provider: {provider_list[0]}", 35)
                subtitles = download_best_subtitles([video], languages, providers=provider_list)
                
                if video in subtitles and subtitles[video]:
                    self.report_progress(f"✓ Legendas encontradas via {provider_list[0]}", 40)
                    break
                else:
                    self.report_progress(f"✗ Nenhuma legenda em {provider_list[0]}", 35)
                    
            except Exception as e:
                error_msg = str(e)
                self.report_progress(f"✗ Erro em {provider_list[0]}: {error_msg[:30]}", 35)
                
                # Se for o erro específico do OpenSubtitles, pular sem falhar
                if "cannot marshal None" in error_msg:
                    self.report_progress("OpenSubtitles requer credenciais - pulando", 35)
                    continue
                
                # Para outros erros, continuar tentando
                continue
        
        # Se nenhum provider funcionou, tentar busca manual/alternativa
        if not (video in subtitles and subtitles[video]):
            self.report_progress("Tentando método alternativo", 45)
            subtitles = self._try_alternative_subtitle_sources(video, languages)
        
        if video in subtitles and subtitles[video]:
            self.report_progress("Processando legendas baixadas", 50)
            
            # Salva temporariamente 
            save_subtitles(video, subtitles[video], single=False)
            
            downloaded_subs = []
            for subtitle in subtitles[video]:
                lang_code = self._get_language_code(subtitle.language)
                
                # Caminho onde o subliminal salvou o arquivo
                temp_subtitle_path = get_subtitle_path(video_file, subtitle.language)
                
                if os.path.exists(temp_subtitle_path):
                    self.report_progress(f"Processando legenda {lang_code}", 60)
                    
                    # Processa e move para pasta final
                    final_subtitle = self._process_subtitle(temp_subtitle_path, lang_code, video_file)
                    if final_subtitle:
                        downloaded_subs.append(final_subtitle)
                        # Verificar se arquivo foi realmente criado
                        final_path = os.path.join(self.subtitles_folder, final_subtitle['file'])
                        if not os.path.exists(final_path):
                            self.report_progress(f"ERRO: Arquivo final não criado: {final_subtitle['file']}")
                        else:
                            self.report_progress(f"✓ Legenda criada: {final_subtitle['file']}")
                
            self.report_progress(f"Concluído: {len(downloaded_subs)} legendas processadas", 90)
            return downloaded_subs
        else:
            self.report_progress("Nenhuma legenda encontrada online", 90)
            return []
    
    def _try_alternative_subtitle_sources(self, video, languages):
        """Tenta fontes alternativas quando providers principais falham"""
        self.report_progress("Buscando em fontes alternativas", 45)
        
        # Implementar busca manual ou API alternativa
        # Por enquanto, retorna dicionário vazio para manter compatibilidade
        # Aqui podem ser adicionadas integrações com:
        # - APIs de legendas diretas
        # - Scraping de sites de legendas
        # - Buscas em repositórios locais
        
        return {}
    
    def _process_subtitle(self, temp_subtitle_path, lang_code, video_file):
        """Processa uma legenda: sincroniza, converte e move para pasta final"""
        try:
            # 1. Sincronização (se disponível e for inglês)
            synced_path = temp_subtitle_path
            if FFSUBSYNC_AVAILABLE and lang_code == 'en':
                synced_path = self._sync_subtitle(temp_subtitle_path, video_file)
                if not synced_path:
                    synced_path = temp_subtitle_path
            
            # 2. Conversão para WebVTT
            webvtt_path = self._convert_to_webvtt(synced_path, lang_code)
            if not webvtt_path:
                return None
            
            # 3. Informações da legenda
            subtitle_info = {
                'language': lang_code,
                'name': self._get_language_name(lang_code),
                'file': os.path.basename(webvtt_path),
                'url': f"/api/subtitles/{self.movie_info['id']}/{os.path.basename(webvtt_path)}"
            }
            
            return subtitle_info
            
        except Exception as e:
            self.report_progress(f"Erro ao processar legenda {lang_code}: {str(e)[:50]}")
            return None
    
    def _sync_subtitle(self, subtitle_path, video_file):
        """Sincroniza legenda usando ffsubsync"""
        try:
            synced_path = os.path.join(self.temp_folder, f"synced_{os.path.basename(subtitle_path)}")
            
            cmd = [
                'ffsubsync',
                video_file,
                '-i', subtitle_path,
                '-o', synced_path,
                '--max-offset-seconds', '60'
            ]
            
            self.report_progress("Sincronizando legenda", 70)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0 and os.path.exists(synced_path):
                self.report_progress("Legenda sincronizada com sucesso", 80)
                return synced_path
            else:
                self.report_progress("Sincronização falhou, usando original")
                return subtitle_path
                
        except subprocess.TimeoutExpired:
            self.report_progress("Timeout na sincronização")
            return subtitle_path
        except FileNotFoundError:
            self.report_progress("ffsubsync não encontrado")
            return subtitle_path
        except Exception as e:
            self.report_progress(f"Erro na sincronização: {str(e)[:50]}")
            return subtitle_path
    
    def _convert_to_webvtt(self, subtitle_path, lang_code):
        """Converte legenda para formato WebVTT e salva na pasta final"""
        try:
            # Garantir que pasta de destino existe
            os.makedirs(self.subtitles_folder, exist_ok=True)
            
            # Detecta encoding do arquivo
            with open(subtitle_path, 'rb') as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
            
            self.report_progress(f"Lendo arquivo SRT ({encoding})", 82)
            
            # Lê o arquivo SRT
            subs = pysrt.open(subtitle_path, encoding=encoding)
            
            # Cria arquivo WebVTT na pasta final
            webvtt_filename = f"subtitle_{lang_code}.vtt"
            webvtt_path = os.path.join(self.subtitles_folder, webvtt_filename)
            
            self.report_progress(f"Convertendo para WebVTT: {webvtt_filename}", 85)
            
            with open(webvtt_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                
                for sub in subs:
                    # Converte timing para formato WebVTT
                    start_time = self._srt_time_to_webvtt(sub.start)
                    end_time = self._srt_time_to_webvtt(sub.end)
                    
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sub.text}\n\n")
            
            # Verificar se arquivo foi criado corretamente
            if os.path.exists(webvtt_path):
                file_size = os.path.getsize(webvtt_path)
                self.report_progress(f"✓ WebVTT criado: {webvtt_filename} ({file_size} bytes)", 88)
                return webvtt_path
            else:
                raise Exception(f"Arquivo WebVTT não foi criado: {webvtt_path}")
            
        except Exception as e:
            self.report_progress(f"Erro na conversão para WebVTT: {str(e)[:50]}")
            logger.error(f"Erro na conversão WebVTT: {e}")
            return None
    
    def _srt_time_to_webvtt(self, srt_time):
        """Converte timestamp SRT para formato WebVTT"""
        return str(srt_time).replace(',', '.')
    
    def _get_language_code(self, language):
        """Converte código de idioma do Babel para nosso padrão"""
        # O objeto Language do babelfish tem propriedades alpha3 e alpha3
        if hasattr(language, 'alpha3'):
            if language.alpha3 == 'eng':
                return 'en'
            elif language.alpha3 == 'por':
                # Verificar se é português brasileiro
                if hasattr(language, 'country') and language.country:
                    country_name = language.country.name.upper() if hasattr(language.country, 'name') else str(language.country).upper()
                    if country_name == 'BRAZIL' or country_name == 'BR':
                        return 'pt-BR'
                return 'pt'
        
        # Fallback usando string representation
        lang_str = str(language)
        if lang_str == 'en':
            return 'en'
        elif lang_str == 'pt-BR':
            return 'pt-BR'
        elif lang_str == 'pt':
            return 'pt'
        
        return lang_str  # Retorna como está se não conseguir mapear
    
    def _get_language_name(self, lang_code):
        """Retorna nome amigável do idioma"""
        names = {
            'en': 'English',
            'pt': 'Português',
            'pt-BR': 'Português (Brasil)'
        }
        return names.get(lang_code, lang_code)
    
    def get_subtitle_info(self):
        """Retorna informações das legendas disponíveis na pasta final"""
        subtitles = []
        
        if not os.path.exists(self.subtitles_folder):
            return subtitles
        
        for file in os.listdir(self.subtitles_folder):
            if file.endswith('.vtt'):
                # Extrai código do idioma do nome do arquivo
                if 'subtitle_en' in file:
                    lang_code = 'en'
                    lang_name = 'English'
                elif 'subtitle_pt-BR' in file:
                    lang_code = 'pt-BR'
                    lang_name = 'Português (Brasil)'
                elif 'subtitle_pt' in file:
                    lang_code = 'pt'
                    lang_name = 'Português'
                else:
                    continue
                
                subtitles.append({
                    'language': lang_code,
                    'name': lang_name,
                    'file': file,
                    'url': f"/api/subtitles/{self.movie_info['id']}/{file}"
                })
        
        return subtitles

def download_and_process_subtitles(movie_folder, movie_info, progress_callback=None):
    """Função principal para download e processamento de legendas"""
    print(f"=== INICIANDO PROCESSAMENTO DE LEGENDAS ===")
    print(f"Pasta do filme: {movie_folder}")
    print(f"Arquivo de vídeo: {movie_info.get('video_file', 'N/A')}")
    
    subtitle_manager = SubtitleManager(movie_folder, movie_info, progress_callback)
    
    try:
        # Baixa e processa legendas
        print("Iniciando download de legendas...")
        downloaded_subs = subtitle_manager.download_subtitles()
        print(f"Download concluído. Legendas baixadas: {len(downloaded_subs)}")
        
        # Verificar pasta final antes de retornar
        subtitle_folder = os.path.join(movie_folder, 'subtitles')
        if os.path.exists(subtitle_folder):
            files_in_folder = os.listdir(subtitle_folder)
            vtt_files = [f for f in files_in_folder if f.endswith('.vtt')]
            print(f"Arquivos .vtt na pasta final: {vtt_files}")
        else:
            print("AVISO: Pasta de legendas não existe!")
            
        # Retorna informações das legendas processadas
        # Usa get_subtitle_info para garantir que só legendas na pasta final sejam listadas
        print("Verificando legendas na pasta final...")
        subtitle_info = subtitle_manager.get_subtitle_info()
        print(f"Legendas verificadas na pasta final: {len(subtitle_info)}")
        
        # Se não há legendas na pasta final mas houve download, investigar
        if not subtitle_info and downloaded_subs:
            print("AVISO: Legendas foram baixadas mas não estão na pasta final!")
            print("Usando dados em memória como fallback...")
            subtitle_info = downloaded_subs
        
        print(f"=== PROCESSAMENTO DE LEGENDAS CONCLUÍDO ===")
        print(f"Legendas finais: {len(subtitle_info)}")
        return subtitle_info
        
    except Exception as e:
        print(f"ERRO no processamento de legendas: {e}")
        logger.error(f"Erro no processamento de legendas: {e}")
        return []
    finally:
        # Limpa arquivos temporários
        print("Limpando arquivos temporários de legendas...")
        subtitle_manager.cleanup_temp()
