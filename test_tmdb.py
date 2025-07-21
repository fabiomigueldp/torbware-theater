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
    
    if results:
        print("Tentando acessar primeiro resultado...")
        try:
            # Método mais seguro para acessar primeiro item
            if hasattr(results, '__getitem__'):
                first_result = results.__getitem__(0)
                print(f"Primeiro resultado obtido via __getitem__")
            else:
                first_result = results[0]
                print(f"Primeiro resultado obtido via indexação direta")
            
            print(f"Primeiro resultado (tipo: {type(first_result)}):")
        except Exception as e:
            print(f"Erro ao acessar primeiro resultado: {e}")
            first_result = None
        
        if first_result:
            # Método mais seguro para acessar ID
        try:
            if hasattr(first_result, 'id'):
                movie_id = first_result.id
                print(f"  ID via atributo: {movie_id}")
            elif hasattr(first_result, '__getitem__'):
                movie_id = first_result['id']
                print(f"  ID via indexação: {movie_id}")
            else:
                print(f"  Estrutura do primeiro resultado: {first_result}")
                print(f"  Dir do primeiro resultado: {dir(first_result)}")
                # Tentar acessar como dicionário se for possível
                if isinstance(first_result, dict):
                    movie_id = first_result.get('id', None)
                    print(f"  ID via get: {movie_id}")
                else:
                    movie_id = None
                    print("  Não foi possível extrair ID")
                    
        except Exception as e:
            print(f"  Erro ao acessar ID: {e}")
            movie_id = None
        
        if movie_id:
            print(f"  Usando ID: {movie_id}")
            
            # Buscar detalhes
            try:
                movie_details = movie.details(movie_id)
                print(f"\nDetalhes do filme (tipo: {type(movie_details)}):")
                
                # Tentar acessar campos de forma mais robusta
                print("\nTentando acessar campos:")
                
                # Título
                try:
                    if hasattr(movie_details, 'title'):
                        title = movie_details.title
                        print(f"  Title (atributo): {title}")
                    elif isinstance(movie_details, dict) and 'title' in movie_details:
                        title = movie_details['title']
                        print(f"  Title (dict): {title}")
                    else:
                        print(f"  Title não encontrado. Tipo: {type(movie_details)}, Dir: {dir(movie_details)}")
                except Exception as e:
                    print(f"  Erro ao acessar title: {e}")
                
                # Overview
                try:
                    if hasattr(movie_details, 'overview'):
                        overview = movie_details.overview
                        print(f"  Overview (atributo): {overview[:50]}...")
                    elif isinstance(movie_details, dict) and 'overview' in movie_details:
                        overview = movie_details['overview']
                        print(f"  Overview (dict): {overview[:50]}...")
                    else:
                        print(f"  Overview não encontrado")
                except Exception as e:
                    print(f"  Erro ao acessar overview: {e}")
                    
            except Exception as e:
                print(f"  Erro ao buscar detalhes: {e}")
        else:
            print("  Não foi possível obter ID do filme")
            
    else:
        print("Nenhum resultado encontrado")
        
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Certifique-se de que as dependências estão instaladas")
except Exception as e:
    print(f"Erro geral: {e}")
