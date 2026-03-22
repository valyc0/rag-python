# Guida Ai File Python Del Progetto

Questa guida spiega, in modo semplice, a cosa serve ogni file Python del progetto.

L'obiettivo non e' spiegare tutta Python, ma darti una mappa pratica del codice: cosa fa ogni file, quando entra in gioco, e come si collega agli altri.

## Da Dove Partire Se Non Conosci Python

Prima di guardare i file, ti basta sapere queste 6 cose:

1. Un file `.py` e' un file Python.
2. `def nome_funzione(...):` definisce una funzione, cioe' un blocco di codice riutilizzabile.
3. `class NomeClasse:` definisce una classe, cioe' un tipo di oggetto con dati e comportamenti.
4. `import ...` serve per usare codice definito in altri file.
5. `async def ...` indica una funzione asincrona, usata quando il programma deve aspettare rete, file o servizi esterni senza bloccarsi inutilmente.
6. In questo progetto quasi tutto ruota attorno a un flusso semplice: leggere documenti, spezzarli, indicizzarli, cercarli, costruire un prompt e chiedere la risposta a Ollama.

## Flusso Generale Del Progetto

Il progetto lavora cosi':

1. legge la configurazione
2. trova i documenti nella cartella `documents/`
3. li converte in testo
4. li divide in chunk
5. calcola embedding dei chunk
6. salva chunk e metadata nei backend configurati
7. quando arriva una domanda, recupera i chunk piu' rilevanti
8. costruisce un prompt
9. chiede la risposta al modello

I file piu' importanti da capire per primi sono:

1. [app/main.py](app/main.py)
2. [app/service.py](app/service.py)
3. [app/parsers.py](app/parsers.py)
4. [app/chunking.py](app/chunking.py)
5. [app/retrieval.py](app/retrieval.py)
6. [app/vector_store.py](app/vector_store.py)
7. [app/repository.py](app/repository.py)
8. [app/ollama_client.py](app/ollama_client.py)

## Glossario Minimo

- Documento: un file sorgente come PDF, TXT, DOCX o Markdown.
- Chunk: un pezzo di testo piu' piccolo estratto da un documento.
- Embedding: rappresentazione numerica del testo, utile per confronto semantico.
- Metadata: informazioni di supporto come nome file, pagina, path, indice del chunk.
- Retrieval: ricerca dei chunk piu' rilevanti per una domanda.
- Prompt: testo finale inviato al modello per ottenere la risposta.
- API: endpoint HTTP che puoi chiamare da script, browser o altri programmi.

## File Python In `app/`

### [app/__init__.py](app/__init__.py)

Scopo semplice:
Dice a Python che la cartella `app/` va trattata come un package, cioe' come un insieme di moduli importabili.

Perche' esiste:
Senza questo file, in molti contesti Python farebbe piu' fatica a importare correttamente i moduli dell'applicazione.

Quando entra in gioco:
Non contiene logica applicativa vera e propria. Serve soprattutto alla struttura del progetto.

### [app/config.py](app/config.py)

Scopo semplice:
Raccoglie tutta la configurazione del sistema in un unico posto.

Cosa contiene:
- classi di configurazione come `AppSettings`, `DocumentSettings`, `ChunkingSettings`, `RetrievalSettings`, `OllamaSettings`, `StorageSettings`, `IngestSettings`, `WatchSettings`
- la classe `Settings`, che raggruppa tutte le sezioni
- le funzioni `load_settings()`, `_deep_update()` e `_apply_env_overrides()`

Cosa fa in pratica:
- legge il file YAML di configurazione
- applica eventuali override da variabili ambiente
- valida i valori letti
- crea anche alcune directory necessarie se non esistono ancora

Perche' e' importante:
Quasi tutti gli altri file dipendono da questo. Se vuoi cambiare porte, modelli, backend, cartelle o concorrenza di ingest, passi da qui.

Dipendenze importanti:
Non dipende dai moduli interni dell'app, ma viene usato da quasi tutti gli altri.

### [app/models.py](app/models.py)

Scopo semplice:
Definisce le strutture dati standard del progetto.

Cosa contiene:
- `DocumentChunk`: rappresenta un chunk di documento
- `SearchHit`: rappresenta un risultato di ricerca
- `QueryRequest`, `QueryResponse`, `QueryDebugResponse`: modelli per le API di query
- `IngestResponse`, `IngestStatusResponse`: modelli per lo stato e il risultato dell'indicizzazione
- `HealthResponse`: modello dell'endpoint health

