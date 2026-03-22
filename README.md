# RAG Python Engine

Sistema RAG locale per interrogare documenti presenti su filesystem usando:

- Ollama come runtime LLM locale
- llama3.2 per la generazione delle risposte
- nomic-embed-text per gli embedding
- Chroma oppure Qdrant come vector store persistente
- SQLite oppure PostgreSQL per stato, metadata e supporto al retrieval lessicale
- FastAPI per esporre API HTTP e streaming

Per una descrizione architetturale piu' ampia, vedi anche [ARCHITETTURA_PROGETTO.md](ARCHITETTURA_PROGETTO.md).

## Cosa fa il progetto

Questo progetto prende documenti locali, li indicizza e li rende interrogabili in linguaggio naturale.

In pratica fa questo:

1. scansiona una directory locale di documenti
2. legge PDF, TXT, DOCX e Markdown
3. estrae e normalizza il testo
4. divide il contenuto in chunk
5. calcola embedding per ogni chunk
6. salva i chunk e i relativi embedding in un indice persistente
7. quando arriva una domanda, recupera i chunk piu' rilevanti
8. costruisce un prompt grounded
9. usa llama3.2 via Ollama per generare una risposta basata sui documenti

L'obiettivo non e' solo generare testo, ma rispondere partendo da contenuti realmente presenti nei documenti indicizzati.

## Come funziona

Il flusso principale del sistema e' questo:

### 1. Ingestion

Il servizio legge i file dalla directory [documents](documents) e supporta:

- `.pdf`
- `.txt`
- `.docx`
- `.md`

Per ogni file:

- estrae il testo con il parser adatto
- normalizza whitespace e caratteri inutili
- divide il testo in chunk con overlap
- deduplica chunk uguali tramite hash

### 2. Embedding

Ogni chunk viene trasformato in un vettore numerico con `nomic-embed-text` via API Ollama.

Questo serve per trovare chunk semanticamente vicini a una domanda, anche quando le parole usate non coincidono esattamente.

### 3. Storage

Il progetto usa due livelli di persistenza:

- un backend vettoriale, che puo' essere Chroma o Qdrant
- un backend metadata, che puo' essere SQLite o PostgreSQL

Nella configurazione standard il progetto usa:

- Chroma per embedding e retrieval vettoriale
- SQLite per file indicizzati, chunk, hash, metadata e supporto BM25

Nella configurazione production il progetto usa invece:

- Qdrant per embedding e retrieval vettoriale
- PostgreSQL per stato, metadata e supporto BM25

### 4. Retrieval

Quando arriva una query:

1. la domanda viene convertita in embedding
2. il vector store configurato recupera i chunk semanticamente piu' simili
3. il motore BM25 recupera chunk lessicalmente rilevanti
4. i risultati vengono fusi e riordinati
5. il contesto viene compresso per stare in una finestra utile

### 5. Generazione

Il contesto recuperato viene inviato a `llama3.2` tramite Ollama REST.

Il prompt istruisce il modello a:

- usare solo le informazioni nel contesto
- non inventare contenuti non presenti
- dichiarare che non sa se il contesto e' insufficiente

## Componenti principali

- [app/main.py](app/main.py): API FastAPI e lifecycle applicativo
- [app/service.py](app/service.py): orchestration end-to-end di ingestion e query, con wiring dei backend configurati
- [app/parsers.py](app/parsers.py): parsing dei formati supportati
- [app/chunking.py](app/chunking.py): chunking con overlap e fallback robusto
- [app/retrieval.py](app/retrieval.py): retrieval ibrido dense + BM25
- [app/vector_store.py](app/vector_store.py): integrazione con backend vettoriale Chroma o Qdrant
- [app/repository.py](app/repository.py): persistenza metadata con backend SQLite o PostgreSQL
- [app/ollama_client.py](app/ollama_client.py): chiamate HTTP a Ollama
- [app/watcher.py](app/watcher.py): watcher filesystem per aggiornamenti automatici
- [config/config.yaml](config/config.yaml): configurazione del progetto
- [config/config.prod.yaml](config/config.prod.yaml): configurazione della variante production
- [docker-compose.yml](docker-compose.yml): stack standard per sviluppo locale
- [docker-compose.prod.yml](docker-compose.prod.yml): stack production con servizi separati
- [start.sh](start.sh): startup semplificato dello stack standard
- [start-prod.sh](start-prod.sh): startup della variante production
- [stop.sh](stop.sh): shutdown di entrambi gli stack

## Cosa e' cambiato nel codice

Il progetto non e' piu' limitato a un solo backend fisso. In origine il flusso applicativo assumeva sempre:

