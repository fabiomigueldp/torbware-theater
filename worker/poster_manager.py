import os
import requests
import shutil
from PIL import Image, ImageDraw, ImageFont
import json
import hashlib
import tempfile
import logging
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

class PosterManager:
    """Gerenciador avançado de posters com múltiplos tamanhos e fallbacks"""
    
    # Configurações de tamanhos TMDB
    TMDB_SIZES = {
        'thumbnail': 'w154',    # Para listagem rápida
        'medium': 'w342',       # Para detalhes
        'large': 'w500',        # Para player
        'xlarge': 'w780',       # Para displays grandes
        'original': 'original'   # Tamanho original
    }
    
    # Tamanhos locais otimizados
    LOCAL_SIZES = {
        'thumbnail': (154, 231),  # Aspect ratio 2:3
        'medium': (342, 513),     
        'large': (500, 750),      
    }
    
    def __init__(self, movie_folder: str, movie_info: Dict, progress_callback=None):
        """
        Args:
            movie_folder: Pasta final do filme (/app/library/{movie_id})
            movie_info: Informações do filme incluindo poster_path do TMDB
            progress_callback: Função para reportar progresso
        """
        self.movie_folder = movie_folder
        self.movie_info = movie_info
        self.progress_callback = progress_callback
        self.posters_folder = os.path.join(movie_folder, 'posters')
        
        # Criar pasta de posters
        os.makedirs(self.posters_folder, exist_ok=True)
        
        # Cache local para fallbacks
        self.cache_folder = '/app/cache/posters'
        os.makedirs(self.cache_folder, exist_ok=True)
    
    def report_progress(self, message: str, progress: Optional[float] = None):
        """Reporta progresso do download de posters"""
        if self.progress_callback:
            self.progress_callback(f"Posters: {message}", progress)
        logger.info(f"Posters: {message}")
        print(f"Posters: {message}")
    
    def download_and_process_posters(self) -> Dict[str, str]:
        """
        Download e processa posters em múltiplos tamanhos
        
        Returns:
            Dict com paths dos posters processados
        """
        self.report_progress("Iniciando download de posters", 0)
        
        poster_info = {
            'thumbnail': None,
            'medium': None,
            'large': None,
            'original': None
        }
        
        # 1. Tentar download do TMDB
        tmdb_poster_path = self.movie_info.get('poster_path')
        if tmdb_poster_path:
            poster_info = self._download_from_tmdb(tmdb_poster_path)
        
        # 2. Se não conseguiu do TMDB, tentar fontes alternativas
        if not any(poster_info.values()):
            self.report_progress("TMDB falhou, tentando fontes alternativas", 30)
            poster_info = self._download_from_alternative_sources()
        
        # 3. Se ainda não tem poster, criar placeholder
        if not any(poster_info.values()):
            self.report_progress("Criando poster placeholder", 80)
            poster_info = self._create_placeholder_poster()
        
        # 4. Gerar tamanhos adicionais se necessário
        self.report_progress("Otimizando tamanhos", 90)
        poster_info = self._ensure_all_sizes(poster_info)
        
        # 5. Criar poster.png padrão para compatibilidade
        self._create_default_poster(poster_info)
        
        self.report_progress("Posters processados com sucesso", 100)
        return poster_info
    
    def _download_from_tmdb(self, poster_path: str) -> Dict[str, str]:
        """Download de posters do TMDB em múltiplos tamanhos"""
        poster_info = {}
        base_url = "https://image.tmdb.org/t/p/"
        
        # Tentar download de diferentes tamanhos
        for size_name, tmdb_size in self.TMDB_SIZES.items():
            if size_name == 'original':
                continue  # Pular original por enquanto
                
            try:
                self.report_progress(f"Baixando {size_name} do TMDB", 10 + (list(self.TMDB_SIZES.keys()).index(size_name) * 15))
                
                url = f"{base_url}{tmdb_size}{poster_path}"
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                
                # Validar se é uma imagem válida
                if not self._is_valid_image_response(response):
                    continue
                
                filename = f"poster_{size_name}.jpg"
                filepath = os.path.join(self.posters_folder, filename)
                
                with open(filepath, 'wb') as f:
                    shutil.copyfileobj(response.raw, f)
                
                # Validar arquivo baixado
                if self._validate_image_file(filepath):
                    poster_info[size_name] = f"/posters/{filename}"
                    self.report_progress(f"✓ {size_name} baixado", None)
                else:
                    os.remove(filepath)
                    self.report_progress(f"✗ {size_name} inválido", None)
                    
            except Exception as e:
                self.report_progress(f"✗ Erro no {size_name}: {str(e)[:30]}", None)
                continue
        
        return poster_info
    
    def _download_from_alternative_sources(self) -> Dict[str, str]:
        """Tenta fontes alternativas para posters"""
        poster_info = {}
        
        # Lista de APIs alternativas (implementar conforme necessário)
        alternative_sources = [
            self._try_omdb_api,
            self._try_fanart_tv,
            self._try_google_images_fallback
        ]
        
        for source_func in alternative_sources:
            try:
                result = source_func()
                if result:
                    poster_info.update(result)
                    if poster_info.get('large'):  # Se conseguiu pelo menos um tamanho grande
                        break
            except Exception as e:
                self.report_progress(f"Fonte alternativa falhou: {str(e)[:30]}", None)
                continue
        
        return poster_info
    
    def _try_omdb_api(self) -> Optional[Dict[str, str]]:
        """Tenta buscar poster via OMDb API"""
        # Implementação futura - requer API key
        return None
    
    def _try_fanart_tv(self) -> Optional[Dict[str, str]]:
        """Tenta buscar poster via Fanart.tv"""
        # Implementação futura - requer API key
        return None
    
    def _try_google_images_fallback(self) -> Optional[Dict[str, str]]:
        """Último recurso - busca via Google Images (cuidado com rate limits)"""
        # Implementação futura - requer cuidado com ToS
        return None
    
    def _create_placeholder_poster(self) -> Dict[str, str]:
        """Cria poster placeholder personalizado"""
        poster_info = {}
        
        try:
            title = self.movie_info.get('title', 'Filme')
            year = self.movie_info.get('release_date', '')[:4] if self.movie_info.get('release_date') else '????'
            
            # Criar poster para cada tamanho
            for size_name, (width, height) in self.LOCAL_SIZES.items():
                filename = f"poster_{size_name}_placeholder.png"
                filepath = os.path.join(self.posters_folder, filename)
                
                self._generate_placeholder_image(filepath, width, height, title, year)
                poster_info[size_name] = f"/posters/{filename}"
            
            return poster_info
            
        except Exception as e:
            self.report_progress(f"Erro ao criar placeholder: {e}", None)
            return {}
    
    def _generate_placeholder_image(self, filepath: str, width: int, height: int, title: str, year: str):
        """Gera imagem placeholder personalizada"""
        # Criar imagem com gradiente
        img = Image.new('RGB', (width, height), color='#1a1a1a')
        draw = ImageDraw.Draw(img)
        
        # Gradiente simples
        for y in range(height):
            color_value = int(26 + (y / height) * 30)  # De #1a1a1a para mais claro
            draw.line([(0, y), (width, y)], fill=(color_value, color_value, color_value))
        
        # Adicionar texto
        try:
            # Tentar fonte do sistema
            font_size = max(12, width // 12)
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            # Fallback para fonte padrão
            font = ImageFont.load_default()
        
        # Título (quebrar em linhas se necessário)
        title_lines = self._wrap_text(title, font, width - 20)
        
        # Calcular posição central
        total_text_height = len(title_lines) * font_size + 10 + font_size  # +year
        start_y = (height - total_text_height) // 2
        
        # Desenhar título
        for i, line in enumerate(title_lines):
            text_width = draw.textlength(line, font=font)
            x = (width - text_width) // 2
            y = start_y + (i * font_size)
            
            # Sombra
            draw.text((x+1, y+1), line, font=font, fill='#000000')
            # Texto principal
            draw.text((x, y), line, font=font, fill='#ffffff')
        
        # Ano
        if year and year != '????':
            year_y = start_y + (len(title_lines) * font_size) + 10
            year_width = draw.textlength(year, font=font)
            year_x = (width - year_width) // 2
            
            # Sombra
            draw.text((year_x+1, year_y+1), year, font=font, fill='#000000')
            # Texto principal
            draw.text((year_x, year_y), year, font=font, fill='#888888')
        
        # Adicionar borda
        draw.rectangle([(0, 0), (width-1, height-1)], outline='#444444', width=2)
        
        # Salvar
        img.save(filepath, 'PNG', quality=95)
    
    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """Quebra texto em múltiplas linhas"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if hasattr(font, 'getsize'):
                text_width = font.getsize(test_line)[0]
            else:
                # PIL mais recente
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)  # Palavra muito longa
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines[:3]  # Máximo 3 linhas
    
    def _ensure_all_sizes(self, poster_info: Dict[str, str]) -> Dict[str, str]:
        """Garante que todos os tamanhos necessários existem"""
        # Se temos um tamanho grande, gerar os menores
        source_path = None
        
        # Encontrar o melhor source
        for size in ['large', 'medium', 'thumbnail']:
            if poster_info.get(size):
                source_path = os.path.join(self.posters_folder, poster_info[size].split('/')[-1])
                break
        
        if not source_path or not os.path.exists(source_path):
            return poster_info
        
        try:
            with Image.open(source_path) as img:
                # Gerar tamanhos faltantes
                for size_name, (target_width, target_height) in self.LOCAL_SIZES.items():
                    if not poster_info.get(size_name):
                        filename = f"poster_{size_name}_resized.jpg"
                        filepath = os.path.join(self.posters_folder, filename)
                        
                        # Redimensionar mantendo aspect ratio
                        resized = img.copy()
                        resized.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                        resized.save(filepath, 'JPEG', quality=90)
                        
                        poster_info[size_name] = f"/posters/{filename}"
        
        except Exception as e:
            self.report_progress(f"Erro ao redimensionar: {e}", None)
        
        return poster_info
    
    def _create_default_poster(self, poster_info: Dict[str, str]):
        """Cria poster.png padrão para compatibilidade com sistema antigo"""
        # Usar o melhor tamanho disponível
        source_rel_path = None
        for size in ['large', 'medium', 'thumbnail']:
            if poster_info.get(size):
                source_rel_path = poster_info[size]
                break
        
        if source_rel_path:
            source_path = os.path.join(self.posters_folder, source_rel_path.split('/')[-1])
            default_path = os.path.join(self.movie_folder, 'poster.png')
            
            try:
                shutil.copy2(source_path, default_path)
                self.report_progress("✓ poster.png criado para compatibilidade", None)
            except Exception as e:
                self.report_progress(f"Erro ao criar poster.png: {e}", None)
    
    def _is_valid_image_response(self, response) -> bool:
        """Valida se a resposta HTTP contém uma imagem válida"""
        content_type = response.headers.get('content-type', '')
        content_length = response.headers.get('content-length')
        
        # Verificar content-type
        if not content_type.startswith('image/'):
            return False
            
        # Verificar tamanho via header se disponível
        if content_length:
            try:
                size = int(content_length)
                return size > 1024
            except ValueError:
                pass
        
        # Se não tem content-length, assumir válido se content-type for imagem
        return True
    
    def _validate_image_file(self, filepath: str) -> bool:
        """Valida se o arquivo é uma imagem válida"""
        try:
            with Image.open(filepath) as img:
                img.verify()  # Verifica se é uma imagem válida
                return True
        except:
            return False
    
    def get_poster_info(self) -> Dict[str, str]:
        """Retorna informações dos posters disponíveis"""
        poster_info = {}
        
        # Verificar posters existentes
        if os.path.exists(self.posters_folder):
            for filename in os.listdir(self.posters_folder):
                if filename.startswith('poster_') and filename.endswith(('.jpg', '.png')):
                    # Extrair tamanho do nome do arquivo
                    size_name = filename.split('_')[1].split('.')[0].split('_')[0]
                    if size_name in self.LOCAL_SIZES:
                        poster_info[size_name] = f"/posters/{filename}"
        
        return poster_info

def download_and_process_posters(movie_folder: str, movie_info: Dict, progress_callback=None) -> Dict[str, str]:
    """
    Função principal para download e processamento de posters
    
    Args:
        movie_folder: Pasta do filme
        movie_info: Informações do filme
        progress_callback: Callback para progresso
    
    Returns:
        Dict com informações dos posters processados
    """
    manager = PosterManager(movie_folder, movie_info, progress_callback)
    return manager.download_and_process_posters()
