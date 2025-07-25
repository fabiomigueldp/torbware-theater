#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gerenciamento de legendas para o Torbware Theater.

Este módulo oferece classes e funções para baixar, sincronizar e converter
legendas para vídeos. Foi reescrito para corrigir problemas da versão
anterior e fornecer uma API mais robusta. Principais melhorias:

* Respeita o caminho absoluto fornecido em ``movie_info['video_file']``.
  Se o caminho não for absoluto, assume que é relativo à pasta do filme.
* Utiliza ``video.name`` e ``video.year`` para buscas no Subliminal em
  vez de ``video.title``. Isso melhora significativamente a precisão.
* Protege chamadas a ``get_matches`` com ``hasattr`` para evitar
  quebras quando o método não estiver disponível.
* Torna público o método ``process_subtitle_content`` para permitir
  processar legendas baixadas manualmente (por exemplo, via Podnapisi).
* Caso o ffsubsync falhe ou não esteja disponível, a sincronização é
  ignorada sem interromper o fluxo.

Dependências: ``subliminal``, ``babelfish``, ``pysrt``, ``chardet``,
``ffsubsync`` (opcional), além de ``ffmpeg`` para conversão e
``ffprobe`` para análise.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

import chardet  # type: ignore
import pysrt  # type: ignore
from babelfish import Language  # type: ignore
from subliminal import Video, download_best_subtitles, save_subtitles  # type: ignore

import logging

try:
    import ffsubsync  # type: ignore
    FFSUBSYNC_AVAILABLE = True
except Exception:
    FFSUBSYNC_AVAILABLE = False

logger = logging.getLogger(__name__)


