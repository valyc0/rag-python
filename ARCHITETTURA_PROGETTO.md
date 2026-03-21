# Architettura del progetto RAG locale

## Obiettivo

Questo progetto realizza un sistema RAG locale, cioe' un sistema di domanda e risposta che non si limita a generare testo con un modello linguistico, ma prima recupera i contenuti piu' rilevanti da una base documentale locale.

In pratica, il sistema:

1. legge documenti presenti in una directory locale
2. estrae e normalizza il testo
3. divide il contenuto in chunk semanticamente utilizzabili
4. calcola embedding per ogni chunk tramite Ollama
5. salva embedding e metadata in un indice persistente
6. quando arriva una domanda, recupera i chunk piu' rilevanti
7. costruisce un prompt grounded
8. chiede a Llama 3.2 di rispondere solo usando il contesto trovato

L'obiettivo e' ridurre le hallucinations e ottenere risposte piu' precise, motivate e verificabili rispetto a una generazione LLM pura.

## Cosa fa il progetto

Il progetto offre queste funzionalita':

- indicizzazione locale di documenti PDF, TXT, DOCX e Markdown
- aggiornamento incrementale dei documenti gia' indicizzati
- retrieval ibrido tramite ricerca vettoriale e BM25
- generazione di risposte con Ollama via REST API
- caching delle risposte piu' recenti
- watcher filesystem per rilevare nuovi file o modifiche
- API HTTP con FastAPI
- CLI per rescan e query
- persistenza locale di indice, metadata e cache
- supporto Docker per un avvio semplice e ripetibile

## Perche' questa architettura

La struttura scelta cerca un equilibrio tra robustezza, semplicità operativa ed estendibilita'.

Le scelte principali sono:

- Ollama per mantenere tutto locale e senza dipendenze cloud obbligatorie
- Llama 3.2 come modello generativo
- nomic-embed-text come modello embedding locale via Ollama
- Chroma come vector store persistente e semplice da integrare
- SQLite per tracciare file, chunk e stato di indicizzazione
- FastAPI per esporre endpoint REST chiari e leggeri
- watchdog per aggiornare la knowledge base quando cambiano i file

Questa combinazione e' adatta a un ambiente locale o a una piccola installazione interna, ma resta abbastanza modulare da poter essere evoluta verso un setup piu' grande.

## Flusso completo del sistema

### 1. Avvio

Quando il progetto parte:

1. carica la configurazione YAML
2. inizializza logging, repository SQLite, vector store Chroma e cache
3. esegue una scansione iniziale della directory documenti
4. opzionalmente avvia un watcher sulla directory documenti

### 2. Ingestion dei documenti

Durante la fase di ingestion il sistema:

1. scansiona ricorsivamente la directory configurata
2. filtra solo le estensioni supportate
3. confronta hash e timestamp dei file con lo stato gia' salvato
4. reindicizza solo file nuovi o modificati
5. rimuove dall'indice i file cancellati dal filesystem

### 3. Parsing

Il parsing e' specifico per formato:

- PDF: estrazione testo con PyMuPDF
- DOCX: lettura paragrafi con python-docx
- TXT e MD: lettura come testo puro

L'output del parser non e' ancora pronto per il retrieval: per questo viene normalizzato.

### 4. Pulizia del testo

La normalizzazione rimuove artefatti comuni che peggiorano embedding e retrieval:

- caratteri nulli
- spaziature eccessive
- newline inutili
- rumore dovuto a parsing non uniforme

Questo passaggio rende piu' stabili sia il chunking sia la similarita' semantica.

### 5. Chunking

Il testo normalizzato viene diviso in parti piu' piccole chiamate chunk.

Le regole usate dal progetto sono:

- chunk basati su una dimensione target in token approssimati
- overlap tra chunk consecutivi
- tentativo di spezzare prima per paragrafi
- poi per frasi
- e infine, se necessario, con una finestra di fallback su parole

