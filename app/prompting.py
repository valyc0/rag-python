from __future__ import annotations

from app.models import SearchHit


def build_prompt(question: str, hits: list[SearchHit], *, extractive: bool = False) -> tuple[str, str]:
    context_blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        block = (
            f"[Fonte {index}]\n"
            f"File: {hit.metadata.get('file_name')}\n"
            f"Percorso: {hit.metadata.get('source_path')}\n"
            f"Pagina: {hit.metadata.get('page_number')}\n"
            f"Contenuto:\n{hit.text}"
        )
        context_blocks.append(block)

    context = "\n\n-----\n\n".join(context_blocks)
    if extractive:
        instructions = (
            "Sei un assistente RAG estrattivo. Rispondi solo con informazioni esplicite presenti nel contesto. "
            "Se trovi nel contesto un valore preciso richiesto dalla domanda, restituiscilo in apertura in forma diretta e breve. "
            "Se il contesto non contiene dati sufficienti, rispondi esattamente con 'Non lo so in base ai documenti forniti.'.\n\n"
            f"CONTESTO\n{context}\n\n"
            f"DOMANDA\n{question}\n\n"
            "ISTRUZIONI\n"
            "- Cerca prima una risposta letterale o numerica nel contesto.\n"
            "- Se la domanda chiede una temperatura, data, numero o soglia, riporta il valore esatto.\n"
            "- Usa massimo 2 frasi.\n"
            "- Nella seconda frase indica file e pagina.\n"
            "- Non aggiungere spiegazioni non richieste.\n"
        )
    else:
        instructions = (
            "Sei un assistente RAG rigoroso. Rispondi usando solo le informazioni presenti nel contesto. "
            "Se il contesto non contiene dati sufficienti, rispondi esattamente con 'Non lo so in base ai documenti forniti.'. "
            "Non inventare, non completare con conoscenza esterna. Se nel contesto e' presente una risposta fattuale precisa, forniscila in modo diretto nella prima frase.\n\n"
            f"CONTESTO\n{context}\n\n"
            f"DOMANDA\n{question}\n\n"
            "ISTRUZIONI\n"
            "- Usa solo fatti presenti nel contesto.\n"
            "- Se ci sono conflitti, evidenzialo.\n"
            "- Sii conciso ma specifico.\n"
            "- Se esiste un valore preciso richiesto dalla domanda, riportalo esplicitamente.\n"
            "- Quando possibile, menziona file e pagina usati.\n"
        )
    prompt = instructions
    return context, prompt
