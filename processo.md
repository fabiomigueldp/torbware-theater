# PROCESSO COMPLETO - Theater System
## Análise Detalhada do Fluxo de Processamento de Mídia e Sistema de Legendas

### 📋 VISÃO GERAL DO SISTEMA

O Theater System é uma aplicação de streaming pessoal que processa arquivos de mídia baixados via torrent e os converte para streaming HLS com suporte a legendas. O sistema é composto por:

1. **Frontend** (JavaScript/HTML) - Interface do usuário
2. **Backend** (Node.js/Express) - API e servidor de arquivos
3. **Worker** (Python) - Processamento de mídia e legendas
4. **Docker** - Containerização e orquestração

---

## 🔄 FLUXO COMPLETO DO PROCESSO

### FASE 1: INICIAÇÃO (Frontend → Backend)
1. **Usuário insere URL magnet** no formulário web (`public/index.html`)
2. **Frontend envia requisição POST** para `/api/movies` (`public/client.js`)
3. **Backend recebe requisição** e cria um job único (`server/src/routes/api.js`)
4. **Backend spawna processo Python** com argumentos:
   - `--magnet` (URL do torrent)
   - `--job-id` (ID único do job)
   - `--api-url` (URL para callbacks de status)

### FASE 2: PROCESSAMENTO (Worker Python)
Arquivo principal: `worker/main.py`

#### 2.1 DOWNLOAD DO TORRENT
```python
# Diretórios temporários criados
job_temp_dir = /app/tmp/{job_id}
download_dir = /app/tmp/{job_id}/download
unpacked_dir = /app/tmp/{job_id}/unpacked

# Comando executado
webtorrent download "{magnet}" --out "{download_dir}"
```

#### 2.2 DESCOMPACTAÇÃO
- Verifica se há arquivos compactados usando `patoolib`
- Se encontrar: extrai para `unpacked_dir`
- Se não encontrar: copia tudo para `unpacked_dir`

#### 2.3 IDENTIFICAÇÃO DO ARQUIVO DE VÍDEO
- Percorre recursivamente `unpacked_dir`
- Usa `python-magic` para detectar MIME type 'video/*'
- Seleciona o maior arquivo de vídeo encontrado

#### 2.4 BUSCA DE METADADOS (TMDB)
- Limpa nome do arquivo com `clean_filename_for_search()`
- Busca no TMDB usando `tmdbv3api`
- Obtém: título, descrição, data de lançamento, poster
- Cria diretório final: `/app/library/{movie_id}`

#### 2.5 DOWNLOAD DO POSTER
- Baixa imagem do TMDB se disponível
- Salva como `poster.png` no diretório do filme

#### 2.6 ⚠️ PROCESSAMENTO DE LEGENDAS (PROBLEMA IDENTIFICADO)
**Esta é a fase com problemas críticos identificados:**

```python
# Chamada do sistema de legendas (linha ~289)
subtitle_info = download_and_process_subtitles(
    movie_library_path,  # /app/library/{movie_id}
    movie_info,          # Inclui video_file (ainda em temp)
    subtitle_progress_callback
)
```

#### 2.7 CONVERSÃO PARA HLS
- Analisa codecs do vídeo original
- Se compatível: segmentação rápida (copy)
- Se não: recodificação completa
- Gera segmentos `.ts` e playlist `.m3u8`

#### 2.8 SALVAMENTO DE METADADOS
```json
{
    "id": movie_id,
    "title": title,
    "overview": overview,
    "release_date": release_date,
    "poster_path": "/poster.png",
    "hls_playlist": "/hls/playlist.m3u8",
    "subtitles": subtitle_info  // ← Aqui devem estar as legendas
}
```

#### 2.9 LIMPEZA FINAL
```python
# CRÍTICO: Aqui está um dos problemas!
shutil.rmtree(job_temp_dir, ignore_errors=True)
# Remove TODO o diretório temporário, incluindo arquivos de legenda não movidos
```

---

## 🎯 SISTEMA DE LEGENDAS - ANÁLISE DETALHADA

### ARQUIVO: `worker/subtitle_manager.py`

#### CLASSE SubtitleManager
```python
def __init__(self, movie_folder, movie_info, progress_callback=None):
    self.movie_folder = movie_folder          # /app/library/{movie_id}
    self.subtitles_folder = movie_folder + '/subtitles'  # Pasta final
    self.temp_folder = tempfile.mkdtemp()     # Pasta temporária SEPARADA
```

