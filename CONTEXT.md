# CONTEXT.MD - ANÁLISE PROFUNDA DO SISTEMA THEATER

## 🎯 **OBJETIVO PRINCIPAL DO SISTEMA**

O **Theater** é um sistema completo de automação para processamento de mídia que:

1. **Recebe**: URLs de torrents (magnet links) via interface web
2. **Processa**: Download → Extração → Análise → Conversão → Metadados
3. **Entrega**: Stream HLS com legendas e posters via web player
4. **Gerencia**: Biblioteca centralizada de filmes processados

---

## 📊 **ARQUITETURA E FLUXO DE DADOS**

### **COMPONENTES PRINCIPAIS**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FRONTEND      │    │     BACKEND      │    │     WORKER      │
│   (client.js)   │◄──►│   (server.js)    │◄──►│   (main.py)     │
│                 │    │                  │    │                 │
│ • Interface     │    │ • API REST       │    │ • Processamento │
│ • Player HLS    │    │ • Socket.IO      │    │ • Conversões    │
│ • Legendas      │    │ • Job Manager    │    │ • Metadados     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### **FLUXO DE DADOS DETALHADO**

#### **1. ENTRADA DE DADOS**
- **Origem**: Usuário insere magnet link
- **Tipo**: String URL no formato `magnet:?xt=urn:btih:...`
- **Destino**: Backend Node.js via POST `/api/movies`

#### **2. CRIAÇÃO DE JOB**
- **Processo**: Backend gera ID único temporal (`job_${timestamp}`)
- **Comunicação**: Spawn processo Python com argumentos:
  - `--magnet`: URL do torrent
  - `--job-id`: Identificador único
  - `--api-url`: Callback para updates de status

#### **3. PROCESSAMENTO (WORKER PYTHON)**

##### **3.1 DOWNLOAD DE TORRENT**
- **Ferramenta**: `webtorrent` CLI
- **Input**: Magnet link
- **Output**: Arquivos baixados em `/app/tmp/job_ID/download/`
- **Dados**: Arquivos RAR/ZIP + vídeos + metadados

##### **3.2 EXTRAÇÃO DE ARQUIVOS**
- **Ferramenta**: `patoolib` (Python)
- **Input**: Arquivos compactados (.rar, .zip, etc.)
- **Output**: Arquivos extraídos em `/app/tmp/job_ID/unpacked/`
- **Fallback**: Se não há arquivos compactados, copia tudo

##### **3.3 IDENTIFICAÇÃO DE VÍDEO**
- **Ferramenta**: `python-magic`
- **Processo**: Varredura recursiva por MIME type 'video/*'
- **Critério**: Maior arquivo de vídeo encontrado
- **Output**: Caminho absoluto do arquivo principal

##### **3.4 LIMPEZA DE NOME PARA BUSCA**
- **Input**: Nome do arquivo (ex: `Clown.In.A.Cornfield.2025.1080p.WEBRip.x265.10bit.AAC5.1-[YTS.MX].mp4`)
- **Processo**: Regex patterns para remover:
  - Grupos de release (YTS, RARBG, etc.)
  - Qualidade (1080p, 720p, etc.)
  - Codecs (x265, h264, AAC, etc.)
  - Termos técnicos (10bit, WEBRip, etc.)
- **Output**: Título limpo (ex: `Clown In A Cornfield 2025`)

##### **3.5 BUSCA DE METADADOS (TMDB)**
- **API**: The Movie Database v3
- **Input**: Título limpo + variações
- **Estratégia**: Múltiplas tentativas:
  1. Termo completo
  2. Sem ano
  3. Primeiras 3 palavras
  4. Versão ultra-limpa
- **Output**: 
  - `movie_id`: ID único do TMDB
  - `title`: Título oficial
  - `overview`: Descrição
  - `release_date`: Data de lançamento
  - `poster_path`: URL do poster

