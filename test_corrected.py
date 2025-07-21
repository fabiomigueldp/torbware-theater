#!/usr/bin/env python3
"""
Teste final com a lógica corrigida
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
    
    # Teste com Avatar
    search_term = "Avatar"
    print(f"Testando busca por: '{search_term}'")
    
    movie = Movie()
    search_results = movie.search(search_term)
    
    print(f"Total de resultados: {search_results.total_results}")
    
    if search_results.total_results > 0 and hasattr(search_results, 'results'):
        results_list = search_results.results
        print(f"Acessando lista de resultados, tipo: {type(results_list)}")
        
        # O objeto AsObj funciona como uma lista, então podemos iterar
        first_result = None
        try:
            # Tentar acessar primeiro item
            if hasattr(results_list, '__getitem__'):
                first_result = results_list[0]
                print(f"Primeiro resultado via __getitem__")
            elif hasattr(results_list, '__iter__'):
                for item in results_list:
                    first_result = item
                    break
                print(f"Primeiro resultado via iteração")
            
            if not first_result:
                print("Não foi possível acessar primeiro resultado")
            else:
                print(f"Primeiro resultado obtido: {type(first_result)}")
                
                # Extrair ID do primeiro resultado
                movie_id = None
                if hasattr(first_result, 'id'):
                    movie_id = first_result.id
                    print(f"ID via atributo: {movie_id}")
                elif isinstance(first_result, dict) and 'id' in first_result:
                    movie_id = first_result['id']
                    print(f"ID via dict: {movie_id}")
                
                if movie_id:
                    print(f"Filme encontrado - ID: {movie_id}")
                    
                    # Busca detalhes do filme
                    movie_details = movie.details(movie_id)
                    print(f"Detalhes obtidos: {type(movie_details)}")
                    
                    # Acesso seguro aos atributos dos detalhes
                    title = getattr(movie_details, 'title', 'Título não encontrado')
                    print(f"Título: {title}")
                    
                    print("✅ Teste passou!")
                else:
                    print("❌ Não foi possível extrair ID")
                    
        except Exception as access_error:
            print(f"❌ Erro ao acessar primeiro resultado: {access_error}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Nenhum resultado encontrado")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