Perche' e' importante:
Ti dice quali dati si passano i moduli tra loro e quali dati escono dalle API.

Come leggerlo se sei all'inizio:
Pensalo come il file che definisce i "contenitori ufficiali" delle informazioni.

### [app/utils.py](app/utils.py)

Scopo semplice:
Contiene funzioni di servizio piccole e riutilizzabili.

Funzioni principali:
- `sha256_text()`
- `sha256_file()`
- `normalize_text()`
- `approximate_token_count()`
- `safe_excerpt()`

Cosa fa in pratica:
- calcola hash per capire se un file o un chunk sono gia' stati visti
- pulisce il testo
- stima grossolanamente i token
- crea estratti brevi e sicuri per output e debug

Perche' e' importante:
E' usato in piu' parti del progetto e toglie rumore dal resto del codice.

### [app/logging_config.py](app/logging_config.py)

Scopo semplice:
Configura i log del progetto.

Funzioni principali:
- `configure_logging(level)`
- `get_logger(name)`

Cosa fa in pratica:
Decide come devono apparire i messaggi di log in console: data, livello, modulo, messaggio.

Perche' e' importante:
Quando cerchi di capire se qualcosa sta funzionando, questo file rende i log leggibili e coerenti.

### [app/parsers.py](app/parsers.py)

Scopo semplice:
Legge i file documentali e li trasforma in testo.

Funzioni principali:
- `parse_file(path)`
- parser interni per PDF, DOCX e testo semplice

Cosa fa in pratica:
- se il file e' PDF, estrae il testo pagina per pagina
- se e' DOCX, legge i paragrafi
- se e' TXT o MD, legge il contenuto testuale

Output concettuale:
Una lista di pagine, dove ogni elemento contiene numero pagina e testo.

Perche' e' importante:
E' il primo passo dell'ingestion. Se qui non si estrae bene il testo, tutto il resto peggiora.

Dipendenze interne:
Usa [app/utils.py](app/utils.py) per normalizzare il testo.

### [app/chunking.py](app/chunking.py)

Scopo semplice:
Divide il testo dei documenti in pezzi piu' piccoli, chiamati chunk.

Classe principale:
- `Chunker`

Metodi principali:
- `chunk_pages(...)`
- `_chunk_text(...)`
- `_build_overlap(...)`
- `_split_large_unit(...)`

Cosa fa in pratica:
- prova prima a spezzare per paragrafi
- poi per frasi
- se serve, scende fino a una divisione a parole
- crea sovrapposizione tra chunk vicini per non perdere contesto
- genera un `chunk_id` e un `content_hash`

Perche' e' importante:
I modelli lavorano meglio su testi piu' piccoli e il retrieval funziona molto meglio su unita' informative compatte.

Dipendenze interne:
Usa [app/models.py](app/models.py) e [app/utils.py](app/utils.py).

### [app/ollama_client.py](app/ollama_client.py)

Scopo semplice:
Parla con Ollama via HTTP.

Classe principale:
- `OllamaClient`

Metodi principali:
- `embed(...)`
- `generate(...)`
- `stream_generate(...)`

Cosa fa in pratica:
- chiede embedding per i chunk e per le query
- chiede al modello la risposta finale
- gestisce anche la modalita' streaming
- ritenta automaticamente in caso di errori di rete temporanei

Perche' e' importante:
E' il ponte verso il modello. Senza questo file, il sistema non saprebbe parlare con Ollama.

### [app/vector_store.py](app/vector_store.py)

Scopo semplice:
Gestisce il salvataggio e la ricerca vettoriale dei chunk.

Classi principali:
- `BaseVectorStore`
- `ChromaVectorStore`
- `QdrantVectorStore`
- `VectorStore`

Cosa fa in pratica:
- salva chunk + embedding nel backend scelto
- rimuove chunk relativi a un file
- esegue ricerca vettoriale dato un embedding di query

Perche' e' importante:
E' il cuore della ricerca semantica.

Nota importante per capirlo bene:
`VectorStore` e' una facciata. Sotto puo' usare Chroma oppure Qdrant, ma il resto del codice chiama sempre la stessa interfaccia.

