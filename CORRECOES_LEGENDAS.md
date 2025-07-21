# CORREÇÕES IMPLEMENTADAS NO SISTEMA DE LEGENDAS

## 📋 RESUMO DAS MUDANÇAS

As seguintes correções foram implementadas para resolver os problemas identificados no sistema de legendas:

---

## 🔧 ALTERAÇÕES NO `worker/main.py`

### 1. **Controle de Limpeza Condicional**
**Problema:** Arquivos temporários eram sempre removidos, mesmo se o processamento falhasse.

**Solução:**
```python
# Adicionada variável de controle
processing_successful = False

# Limpeza condicional no finally
if 'processing_successful' in locals() and processing_successful:
    print(f"Processamento concluído com sucesso. Limpando diretório temporário: {job_temp_dir}")
    shutil.rmtree(job_temp_dir, ignore_errors=True)
else:
    print(f"Processamento falhou. Mantendo arquivos temporários para debug: {job_temp_dir}")
```

### 2. **Verificação de Integridade das Legendas**
**Problema:** Metadados eram salvos sem verificar se os arquivos de legenda realmente existiam.

**Solução:**
```python
# Verificação antes de salvar metadados
verified_subtitles = []
if subtitle_info:
    for subtitle in subtitle_info:
        subtitle_path = os.path.join(movie_library_path, 'subtitles', subtitle['file'])
        if os.path.exists(subtitle_path):
            verified_subtitles.append(subtitle)
            print(f"✓ Legenda verificada: {subtitle['name']}")
        else:
            print(f"✗ AVISO: Arquivo não encontrado: {subtitle_path}")

metadata["subtitles"] = verified_subtitles  # Usa apenas legendas verificadas
```

### 3. **Logs Detalhados para Debug**
**Problema:** Falta de informações detalhadas durante o processamento.

**Solução:**
```python
print(f"=== INICIANDO DOWNLOAD DE LEGENDAS ===")
print(f"Informações do filme para legendas:")
print(f"  - ID: {movie_info['id']}")
print(f"  - Título: {movie_info['title']}")
print(f"  - Arquivo de vídeo: {movie_info['video_file']}")
print(f"Resultado: {len(subtitle_info)} legendas encontradas")
```

---

## 🎯 ALTERAÇÕES NO `worker/subtitle_manager.py`

### 1. **Sistema de Retry para Downloads**
**Problema:** Falhas temporárias causavam perda completa de legendas.

**Solução:**
```python
def download_subtitles(self):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return self._download_subtitles_attempt()
        except Exception as e:
            if attempt == max_retries - 1:
                return []
            time.sleep(2)  # Aguarda antes de tentar novamente
```

### 2. **Verificação Robusta de Arquivos Criados**
**Problema:** Arquivos WebVTT não eram verificados após criação.

**Solução:**
```python
def _convert_to_webvtt(self, subtitle_path, lang_code):
    # ... conversão ...
    
    # Verificar se arquivo foi criado corretamente
    if os.path.exists(webvtt_path):
        file_size = os.path.getsize(webvtt_path)
        self.report_progress(f"✓ WebVTT criado: {webvtt_filename} ({file_size} bytes)")
        return webvtt_path
    else:
        raise Exception(f"Arquivo WebVTT não foi criado: {webvtt_path}")
```

### 3. **Garantia de Criação de Diretórios**
**Problema:** Pasta de legendas poderia não existir.

**Solução:**
```python
def _convert_to_webvtt(self, subtitle_path, lang_code):
    # Garantir que pasta de destino existe
    os.makedirs(self.subtitles_folder, exist_ok=True)
```

### 4. **Logs Detalhados na Função Principal**
**Problema:** Falta de visibilidade do processo interno.

