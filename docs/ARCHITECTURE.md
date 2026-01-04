# 📊 Arquitectura de Datos: Hybrid RAG System

## Visión General

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLUJO DE INGESTA                                │
└─────────────────────────────────────────────────────────────────────────┘

     Google Drive
          │
          ▼
   ┌──────────────┐
   │   PDF File   │  (trigger: fileCreated)
   └──────────────┘
          │
          ├──────────────────────────────────────────────────────┐
          ▼                                                      ▼
   ┌──────────────┐                                      ┌──────────────┐
   │ PINECONE     │  (Vía A: Semántica)                  │ LIGHTRAG     │  (Vía B: Conceptual)
   │ Assistant    │                                      │ Service      │
   └──────────────┘                                      └──────────────┘
          │                                                      │
          ▼                                                      ▼
   ┌──────────────┐                                      ┌──────────────┐
   │ Pinecone     │                                      │ nano-vectordb│
   │ Index        │                                      │ + NetworkX   │
   └──────────────┘                                      └──────────────┘
          │
          ▼
   ┌──────────────┐
   │  SUPABASE    │
   │  (Metadatos) │
   └──────────────┘
```

## Responsabilidades por Sistema

| Sistema | Rol | Tipo de Búsqueda | Persistencia |
|---------|-----|------------------|--------------|
| **Pinecone** | Búsqueda semántica | "¿Qué docs hablan de X?" | Cloud |
| **LightRAG** | Razonamiento conceptual | "¿Cómo se relaciona X con Y?" | Railway Volume |
| **Supabase** | Gobernanza/trazabilidad | Estado de ingesta | PostgreSQL |

---

## Modelo de Datos

### 1️⃣ Pinecone Assistant

Almacena vectores de chunks con metadatos del archivo.

```json
{
  "id": "file_abc123",
  "vectors": [...],
  "metadata": {
    "source": "google_drive",
    "filename": "EUDI_Wallet_FAQs.pdf",
    "drive_file_id": "1BGWr..."
  }
}
```

### 2️⃣ LightRAG (nano-vectordb + NetworkX)

Almacena grafo de conocimiento en `/app/data/`:

| Archivo | Contenido |
|---------|-----------|
| `kv_store_full_docs.json` | Documentos completos |
| `kv_store_text_chunks.json` | Chunks de texto |
| `vdb_entities.json` | Vectores de entidades |
| `vdb_relationships.json` | Vectores de relaciones |
| `graph_chunk_entity_relation.graphml` | Grafo NetworkX |

**Entidad (nodo):**
```json
{
  "entity_name": "EUDI Wallet",
  "entity_type": "TECHNOLOGY",
  "description": "European Digital Identity Wallet",
  "source_ids": ["doc_123"]
}
```

**Relación (edge):**
```json
{
  "src_id": "EUDI Wallet",
  "tgt_id": "eIDAS 2",
  "relation": "COMPLIES_WITH",
  "weight": 0.95
}
```

### 3️⃣ Supabase (Metadatos de Gobernanza)

```sql
CREATE TABLE ingest_items (
  id UUID PRIMARY KEY,
  drive_file_id TEXT,
  drive_file_name TEXT,
  pinecone_file_id TEXT,
  status TEXT,  -- 'pending' | 'available'
  enrichment JSONB,
  created_at TIMESTAMPTZ
);
```

---

## Flujo de Query (Hybrid RAG)

```
      ┌─────────────┐
      │   Query     │
      └─────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌─────────┐     ┌─────────────┐
│Pinecone │     │  LightRAG   │
│(chunks) │     │  (grafo)    │
└─────────┘     └─────────────┘
    │                 │
    └────────┬────────┘
             ▼
        Respuesta
        (fusionada)
```

---

## Payload de Ingesta LightRAG

```json
{
  "text": "Contenido del documento...",
  "metadata": {
    "source": "google_drive",
    "filename": "EUDI_FAQs.pdf",
    "drive_file_id": "1abc...",
    "doc_id": "1abc..._2026-01-04T...",
    "modified_time": "2026-01-04T10:30:00Z"
  }
}
```

El `doc_id` combina `drive_file_id` + `modified_time` para idempotencia.
