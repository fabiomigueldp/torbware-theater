from config import TMDB_API_KEY
import requests

def test_sinners_search():
    """Testa busca por filme Sinners no TMDB"""
    
    print("=== TESTE DE BUSCA POR 'SINNERS' ===\n")
    
    # Buscar por diferentes variações de Sinners
    terms = ['Sinners', 'Sinners 2025', 'The Sinners', 'Seven Sinners']
    movie_found = None
    
    for term in terms:
        print(f"🔍 Buscando: '{term}'")
        response = requests.get(f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={term}')
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                movie = data['results'][0]
                print(f"  ✅ Encontrado: {movie['title']} ({movie.get('release_date', 'N/A')[:4]})")
                print(f"  📋 ID TMDB: {movie['id']}")
                print(f"  🖼️ Poster: {movie.get('poster_path', 'N/A')}")
                movie_found = movie
                break
            else:
                print(f"  ❌ Nenhum resultado")
        else:
            print(f"  ❌ Erro HTTP {response.status_code}")
    
    if movie_found:
        poster_path = movie_found.get('poster_path')
        if poster_path:
            poster_url = f'https://image.tmdb.org/t/p/w500{poster_path}'
            print(f"\n🌐 URL completa do poster: {poster_url}")
            
            # Testar se o poster existe
            print("📡 Testando disponibilidade do poster...")
            response = requests.head(poster_url)
            print(f"   Status HTTP: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ Poster disponível para download")
                content_length = response.headers.get('content-length')
                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    print(f"   📦 Tamanho: {size_mb:.2f} MB")
            else:
                print("   ❌ Poster não disponível")
        else:
            print("\n❌ Filme não possui poster_path")
            
        return movie_found
    else:
        print("\n🔄 Nenhum filme 'Sinners' encontrado. Testando com 'Inception' como exemplo...")
        response = requests.get(f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query=Inception')
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                movie_found = data['results'][0]
                print(f"✅ Filme de teste: {movie_found['title']}")
                print(f"🖼️ Poster: {movie_found.get('poster_path')}")
                return movie_found
        
        print("❌ Erro ao buscar filme de teste")
        return None

if __name__ == "__main__":
    movie = test_sinners_search()
    
    if movie:
        print(f"\n🎬 Filme selecionado para teste: {movie['title']}")
        print("✨ Pronto para testar o sistema de posters!")
    else:
        print("\n❌ Nenhum filme disponível para teste")