class SubtitleManager:
    """
    Classe responsável por baixar, sincronizar e converter legendas.

    Args:
        movie_folder: Caminho absoluto para a pasta do filme na biblioteca.
        movie_info: Dicionário contendo informações do filme (``video_file``,
            ``original_title``, ``title``, ``year`` etc.).
        progress_callback: Função opcional para reportar progresso. Recebe
            ``message`` e ``progress`` (0–100).
    """

    def __init__(self, movie_folder: str, movie_info: Dict[str, object], progress_callback=None) -> None:
        self.movie_folder = movie_folder
        self.movie_info = movie_info
        self.progress_callback = progress_callback
        self.subtitles_folder = os.path.join(movie_folder, 'subtitles')
        os.makedirs(self.subtitles_folder, exist_ok=True)
        self.temp_folder = tempfile.mkdtemp(prefix='subtitles_')

    # ---------------------------------------------------------------------
    # Utilidades de progresso

    def report_progress(self, message: str, progress: Optional[float] = None) -> None:
        """Reporta mensagens e progresso para o callback e logger."""
        if self.progress_callback:
            self.progress_callback(f"Legendas: {message}", progress)
        logger.info(f"Legendas: {message}")
        print(f"Legendas: {message}")

    # ---------------------------------------------------------------------
    # Limpeza

    def cleanup_temp(self) -> None:
        """Remove a pasta temporária utilizada para processar legendas."""
        try:
            if os.path.exists(self.temp_folder):
                temp_files = os.listdir(self.temp_folder)
                if temp_files:
                    print(f"Arquivos temporários de legenda a serem removidos: {temp_files}")
                shutil.rmtree(self.temp_folder, ignore_errors=True)
        except Exception as exc:
            print(f"Erro ao limpar arquivos temporários: {exc}")

    # ---------------------------------------------------------------------
    # Entrada pública

    def download_subtitles(self) -> List[Dict[str, str]]:
        """Baixa e processa legendas em inglês e português com tentativas de retry."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self._download_subtitles_attempt()
            except Exception as exc:
                self.report_progress(f"Tentativa {attempt + 1} falhou: {str(exc)[:50]}")
                if attempt == max_retries - 1:
                    self.report_progress("Todas as tentativas de download falharam", 100)
                    return []
                import time
                time.sleep(2)
        return []

    def process_subtitle_content(self, subtitle, lang_code: str) -> Optional[Dict[str, str]]:
        """
        Processa uma legenda diretamente a partir de um objeto retornado pelo
        Subliminal (ou estrutura similar). Permite converter conteúdos
        obtidos externamente (por exemplo, Podnapisi) sem salvar primeiro
        como arquivo na temp.

        Args:
            subtitle: Objeto da Subliminal que possui o atributo ``content``.
            lang_code: Código de idioma final (ex.: 'pt-BR').
        Returns:
            Dicionário com informações sobre a legenda ou ``None`` em caso de erro.
        """
        try:
            content = subtitle.content
            if not content:
                return None
            # Detectar encoding
            encoding = chardet.detect(content)['encoding'] or 'utf-8'
            try:
                content_str = content.decode(encoding)
            except Exception:
                # fallback para encodings comuns
                for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        content_str = content.decode(enc)
                        break
                    except Exception:
                        continue
                else:
                    return None
            # Converter para WebVTT
            filename = f"subtitle_{lang_code}.vtt"
            out_path = os.path.join(self.subtitles_folder, filename)
            os.makedirs(self.subtitles_folder, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                if 'WEBVTT' not in content_str[:20].upper():
                    f.write('WEBVTT\n\n')
                    # substituir vírgulas para o formato VTT
                    f.write(content_str.replace(',', '.'))
                else:
                    f.write(content_str)
            return {
                'language': lang_code,
                'name': self._get_language_name(lang_code),
                'file': filename,
                'url': f"/api/subtitles/{self.movie_info['id']}/{filename}",
            }
        except Exception as exc:
            self.report_progress(f"Erro ao processar conteúdo de legenda: {str(exc)[:50]}")
            return None

    # ---------------------------------------------------------------------
    # Download interno

    def _download_subtitles_attempt(self) -> List[Dict[str, str]]:
        """
        Realiza uma tentativa de download das melhores legendas utilizando
        Subliminal. Prepara o objeto Video com os dados corretos,
        incluindo o caminho absoluto do vídeo.
        """
        self.report_progress("Iniciando busca pelas melhores legendas", 10)
        # Determinar caminho absoluto do arquivo de vídeo
        vf = self.movie_info.get('video_file')
        if not vf:
            raise Exception("Arquivo de vídeo não encontrado para download de legendas")
        if os.path.isabs(vf):
            video_path = vf
        else:
            vf_clean = str(vf).lstrip('/\\')
            video_path = os.path.join(self.movie_folder, vf_clean)
        if not os.path.exists(video_path):
            raise Exception(f"Arquivo de vídeo não encontrado: {video_path}")
        self.report_progress(f"Usando arquivo: {os.path.basename(video_path)}", 20)
        # Configurar Video
        video = Video.fromname(video_path)
        if self.movie_info.get('original_title'):
            video.name = self.movie_info['original_title']
        elif self.movie_info.get('title'):
            video.name = self.movie_info['title']
        if self.movie_info.get('year'):
            try:
                video.year = int(self.movie_info['year'])
            except Exception:
                pass
        elif self.movie_info.get('release_date'):
            try:
                video.year = int(str(self.movie_info['release_date'])[:4])
            except Exception:
                pass
        # Idiomas desejados
        languages = {Language('eng'), Language('por', country='BR'), Language('por')}
        self.report_progress("Procurando as melhores legendas online...", 30)
        try:
            best_subtitles = download_best_subtitles([video], languages)
        except Exception as exc:
            self.report_progress(f"Erro ao buscar legendas: {str(exc)[:50]}", 90)
            return []
        if not best_subtitles or not best_subtitles.get(video):
            self.report_progress("Nenhuma legenda encontrada online", 90)
            return []
        found = best_subtitles.get(video, [])
        self.report_progress(f"Processando {len(found)} legenda(s) encontrada(s)", 50)
        processed_subs: List[Dict[str, str]] = []
        for sub in found:
            lang_code = self._get_language_code(sub.language)
            self.report_progress(f"Processando legenda {lang_code}", 60)
            try:
                save_subtitles(video, [sub], directory=self.temp_folder)
            except Exception as exc:
                self.report_progress(f"✗ Falha ao salvar legenda {lang_code}: {str(exc)[:30]}")
                continue
            temp_subtitle_path = self._get_subtitle_temp_path(video, sub)
            if temp_subtitle_path and os.path.exists(temp_subtitle_path):
                result = self._process_subtitle_file(temp_subtitle_path, lang_code, video_path)
                if result:
                    processed_subs.append(result)
                    self.report_progress(f"✓ Legenda criada: {result['file']}")
            else:
                self.report_progress(f"✗ Falha ao encontrar legenda temporária para {lang_code}")
        self.report_progress(f"Concluído: {len(processed_subs)} legendas processadas", 90)
        return processed_subs

    # ---------------------------------------------------------------------
    # Caminho temporário
    def _get_subtitle_temp_path(self, video: Video, subtitle) -> Optional[str]:
        """Constrói o caminho do arquivo temporário salvo pelo Subliminal."""
        try:
            video_name = os.path.splitext(os.path.basename(video.name))[0]
            subtitle_ext = subtitle.get_path(video)
            if subtitle_ext:
                return os.path.join(self.temp_folder, os.path.basename(subtitle_ext))
            else:
                lang_suffix = f".{subtitle.language.alpha2}"
                return os.path.join(self.temp_folder, f"{video_name}{lang_suffix}.srt")
        except Exception as exc:
            self.report_progress(f"Erro ao construir caminho temporário: {str(exc)}")
            return None

    # ---------------------------------------------------------------------
    # Processamento de arquivo temporário
    def _process_subtitle_file(self, subtitle_path: str, lang_code: str, video_file: str) -> Optional[Dict[str, str]]:
        """Sincroniza e converte uma legenda salva em disco."""
        try:
            srt_to_convert = subtitle_path
            if video_file and os.path.exists(video_file):
                srt_to_convert = self._sync_subtitle_with_video(subtitle_path, video_file)
            webvtt_path = self._convert_to_webvtt(srt_to_convert, lang_code)
            if srt_to_convert != subtitle_path and os.path.exists(srt_to_convert):
                os.unlink(srt_to_convert)
            if webvtt_path:
                return {
                    'language': lang_code,
                    'name': self._get_language_name(lang_code),
                    'file': os.path.basename(webvtt_path),
                    'url': f"/api/subtitles/{self.movie_info['id']}/{os.path.basename(webvtt_path)}",
                }
            return None
        except Exception as exc:
            self.report_progress(f"Erro ao processar arquivo de legenda {lang_code}: {str(exc)[:50]}")
            return None

    # ---------------------------------------------------------------------
    # Sincronização via ffsubsync
    def _sync_subtitle_with_video(self, subtitle_path: str, video_path: str) -> str:
        """Sincroniza SRT com o áudio usando ffsubsync. Retorna o caminho do arquivo sincronizado ou original."""
        if not FFSUBSYNC_AVAILABLE:
            self.report_progress("ffsubsync não disponível, pulando sincronização", 75)
            return subtitle_path
        try:
            self.report_progress("🔄 Sincronizando legenda com áudio do vídeo...", 75)
            sync_path = subtitle_path.replace('.srt', '_synced.srt')
            try:
                # Tentar API direta do ffsubsync
                import ffsubsync.ffsubsync as ffs  # type: ignore
                import sys as _sys
                original_argv = _sys.argv
                _sys.argv = ['ffsubsync', video_path, '-i', subtitle_path, '-o', sync_path]
                try:
                    ffs.main()
                finally:
                    _sys.argv = original_argv
                if os.path.exists(sync_path):
                    self.report_progress("✅ Legenda sincronizada com sucesso!", 78)
                    return sync_path
                else:
                    raise Exception("Arquivo sincronizado não foi criado")
            except Exception as api_error:
                self.report_progress(f"⚠️ API direta falhou: {str(api_error)[:30]}", 76)
                import shutil as _shutil
                ffsubsync_exe = _shutil.which('ffsubsync')
                if ffsubsync_exe:
                    cmd = [ffsubsync_exe, video_path, '-i', subtitle_path, '-o', sync_path]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0 and os.path.exists(sync_path):
                        self.report_progress("✅ Legenda sincronizada com sucesso!", 78)
                        return sync_path
                    else:
                        raise Exception(f"Executável ffsubsync falhou: {result.stderr}")
                else:
                    raise Exception("ffsubsync executável não encontrado")
        except subprocess.TimeoutExpired:
            self.report_progress("⚠️ Sincronização excedeu tempo limite", 76)
            return subtitle_path
        except Exception as exc:
            self.report_progress(f"⚠️ Erro na sincronização: {str(exc)[:30]}", 76)
            logger.warning(f"Erro na sincronização: {exc}")
            return subtitle_path

    # ---------------------------------------------------------------------
    # Conversão para WebVTT
    def _convert_to_webvtt(self, subtitle_path: str, lang_code: str) -> Optional[str]:
        """Converte um arquivo SRT para WebVTT na pasta final de legendas."""
        try:
            os.makedirs(self.subtitles_folder, exist_ok=True)
            with open(subtitle_path, 'rb') as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
            self.report_progress(f"Lendo arquivo SRT ({encoding})", 82)
            subs = pysrt.open(subtitle_path, encoding=encoding)
            webvtt_filename = f"subtitle_{lang_code}.vtt"
            webvtt_path = os.path.join(self.subtitles_folder, webvtt_filename)
            self.report_progress(f"Convertendo para WebVTT: {webvtt_filename}", 85)
            with open(webvtt_path, 'w', encoding='utf-8') as f:
                f.write('WEBVTT\n\n')
                for sub in subs:
                    start_time = self._srt_time_to_webvtt(sub.start)
                    end_time = self._srt_time_to_webvtt(sub.end)
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sub.text}\n\n")
            if os.path.exists(webvtt_path):
                size = os.path.getsize(webvtt_path)
                self.report_progress(f"✓ WebVTT criado: {webvtt_filename} ({size} bytes)", 88)
                return webvtt_path
            else:
                raise Exception(f"Arquivo WebVTT não foi criado: {webvtt_path}")
        except Exception as exc:
            self.report_progress(f"Erro na conversão para WebVTT: {str(exc)[:50]}")
            logger.error(f"Erro na conversão WebVTT: {exc}")
            return None

    # ---------------------------------------------------------------------
    # Utilidades para tempo e idioma
    def _srt_time_to_webvtt(self, srt_time) -> str:
        return str(srt_time).replace(',', '.')

    def _get_language_code(self, language) -> str:
        if hasattr(language, 'alpha3'):
            if language.alpha3 == 'eng':
                return 'en'
            elif language.alpha3 == 'por':
                if hasattr(language, 'country') and language.country:
                    if str(language.country) == 'BR':
                        return 'pt-BR'
                return 'pt'
        lang_str = str(language)
        if lang_str == 'en':
            return 'en'
        elif lang_str in ('pt-BR', 'pt'):
            return lang_str
        return lang_str

    def _get_language_name(self, lang_code: str) -> str:
        names = {
            'en': 'English',
            'pt': 'Português',
            'pt-BR': 'Português (Brasil)',
        }
        return names.get(lang_code, lang_code)

    # ---------------------------------------------------------------------
    # Consulta de legendas existentes
    def get_subtitle_info(self) -> List[Dict[str, str]]:
        """Retorna as legendas atualmente disponíveis na pasta final."""
        results: List[Dict[str, str]] = []
        if not os.path.exists(self.subtitles_folder):
            return results
        for file in os.listdir(self.subtitles_folder):
            if file.endswith('.vtt'):
                if file == 'subtitle_en.vtt':
                    lang_code, lang_name = 'en', 'English'
                elif file == 'subtitle_pt.vtt':
                    lang_code, lang_name = 'pt', 'Português'
                elif file == 'subtitle_pt-BR.vtt':
                    lang_code, lang_name = 'pt-BR', 'Português (Brasil)'
                else:
                    lang_code = file.replace('subtitle_', '').replace('.vtt', '')
                    lang_name = lang_code
                results.append({
                    'language': lang_code,
                    'name': lang_name,
                    'file': file,
                    'url': f"/api/subtitles/{self.movie_info['id']}/{file}",
                })
        return results


def download_and_process_subtitles(movie_folder: str, movie_info: Dict[str, object], progress_callback=None) -> List[Dict[str, str]]:
    """
    Interface de conveniência para baixar e processar legendas.
    Cria uma instância de SubtitleManager, baixa legendas e garante a
    limpeza de arquivos temporários, mesmo em caso de erro.
    """
    manager = SubtitleManager(movie_folder, movie_info, progress_callback)
    try:
        subtitles = manager.download_subtitles()
        manager.cleanup_temp()
        return subtitles
    except Exception:
        manager.cleanup_temp()
        raise