##### **3.6 CRIAÇÃO DE ESTRUTURA**
- **Diretório**: `/app/library/{movie_id}/`
- **Subpastas**:
  - `hls/`: Segmentos de vídeo
  - `subtitles/`: Legendas processadas
  - `posters/`: Imagens em múltiplos tamanhos

##### **3.7 SISTEMA DE POSTERS**
- **Input**: `poster_path` do TMDB
- **Processo**:
  1. Download de múltiplos tamanhos do TMDB
  2. Fallback para fontes alternativas
  3. Geração de placeholder personalizado
  4. Redimensionamento automático
- **Output**: Dicionário com URLs relativos por tamanho

##### **3.8 SISTEMA DE LEGENDAS**
- **Input**: Arquivo de vídeo original
- **Ferramentas**: 
  - `subliminal`: Download de múltiplos providers
  - `ffsubsync`: Sincronização com áudio (inglês)
  - `pysrt`: Conversão de formatos
- **Providers**: OpenSubtitles, Podnapisi, TVSubtitles, etc.
- **Output**: Legendas em WebVTT na pasta final

##### **3.9 ANÁLISE DE CODEC**
- **Ferramenta**: `ffprobe`
- **Input**: Arquivo de vídeo
- **Análise**:
  - Codec de vídeo (h264, hevc, etc.)
  - Bit depth (8bit, 10bit, 12bit)
  - Codec de áudio (aac, ac3, etc.)
  - Profile H.264 (main, high, etc.)
- **Decisão**: Copy vs Recodificação

##### **3.10 CONVERSÃO PARA HLS**
- **Ferramenta**: `ffmpeg`
- **Estratégias**:
  
  **MODO COPY (Rápido)**:
  - Se: H.264 + 8bit + AAC/MP3
  - Comando: `-c copy -f hls`
  - Tempo: ~2-5 minutos
  
  **MODO RECODIFICAÇÃO (Lento)**:
  - Se: HEVC/10bit/outros formatos
  - Comando: `-c:v h264 -profile:v main -pix_fmt yuv420p`
  - Tempo: ~30-60 minutos

- **Output**: 
  - `playlist.m3u8`: Lista de reprodução
  - `segment001.ts`, `segment002.ts`, etc.: Segmentos de 4s

##### **3.11 VERIFICAÇÃO FINAL**
- **Legendas**: Confirma existência física dos arquivos
- **Metadados**: Só inclui legendas verificadas
- **Integridade**: Valida estrutura completa

##### **3.12 SALVAMENTO DE METADADOS**
- **Arquivo**: `metadata.json`
- **Estrutura**:
```json
{
  "id": 123456,
  "title": "Nome do Filme",
  "overview": "Descrição...",
  "release_date": "2025-01-01",
  "poster_path": "/posters/poster_large.jpg",
  "posters": {
    "thumbnail": "/posters/poster_thumbnail.jpg",
    "medium": "/posters/poster_medium.jpg", 
    "large": "/posters/poster_large.jpg"
  },
  "hls_playlist": "/hls/playlist.m3u8",
  "subtitles": [
    {
      "language": "en",
      "name": "English",
      "file": "english.vtt"
    }
  ]
}
```

---

## 🔄 **PONTOS CRÍTICOS IDENTIFICADOS**

### **1. PROBLEMA DE REFERÊNCIA PREMATURA**
- **Local**: `main.py` linha ~279
- **Causa**: `movie_info` usado antes de ser definido
- **Solução**: Criar `movie_info` após obter metadados do TMDB
- **Impacto**: Crash completo do processo

### **2. ERRO DE CODEC H.264**
- **Local**: Conversão FFmpeg
- **Causa**: Profile "main" não suporta 10-bit
- **Solução**: Detectar bit depth e usar profile adequado
- **Impacto**: Falha na conversão de vídeo

