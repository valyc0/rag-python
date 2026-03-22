# Production Deployment

Questa variante usa uno stack piu' adatto alla produzione rispetto alla modalita' di sviluppo:

- PostgreSQL per metadata e stato
- Qdrant come vector database server
- Ollama separato come servizio persistente
- FastAPI con container healthchecked
- watcher disabilitato per evitare comportamento ambiguo in ambienti multi-processo

## Perche' questa variante

La configurazione base del progetto usa SQLite e Chroma embedded, che vanno bene per sviluppo e single-node leggero.

La variante produzione passa a:

- PostgreSQL per concorrenza, backup e affidabilita' maggiori
- Qdrant per un vector store server-based piu' adatto a deployment persistenti

## File dedicati

- [docker-compose.prod.yml](docker-compose.prod.yml)
- [config/config.prod.yaml](config/config.prod.yaml)
- [start-prod.sh](start-prod.sh)
- [.env.prod.example](.env.prod.example)

## Avvio rapido

1. Crea un file `.env.prod` a partire da [.env.prod.example](.env.prod.example)
2. Se vuoi una password diversa dalla default, imposta `POSTGRES_PASSWORD`
3. Avvia:

```bash
chmod +x start-prod.sh
./start-prod.sh
```

Per fermare rapidamente stack standard e production con un solo comando:

```bash
chmod +x stop.sh
./stop.sh
```

Se vuoi fermare e rimuovere anche i volumi Docker del progetto:

```bash
./stop.sh --volumes
```

## Controlli

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8010/health
curl http://localhost:8010/ingest/status
curl http://localhost:11435/api/tags
curl http://localhost:6333/collections
```

## Variabili importanti

- `POSTGRES_PASSWORD`
- `RAG_API_HOST_PORT`
- `OLLAMA_HOST_PORT`
- `QDRANT_HOST_PORT`
- `RAG_INGEST_CONCURRENT_FILES`

La password di default del setup production e' `postgres`.
La concorrenza di ingest dei file e' `2` di default.

## Note operative

- i documenti restano montati da [documents](documents)
- i dati persistenti stanno nei volumi Docker `postgres_data`, `qdrant_data`, `ollama_data`, `rag_api_data`
- il watcher filesystem e' disabilitato in prod; usa rescan esplicito quando aggiungi documenti
- per vedere se l'indicizzazione e' in corso usa `GET /ingest/status`; l'endpoint espone file correnti, coda residua e concorrenza massima

## Rescan e query

```bash
curl -X POST http://localhost:8010/ingest/rescan
curl -s -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Riassumi il documento"}' | python3 -m json.tool
```

Per eliminare un documento dal corpus host e aggiornare subito l'indice:

```bash
./script/delete_document.sh "1Samuele.pdf"
```
