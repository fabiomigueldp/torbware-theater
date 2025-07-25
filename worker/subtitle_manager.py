import os
import json
import subprocess
import requests
import pysrt
import chardet
from subliminal import Video, download_best_subtitles, save_subtitles
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
        self.temp_folder = tempfile.mkdtemp(prefix='subtitles_')

    def report_progress(self, message, progress=None):
        if self.progress_callback:
            self.progress_callback(f"Legendas: {message}", progress)
        logger.info(f"Legendas: {message}")
        print(f"Legendas: {message}")

    def cleanup_temp(self):
        try:
            if os.path.exists(self.temp_folder):
                shutil.rmtree(self.temp_folder, ignore_errors=True)
        except Exception as e:
            print(f"Erro ao limpar arquivos temporários: {e}")

    def _normalize_language_code(self, language) -> str:
        lang_str = str(language).lower()
        if 'pt' in lang_str or 'por' in lang_str or 'pb' in lang_str:
            return 'pt-BR'
        if 'en' in lang_str or 'eng' in lang_str:
            return 'en'
        return lang_str

    def _force_pt_br_with_podnapisi(self, video) -> list:
        self.report_progress("🇧🇷 PT-BR fallback ativado...", 70)
        try:
            from subliminal.providers.podnapisi import PodnapisiProvider
            from subliminal.core import ProviderPool
            
            with ProviderPool(providers=[PodnapisiProvider]) as pool:
                subtitles = pool.list_subtitles(video, {Language('por')})
            
            if subtitles:
                self.report_progress(f"Encontrado {len(subtitles)} legendas PT-BR no Podnapisi.")
                # Baixar a melhor legenda encontrada
                best_pt_sub = subtitles[0]
                save_subtitles(video, [best_pt_sub], directory=self.temp_folder)
                temp_path = self._get_subtitle_temp_path(video, best_pt_sub)
                if temp_path and os.path.exists(temp_path):
                    return [self._process_subtitle_file(temp_path, 'pt-BR', video.name)]
            return []
        except Exception as e:
            self.report_progress(f"Erro no fallback PT-BR: {e}")
            return []

    def download_subtitles(self):
        video_file = self.movie_info.get('video_file')
        if not video_file or not os.path.exists(video_file):
            raise Exception("Arquivo de vídeo não encontrado")

        video = Video.fromname(video_file)
        if self.movie_info.get('original_title'):
            video.title = self.movie_info['original_title']
            self.report_progress(f"Usando título original para busca: '{video.title}'", 25)
        else:
            video.title = self.movie_info.get('title')
            self.report_progress(f"Usando título de fallback para busca: '{video.title}'", 25)
        
        if self.movie_info.get('year'):
            video.year = self.movie_info['year']

        languages = {Language('eng'), Language('por')}
        self.report_progress("Procurando legendas online...", 30)

        # Excluir provedores problemáticos
        providers = ['opensubtitles', 'podnapisi', 'addic7ed', 'gestdown', 'napiprojekt', 'subtitulamos', 'tvsubtitles']

        found_subtitles = download_best_subtitles([video], languages, providers=providers)

        processed_subs = {}
        if found_subtitles:
            self.report_progress(f"Processando {len(found_subtitles.get(video, []))} legenda(s)...", 50)
            for sub in found_subtitles.get(video, []):
                lang_code = self._normalize_language_code(sub.language)
                save_subtitles(video, [sub], directory=self.temp_folder)
                temp_path = self._get_subtitle_temp_path(video, sub)
                if temp_path and os.path.exists(temp_path):
                    final_subtitle = self._process_subtitle_file(temp_path, lang_code, video_file)
                    if final_subtitle:
                        processed_subs[lang_code] = final_subtitle
                        if lang_code == 'pt-BR':
                            self.report_progress("✅ Legenda em português baixada com sucesso.", 60)

        if 'pt-BR' not in processed_subs:
            self.report_progress("Nenhuma legenda em português encontrada, tentando fallback...", 65)
            pt_br_fallback = self._force_pt_br_with_podnapisi(video)
            if pt_br_fallback:
                processed_subs['pt-BR'] = pt_br_fallback[0]
                self.report_progress("✅ Legenda em português baixada com sucesso via fallback.", 70)

        # Ordenar: pt-BR, en, outros
        final_list = sorted(processed_subs.values(), key=lambda x: (
            x['language'] != 'pt-BR',
            x['language'] != 'en',
            x['language']
        ))

        self.report_progress(f"Concluído: {len(final_list)} legendas processadas.", 90)
        return final_list

    def _get_subtitle_temp_path(self, video, subtitle):
        """Constrói o caminho da legenda temporária salva"""
        try:
            # O save_subtitles salva com base no nome do vídeo e extensão da legenda
            video_name = os.path.splitext(os.path.basename(video.name))[0]
            subtitle_ext = subtitle.get_path(video)
            if subtitle_ext:
                return os.path.join(self.temp_folder, os.path.basename(subtitle_ext))
            else:
                # Fallback: usar a extensão padrão da legenda
                lang_suffix = f".{subtitle.language.alpha2}"
                return os.path.join(self.temp_folder, f"{video_name}{lang_suffix}.srt")
        except Exception as e:
            self.report_progress(f"Erro ao construir caminho temporário: {str(e)}")
            return None

    def _process_subtitle_file(self, subtitle_path, lang_code, video_file):
        """Processa uma legenda a partir de um arquivo no disco"""
        try:
            # Sincronizar se arquivo de vídeo fornecido
            srt_to_convert = subtitle_path
            if video_file and os.path.exists(video_file):
                srt_to_convert = self._sync_subtitle_with_video(subtitle_path, video_file)
            
            # Converter para WebVTT
            webvtt_path = self._convert_to_webvtt(srt_to_convert, lang_code)
            
            # Limpeza do arquivo sincronizado temporário
            if srt_to_convert != subtitle_path and os.path.exists(srt_to_convert):
                os.unlink(srt_to_convert)
            
            if webvtt_path:
                # Informações da legenda
                subtitle_info = {
                    'language': lang_code,
                    'name': self._get_language_name(lang_code),
                    'file': os.path.basename(webvtt_path),
                    'url': f"/api/subtitles/{self.movie_info['id']}/{os.path.basename(webvtt_path)}"
                }
                
                return subtitle_info
            else:
                return None
            
        except Exception as e:
            self.report_progress(f"Erro ao processar arquivo de legenda {lang_code}: {str(e)[:50]}")
            return None
    
    def _process_subtitle_content(self, subtitle, lang_code):
        """Processa uma legenda diretamente do conteúdo baixado"""
        try:
            # Detectar encoding do conteúdo
            encoding = chardet.detect(subtitle.content)['encoding']
            if not encoding:
                # Tentar encodings comuns
                for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        content_str = subtitle.content.decode(enc)
                        encoding = enc
                        break
                    except:
                        continue
                else:
                    raise Exception("Não foi possível decodificar o conteúdo")
            else:
                content_str = subtitle.content.decode(encoding)
            
            # Criar arquivo SRT temporário
            temp_srt = tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8')
            temp_srt.write(content_str)
            temp_srt.close()
            
            # Tentar sincronizar com vídeo se disponível
            video_file_path = None
            if 'video_file' in self.movie_info:
                # Procurar arquivo de vídeo na pasta do filme
                video_file_path = os.path.join(self.movie_folder, self.movie_info['video_file'])
                if not os.path.exists(video_file_path):
                    # Tentar procurar qualquer arquivo de vídeo
                    for file in os.listdir(self.movie_folder):
                        if file.endswith(('.mp4', '.mkv', '.avi', '.mov')):
                            video_file_path = os.path.join(self.movie_folder, file)
                            break
            
            # Sincronizar se arquivo de vídeo encontrado
            srt_to_convert = temp_srt.name
            if video_file_path and os.path.exists(video_file_path):
                srt_to_convert = self._sync_subtitle_with_video(temp_srt.name, video_file_path)
            
            # Converter para WebVTT
            webvtt_path = self._convert_to_webvtt(srt_to_convert, lang_code)
            
            # Limpeza
            os.unlink(temp_srt.name)
            if srt_to_convert != temp_srt.name and os.path.exists(srt_to_convert):
                os.unlink(srt_to_convert)
            
            if webvtt_path:
                # Informações da legenda
                subtitle_info = {
                    'language': lang_code,
                    'name': self._get_language_name(lang_code),
                    'file': os.path.basename(webvtt_path),
                    'url': f"/api/subtitles/{self.movie_info['id']}/{os.path.basename(webvtt_path)}"
                }
                
                return subtitle_info
            else:
                return None
            
        except Exception as e:
            self.report_progress(f"Erro ao processar legenda {lang_code}: {str(e)[:50]}")
            return None
    
    def _sync_subtitle_with_video(self, subtitle_path, video_path):
        """Sincroniza legenda com vídeo usando ffsubsync"""
        if not FFSUBSYNC_AVAILABLE:
            self.report_progress("ffsubsync não disponível, pulando sincronização", 75)
            return subtitle_path
        
        try:
            self.report_progress("🔄 Sincronizando legenda com áudio do vídeo...", 75)
            
            # Arquivo de saída sincronizado
            sync_path = subtitle_path.replace('.srt', '_synced.srt')
            
            # Comando ffsubsync
            import ffsubsync
            from ffsubsync.sklearn_shim import Pipeline
            
            # Usar ffsubsync via API direta ao invés de subprocess
            try:
                # Tentar usar API direta do ffsubsync
                import ffsubsync.ffsubsync as ffs
                
                # Simular argumentos de linha de comando
                import argparse
                import sys
                
                # Salvar argv original
                original_argv = sys.argv
                
                # Configurar argumentos falsos para o parser
                sys.argv = ['ffsubsync', video_path, '-i', subtitle_path, '-o', sync_path]
                
                try:
                    # Executar sincronização
                    ffs.main()
                    
                    if os.path.exists(sync_path):
                        self.report_progress("✅ Legenda sincronizada com sucesso!", 78)
                        return sync_path
                    else:
                        raise Exception("Arquivo sincronizado não foi criado")
                        
                finally:
                    # Restaurar argv original
                    sys.argv = original_argv
                
            except Exception as api_error:
                self.report_progress(f"⚠️ API direta falhou: {str(api_error)[:30]}", 76)
                
                # Fallback: tentar encontrar executável
                import shutil
                ffsubsync_exe = shutil.which('ffsubsync')
                
                if ffsubsync_exe:
                    self.report_progress("🔄 Tentando executável ffsubsync...", 76)
                    cmd = [ffsubsync_exe, video_path, '-i', subtitle_path, '-o', sync_path]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    
                    if result.returncode == 0 and os.path.exists(sync_path):
                        self.report_progress("✅ Legenda sincronizada com sucesso!", 78)
                        return sync_path
                    else:
                        raise Exception(f"Executável falhou: {result.stderr}")
                else:
                    raise Exception("ffsubsync executável não encontrado")
                
        except subprocess.TimeoutExpired:
            self.report_progress("⚠️ Sincronização excedeu tempo limite", 76)
            return subtitle_path
        except Exception as e:
            self.report_progress(f"⚠️ Erro na sincronização: {str(e)[:30]}", 76)
            logger.warning(f"Erro na sincronização: {e}")
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
                # Extrair código de idioma do nome do arquivo
                if file == "subtitle_en.vtt":
                    lang_code = "en"
                    lang_name = "English"
                elif file == "subtitle_pt.vtt":
                    lang_code = "pt"
                    lang_name = "Português"
                elif file == "subtitle_pt-BR.vtt":
                    lang_code = "pt-BR"
                    lang_name = "Português (Brasil)"
                else:
                    # Tentar extrair do nome do arquivo
                    lang_code = file.replace("subtitle_", "").replace(".vtt", "")
                    lang_name = lang_code
                
                subtitles.append({
                    'language': lang_code,
                    'name': lang_name,
                    'file': file,
                    'url': f"/api/subtitles/{self.movie_info['id']}/{file}"
                })
        
        return subtitles

def download_and_process_subtitles(movie_folder, movie_info, progress_callback=None):
    """
    Função principal para download e processamento de legendas
    
    Args:
        movie_folder: Pasta do filme na biblioteca
        movie_info: Informações do filme (incluindo video_file)
        progress_callback: Callback para reportar progresso
    
    Returns:
        Lista de informações das legendas processadas
    """
    subtitle_manager = SubtitleManager(movie_folder, movie_info, progress_callback)
    
    try:
        # Baixar e processar legendas
        subtitles = subtitle_manager.download_subtitles()
        
        # Limpar arquivos temporários
        subtitle_manager.cleanup_temp()
        
        return subtitles
        
    except Exception as e:
        # Limpar arquivos temporários mesmo em caso de erro
        subtitle_manager.cleanup_temp()
        raise e