- SQLite per metadata e stato
- Chroma per il vector store

Ora il codice e' stato rifattorizzato per supportare backend selezionabili via configurazione.

### Backend configurabili

La sezione `storage` della configurazione ora include parametri per scegliere i backend e i relativi endpoint:

- `metadata_backend`: `sqlite` oppure `postgres`
- `vector_backend`: `chroma` oppure `qdrant`
- `postgres_dsn`
- `qdrant_url`
- `qdrant_api_key`
- `qdrant_collection_name`
- `qdrant_timeout_seconds`

Questo permette allo stesso servizio applicativo di funzionare in due modalita' diverse senza cambiare la logica di business.

### Repository metadata astratto

La gestione dei metadata in [app/repository.py](app/repository.py) e' stata generalizzata:

- `SqliteMetadataRepository` mantiene il comportamento originale basato su SQLite
- `PostgresMetadataRepository` implementa lo stesso contratto su PostgreSQL
- `MetadataRepository` sceglie automaticamente il backend corretto in base alla configurazione

L'effetto pratico e' che ingestion, aggiornamento incrementale, cancellazione documenti e retrieval lessicale continuano a usare la stessa API interna, ma possono poggiare su un database diverso.

### Vector store astratto

Anche la persistenza vettoriale in [app/vector_store.py](app/vector_store.py) e' stata resa pluggable:

- `ChromaVectorStore` copre il caso standard locale
- `QdrantVectorStore` aggiunge supporto a un vector database server-based
- `VectorStore` incapsula la scelta del backend attivo

In questo modo query, upsert dei chunk e cancellazioni per file funzionano allo stesso modo per il resto del sistema, ma possono usare Chroma o Qdrant sotto il cofano.

### Wiring del servizio

In [app/service.py](app/service.py) il servizio principale inizializza repository e vector store leggendo i backend dalla configurazione. Questo e' il punto in cui il supporto multi-backend entra nel runtime reale.

### Nuove dipendenze

In [pyproject.toml](pyproject.toml) sono state aggiunte:

- `psycopg[binary]` per PostgreSQL
- `qdrant-client` per Qdrant

Senza queste librerie il percorso production non sarebbe utilizzabile.

## Variante produzione

Per una variante piu' adatta alla produzione, il progetto include anche:

- [docker-compose.prod.yml](docker-compose.prod.yml)
- [config/config.prod.yaml](config/config.prod.yaml)
- [start-prod.sh](start-prod.sh)
- [PRODUCTION.md](PRODUCTION.md)

Questa variante usa PostgreSQL per metadata e stato, e Qdrant come vector database server.

## Start standard vs start production

Il repository contiene due script di avvio per due scenari diversi.

### `./start.sh`

Usa lo stack standard definito in [docker-compose.yml](docker-compose.yml) ed e' pensato per sviluppo locale e setup semplice.

Avvia:

- `ollama`
- `rag-api`

Usa:

- SQLite come metadata store
- Chroma come vector store
- watcher filesystem attivo

Vantaggi:

- meno componenti da gestire
- startup piu' semplice
- persistenza locale immediata su filesystem

### `./start-prod.sh`

Usa lo stack production definito in [docker-compose.prod.yml](docker-compose.prod.yml) ed e' pensato per un deployment piu' robusto.

Avvia:

- `postgres`
- `qdrant`
- `ollama`
- `rag-api`

Usa:

- PostgreSQL come metadata store
- Qdrant come vector store
- watcher filesystem disabilitato

In piu':

- verifica la disponibilita' di Qdrant prima di avviare l'API
- costruisce l'API con la configurazione production

### Quando usare l'uno o l'altro

Usa [start.sh](start.sh) quando vuoi:

- sviluppare localmente
- fare test veloci
- mantenere una dipendenza minima dall'infrastruttura

Usa [start-prod.sh](start-prod.sh) quando vuoi:

- separare storage metadata e vector store in servizi dedicati
- avvicinarti a un deployment persistente reale
- evitare i limiti di un backend embedded su scenari piu' lunghi o piu' strutturati

## Requisiti

### Requisiti minimi per l'avvio con Docker

- Docker installato
- Docker Compose disponibile come `docker compose`
- accesso internet la prima volta per scaricare immagini e modelli
- porte host libere di default:
  - `8010` per l'API RAG
  - `11435` per Ollama del progetto

### Requisiti minimi per avvio manuale dell'app

- Python 3.11+
- Ollama gia' funzionante localmente
- modelli disponibili in Ollama:
  - `llama3.2`
  - `nomic-embed-text`

## Installazione consigliata con Docker

Questa e' la modalita' consigliata.

