import os
import json
import re

# --- CONFIGURAÇÕES ---
# Obtém o caminho do diretório do script e sobe um nível para a raiz do projeto
# Isso torna o script executável de qualquer lugar, desde que esteja em /scripts
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LIBRARY_PATH = os.path.join(ROOT_DIR, 'library')
print(f"Raiz do projeto detectada em: {ROOT_DIR}")
print(f"Pasta da biblioteca: {LIBRARY_PATH}")

# --- FUNÇÕES DE NORMALIZAÇÃO (replicadas do worker/subtitle_manager.py) ---

def normalize_language_code(language: str) -> str:
    """
    Normaliza códigos de idioma para um padrão consistente.
    Mapeia variações de português para 'pt-BR' e inglês para 'en'.
    """
    if not isinstance(language, str):
        return 'unknown' # Lida com casos de dados malformados

    lang_lower = language.lower()

    # Mapeamentos para Português (Brasil)
    if lang_lower in ['pt', 'por', 'pb', 'pt-br', 'portuguese', 'brazilian portuguese']:
        return 'pt-BR'

    # Mapeamentos para Inglês
    if lang_lower in ['en', 'eng', 'english']:
        return 'en'

    # Para outros idiomas, podemos adicionar mais mapeamentos ou apenas retornar o código
    # Por enquanto, retorna o código original em minúsculas se não for um dos acima
    return lang_lower

def get_language_name(lang_code: str) -> str:
    """Retorna um nome amigável para o código de idioma normalizado."""
    names = {
        'pt-BR': 'Português (Brasil)',
        'en': 'English'
    }
    # Retorna o nome mapeado ou o próprio código como fallback
    return names.get(lang_code, lang_code)

def sort_subtitles(subtitles: list) -> list:
    """
    Ordena as legendas com a prioridade: pt-BR, en, depois alfabeticamente.
    """
    def get_sort_key(subtitle):
        lang_code = subtitle.get('language', 'unknown')
        if lang_code == 'pt-BR':
            return (0, lang_code)  # Prioridade máxima
        if lang_code == 'en':
            return (1, lang_code)  # Segunda prioridade
        return (2, lang_code)  # Demais, ordenados alfabeticamente

    return sorted(subtitles, key=get_sort_key)

# --- FUNÇÃO PRINCIPAL DA MIGRAÇÃO ---

def migrate_metadata_files():
    """
    Percorre todos os arquivos metadata.json na biblioteca e os normaliza
    para o novo padrão.
    """
    if not os.path.exists(LIBRARY_PATH):
        print(f"AVISO: A pasta da biblioteca '{LIBRARY_PATH}' não foi encontrada. Nada a fazer.")
        return

    print("\nIniciando a migração dos metadados da biblioteca...")
    migrated_count = 0
    error_count = 0

    # Percorre todas as subpastas da biblioteca (cada uma é um filme)
    for movie_id in os.listdir(LIBRARY_PATH):
        movie_path = os.path.join(LIBRARY_PATH, movie_id)
        metadata_path = os.path.join(movie_path, 'metadata.json')

        if os.path.isfile(metadata_path):
            print(f"\nProcessando: {metadata_path}")
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # --- LÓGICA DE MIGRAÇÃO ---
                changes_made = False

                # 1. Normalizar Títulos: title e original_title devem ser iguais
                # Priorizamos o original_title se ele existir e parecer válido
                original_title = metadata.get('original_title')
                title = metadata.get('title')

                final_title = original_title if original_title else title

                if metadata.get('title') != final_title:
                    print(f"  - Título atualizado: '{metadata.get('title')}' -> '{final_title}'")
                    metadata['title'] = final_title
                    changes_made = True

                if metadata.get('original_title') != final_title:
                    print(f"  - Título original atualizado: '{metadata.get('original_title')}' -> '{final_title}'")
                    metadata['original_title'] = final_title
                    changes_made = True

                # 2. Garantir campo 'year' a partir de 'release_date'
                if 'release_date' in metadata and 'year' not in metadata:
                    release_date = metadata['release_date']
                    if release_date and isinstance(release_date, str) and len(release_date) >= 4:
                        year = int(release_date[:4])
                        metadata['year'] = year
                        print(f"  - Campo 'year' adicionado: {year}")
                        changes_made = True

                # 3. Normalizar e Ordenar Legendas
                if 'subtitles' in metadata and isinstance(metadata['subtitles'], list):
                    original_subtitles = metadata['subtitles'].copy()

                    # Deduplicação por idioma (a última ocorrência vence)
                    deduped_subtitles = {}
                    for sub in metadata['subtitles']:
                        if not isinstance(sub, dict) or 'language' not in sub:
                            continue # Ignora entradas malformadas

                        lang_code = normalize_language_code(sub['language'])

                        # Atualiza a legenda com dados normalizados
                        sub['language'] = lang_code
                        sub['name'] = get_language_name(lang_code)

                        # Garante que a URL está no formato correto
                        sub_filename = sub.get('file')
                        if sub_filename:
                            expected_url = f"/api/subtitles/{movie_id}/{sub_filename}"
                            if sub.get('url') != expected_url:
                                sub['url'] = expected_url

                        deduped_subtitles[lang_code] = sub

                    # Ordena as legendas
                    sorted_subtitles = sort_subtitles(list(deduped_subtitles.values()))

                    # Compara a lista final com a original para ver se houve mudança
                    if json.dumps(sorted_subtitles) != json.dumps(original_subtitles):
                        print("  - Legendas normalizadas e reordenadas.")
                        metadata['subtitles'] = sorted_subtitles
                        changes_made = True
                else:
                    # Garante que o campo 'subtitles' exista como uma lista vazia
                    if 'subtitles' not in metadata:
                        metadata['subtitles'] = []
                        changes_made = True

                # --- SALVAR ARQUIVO (se houver mudanças) ---
                if changes_made:
                    # Cria um backup do arquivo original por segurança
                    backup_path = metadata_path + '.bak'
                    print(f"  - Salvando backup em: {backup_path}")
                    os.rename(metadata_path, backup_path)

                    # Salva o novo arquivo de metadados formatado
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=4)

                    print("  - ✅ Migração concluída para este filme.")
                    migrated_count += 1
                else:
                    print("  - Nenhuma mudança necessária.")

            except json.JSONDecodeError:
                print(f"  - ERRO: Arquivo JSON inválido: {metadata_path}")
                error_count += 1
            except Exception as e:
                print(f"  - ERRO: Ocorreu um erro inesperado: {e}")
                error_count += 1

    print("\n--- Relatório da Migração ---")
    print(f"Filmes processados: {migrated_count + error_count}")
    print(f"✅ Filmes migrados com sucesso: {migrated_count}")
    if error_count > 0:
        print(f"❌ Filmes com erro: {error_count}")
    print("-----------------------------\n")
    if migrated_count > 0:
        print("IMPORTANTE: Verifique os arquivos `metadata.json.bak` para confirmar as mudanças.")
        print("Se tudo estiver correto, você pode remover os backups com segurança.")


if __name__ == "__main__":
    # Confirmação do usuário para evitar execução acidental
    confirm = input("Este script irá modificar os arquivos `metadata.json` na sua biblioteca. "
                    "Backups (.bak) serão criados.\nVocê deseja continuar? (s/n): ")
    if confirm.lower() == 's':
        migrate_metadata_files()
    else:
        print("Migração cancelada pelo usuário.")
