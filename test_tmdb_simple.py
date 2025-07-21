#!/usr/bin/env python3
"""
Script de teste para verificar a API do TMDB e estrutura dos objetos retornados
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
    
    print(f"API Key configurada: {config.TMDB_API_KEY[:10]}...")
    
    # Teste de busca
    search_term = "Pecos Pest 1955"
    print(f"\nTestando busca por: '{search_term}'")
    
    movie = Movie()
    results = movie.search(search_term)
    
    print(f"Resultados encontrados: {len(results)}")
    print(f"Tipo de results: {type(results)}")
    
    if results and len(results) > 0:
        print("Tentando acessar primeiro resultado...")
        
        # Debug: vamos ver o que está em results
        print(f"Results é uma lista? {isinstance(results, list)}")
        print(f"Results tem atributo __iter__? {hasattr(results, '__iter__')}")
        print(f"Results: {results}")
        
        # Tenta diferentes maneiras de acessar
        try:
            first_result = None
            for i, result in enumerate(results):
                if i == 0:
                    first_result = result
                    break
            
            if first_result:
                print(f"Primeiro resultado obtido via loop")
                print(f"Tipo: {type(first_result)}")
                
                # Tentar acessar ID
                movie_id = None
                if hasattr(first_result, 'id'):
                    movie_id = first_result.id
                    print(f"ID via atributo: {movie_id}")
                elif hasattr(first_result, '__dict__') and 'id' in first_result.__dict__:
                    movie_id = first_result.__dict__['id']
                    print(f"ID via __dict__: {movie_id}")
                
                if movie_id:
                    print(f"Buscando detalhes para ID: {movie_id}")
                    movie_details = movie.details(movie_id)
                    print(f"Detalhes obtidos: {type(movie_details)}")
                    
                    # Tentar acessar título
                    if hasattr(movie_details, 'title'):
                        print(f"Título: {movie_details.title}")
                    else:
                        print("Título não encontrado como atributo")
                        
        except Exception as e:
            print(f"Erro durante teste: {e}")
            import traceback
            traceback.print_exc()
        
    else:
        print("Nenhum resultado encontrado ou lista vazia")
        
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Certifique-se de que as dependências estão instaladas")
except Exception as e:
    print(f"Erro geral: {e}")
    import traceback
    traceback.print_exc()
