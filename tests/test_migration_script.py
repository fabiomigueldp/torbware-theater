import pytest
import os
import json
import shutil
import sys

# Adiciona a pasta 'scripts' ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from migrate_library_metadata import migrate_metadata_files, normalize_language_code, sort_subtitles

# --- FIXTURES E SETUP ---

@pytest.fixture
def temp_library(tmp_path):
    """
    Cria uma estrutura de biblioteca temporária para os testes.
    Esta fixture será executada antes de cada teste que a solicitar.
    """
    # tmp_path é uma fixture do pytest que fornece um diretório temporário
    library_dir = tmp_path / "library"
    library_dir.mkdir()

    # --- Cenário 1: Metadado antigo, precisando de todas as migrações ---
    movie1_dir = library_dir / "101"
    movie1_dir.mkdir()
    metadata1 = {
        "id": "101",
        "title": "Meu Filme Em Portugues",
        "original_title": "My English Movie", # Título original diferente
        "overview": "Uma descrição.",
        "release_date": "2023-01-15",
        # Sem 'year'
        "subtitles": [
            {"language": "eng", "name": "English", "file": "sub1.vtt", "url": "/old/path/sub1.vtt"},
            {"language": "por", "name": "Portuguese", "file": "sub2.vtt", "url": "/old/path/sub2.vtt"},
            {"language": "pb", "name": "Brazilian", "file": "sub3.vtt", "url": "/old/path/sub3.vtt"} # Duplicata de pt-BR
        ]
    }
    with open(movie1_dir / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata1, f, indent=4)

    # --- Cenário 2: Metadado parcialmente correto ---
    movie2_dir = library_dir / "102"
    movie2_dir.mkdir()
    metadata2 = {
        "id": "102",
        "title": "Another Movie",
        "original_title": "Another Movie", # Títulos já iguais
        "year": 2022, # 'year' já presente
        "subtitles": [
            {"language": "en", "name": "English", "file": "sub_en.vtt"}, # Já normalizado
            {"language": "es", "name": "Español", "file": "sub_es.vtt"}
        ]
    }
    with open(movie2_dir / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata2, f, indent=4)

    # --- Cenário 3: Metadado sem legendas ---
    movie3_dir = library_dir / "103"
    movie3_dir.mkdir()
    metadata3 = {
        "id": "103",
        "title": "No Subtitle Movie",
        "original_title": "No Subtitle Movie",
        "release_date": "2021-10-10",
        # Sem campo 'subtitles'
    }
    with open(movie3_dir / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata3, f, indent=4)

    # Retorna o caminho para a biblioteca temporária para que o teste possa usá-lo
    return str(library_dir)


# --- TESTES ---

def test_migration_logic(temp_library, monkeypatch):
    """
    Testa o script de migração em uma biblioteca temporária.
    Verifica se os arquivos metadata.json são atualizados corretamente.
    """
    # Usamos monkeypatch para sobrescrever a constante LIBRARY_PATH no script
    # para que ele aponte para nossa pasta de teste.
    monkeypatch.setattr('migrate_library_metadata.LIBRARY_PATH', temp_library)

    # Também "enganamos" a confirmação do usuário para que o teste não pare
    monkeypatch.setattr('builtins.input', lambda _: 's')

    # Executa a função de migração
    migrate_metadata_files()

    # --- Verificações para o Filme 1 ---
    migrated_path1 = os.path.join(temp_library, "101", "metadata.json")
    assert os.path.exists(migrated_path1)

    with open(migrated_path1, 'r', encoding='utf-8') as f:
        data1 = json.load(f)

    # 1. Títulos devem ser o 'original_title'
    assert data1['title'] == "My English Movie"
    assert data1['original_title'] == "My English Movie"

    # 2. 'year' deve ter sido adicionado
    assert data1['year'] == 2023

    # 3. Legendas devem ter sido normalizadas, deduplicadas e ordenadas
    assert len(data1['subtitles']) == 2
    assert data1['subtitles'][0]['language'] == 'pt-BR'
    assert data1['subtitles'][1]['language'] == 'en'
    assert data1['subtitles'][0]['name'] == 'Português (Brasil)'
    assert data1['subtitles'][0]['url'] == '/api/subtitles/101/sub3.vtt' # URL corrigida

    # 4. Backup deve ter sido criado
    assert os.path.exists(migrated_path1 + ".bak")

    # --- Verificações para o Filme 2 ---
    migrated_path2 = os.path.join(temp_library, "102", "metadata.json")
    with open(migrated_path2, 'r', encoding='utf-8') as f:
        data2 = json.load(f)

    # Nenhuma mudança deveria ter ocorrido, então o backup não deve existir
    assert not os.path.exists(migrated_path2 + ".bak")
    assert data2['title'] == "Another Movie"
    assert len(data2['subtitles']) == 2 # Ordenação não mudou

    # --- Verificações para o Filme 3 ---
    migrated_path3 = os.path.join(temp_library, "103", "metadata.json")
    with open(migrated_path3, 'r', encoding='utf-8') as f:
        data3 = json.load(f)

    # O campo 'subtitles' deve ter sido adicionado como uma lista vazia
    assert 'subtitles' in data3
    assert data3['subtitles'] == []
    assert os.path.exists(migrated_path3 + ".bak") # Houve mudança
