#!/usr/bin/env python3
"""
Teste com termo que não retorna resultados
"""

import os
import sys

# Adiciona o diretório worker ao path para importar config
sys.path.append(os.path.join(os.path.dirname(__file__), 'worker'))

try:
    import config
    from tmdbv3api import TMDb, Movie
    
    # Configuração do TMDB
    tmdb = TMDb()
    tmdb.api_key = config.TMDB_API_KEY
    tmdb.language = 'pt-BR'
    
    # Teste com termo que não encontra nada
    search_term = "Pecos Pest 1955"
    print(f"Testando busca por: '{search_term}'")
    
    movie = Movie()
    search_results = movie.search(search_term)
    
    print(f"Total de resultados: {search_results.total_results}")
    
    if search_results.total_results > 0 and hasattr(search_results, 'results'):
        print("✅ Resultados encontrados (não deveria acontecer)")
    else:
        print("❌ Nenhum resultado encontrado (esperado)")
        # Fallback
        title = search_term
        overview = 'Descrição não disponível'
        release_date = ''
        poster_path = None
        movie_id = abs(hash(search_term)) % 1000000  # ID único baseado no hash do nome
        print(f"✅ Usando fallback - ID: {movie_id}, Título: {title}")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
