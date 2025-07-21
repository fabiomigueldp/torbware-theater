#!/usr/bin/env python3
"""
Script de teste para investigar problema com babelfish Language
"""

import sys
import traceback

def test_babelfish_imports():
    """Testa imports do babelfish"""
    print("=== TESTE DE IMPORTS ===")
    
    try:
        from babelfish import Language
        print("✅ Import babelfish.Language: OK")
    except Exception as e:
        print(f"❌ Import babelfish.Language: {e}")
        return False
    
    try:
        import subliminal
        print("✅ Import subliminal: OK")
    except Exception as e:
        print(f"❌ Import subliminal: {e}")
        return False
    
    return True

def test_language_creation():
    """Testa criação de objetos Language"""
    print("\n=== TESTE DE CRIAÇÃO DE LANGUAGE ===")
    
    from babelfish import Language
    
    # Testa diferentes formas de criar Language objects
    test_cases = [
        # (descrição, código, deve_funcionar)
        ("Inglês alpha2", "en", True),
        ("Português alpha2", "pt", True),
        ("Português Brasil", "pt-BR", True),
        ("Português Brasil alternativo", "pt_BR", True),
        ("Código inválido", "xx", False),
    ]
    
    for desc, code, should_work in test_cases:
        try:
            lang = Language(code)
            print(f"✅ {desc} ({code}): {lang} - alpha2: {lang.alpha2}")
        except Exception as e:
            if should_work:
                print(f"❌ {desc} ({code}): ERRO - {e}")
            else:
                print(f"⚠️  {desc} ({code}): Erro esperado - {e}")

def test_subliminal_languages():
    """Testa como criar languages para o Subliminal"""
    print("\n=== TESTE SUBLIMINAL LANGUAGES ===")
    
    from babelfish import Language
    
    try:
        # Testa criação de set de languages como no código original
        languages = {Language('en'), Language('pt-BR'), Language('pt')}
        print(f"✅ Set de languages criado: {languages}")
        
        for lang in languages:
            print(f"   - {lang}: alpha2={lang.alpha2}, alpha3={lang.alpha3}")
    
    except Exception as e:
        print(f"❌ Erro ao criar set de languages: {e}")
        traceback.print_exc()

def test_subliminal_video():
    """Testa criação de objeto Video do Subliminal"""
    print("\n=== TESTE SUBLIMINAL VIDEO ===")
    
    try:
        from subliminal import Video
        
        # Cria um objeto Video como no código original
        fake_video_path = "/tmp/test_video.mp4"
        video = Video.fromname(fake_video_path)
        
        print(f"✅ Video object criado: {video}")
        print(f"   - Name: {video.name}")
        print(f"   - Title: {getattr(video, 'title', 'N/A')}")
        print(f"   - Year: {getattr(video, 'year', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Erro ao criar Video object: {e}")
        traceback.print_exc()

def test_download_simulation():
    """Simula o download de legendas sem fazer o download real"""
    print("\n=== SIMULAÇÃO DE DOWNLOAD ===")
    
    try:
        from subliminal import Video, download_best_subtitles
        from babelfish import Language
        
        # Configura um video fake
        fake_video_path = "/tmp/Sinners.2025.720p.WEBRip.x264.AAC-YTS.MX.mp4"
        video = Video.fromname(fake_video_path)
        video.title = "Sinners"
        video.year = 2025
        
        # Configura languages
        languages = {Language('en'), Language('pt')}
        
        print(f"Video configurado: {video}")
        print(f"Languages: {languages}")
        print(f"Tentando buscar legendas (pode falhar por não ter arquivo real)...")
        
        # Tenta download (vai falhar mas vamos ver o erro)
        subtitles = download_best_subtitles([video], languages)
        print(f"✅ Subtitles encontradas: {subtitles}")
        
    except Exception as e:
        print(f"⚠️  Erro esperado (arquivo não existe): {e}")
        # Isso é esperado já que o arquivo não existe

if __name__ == "__main__":
    print("🔍 INVESTIGAÇÃO DE PROBLEMA COM BABELFISH/SUBLIMINAL")
    print("=" * 60)
    
    if not test_babelfish_imports():
        print("❌ Falha nos imports básicos")
        sys.exit(1)
    
    test_language_creation()
    test_subliminal_languages()
    test_subliminal_video()
    test_download_simulation()
    
    print("\n" + "=" * 60)
    print("🏁 TESTE CONCLUÍDO")