Dipendenze interne:
Usa [app/models.py](app/models.py).

### [app/repository.py](app/repository.py)

Scopo semplice:
Gestisce i metadata dei documenti e dei chunk.

Classi principali:
- `BaseMetadataRepository`
- `SqliteMetadataRepository`
- `PostgresMetadataRepository`
- `MetadataRepository`

Cosa salva:
- file indicizzati
- hash del file
- timestamp di indicizzazione
- chunk e relativi metadata

Cosa fa in pratica:
- legge se un file e' gia' noto
- aggiorna o sostituisce i chunk di un file
- rimuove un file dall'indice metadata
- elenca file e chunk

Perche' e' importante:
Serve sia per sapere cosa e' gia' indicizzato, sia per la parte BM25 del retrieval.

Nota importante:
Anche qui c'e' un'astrazione: il resto del progetto parla con `MetadataRepository`, che dietro usa SQLite o PostgreSQL.

### [app/retrieval.py](app/retrieval.py)

Scopo semplice:
Decide quali chunk sono piu' rilevanti per una domanda.

Classe principale:
- `HybridRetriever`

Metodi principali:
- `search(...)`
- `_bm25_search(...)`
- `_rerank_bonus(...)`
- `_tokenize(...)`

Cosa fa in pratica:
- esegue ricerca semantica con embedding
- esegue anche ricerca lessicale con BM25
- combina i due risultati in un ranking finale

Perche' e' importante:
Questo file decide cosa finira' nel contesto che il modello usera' per rispondere.

Se vuoi capire perche' una risposta e' buona o cattiva, spesso devi passare da qui.

Dipendenze interne:
Usa [app/models.py](app/models.py), [app/repository.py](app/repository.py) e [app/vector_store.py](app/vector_store.py).

### [app/prompting.py](app/prompting.py)

Scopo semplice:
Costruisce il prompt finale da inviare al modello.

Funzione principale:
- `build_prompt(question, hits, extractive=False)`

Cosa fa in pratica:
- prende i chunk recuperati
- li formatta con file, pagina e contenuto
- aggiunge istruzioni chiare al modello
- produce due stringhe: contesto e prompt completo

Perche' e' importante:
Lo stesso retrieval puo' produrre risposte diverse a seconda di come formatti il prompt.

### [app/service.py](app/service.py)

Scopo semplice:
E' il regista principale di tutto il progetto.

Classe principale:
- `RagService`

Cosa fa in pratica:
- inizializza repository, vector store, retriever, cache e client Ollama
- esegue la rescan dei documenti
- gestisce l'ingestion parallela dei file
- risponde alle domande
- costruisce risposte debug
- tiene traccia dello stato di ingest
- applica fallback quando il modello non risponde bene ma il contesto contiene gia' una risposta utile

Metodi particolarmente importanti:
- `rescan_documents()`
- `answer_question()`
- `debug_question()`
- `_run_query()`
- `_embed_in_batches()`
- `get_ingest_status()`

Perche' e' importante:
Se dovessi scegliere un solo file per capire davvero il progetto, questo sarebbe il piu' importante.

Dipendenze interne:
Usa quasi tutti i moduli principali del progetto.

### [app/watcher.py](app/watcher.py)

Scopo semplice:
Osserva la cartella dei documenti e reagisce quando un file cambia.

Classi principali:
- `DocumentWatcher`
- `_DocumentEventHandler`

Cosa fa in pratica:
- ascolta eventi filesystem
- aspetta un piccolo tempo di debounce
- poi chiede al servizio di rivalutare i documenti

Perche' e' utile:
In sviluppo o in modalita' standard puo' aggiornare l'indice senza dover lanciare a mano una rescan.

### [app/cli.py](app/cli.py)

Scopo semplice:
Permette di usare il sistema da terminale senza passare per le API HTTP.

Funzioni principali:
- `main()`
- `build_parser()`
- `_run()`

Comandi principali:
- `rescan`
- `ask`

Cosa fa in pratica:
Prepara la configurazione, crea il servizio e lancia il comando scelto.

Perche' e' utile:
E' comodo per test, script e automazioni.

### [app/main.py](app/main.py)

Scopo semplice:
Espone il progetto come API web con FastAPI.

