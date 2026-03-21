# Ollama

Questa cartella non contiene piu' un compose separato.

La sorgente di verita' Docker del progetto e' una sola:

- [docker-compose.yml](../docker-compose.yml)

## Perche'

Prima esisteva una duplicazione:

- compose standalone qui dentro per Ollama
- compose completo in root per l'intero sistema RAG

Questo creava ambiguita' su quale stack usare davvero.

Ora il progetto usa un solo compose ufficiale in root, che avvia:

- Ollama
- API RAG

## Come avviare

Dalla root del progetto:

```bash
chmod +x start.sh
./start.sh
```

Oppure da questa cartella, usando lo script compatibile:

```bash
cd ollama
./start.sh
```

In questo secondo caso, lo script delega comunque allo startup root.

## Modelli usati

- `llama3.2` per la generazione
- `nomic-embed-text` per gli embedding

## Porta host di default

Per evitare conflitti con altri servizi gia' presenti sulla macchina, il progetto espone di default Ollama su `11435`, non su `11434`.

La porta puo' essere cambiata con la variabile `OLLAMA_HOST_PORT`.

## Note

- il runtime resta completamente locale
- i modelli sono salvati nel volume Docker `ollama_data`
- l'avvio consigliato resta quello dalla root del progetto