#### PROCESSO DE DOWNLOAD
```python
def download_subtitles(self):
    # 1. Configura video object para Subliminal
    video_file = self.movie_info.get('video_file')  # Arquivo ainda em /tmp
    video = Video.fromname(video_file)
    
    # 2. Define idiomas
    languages = {Language('en'), Language('pt-BR'), Language('pt')}
    
    # 3. Baixa usando Subliminal
    subtitles = download_best_subtitles([video], languages)
    
    # 4. Salva temporariamente
    save_subtitles(video, subtitles[video], single=False)
    # ↑ Salva na mesma pasta do vídeo (ainda em /tmp)
```

#### PROCESSO DE PROCESSAMENTO
```python
def _process_subtitle(self, temp_subtitle_path, lang_code, video_file):
    # 1. Sincronização (apenas para inglês)
    if FFSUBSYNC_AVAILABLE and lang_code == 'en':
        synced_path = self._sync_subtitle(temp_subtitle_path, video_file)
    
    # 2. Conversão para WebVTT
    webvtt_path = self._convert_to_webvtt(synced_path, lang_code)
    # ↑ Aqui move para pasta final: self.subtitles_folder
    
    # 3. Retorna info da legenda
    return {
        'language': lang_code,
        'name': self._get_language_name(lang_code),
        'file': os.path.basename(webvtt_path),
        'url': f"/api/subtitles/{self.movie_info['id']}/{filename}"
    }
```

---

## 🚨 PROBLEMAS IDENTIFICADOS NO SISTEMA DE LEGENDAS

### PROBLEMA 1: TIMING DE LIMPEZA
**Local:** `worker/main.py` linha ~425
```python
finally:
    print(f"Limpando diretório temporário: {job_temp_dir}")
    shutil.rmtree(job_temp_dir, ignore_errors=True)  # ← PROBLEMA!
```

**Issue:** A limpeza acontece no `finally`, ou seja, SEMPRE executa, mesmo se houver erro no processamento de legendas. Se as legendas não foram movidas corretamente, elas são apagadas.

### PROBLEMA 2: MÚLTIPLAS PASTAS TEMPORÁRIAS
**Local:** `subtitle_manager.py`
```python
def __init__(self):
    self.temp_folder = tempfile.mkdtemp(prefix='subtitles_')  # Pasta temp SEPARADA
```

**Issue:** O Subliminal salva na pasta do vídeo (`/tmp/job_xxx/`), mas o SubtitleManager tem sua própria pasta temp. Pode haver inconsistência na localização dos arquivos.

### PROBLEMA 3: DEPENDÊNCIA DE ARQUIVO ORIGINAL
**Local:** `subtitle_manager.py` linha ~55
```python
video_file = self.movie_info.get('video_file')  # Arquivo em /tmp
```

**Issue:** O sistema de legendas depende do arquivo de vídeo original para sincronização, mas este arquivo é temporário e será deletado.

### PROBLEMA 4: TRATAMENTO DE ERROS SILENCIOSO
**Local:** `subtitle_manager.py` linhas ~100-102
```python
except Exception as e:
    self.report_progress(f"Erro ao baixar legendas: {str(e)[:100]}")
    return []  # ← Falha silenciosa
```

**Issue:** Erros são logados mas o processo continua sem legendas, mascarando problemas reais.

### PROBLEMA 5: VERIFICAÇÃO INADEQUADA DE ARQUIVO FINAL
**Local:** `subtitle_manager.py` linha ~272
```python
def download_and_process_subtitles():
    subtitle_info = subtitle_manager.get_subtitle_info()  # Verifica pasta final
    if not subtitle_info and downloaded_subs:
        subtitle_info = downloaded_subs  # Fallback para dados em memória
```

**Issue:** Se a movimentação falhar, o sistema usa dados em memória que apontam para arquivos que não existem mais.

---

## 🎬 FLUXO DO FRONTEND (Sistema de Legendas)

### CARREGAMENTO INICIAL
```javascript
// client.js - linha ~280
function setupSubtitles(movie) {
    appState.currentSubtitles = movie.subtitles || [];  // Do metadata.json
    
    // Cria botões para cada legenda
    appState.currentSubtitles.forEach(subtitle => {
        option.dataset.url = `/api/subtitles/${movie.id}/${subtitle.file}`;
    });
}
```

