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
        
    def report_progress(self, message, progress=None):
        """Reporta progresso das legendas"""
        if self.progress_callback:
            self.progress_callback(f"Legendas: {message}", progress)
        logger.info(f"Legendas: {message}")
    
    def download_subtitles(self):
        """Baixa legendas em inglês e português"""
        self.report_progress("Iniciando download de legendas")
        
        # Procura pelo arquivo de vídeo principal
        video_file = self._find_main_video_file()
        if not video_file:
            self.report_progress("Arquivo de vídeo não encontrado")
            return []
        
        try:
            # Configura o vídeo para o Subliminal
            video = Video.fromname(video_file)
            if self.movie_info.get('title'):
                video.title = self.movie_info['title']
            if self.movie_info.get('release_date'):
                try:
                    video.year = int(self.movie_info['release_date'][:4])
                except:
                    pass
            
            # Define as linguagens desejadas
            languages = {Language('en'), Language('pt-BR'), Language('pt')}
            
            self.report_progress("Procurando legendas online", 25)
            
            # Baixa as melhores legendas disponíveis
            subtitles = download_best_subtitles([video], languages)
            
            if video in subtitles and subtitles[video]:
                self.report_progress("Salvando legendas baixadas", 50)
                save_subtitles(video, subtitles[video])
                
                downloaded_subs = []
                for subtitle in subtitles[video]:
                    lang_code = self._get_language_code(subtitle.language)
                    subtitle_path = get_subtitle_path(video_file, subtitle.language)
                    
                    if os.path.exists(subtitle_path):
                        # Converte para WebVTT se necessário
                        webvtt_path = self._convert_to_webvtt(subtitle_path, lang_code)
                        if webvtt_path:
                            downloaded_subs.append({
                                'language': lang_code,
                                'name': self._get_language_name(lang_code),
                                'file': os.path.basename(webvtt_path),
                                'path': webvtt_path
                            })
                
                self.report_progress(f"Baixadas {len(downloaded_subs)} legendas", 75)
                
                # Tenta sincronização se houver arquivo de áudio/vídeo
                self._sync_subtitles(video_file, downloaded_subs)
                
                self.report_progress("Legendas processadas com sucesso", 100)
                return downloaded_subs
            else:
                self.report_progress("Nenhuma legenda encontrada online")
                return []
                
        except Exception as e:
            self.report_progress(f"Erro ao baixar legendas: {str(e)}")
            logger.error(f"Erro no download de legendas: {e}")
            return []
    
    def _find_main_video_file(self):
        """Encontra o arquivo de vídeo principal"""
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
        
        for file in os.listdir(self.movie_folder):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                return os.path.join(self.movie_folder, file)
        return None
    
    def _get_language_code(self, language):
        """Converte código de idioma do Babel para nosso padrão"""
        if language.alpha2 == 'en':
            return 'en'
        elif language.alpha2 == 'pt':
            return 'pt-BR' if str(language) == 'pt-BR' else 'pt'
        return language.alpha2
    
    def _get_language_name(self, lang_code):
        """Retorna nome amigável do idioma"""
        names = {
            'en': 'English',
            'pt': 'Português',
            'pt-BR': 'Português (Brasil)'
        }
        return names.get(lang_code, lang_code)
    
    def _convert_to_webvtt(self, subtitle_path, lang_code):
        """Converte legenda para formato WebVTT"""
        try:
            # Detecta encoding do arquivo
            with open(subtitle_path, 'rb') as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
            
            # Lê o arquivo SRT
            subs = pysrt.open(subtitle_path, encoding=encoding)
            
            # Cria arquivo WebVTT
            webvtt_filename = f"subtitle_{lang_code}.vtt"
            webvtt_path = os.path.join(self.subtitles_folder, webvtt_filename)
            
            with open(webvtt_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                
                for sub in subs:
                    # Converte timing para formato WebVTT
                    start_time = self._srt_time_to_webvtt(sub.start)
                    end_time = self._srt_time_to_webvtt(sub.end)
                    
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sub.text}\n\n")
            
            self.report_progress(f"Convertido para WebVTT: {lang_code}")
            return webvtt_path
            
        except Exception as e:
            self.report_progress(f"Erro na conversão para WebVTT: {str(e)}")
            logger.error(f"Erro na conversão WebVTT: {e}")
            return None
    
    def _srt_time_to_webvtt(self, srt_time):
        """Converte timestamp SRT para formato WebVTT"""
        return str(srt_time).replace(',', '.')
    
    def _sync_subtitles(self, video_file, subtitles):
        """Sincroniza legendas usando ffsubsync"""
        if not FFSUBSYNC_AVAILABLE:
            self.report_progress("ffsubsync não disponível, pulando sincronização")
            return
            
        try:
            self.report_progress("Iniciando sincronização de legendas", 80)
            
            for subtitle in subtitles:
                if subtitle['language'] == 'en':  # Prioriza inglês para referência
                    original_path = subtitle['path']
                    synced_path = original_path.replace('.vtt', '_synced.vtt')
                    
                    # Comando ffsubsync
                    cmd = [
                        'ffsubsync',
                        video_file,
                        '-i', original_path,
                        '-o', synced_path,
                        '--max-offset-seconds', '60'
                    ]
                    
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                        if result.returncode == 0 and os.path.exists(synced_path):
                            # Substitui arquivo original pelo sincronizado
                            os.replace(synced_path, original_path)
                            self.report_progress(f"Legenda {subtitle['language']} sincronizada")
                        else:
                            self.report_progress(f"Sincronização falhou para {subtitle['language']}")
                    except subprocess.TimeoutExpired:
                        self.report_progress(f"Timeout na sincronização de {subtitle['language']}")
                    except FileNotFoundError:
                        self.report_progress("ffsubsync não encontrado, pulando sincronização")
                        break
                        
        except Exception as e:
            self.report_progress(f"Erro na sincronização: {str(e)}")
            logger.error(f"Erro na sincronização: {e}")
    
    def get_subtitle_info(self):
        """Retorna informações das legendas disponíveis"""
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
                    'url': f"/library/{self.movie_info['id']}/subtitles/{file}"
                })
        
        return subtitles
    
    def create_hls_subtitle_playlists(self):
        """Cria playlists HLS para legendas se necessário"""
        # Para HLS.js, WebVTT funcionará diretamente
        # Esta função pode ser expandida para segmentação se necessário
        pass

def download_and_process_subtitles(movie_folder, movie_info, progress_callback=None):
    """Função principal para download e processamento de legendas"""
    subtitle_manager = SubtitleManager(movie_folder, movie_info, progress_callback)
    
    # Baixa legendas
    downloaded_subs = subtitle_manager.download_subtitles()
    
    # Obtém informações finais
    subtitle_info = subtitle_manager.get_subtitle_info()
    
    return subtitle_info
