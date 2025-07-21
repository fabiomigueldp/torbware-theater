from config import TMDB_API_KEY
import requests
import os
import sys
from poster_manager import PosterManager
import json

def test_poster_system():
    """Testa o sistema completo de posters para Sinners"""
    
    print("=== TESTE COMPLETO DO SISTEMA DE POSTERS PARA 'SINNERS' ===\n")
    
    # 1. Buscar filme no TMDB
    print("🔍 1. Buscando filme 'Sinners' no TMDB...")
    response = requests.get(f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query=Sinners')
    
    if response.status_code != 200:
        print(f"❌ Erro na API TMDB: {response.status_code}")
        return
    
    data = response.json()
    if not data.get('results'):
        print("❌ Filme não encontrado")
        return
    
    movie_data = data['results'][0]
    print(f"✅ Filme encontrado: {movie_data['title']} ({movie_data.get('release_date', 'N/A')[:4]})")
    print(f"   ID TMDB: {movie_data['id']}")
    print(f"   Poster path: {movie_data.get('poster_path')}")
    
    # 2. Configurar dados do filme para teste
    test_movie = {
        'id': 999999,  # ID fictício para teste
        'title': movie_data['title'],
        'tmdb_id': movie_data['id'],
        'poster_path': movie_data.get('poster_path')
    }
    
    print(f"\n🎬 2. Configurando filme de teste:")
    print(f"   ID local: {test_movie['id']}")
    print(f"   Título: {test_movie['title']}")
    print(f"   TMDB ID: {test_movie['tmdb_id']}")
    
    # 3. Criar diretório de teste
    test_dir = f"../library/{test_movie['id']}"
    print(f"\n📂 3. Criando diretório: {test_dir}")
    os.makedirs(test_dir, exist_ok=True)
    
    # 4. Inicializar PosterManager
    print("\n🔧 4. Inicializando PosterManager...")
    poster_manager = PosterManager(test_dir, test_movie)
    print("✅ PosterManager criado")
    
    # 5. Testar download e processamento
    print(f"\n⬇️ 5. Baixando e processando posters...")
    try:
        result = poster_manager.download_and_process_posters()
        
        if result:
            print("✅ Processamento concluído com sucesso!")
            print("\n📊 Resultados:")
            for size, path in result.items():
                print(f"   {size:>9}: {path}")
            
            # 6. Verificar arquivos gerados
            print(f"\n📁 6. Verificando arquivos gerados...")
            total_size = 0
            
            for size, path in result.items():
                full_path = os.path.join(test_dir, path.lstrip('/'))
                if os.path.exists(full_path):
                    file_size = os.path.getsize(full_path)
                    size_mb = file_size / (1024 * 1024)
                    total_size += file_size
                    print(f"   ✅ {size:>9}: {path} ({size_mb:.2f} MB)")
                else:
                    print(f"   ❌ {size:>9}: {path} (arquivo não encontrado)")
            
            print(f"\n📦 Tamanho total: {total_size / (1024 * 1024):.2f} MB")
            
            # 7. Testar sistema de fallback do frontend
            print(f"\n🌐 7. Testando URLs do frontend...")
            movie_with_posters = {**test_movie, 'posters': result}
            
            # Simular função getPosterUrl do frontend
            sizes = ['thumbnail', 'medium', 'large']
            for size in sizes:
                if result.get(size):
                    url = f"/library/{test_movie['id']}{result[size]}"
                    print(f"   {size:>9}: {url}")
                else:
                    print(f"   {size:>9}: fallback necessário")
            
            print(f"\n✅ Teste concluído com sucesso!")
            print(f"🎯 O filme '{test_movie['title']}' agora possui posters em múltiplos tamanhos!")
            
        else:
            print("❌ Falha no processamento dos posters")
            
    except Exception as e:
        print(f"❌ Erro durante o processamento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_poster_system()