### 1. Entra nella root del progetto

```bash
cd /home/valerio/lavoro/appo/git/rag
```

### 2. Rendi eseguibile lo script di avvio

```bash
chmod +x start.sh
```

### 3. Avvia tutto lo stack

```bash
./start.sh
```

Questo comando:

- crea le directory locali necessarie
- avvia il container Ollama
- verifica che Ollama risponda
- scarica `llama3.2`
- scarica `nomic-embed-text`
- avvia il container API

### 3.b Ferma tutto lo stack

```bash
chmod +x stop.sh
./stop.sh
```

Per fermare anche i volumi nominati Docker del progetto:

```bash
./stop.sh --volumes
```

### 4. Verifica lo stato dei container

```bash
docker compose ps
```

### 5. Verifica che l'API risponda

```bash
curl http://localhost:8010/health
```

### 6. Verifica che Ollama del progetto risponda

```bash
curl http://localhost:11435/api/tags
```

## Installazione manuale senza Docker per l'app

Questa modalita' e' utile se vuoi sviluppare l'API localmente senza containerizzare il servizio Python.

### 1. Avvia o prepara Ollama

Assicurati che Ollama sia in esecuzione e che i modelli richiesti siano presenti.

### 2. Crea l'ambiente virtuale Python

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installa le dipendenze

```bash
pip install -e .[dev]
```

### 4. Avvia l'API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Se Ollama non usa la URL di default, imposta la variabile ambiente

```bash
export OLLAMA_BASE_URL=http://localhost:11434
```

## Porte di default

Per evitare conflitti con altri servizi sulla macchina, il progetto usa di default queste porte host:

- API RAG: `8010`
- Ollama del progetto: `11435`

Puoi cambiarle prima dell'avvio:

```bash
export RAG_API_HOST_PORT=8020
export OLLAMA_HOST_PORT=11436
./start.sh
```

## Configurazione

La configurazione principale si trova in [config/config.yaml](config/config.yaml).

I parametri piu' importanti sono:

- path dei documenti
- dimensione chunk e overlap
- top-k retrieval
- modello LLM
- modello embedding
- timeout di Ollama
- scelta dei backend storage
- percorsi persistenti di Chroma, SQLite e cache
- DSN PostgreSQL e impostazioni Qdrant

Override supportati via variabili ambiente:

