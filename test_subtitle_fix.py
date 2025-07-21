#!/usr/bin/env python3
"""
Teste específico do sistema de legendas corrigido
"""

print("=== TESTE DO SISTEMA DE LEGENDAS CORRIGIDO ===")

# Teste básico dos códigos de idioma
print("\n1. Testando criação de Language objects:")
try:
    from babelfish import Language
    
    # Testar códigos corretos
    eng = Language('eng')
    por = Language('por')
    por_br = Language('por', country='BR')
    
    print(f"✓ Inglês: {eng}")
    print(f"✓ Português: {por}") 
    print(f"✓ Português BR: {por_br}")
    
    # Testar função de mapeamento
    print("\n2. Testando mapeamento de códigos:")
    
    def test_get_language_code(language):
        """Versão de teste da função _get_language_code"""
        if hasattr(language, 'alpha3'):
            if language.alpha3 == 'eng':
                return 'en'
            elif language.alpha3 == 'por':
                if hasattr(language, 'country') and language.country and language.country.name == 'Brazil':
                    return 'pt-BR'
                return 'pt'
        
        lang_str = str(language)
        if lang_str == 'en':
            return 'en'
        elif lang_str == 'pt-BR':
            return 'pt-BR'
        elif lang_str == 'pt':
            return 'pt'
        
        return lang_str
    
    print(f"  Inglês (eng) → {test_get_language_code(eng)}")
    print(f"  Português (por) → {test_get_language_code(por)}")
    print(f"  Português BR (por+BR) → {test_get_language_code(por_br)}")
    
except Exception as e:
    print(f"✗ Erro no teste: {e}")
    import traceback
    traceback.print_exc()

print("\n3. Testando Subliminal:")
try:
    from subliminal import Video, download_best_subtitles
    
    # Criar um video object fake para teste
    video_path = "/tmp/test_video.mp4"
    
    # Criar arquivo fake
    with open(video_path, "w") as f:
        f.write("fake video content")
    
    video = Video.fromname(video_path)
    video.title = "Test Movie"
    video.year = 2023
    
    print(f"✓ Video object criado: {video}")
    
    # Testar busca de legendas (sem baixar)
    languages = {
        Language('eng'),
        Language('por', country='BR'),
        Language('por')
    }
    
    print(f"✓ Languages set criado: {languages}")
    print("  Nota: Não vamos baixar legendas neste teste")
    
    # Limpar arquivo fake
    import os
    if os.path.exists(video_path):
        os.remove(video_path)
    
except Exception as e:
    print(f"✗ Erro no teste Subliminal: {e}")

print("\n=== TESTE CONCLUÍDO ===")
