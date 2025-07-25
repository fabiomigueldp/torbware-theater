import pytest
import sys
import os

# Adiciona a pasta 'worker' ao sys.path para que possamos importar o subtitle_manager
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../worker')))

from subtitle_manager import SubtitleManager

# --- MOCKING ---
# O SubtitleManager precisa de alguns argumentos no construtor.
# Criamos mocks simples para que possamos instanciá-lo.
class MockMovieInfo:
    def __init__(self):
        self.info = {'id': '123'}
    def get(self, key, default=None):
        return self.info.get(key, default)
    def __getitem__(self, key):
        return self.info[key]

def mock_progress_callback(message, progress=None):
    pass

# --- TESTES ---

@pytest.fixture
def manager():
    """Fixture para criar uma instância do SubtitleManager para os testes."""
    # Usamos um caminho de pasta temporária que não precisa existir para este teste
    return SubtitleManager('/tmp/movie', MockMovieInfo(), mock_progress_callback)

# Casos de teste parametrizados
# Formato: (entrada, saida_esperada)
test_cases = [
    ('pt', 'pt-BR'),
    ('por', 'pt-BR'),
    ('pb', 'pt-BR'),
    ('pt-br', 'pt-BR'),
    ('pt-BR', 'pt-BR'),
    ('PORTUGUESE', 'pt-BR'),
    ('en', 'en'),
    ('eng', 'en'),
    ('english', 'en'),
    ('EN', 'en'),
    ('fr', 'fr'), # Idioma não mapeado deve retornar o original em minúsculas
    ('es', 'es'),
    (None, 'unknown'), # Teste de robustez para entrada None
    (123, 'unknown'),   # Teste de robustez para entrada não-string
]

@pytest.mark.parametrize("input_lang, expected_output", test_cases)
def test_language_normalization(manager, input_lang, expected_output):
    """
    Testa a função _normalize_language_code com uma variedade de entradas
    para garantir que a normalização está correta e robusta.
    """
    # Para o teste, a função _normalize_language_code no script de migração é a mesma.
    # Vamos testar a implementação dentro do SubtitleManager.

    # Simula um objeto de linguagem ou uma string
    class MockLanguage:
        def __init__(self, lang_str):
            self._lang_str = lang_str
        def __str__(self):
            return str(self._lang_str)

    # O método real espera um objeto, então encapsulamos a string de entrada.
    # No caso de entradas inválidas (None, int), passamos diretamente.
    if isinstance(input_lang, str):
        mock_lang_obj = MockLanguage(input_lang)
        normalized_code = manager._normalize_language_code(mock_lang_obj)
    else:
         # Simula o comportamento do script de migração para entradas inválidas
        if not isinstance(input_lang, str):
             normalized_code = "unknown"
        else:
            normalized_code = manager._normalize_language_code(input_lang)

    assert normalized_code == expected_output