- `RAG_CONFIG_PATH`
- `OLLAMA_BASE_URL`
- `OLLAMA_LLM_MODEL`
- `OLLAMA_EMBEDDING_MODEL`
- `RAG_DOCUMENTS_PATH`
- `RAG_METADATA_BACKEND`
- `RAG_VECTOR_BACKEND`
- `RAG_CHROMA_PATH`
- `RAG_SQLITE_PATH`
- `RAG_POSTGRES_DSN`
- `RAG_CACHE_PATH`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_TIMEOUT_SECONDS`
- `RAG_WATCH_ENABLED`

### Configurazione standard e configurazione production

- [config/config.yaml](config/config.yaml) e' la configurazione standard: SQLite + Chroma
- [config/config.prod.yaml](config/config.prod.yaml) e' la configurazione production: PostgreSQL + Qdrant

Nel setup production la password PostgreSQL di default e' `postgres`, sovrascrivibile con `POSTGRES_PASSWORD`.

La differenza non e' solo infrastrutturale. Anche il codice applicativo e' stato adattato per poter istanziare il backend corretto a runtime.

## Directory usate dal progetto

- [documents](documents): documenti sorgente da indicizzare
- [data/chroma](data/chroma): vector store persistente
- [data/state](data/state): stato SQLite e metadata
- [data/cache](data/cache): cache delle risposte
- [script](script): helper shell pronti all'uso per check, rescan, log e query
- [ollama](ollama): wrapper/documentazione compatibile, non stack separato

## Script pronti all'uso

La directory [script](script) contiene comandi shell gia' pronti per le operazioni piu' comuni.

Script disponibili:

- [script/check_stack.sh](script/check_stack.sh): mostra lo stato dei container
- [script/health.sh](script/health.sh): chiama `GET /health`
- [script/ingest_status.sh](script/ingest_status.sh): mostra se l'indicizzazione e' in corso, il file corrente e la coda residua
- [script/ollama_tags.sh](script/ollama_tags.sh): verifica i tag/modelli esposti da Ollama
- [script/models.sh](script/models.sh): mostra i modelli disponibili dentro il container Ollama
- [script/list_documents.sh](script/list_documents.sh): elenca i documenti indicizzati
- [script/rescan.sh](script/rescan.sh): forza la nuova scansione dei documenti
- [script/logs_api.sh](script/logs_api.sh): segue i log dell'API
- [script/logs_ollama.sh](script/logs_ollama.sh): segue i log di Ollama
- [script/query_example.sh](script/query_example.sh): esegue una query di esempio
- [script/query_debug.sh](script/query_debug.sh): esegue una query in modalita' debug mostrando prompt e chunk selezionati
- [script/query_file_example.sh](script/query_file_example.sh): esegue una query filtrata per file

Esempi rapidi:

```bash
/home/valerio/lavoro/appo/git/rag/script/health.sh
/home/valerio/lavoro/appo/git/rag/script/ingest_status.sh
/home/valerio/lavoro/appo/git/rag/script/check_stack.sh
/home/valerio/lavoro/appo/git/rag/script/list_documents.sh
/home/valerio/lavoro/appo/git/rag/script/rescan.sh
/home/valerio/lavoro/appo/git/rag/script/query_example.sh "Riassumi i documenti indicizzati"
/home/valerio/lavoro/appo/git/rag/script/query_debug.sh "A che temperatura c'e' pericolo di ghiaccio?"
/home/valerio/lavoro/appo/git/rag/script/query_file_example.sh "1Samuele.pdf" "Riassumi il contenuto del documento"
```

Per bypassare la cache durante i test:

```bash
USE_CACHE=false /home/valerio/lavoro/appo/git/rag/script/query_example.sh "A che temperatura c'e' pericolo di ghiaccio?"
```

Per controllare se il servizio sta ancora indicizzando documenti e quali file mancano:

```bash
curl http://localhost:8010/ingest/status | python3 -m json.tool
```

## Comandi di avvio e gestione

### Avvia lo stack

```bash
./start.sh
```

### Ricostruisci e riavvia solo l'API

```bash
docker compose up -d --build rag-api
```

### Vedi lo stato dei servizi

```bash
docker compose ps
```

### Vedi tutti i log

```bash
docker compose logs -f
```

### Vedi i log dell'API

```bash
docker compose logs -f rag-api
```

### Vedi i log di Ollama

```bash
docker compose logs -f ollama
```

### Ferma tutto

```bash
docker compose down
```

### Ferma tutto e rimuovi i volumi del progetto

```bash
docker compose down -v
```

## Comandi di verifica

### Health dell'API

```bash
curl http://localhost:8010/health
```

### Modelli disponibili in Ollama del progetto

```bash
docker exec rag-ollama ollama list
```

### Tag/modelli esposti via API Ollama

```bash
curl http://localhost:11435/api/tags
```

### Documenti indicizzati

```bash
curl http://localhost:8010/documents
```

Versione piu' leggibile:

```bash
curl -s http://localhost:8010/documents | python3 -m json.tool
```

## Come aggiungere documenti

### 1. Copia il file nella directory documenti

```bash
cp /percorso/del/file.pdf documents/
```

### 2. Forza una scansione manuale

```bash
curl -X POST http://localhost:8010/ingest/rescan
```

### 3. Controlla che il file sia stato indicizzato

```bash
curl -s http://localhost:8010/documents | python3 -m json.tool
```

Nota:

Il watcher filesystem prova a rilevare automaticamente i nuovi file, ma il comando di rescan e' la verifica piu' chiara e affidabile.

## Comandi per interrogare i documenti

### Query base

```bash
curl -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il contenuto dei documenti indicizzati"}'
```

### Query con JSON formattato

```bash
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il contenuto dei documenti indicizzati"}' | python3 -m json.tool
```

### Query su un file specifico

```bash
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{
    "question":"Riassumi il contenuto di 1Samuele.pdf",
    "metadata_filter": {
      "file_name": "1Samuele.pdf"
    }
  }' | python3 -m json.tool
```

### Query con top-k esplicito

```bash
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{
    "question":"Quali sono i concetti principali del documento?",
    "top_k": 3,
    "use_cache": true
  }' | python3 -m json.tool
```

### Query filtrata per percorso sorgente

```bash
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{
    "question":"Riassumi il contenuto",
    "metadata_filter": {
      "source_path": "/app/documents/1Samuele.pdf"
    }
  }' | python3 -m json.tool
```

### Query in streaming

```bash
curl -N -X POST http://localhost:8010/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il documento in streaming"}'
```

### Query in modalita' debug

Restituisce anche il prompt finale, il contesto e i chunk selezionati.

```bash
curl -s -X POST http://localhost:8010/query/debug \
  -H "Content-Type: application/json" \
  -d '{"question":"A che temperatura c'e' pericolo di ghiaccio?"}' | python3 -m json.tool
