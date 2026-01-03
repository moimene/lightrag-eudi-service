# LightRAG EUDI Knowledge Graph Service

Microservicio para ingestión de documentos en un Grafo de Conocimiento usando [LightRAG](https://github.com/HKUDS/LightRAG).

## 🏗️ Arquitectura

```
n8n (Pinecone Assistant UNIFICADO)
    │
    ├── Vía A: Pinecone Assistant (Rápida/Semántica)
    │   └── Búsqueda vectorial tradicional
    │
    └── Vía B: LightRAG Service (Profunda/Conceptual)  ← Este servicio
        ├── Extracción de Entidades (LLM)
        ├── Extracción de Relaciones (LLM)
        ├── Construcción de Grafo
        └── Vectorización en Pinecone (namespaces separados)
```

## 🚀 Despliegue en Railway

### 1. Crear nuevo servicio

```bash
# Conectar repositorio desde GitHub
railway link
railway up
```

### 2. Configurar Variables de Entorno

En el dashboard de Railway, añadir:

| Variable | Descripción |
|----------|-------------|
| `OPENAI_API_KEY` | API key de OpenAI para LLM |
| `PINECONE_API_KEY` | API key de Pinecone |
| `PINECONE_INDEX_NAME` | Nombre del índice (ej: `liquid-graph`) |
| `PINECONE_NS_ENTITIES` | Namespace para entidades (default: `liquid_entities`) |
| `PINECONE_NS_RELATIONS` | Namespace para relaciones (default: `liquid_relations`) |
| `PINECONE_NS_CHUNKS` | Namespace para chunks (default: `liquid_chunks`) |

### 3. Montar Volumen (CRÍTICO)

1. En Railway Dashboard → Tu servicio → Settings
2. Add Volume
3. Mount path: `/app/data`
4. Tamaño: mínimo 1GB

> ⚠️ **Sin volumen, el grafo se pierde en cada deploy**

## 📡 Endpoints

### `GET /health`
Health check del servicio.

```bash
curl https://tu-app.up.railway.app/health
```

### `POST /ingest`
Ingestar documento en el grafo. Retorna inmediatamente, procesa en background.

```bash
curl -X POST https://tu-app.up.railway.app/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "text": "El EUDI Wallet es una cartera de identidad digital europea...",
    "metadata": {
      "source": "google_drive",
      "filename": "eudi_overview.pdf",
      "summary": "Introducción al EUDI Wallet",
      "keywords": ["EUDI", "identidad digital", "eIDAS"]
    }
  }'
```

### `POST /query`
Consultar el grafo de conocimiento.

```bash
curl -X POST https://tu-app.up.railway.app/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Cuáles son los requisitos de seguridad del EUDI Wallet?",
    "mode": "hybrid"
  }'
```

Modos disponibles:
- `local`: Solo entidades (hechos precisos)
- `global`: Solo relaciones (temas abstractos)
- `hybrid`: Ambos (recomendado)

## 🔧 Desarrollo Local

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables
export OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY="..."
export PINECONE_INDEX_NAME="liquid-graph"
export LIGHTRAG_WORKDIR="./data"

# Ejecutar
python main.py
```

## 📁 Estructura

```
lightrag-service/
├── Dockerfile           # Imagen Docker para Railway
├── requirements.txt     # Dependencias Python
├── main.py             # Servidor FastAPI
├── pinecone_storage.py # Conector LightRAG → Pinecone
└── README.md           # Esta documentación
```

## 🔗 Integración con n8n

Añadir nodo HTTP Request después de "Merge Data":

- **URL**: `https://tu-app.up.railway.app/ingest`
- **Method**: POST
- **Body**: JSON con `text` y `metadata`

Ver [implementation_plan.md](../implementation_plan.md) para detalles completos.
