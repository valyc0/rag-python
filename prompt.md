PROMPT

Sei un esperto di sistemi RAG (Retrieval-Augmented Generation), architetture LLM e backend scalabili.

Il tuo obiettivo è progettare e implementare un sistema RAG completo, robusto e ottimizzato, che utilizzi:

LLM: Ollama con modello llama3.2 (accessibile via REST API)
Input: documenti (PDF, TXT, DOCX, ecc.) presenti in una directory locale
Output: risposte accurate e contestuali a domande dell’utente
🎯 Obiettivi del sistema

Il sistema deve:

Permettere di fare domande in linguaggio naturale
Recuperare i documenti più rilevanti dalla knowledge base
Costruire un contesto ottimizzato
Generare risposte coerenti, precise e grounded nei documenti
Evitare hallucinations
🧱 Architettura richiesta

Descrivi e implementa chiaramente queste componenti:

1. Ingestion Pipeline
Scansione directory documenti
Parsing file:
PDF → estrazione testo (gestire anche PDF complessi)
TXT / DOCX → parsing diretto
Pulizia testo (normalizzazione, rimozione caratteri inutili)
Chunking intelligente:
dimensione chunk (es. 500–1000 token)
overlap (es. 10–20%)
evitare tagli semantici
2. Embedding
Usa un modello embedding compatibile (locale o via API)
Genera embedding per ogni chunk
Spiega quale modello usare e perché
Ottimizza:
batch processing
caching
3. Vector Store
Usa un database vettoriale (scegline uno e motivalo):
Chroma / FAISS / Weaviate / Qdrant
Salva:
embedding
testo chunk
metadata (file, pagina, posizione)
4. Retrieval
Implementa:
similarity search (top-k)
eventualmente hybrid search (BM25 + embedding)
Aggiungi:
filtering per metadata
reranking (opzionale ma consigliato)
5. Prompt Engineering

Costruisci prompt ottimizzati per Llama 3.2:

Istruzioni chiare:
rispondere SOLO con info presenti nei documenti
dire “non lo so” se info non trovata
Struttura:
contesto
domanda
istruzioni

Esempio:

separatori chiari
limitare lunghezza contesto
evitare rumore
6. Generazione (LLM via Ollama REST)
Spiega come chiamare Ollama via HTTP (curl o codice)
Parametri:
temperature
top_p
max_tokens
Gestione timeout e retry
7. Pipeline Query

Flusso completo:

input utente
embedding query
retrieval chunk
costruzione contesto
chiamata LLM
risposta finale
⚙️ Requisiti tecnici
Linguaggio: preferibilmente Python o Java (Spring Boot)
Codice modulare e pulito
Configurazione via file (es. YAML/properties)
Logging dettagliato
Gestione errori
🚀 Ottimizzazioni richieste

Implementa best practices:

deduplicazione chunk
compressione contesto (context window optimization)
caching risposte
aggiornamento incrementale documenti
supporto directory dinamica (watcher filesystem)
🧪 Valutazione qualità

Aggiungi:

test di retrieval
metriche:
precision@k
recall
esempi di query e output attesi
📦 Output richiesto

Fornisci:

Architettura spiegata chiaramente
Codice completo funzionante
Esempi di chiamate REST a Ollama
Esempio reale:
documenti → query → risposta
Suggerimenti per scalabilità e produzione
❗ Vincoli importanti
Il sistema deve funzionare completamente in locale
Nessun servizio cloud obbligatorio
Deve essere estendibile facilmente
🧠 Extra (opzionale ma consigliato)
Multi-query retrieval
Query rewriting
Answer streaming
UI minimale (CLI o web)
✅ Risultato atteso

Un sistema RAG:

preciso
scalabile
modulare


usa docker dove puoi.
pronto per produzione