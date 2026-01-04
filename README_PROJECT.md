# 🧠 LightRAG EUDI Knowledge Graph

Sistema de Grafo de Conocimiento para documentación EUDI Wallet usando [LightRAG](https://github.com/HKUDS/LightRAG).

## 🏗️ Arquitectura

```
n8n Workflow (Hybrid RAG)
    │
    ├── Vía A: Pinecone Assistant (Semántica)
    │   └── Búsqueda vectorial tradicional
    │
    └── Vía B: LightRAG Service (Conceptual)
        ├── Extracción de Entidades (LLM)
        ├── Extracción de Relaciones (LLM)
        ├── Grafo (NetworkX + nano-vectordb)
        └── Persistencia (Railway Volume)
```

## 📂 Estructura

| Carpeta/Archivo | Descripción |
|-----------------|-------------|
| `lightrag-service/` | Microservicio FastAPI desplegado en Railway |
| `n8n-workflow-PRODUCTION.json` | **Workflow n8n válido** para ingesta |
| `smoke_test_ingest.sh` | Script de pruebas de ingesta |
| `_archive/` | Workflows obsoletos |

## 🚀 Despliegue

### Railway (Backend)

```bash
cd lightrag-service
railway up
```

**Variables requeridas:**
- `OPENAI_API_KEY`
- `SERVICE_API_KEY`

**Volumen:** `/app/data` (crítico para persistencia)

### n8n (Orquestación)

1. Importar `n8n-workflow-PRODUCTION.json`
2. Añadir variable `LIGHTRAG_API_KEY`

## 🔗 Endpoints

| Endpoint | Método | Auth | Descripción |
|----------|--------|------|-------------|
| `/health` | GET | ❌ | Health check |
| `/ingest` | POST | ✅ | Ingestar documento |
| `/query` | POST | ✅ | Consultar grafo |

## 📚 Documentación

Ver [lightrag-service/README.md](./lightrag-service/README.md) para detalles técnicos.

## 🏷️ Versión

- **LightRAG**: 1.4.9rc4
- **Storage**: nano-vectordb + NetworkX
- **Producción**: Railway