Endpoint principali:
- `GET /health`
- `GET /documents`
- `POST /ingest/rescan`
- `GET /ingest/status`
- `POST /query`
- `POST /query/debug`
- `POST /query/stream`

Cosa fa in pratica:
- legge la configurazione
- configura i log
- crea un'istanza di `RagService`
- gestisce lo startup dell'applicazione
- lancia la rescan iniziale in background
- opzionalmente avvia il watcher

Perche' e' importante:
E' la porta di ingresso principale del backend.

Se apri il progetto come servizio web, il primo file da guardare e' questo.

### [app/evaluation.py](app/evaluation.py)

Scopo semplice:
Contiene metriche semplici per valutare la qualita' del retrieval.

Funzioni principali:
- `precision_at_k(...)`
- `recall_at_k(...)`

Cosa fa in pratica:
Misura quanto i risultati recuperati sono buoni rispetto a un insieme di risultati attesi.

Perche' e' utile:
Non serve al flusso operativo del progetto, ma e' utile per test e valutazione tecnica.

## File Python In `tests/`

### [tests/test_chunking.py](tests/test_chunking.py)

Scopo semplice:
Verifica che il chunker si comporti correttamente.

Cosa controlla:
- che il chunking produca piu' chunk quando necessario
- che i chunk prodotti non siano vuoti
- che la logica base di overlap e dimensione funzioni

Perche' e' utile:
Evita regressioni in una parte molto importante del pipeline.

### [tests/test_evaluation.py](tests/test_evaluation.py)

Scopo semplice:
Verifica che le metriche di evaluation restituiscano i valori attesi.

Cosa controlla:
- correttezza di `precision_at_k`
- correttezza di `recall_at_k`

Perche' e' utile:
Garantisce che i numeri usati per valutare il retrieval siano affidabili.

## Ordine Consigliato Di Lettura

Se non conosci Python, ti consiglio questo ordine:

1. [app/models.py](app/models.py)
2. [app/config.py](app/config.py)
3. [app/main.py](app/main.py)
4. [app/service.py](app/service.py)
5. [app/parsers.py](app/parsers.py)
6. [app/chunking.py](app/chunking.py)
7. [app/retrieval.py](app/retrieval.py)
8. [app/prompting.py](app/prompting.py)
9. [app/ollama_client.py](app/ollama_client.py)
10. [app/vector_store.py](app/vector_store.py)
11. [app/repository.py](app/repository.py)
12. [app/watcher.py](app/watcher.py)
13. [app/cli.py](app/cli.py)
14. [app/evaluation.py](app/evaluation.py)
15. [tests/test_chunking.py](tests/test_chunking.py)
16. [tests/test_evaluation.py](tests/test_evaluation.py)

## Riassunto Finale In Una Frase Per File

- [app/config.py](app/config.py): decide come il sistema deve partire e con quali parametri.
- [app/models.py](app/models.py): definisce i tipi di dati che si scambiano i moduli.
- [app/parsers.py](app/parsers.py): legge i documenti e li trasforma in testo.
- [app/chunking.py](app/chunking.py): spezza il testo in pezzi utili.
- [app/ollama_client.py](app/ollama_client.py): parla con Ollama.
- [app/vector_store.py](app/vector_store.py): salva e cerca gli embedding.
- [app/repository.py](app/repository.py): salva e legge i metadata dei documenti.
- [app/retrieval.py](app/retrieval.py): sceglie i chunk migliori per rispondere.
- [app/prompting.py](app/prompting.py): costruisce il prompt da dare al modello.
- [app/service.py](app/service.py): orchestra tutto il flusso.
- [app/main.py](app/main.py): espone il backend via API HTTP.
- [app/watcher.py](app/watcher.py): osserva modifiche ai documenti.
- [app/cli.py](app/cli.py): permette di usare il sistema da terminale.
- [app/evaluation.py](app/evaluation.py): misura la qualita' del retrieval.
- [tests/test_chunking.py](tests/test_chunking.py): controlla il chunking.
- [tests/test_evaluation.py](tests/test_evaluation.py): controlla le metriche di evaluation.

Se vuoi, il passo naturale successivo e' leggere questa guida assieme a [README.md](README.md) e [ARCHITETTURA_PROGETTO.md](ARCHITETTURA_PROGETTO.md): il README ti spiega cosa fa il progetto, questa guida ti spiega dove guardare nel codice.