```

## Sequenza completa tipica

Se aggiungi un nuovo file e vuoi interrogarlo subito:

```bash
cp /percorso/del/file.pdf documents/
curl -X POST http://localhost:8010/ingest/rescan
curl -s http://localhost:8010/documents | python3 -m json.tool
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il nuovo documento"}' | python3 -m json.tool
```

## Test diretti su Ollama

Questi comandi bypassano il RAG e parlano direttamente con Ollama.

### Generazione diretta con llama3.2

```bash
curl http://localhost:11435/api/generate \
  -d '{
    "model": "llama3.2",
    "prompt": "Rispondi in una frase: cosa e' un RAG?",
    "stream": false,
    "options": {
      "temperature": 0.1,
      "top_p": 0.9,
      "num_predict": 128
    }
  }'
```

### Embedding diretto con nomic-embed-text

```bash
curl http://localhost:11435/api/embed \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "input": ["test embedding"]
  }'
```

## API disponibili

### `GET /health`

Stato dell'app e modelli configurati.

```bash
curl http://localhost:8010/health
```

### `GET /documents`

Elenco dei documenti indicizzati con metadata di base.

```bash
curl http://localhost:8010/documents
```

### `POST /ingest/rescan`

Forza una nuova scansione della directory documenti.

```bash
curl -X POST http://localhost:8010/ingest/rescan
```

### `POST /query`

Esegue una query standard e restituisce:

- risposta
- flag cache
- dimensione del contesto
- fonti usate

```bash
curl -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il documento"}'
```

### `POST /query/stream`

Esegue una query in streaming SSE.

```bash
curl -N -X POST http://localhost:8010/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il documento"}'
```

## Qualita', limiti e note pratiche

### Cosa e' gia' implementato

- ingestion incrementale
- watcher filesystem
- retrieval ibrido dense + BM25
- cache risposte
- prompt grounding
- persistenza locale completa

### Limiti attuali

- il reranking e' leggero, non neurale
- documenti PDF complessi o scansioni pure potrebbero richiedere OCR aggiuntivo
- la qualita' finale dipende dal contenuto estratto e dalla qualita' del retrieval
- alcune query molto generiche possono produrre riassunti troppo liberi e richiedere prompt piu' stretti

## Troubleshooting

### `./start.sh` fallisce sul download dei modelli

Possibili cause:

- DNS non raggiungibile nel container
- rete assente o filtrata
- registry Ollama temporaneamente non raggiungibile

Controlla i log:

```bash
docker compose logs -f ollama
```

### La porta 8010 o 11435 e' occupata

Cambia le porte prima dell'avvio:

```bash
export RAG_API_HOST_PORT=8020
export OLLAMA_HOST_PORT=11436
./start.sh
```

### Un file nuovo non compare subito

Forza manualmente la scansione:

```bash
curl -X POST http://localhost:8010/ingest/rescan
```

Poi verifica:

```bash
curl -s http://localhost:8010/documents | python3 -m json.tool
```

### Vuoi ricostruire l'API dopo modifiche al codice

```bash
docker compose up -d --build rag-api
```

## Esempio reale

Esempio di flusso reale con un PDF aggiunto in [documents](documents):

1. copia del file nella cartella documenti
2. esecuzione di `POST /ingest/rescan`
3. verifica con `GET /documents`
4. query filtrata per `file_name`
5. restituzione della risposta con elenco delle fonti usate

## Sintesi

Questo progetto serve a costruire un RAG locale completo e usabile subito.

Se vuoi usarlo in modo pratico, la sequenza minima e' questa:

```bash
./start.sh
cp /percorso/del/file.pdf documents/
curl -X POST http://localhost:8010/ingest/rescan
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il documento appena aggiunto"}' | python3 -m json.tool
```

Test inclusi:

```bash
pytest
```

Esempi di valutazione retrieval:

- query: "tie-break"
  - atteso: chunk del PDF con la sezione dedicata al tie-break tra i primi risultati
- query: "quanti set servono per vincere"
  - atteso: chunk con le regole sul numero di set

## Ottimizzazioni implementate

- deduplicazione chunk tramite hash del contenuto
- compressione contesto per rientrare nella context window
- caching delle risposte su disco con TTL
- aggiornamento incrementale basato su hash file
- watcher filesystem per directory dinamica

## Scalabilita' e produzione

Per carichi superiori:

1. separare API e worker di ingestion
2. spostare Chroma su storage dedicato o valutare Qdrant per concorrenza maggiore
3. introdurre reranker neurale locale opzionale
4. aggiungere autenticazione e rate limiting
5. schedulare benchmark retrieval regressivi su dataset noto
