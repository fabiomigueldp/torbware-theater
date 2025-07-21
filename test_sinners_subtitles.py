#!/usr/bin/env python3
"""
Teste específico para obter legendas do filme "Sinners"
Investigar diferentes estratégias de busca
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

print("=== TESTE ESPECÍFICO PARA LEGENDAS DO FILME SINNERS ===")

# Simular informações do filme Sinners
movie_info = {
    'title': 'Sinners',
    'year': 2025,
    'release_date': '2025-01-01'
}

# Nomes de arquivo para testar
test_filenames = [
    'Sinners.2025.720p.WEBRip.x264.AAC-[YTS.MX].mp4',
    'Sinners.2025.mp4',
    'Sinners (2025).mp4',
    'sinners.2025.720p.webrip.mp4'
]

print("\n1. TESTANDO CRIAÇÃO DE OBJETOS VIDEO")
try:
    from subliminal import Video
    
    for filename in test_filenames:
        # Criar arquivo temporário
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, filename)
        
        with open(temp_file, 'w') as f:
            f.write("fake video content")
        
        try:
            video = Video.fromname(temp_file)
            video.title = movie_info['title']
            video.year = movie_info['year']
            
            print(f"✓ {filename}")
            print(f"  Video object: {video}")
            print(f"  Title: {video.title}")
            print(f"  Year: {video.year}")
            
        except Exception as e:
            print(f"✗ {filename}: {e}")
        
        # Limpeza
        shutil.rmtree(temp_dir, ignore_errors=True)
        
except ImportError:
    print("✗ Subliminal não disponível")

print("\n2. TESTANDO CÓDIGOS DE IDIOMA")
try:
    from babelfish import Language
    
    # Testar diferentes combinações de idiomas
    language_tests = [
        ('eng', 'Inglês'),
        ('por', 'Português'),
        ('por + BR', 'Português Brasil'),
        ('spa', 'Espanhol'),
        ('fra', 'Francês')
    ]
    
    languages_set = set()
    for code, name in language_tests:
        try:
            if '+' in code:
                lang = Language('por', country='BR')
            else:
                lang = Language(code)
            languages_set.add(lang)
            print(f"✓ {name}: {lang}")
        except Exception as e:
            print(f"✗ {name}: {e}")
    
    print(f"\nLanguages set criado: {languages_set}")
    
except ImportError:
    print("✗ Babelfish não disponível")

print("\n3. TESTANDO BUSCA MANUAL DE LEGENDAS (SEM DOWNLOAD)")
try:
    from subliminal.core import search_external_subtitles
    from subliminal import scan_videos
    
    # Criar estrutura de teste
    test_dir = tempfile.mkdtemp()
    video_file = os.path.join(test_dir, 'Sinners.2025.720p.WEBRip.x264.AAC-[YTS.MX].mp4')
    
    with open(video_file, 'w') as f:
        f.write("fake video content")
    
    # Testar scan de vídeos
    videos = scan_videos(test_dir)
    print(f"Videos encontrados: {len(videos)}")
    for video in videos:
        print(f"  - {video}")
    
    # Limpeza
    shutil.rmtree(test_dir, ignore_errors=True)
    
except ImportError:
    print("✗ Funcionalidades avançadas do Subliminal não disponíveis")

print("\n4. TESTANDO PROVEDORES DE LEGENDAS")
try:
    from subliminal import provider_manager
    
    print("Provedores disponíveis:")
    for name in provider_manager.names():
        print(f"  - {name}")
    
    # Testar configuração específica
    print("\nTestando configuração de provedores...")
    
    # Lista de provedores mais confiáveis para filmes em inglês/português
    recommended_providers = ['opensubtitles', 'podnapisi', 'thesubdb', 'tvsubtitles']
    available_providers = []
    
    for provider in recommended_providers:
        if provider in provider_manager.names():
            available_providers.append(provider)
            print(f"✓ {provider} disponível")
        else:
            print(f"✗ {provider} não disponível")
    
    print(f"\nProvedores recomendados disponíveis: {available_providers}")
    
except ImportError:
    print("✗ Provider manager não disponível")

print("\n5. TESTANDO ESTRATÉGIAS DE BUSCA ALTERNATIVAS")

# Informações alternativas para teste
alternative_searches = [
    {'title': 'Sinners', 'year': 2025},
    {'title': 'Sinners', 'year': 2024},  # Caso o ano esteja errado
    {'title': 'The Sinners', 'year': 2025},  # Com artigo
    {'title': 'Sinners 2025', 'year': None},  # Título com ano
]

for i, search_info in enumerate(alternative_searches, 1):
    print(f"  Estratégia {i}: {search_info}")

print("\n=== RECOMENDAÇÕES BASEADAS NO TESTE ===")
print("1. Usar múltiplos provedores de legendas")
print("2. Testar diferentes variações do título")
print("3. Implementar fallback para anos diferentes")
print("4. Usar configuração específica de provedores")
print("5. Adicionar logs detalhados para cada tentativa")

print("\n=== TESTE CONCLUÍDO ===")
