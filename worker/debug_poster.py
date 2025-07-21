import requests
from config import TMDB_API_KEY

def debug_poster_download():
    """Debug detalhado do download de poster"""
    
    print("=== DEBUG DETALHADO DO DOWNLOAD DE POSTER ===\n")
    
    poster_path = '/4CkZl1LK6a5rXBqJB2ZP77h3N5i.jpg'
    base_url = "https://image.tmdb.org/t/p/"
    sizes = {'thumbnail': 'w154', 'medium': 'w342', 'large': 'w500'}
    
    for size_name, tmdb_size in sizes.items():
        print(f"🔍 Testando {size_name} ({tmdb_size})...")
        
        url = f"{base_url}{tmdb_size}{poster_path}"
        print(f"   URL: {url}")
        
        try:
            # Teste HEAD primeiro
            head_response = requests.head(url, timeout=10)
            print(f"   HEAD Status: {head_response.status_code}")
            print(f"   Content-Type: {head_response.headers.get('content-type')}")
            print(f"   Content-Length: {head_response.headers.get('content-length')}")
            
            if head_response.status_code == 200:
                # Agora teste GET
                response = requests.get(url, stream=True, timeout=30)
                print(f"   GET Status: {response.status_code}")
                print(f"   GET Content-Type: {response.headers.get('content-type')}")
                
                # Verificar validação
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content) if hasattr(response, 'content') else 'N/A'
                
                print(f"   Content length: {content_length}")
                print(f"   Is image content-type: {content_type.startswith('image/')}")
                
                if content_type.startswith('image/'):
                    # Verificar tamanho do conteúdo
                    actual_content = response.content
                    print(f"   Actual content size: {len(actual_content)} bytes")
                    print(f"   Size > 1024: {len(actual_content) > 1024}")
                    
                    # Salvar para teste
                    test_file = f"test_{size_name}.jpg"
                    with open(test_file, 'wb') as f:
                        f.write(actual_content)
                    print(f"   ✅ Salvo em {test_file}")
                    
                    # Verificar se é imagem válida
                    try:
                        from PIL import Image
                        with Image.open(test_file) as img:
                            print(f"   ✅ Imagem válida: {img.size}")
                    except Exception as e:
                        print(f"   ❌ Erro PIL: {e}")
                else:
                    print(f"   ❌ Content-type inválido")
            else:
                print(f"   ❌ HEAD falhou")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        print()

if __name__ == "__main__":
    debug_poster_download()