Perche' serve il chunking:

- un documento intero e' troppo grande per essere passato direttamente al modello
- il retrieval funziona meglio su unita' informative piu' precise
- l'overlap riduce il rischio di perdere continuita' semantica tra parti contigue

Inoltre il progetto deduplica i chunk usando un hash del contenuto, cosi' evita di salvare piu' volte testo uguale.

## Embedding

Ogni chunk viene convertito in un vettore numerico con il modello embedding locale.

Nel progetto il calcolo avviene tramite Ollama REST usando il modello nomic-embed-text.

Perche' questa scelta:

- resta coerente con il vincolo di local-only
- evita dipendenze cloud
- offre buona qualita' per ricerca semantica generale
- riduce complessita' operativa, perche' generazione ed embedding passano dallo stesso runtime

Ottimizzazioni implementate:

- elaborazione embedding a batch
- reindicizzazione solo dei file che cambiano
- caching delle risposte finali

## Storage dei dati

Il progetto usa due livelli di persistenza.

### Chroma

Chroma memorizza:

- embedding dei chunk
- testo associato ai chunk
- metadata come file, pagina, posizione e hash contenuto

Serve per la ricerca vettoriale, cioe' per recuperare chunk semanticamente simili alla domanda.

### SQLite

SQLite memorizza:

- file indicizzati
- hash dei file
- data di indicizzazione
- chunk salvati e metadata di supporto

Serve per:

- gestire aggiornamenti incrementali
- costruire la ricerca BM25
- tenere traccia dello stato del corpus

## Retrieval

Il retrieval non si basa su una sola tecnica.

Il progetto implementa una strategia ibrida:

### Dense retrieval

1. viene calcolato l'embedding della query
2. Chroma recupera i chunk piu' vicini nello spazio vettoriale

Questo approccio e' utile quando la domanda usa parole diverse dal documento ma ha significato simile.

### Sparse retrieval con BM25

Il sistema costruisce anche una ricerca lessicale BM25 sui chunk salvati in SQLite.

Questo approccio e' utile quando termini esatti, nomi, sigle o frasi chiave sono importanti.

### Fusione dei risultati

I due insiemi di risultati vengono fusi con una logica di scoring ibrido che combina:

- score vettoriale
- score BM25
- rank reciproco
- bonus di reranking lessicale leggero

Il risultato finale e' piu' robusto di una ricerca solo dense o solo sparse.

## Costruzione del contesto

Una volta recuperati i chunk migliori, il sistema non invia tutto ciecamente al modello.

Prima applica una compressione del contesto che:

- limita la lunghezza massima complessiva
- evita duplicati logici
- mantiene i chunk piu' utili in ordine di rilevanza

Questo e' importante per tre motivi:

1. riduce rumore nel prompt
2. evita di sprecare finestra di contesto
3. migliora grounding e precisione

## Prompt engineering

Il prompt costruito per Llama 3.2 segue una regola chiara: il modello deve rispondere solo con informazioni presenti nel contesto.

La struttura del prompt contiene:

1. istruzioni di comportamento
2. blocco contesto con fonti e metadata
3. domanda dell'utente
4. regole per rispondere o dichiarare assenza di informazioni

La policy di fallback e' esplicita:

Se il contesto non contiene abbastanza informazioni, il modello deve rispondere con:

Non lo so in base ai documenti forniti.

Questo riduce il rischio di risposte inventate.

## Generazione con Ollama

La risposta finale viene prodotta tramite chiamata HTTP a Ollama.

Il progetto usa i seguenti parametri configurabili:

- modello LLM
- temperature
- top_p
- num_predict
- timeout

Sono gestiti anche:

- retry automatici
- backoff esponenziale
- endpoint streaming per output incrementale

## API esposte

L'app FastAPI espone questi endpoint principali:

- GET /health
  - verifica lo stato dell'app e i modelli configurati
- GET /documents
  - restituisce i documenti indicizzati