**Solução:**
```python
def download_and_process_subtitles(movie_folder, movie_info, progress_callback=None):
    print(f"=== INICIANDO PROCESSAMENTO DE LEGENDAS ===")
    print(f"Pasta do filme: {movie_folder}")
    
    # ... processamento ...
    
    # Verificar pasta final
    if os.path.exists(subtitle_folder):
        vtt_files = [f for f in os.listdir(subtitle_folder) if f.endswith('.vtt')]
        print(f"Arquivos .vtt na pasta final: {vtt_files}")
    
    print(f"=== PROCESSAMENTO CONCLUÍDO: {len(subtitle_info)} legendas ===")
```

### 5. **Limpeza Cautelosa de Temporários**
**Problema:** Arquivos eram removidos sem logs adequados.

**Solução:**
```python
def cleanup_temp(self):
    if os.path.exists(self.temp_folder):
        temp_files = os.listdir(self.temp_folder)
        if temp_files:
            print(f"Arquivos a serem removidos: {temp_files}")
        shutil.rmtree(self.temp_folder, ignore_errors=True)
        print("Limpeza concluída")
```

---

## 🛠️ SCRIPTS DE DEBUG CRIADOS

### 1. **debug_system.py**
Script para verificar dependências e configuração fora do container.

### 2. **debug_container.sh**
Script bash para executar dentro do container Docker e verificar o ambiente.

### 3. **test_subtitles.py**
Script para testar o sistema de legendas isoladamente.

---

## 🚀 COMO TESTAR AS CORREÇÕES

### 1. **Reconstruir o Container**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 2. **Executar Debug no Container**
```bash
docker exec -it torbware_theater bash
chmod +x debug_container.sh
./debug_container.sh
```

### 3. **Testar com um Filme**
1. Adicionar um magnet link através da interface
2. Acompanhar logs detalhados no console do container
3. Verificar se legendas são criadas em `/app/library/{movie_id}/subtitles/`

### 4. **Verificar Logs do Container**
```bash
docker logs torbware_theater -f
```

---

## 📊 PONTOS DE VERIFICAÇÃO

### ✅ **Antes do Processamento**
- [ ] Arquivo de vídeo existe na pasta temporária
- [ ] Informações do filme estão corretas
- [ ] Pasta de destino foi criada

### ✅ **Durante o Download**
- [ ] Subliminal encontra legendas online
- [ ] Arquivos SRT são baixados para pasta temporária
- [ ] Sincronização executa sem erros (se aplicável)

### ✅ **Durante a Conversão**
- [ ] Pasta `/subtitles` é criada no destino final
- [ ] Arquivos WebVTT são gerados corretamente
- [ ] Tamanho dos arquivos é verificado

### ✅ **Após o Processamento**
- [ ] Arquivos WebVTT existem na pasta final
- [ ] Metadados contêm apenas legendas verificadas
- [ ] Limpeza só ocorre se tudo funcionou

### ✅ **Na Interface**
- [ ] Botão de legendas aparece se há legendas disponíveis
- [ ] URLs das legendas respondem corretamente
- [ ] Player HTML5 carrega e exibe legendas

---

## 🔍 DEBUGGING EM CASO DE PROBLEMAS

### 1. **Legendas não aparecem**
```bash
# Verificar se arquivos existem
docker exec torbware_theater ls -la /app/library/{movie_id}/subtitles/

# Verificar metadados
docker exec torbware_theater cat /app/library/{movie_id}/metadata.json
```

### 2. **Erro de dependências**
```bash
# Verificar instalação dentro do container
docker exec torbware_theater pip3 list | grep subliminal
```

### 3. **Erro de permissões**
```bash
# Verificar permissões das pastas
docker exec torbware_theater ls -ld /app/library /app/tmp
```

---

## 📈 MELHORIAS FUTURAS SUGERIDAS

1. **Cache de Legendas:** Reutilizar legendas já baixadas para filmes similares
2. **Múltiplas Fontes:** Adicionar outros provedores além do Subliminal
3. **Interface Aprimorada:** Permitir upload manual de legendas
4. **Sincronização Avançada:** Melhorar algoritmos de sync temporal
5. **Compressão:** Compactar arquivos WebVTT para economia de espaço

---

*Correções implementadas em: 21 de julho de 2025*
*Status: Pronto para teste*