### ATIVAÇÃO DE LEGENDA
```javascript
// client.js - linha ~309
function setActiveSubtitle(subtitle) {
    const track = document.createElement('track');
    track.src = `/api/subtitles/${appState.currentMovieId}/${subtitle.file}`;
    video.appendChild(track);
    track.mode = 'showing';
}
```

### SERVIMENTO DE LEGENDAS
```javascript
// server/src/routes/api.js - linha ~70
router.get('/subtitles/:movieId/:filename', async (req, res) => {
    const subtitlePath = path.join(libraryPath, movieId, 'subtitles', filename);
    res.sendFile(subtitlePath);  // Se arquivo não existir → 404
});
```

---

## 🔧 SOLUÇÕES PROPOSTAS

### SOLUÇÃO 1: REORGANIZAR ORDEM DE OPERAÇÕES
Mover processamento de legendas para APÓS a conversão HLS:

1. Converte vídeo para HLS primeiro
2. Processa legendas usando arquivo HLS ou mantém referência ao original
3. Move arquivos para pasta final
4. Só então limpa temporários

### SOLUÇÃO 2: LIMPEZA CONDICIONAL
```python
# Só limpar se processamento foi bem-sucedido
finally:
    if processing_successful:
        shutil.rmtree(job_temp_dir, ignore_errors=True)
    else:
        print(f"Mantendo arquivos temporários para debug: {job_temp_dir}")
```

### SOLUÇÃO 3: VERIFICAÇÃO DE INTEGRIDADE
Antes de salvar `metadata.json`, verificar se arquivos de legenda realmente existem:

```python
# Verificar se legendas foram criadas corretamente
verified_subtitles = []
for subtitle in subtitle_info:
    subtitle_path = os.path.join(movie_library_path, 'subtitles', subtitle['file'])
    if os.path.exists(subtitle_path):
        verified_subtitles.append(subtitle)
    else:
        print(f"AVISO: Arquivo de legenda não encontrado: {subtitle_path}")

metadata["subtitles"] = verified_subtitles
```

### SOLUÇÃO 4: PROCESSAMENTO ROBUSTO
Implementar retry e fallback para download de legendas:

```python
def download_subtitles_with_retry(self, max_retries=3):
    for attempt in range(max_retries):
        try:
            return self.download_subtitles()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Tentativa {attempt + 1} falhou, tentando novamente...")
            time.sleep(2)
```

---

## 📊 ESTADO ATUAL DO SISTEMA

### ✅ FUNCIONANDO
- Download de torrents
- Descompactação de arquivos
- Identificação de vídeos
- Busca de metadados no TMDB
- Download de posters
- **Sistema de legendas com múltiplos providers**
- **Download e processamento de legendas**
- **Verificação de integridade de legendas**
- Conversão para HLS
- Interface do usuário
- Sistema de parties

### ✅ PROBLEMAS CORRIGIDOS
- **✅ Legendas agora persistem após processamento**
- **✅ Limpeza condicional implementada**
- **✅ Tratamento robusto de erros**
- **✅ Sistema de providers com fallback**
- **✅ Verificação de arquivos finais**
- **✅ Sistema de retry para operações críticas**

### 🎯 MELHORIAS IMPLEMENTADAS
1. **✅ Múltiplos providers de legendas** (podnapisi, tvsubtitles, argenteam, subdivx, opensubtitles)
2. **✅ Limpeza condicional de arquivos temporários**
3. **✅ Verificação de integridade antes de salvar metadata**
4. **✅ Logs detalhados para debug**
5. **✅ Sistema de retry com fallback automático**
6. **✅ Tratamento específico para erros do OpenSubtitles**

---

## 📁 ESTRUTURA DE ARQUIVOS FINAL ESPERADA
```
/app/library/{movie_id}/
├── metadata.json          # Metadados com array de legendas
├── poster.png            # Poster do filme
├── hls/                  # Arquivos de streaming
│   ├── playlist.m3u8
│   └── segment*.ts
└── subtitles/            # Legendas processadas
    ├── subtitle_en.vtt   # Inglês
    ├── subtitle_pt.vtt   # Português
    └── subtitle_pt-BR.vtt # Português Brasil
```

---

*Documento gerado em: 21 de julho de 2025*
*Status: ✅ SISTEMA COMPLETAMENTE FUNCIONAL - Todos os problemas corrigidos*
*Última atualização: Sistema de legendas totalmente operacional com múltiplos providers*