- POST /ingest/rescan
  - forza una nuova scansione della directory documenti
- POST /query
  - esegue una query standard e restituisce risposta e fonti
- POST /query/stream
  - esegue una query con streaming SSE

## CLI

Oltre alle API c'e' una CLI utile per operazioni manuali o scriptate.

Comandi disponibili:

- rag-cli rescan
- rag-cli ask "domanda"

Questo consente di usare il progetto anche senza interfaccia web.

## Watcher filesystem

Il watcher osserva la directory documenti e reagisce ai cambiamenti.

Quando rileva:

- nuovi file
- modifiche ai file
- cancellazioni

programma una nuova scansione con debounce, evitando reindicizzazioni continue durante scritture multiple ravvicinate.

Questo rende il corpus dinamico senza dover riavviare il servizio.

## Caching

Le risposte finali vengono salvate su disco in cache con TTL.

Il caching riduce:

- latenza sulle domande ripetute
- numero di chiamate al modello
- carico di calcolo locale

La cache e' legata a:

- testo della domanda
- top_k
- filtro metadata

## Test e valutazione

Il progetto include una base per la valutazione del retrieval.

Metriche presenti:

- precision@k
- recall@k

Queste metriche servono a misurare se i chunk restituiti contengono davvero le informazioni attese.

Sono presenti anche test unitari iniziali per:

- chunking
- metriche di retrieval

## Struttura delle directory principali

- app
  - contiene il codice applicativo
- config
  - contiene la configurazione YAML
- docker-compose.yml
  - compose unico e ufficiale dell'intero stack
- documents
  - directory locale dei documenti da indicizzare
- data
  - contiene persistenza indice, cache e stato
- tests
  - contiene i test unitari
- ollama
  - contiene solo documentazione e uno script compatibile che delega allo startup root

## Persistenza locale

I dati persistono localmente in modo separato:

- indice vettoriale in data/chroma
- stato e metadata in data/state/index.db
- cache in data/cache

Questo significa che il sistema puo' essere riavviato senza perdere l'indice gia' costruito.

## Come si usa in pratica

Scenario tipico:

1. si avvia Ollama e l'API RAG tramite Docker
2. si copiano documenti in documents
3. il sistema indicizza i file
4. l'utente invia una domanda
5. il sistema recupera i chunk migliori
6. il modello genera una risposta grounded
7. la risposta torna con le fonti usate

## Punti forti del progetto

- tutto locale
- nessun cloud obbligatorio
- struttura modulare
- retrieval ibrido invece di sola similarita' vettoriale
- aggiornamento incrementale
- watcher per corpus dinamico
- API e CLI entrambe disponibili
- pronto per essere esteso

## Limiti attuali

I limiti piu' rilevanti sono questi:

- il reranking e' leggero e non neurale
- il parsing PDF si basa sul testo estratto, quindi documenti molto complessi o scansioni richiederebbero OCR aggiuntivo
- non ci sono ancora autenticazione, rate limiting o multiutenza
- la valutazione retrieval e' di base e puo' essere ampliata con dataset annotati

## Evoluzioni consigliate

Per una versione piu' vicina a un deployment enterprise, gli sviluppi piu' utili sarebbero:

1. OCR per PDF scannerizzati
2. reranker locale dedicato
3. query rewriting o multi-query retrieval
4. UI web minimale per interrogazione e upload documenti
5. autenticazione e autorizzazione
6. benchmark retrieval automatici
7. separazione tra worker ingestion e API query

## Sintesi finale

Questo progetto implementa un RAG locale completo: indicizza documenti, li trasforma in conoscenza interrogabile, recupera i passaggi piu' pertinenti e usa un LLM locale per costruire risposte basate su fonti reali.

La logica chiave non e' soltanto generare testo, ma farlo a partire da contenuti recuperati e controllati. E' questo che rende il sistema piu' affidabile di una semplice chat con un modello generativo.