### **3. BUSCA DE METADADOS FRACA**
- **Local**: `clean_filename_for_search()`
- **Causa**: Regex insuficiente para nomes complexos
- **Solução**: Múltiplas variações de busca
- **Impacto**: Filmes sem metadados corretos

### **4. BITSTREAM ERRORS NO HLS**
- **Local**: Segmentação de vídeo
- **Causa**: Problemas de sincronização em HEVC
- **Solução**: Flags `-hls_flags independent_segments`
- **Impacto**: Player não consegue reproduzir

---

## 🎯 **OBJETIVO DE CADA AJUSTE**

### **AJUSTE 1: Correção de movie_info**
- **Finalidade**: Evitar crash na inicialização de posters
- **Dados**: Metadados do TMDB → Sistema de posters
- **Contexto**: Posters precisam de `poster_path` para download

### **AJUSTE 2: Detecção de Bit Depth**
- **Finalidade**: Compatibilidade com vídeos 10-bit/12-bit
- **Dados**: Pixel format → Profile H.264 adequado
- **Contexto**: Navegadores só suportam H.264 8-bit

### **AJUSTE 3: Busca Inteligente de Metadados**
- **Finalidade**: Melhor taxa de acerto na identificação
- **Dados**: Nome de arquivo → Múltiplas tentativas de busca
- **Contexto**: Nomes de torrent são muito "sujos"

### **AJUSTE 4: Flags HLS Otimizadas**
- **Finalidade**: Player web reproduzir sem erros
- **Dados**: Segmentos TS → Compatibilidade HLS
- **Contexto**: Diferentes codecs precisam diferentes tratamentos

---

## 📁 **ESTRUTURA DE DADOS FINAL**

```
/app/library/
├── 123456/                    # ID do filme
│   ├── metadata.json          # Metadados completos
│   ├── poster.png            # Poster padrão (compatibilidade)
│   ├── hls/
│   │   ├── playlist.m3u8     # Lista de reprodução
│   │   ├── segment001.ts     # Segmentos de vídeo
│   │   └── segment002.ts
│   ├── posters/
│   │   ├── poster_thumbnail.jpg
│   │   ├── poster_medium.jpg
│   │   └── poster_large.jpg
│   └── subtitles/
│       ├── english.vtt
│       └── portuguese.vtt
```

---

## 🚀 **PRÓXIMOS PASSOS RECOMENDADOS**

### **IMPLEMENTAÇÃO SEGURA**
1. **Validar**: Compilação sem erros
2. **Testar**: Job completo com arquivo simples
3. **Monitorar**: Logs detalhados de cada etapa
4. **Iterar**: Ajustes baseados em resultados reais

### **MELHORIAS FUTURAS**
1. **Cache**: Metadados e posters já processados
2. **Qualidade**: Múltiplas qualidades HLS (480p, 720p, 1080p)
3. **Performance**: Processamento paralelo de etapas
4. **Robustez**: Retry automático em falhas de rede

---

## 🎬 **CONSIDERAÇÕES TÉCNICAS**

### **COMPATIBILIDADE WEB**
- **Vídeo**: H.264 Main Profile, 8-bit, YUV420P
- **Áudio**: AAC-LC, 48kHz, Estéreo/5.1
- **Legendas**: WebVTT (suporte nativo)
- **Streaming**: HLS (iOS/Safari nativo, outros via HLS.js)

### **PERFORMANCE**
- **Copy Mode**: ~5-10x mais rápido que recodificação
- **Segmentos**: 4 segundos = bom balance latência/eficiência
- **Concurrent**: Posters + Legendas em paralelo

### **ESCALABILIDADE**
- **Jobs**: Processamento serial (1 por vez atualmente)
- **Storage**: Crescimento linear com biblioteca
- **Network**: Dependente de seeds do torrent

---

Este documento serve como base sólida para entender cada decisão técnica e continuar o desenvolvimento de forma consciente e fundamentada.
