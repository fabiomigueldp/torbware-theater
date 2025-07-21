#!/usr/bin/env python3
"""
Script de teste simples para verificar nova implementação
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
    search_results = movie.search(search_term)
    
    print(f"Resultado da busca: {search_results}")
    print(f"Tipo: {type(search_results)}")
    
    # Acesso correto aos resultados da busca
    if hasattr(search_results, 'results') and search_results.results:
        results_list = search_results.results
        print(f"Lista de resultados: {results_list}")
        print(f"Tipo da lista: {type(results_list)}")
        
        # Verificar se é um dicionário de resultados ou uma lista
        if isinstance(results_list, dict):
            print("É um dicionário")
            if results_list:
                first_key = list(results_list.keys())[0]
                first_result = results_list[first_key]
                print(f"Primeira chave: {first_key}, Primeiro resultado: {first_result}")
        elif isinstance(results_list, (list, tuple)) and len(results_list) > 0:
            print("É uma lista/tupla")
            first_result = results_list[0]
            print(f"Primeiro resultado: {first_result}")
        else:
            print("Formato de resultados não reconhecido")
    else:
        print("Nenhum resultado encontrado")
        # Tentar abordagem alternativa
        print("Tentando abordagem direta...")
        print(f"search_results.total_results: {getattr(search_results, 'total_results', 'não encontrado')}")
        
        # Verificar se há outro atributo
        for attr in dir(search_results):
            if not attr.startswith('_'):
                value = getattr(search_results, attr)
                print(f"Atributo {attr}: {value}")
        
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
