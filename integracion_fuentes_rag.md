# Separación de Fuentes por Colección en el RAG

## Contexto y objetivo

El sistema RAG actualmente tiene una sola colección Qdrant (`document_child_chunks`) donde
conviven documentos subidos manualmente y normas scrapeadas. El agente no puede distinguirlos
porque `tools.py` ejecuta un `similarity_search` plano sin filtros.

**Objetivo:** Colección separada `normas_child_chunks` para las normas de El Peruano.
El agente tendrá dos herramientas de búsqueda distintas con descripciones diferentes,
permitiendo al LLM decidir automáticamente cuál usar según la pregunta del usuario.

> **Nota:** Los cambios de `document_chunker.py` y `manager.py` del MD anterior
> ya están deployados y son compatibles con este. Este MD es complementario.

---

## Archivos a modificar (5)

### 1. `project/config.py`

Agregar al final del bloque de configuración de Qdrant:

```diff
 CHILD_COLLECTION = "document_child_chunks"
+NORMAS_COLLECTION = "normas_child_chunks"
+NORMAS_MARKDOWN_DIR = os.environ.get("NORMAS_MARKDOWN_DIR", os.path.join(_BASE_DIR, "normas_markdown_docs"))
 SPARSE_VECTOR_NAME = "sparse"
```

---

### 2. `project/shared/agent/rag_system.py`

```diff
 class RAGSystem:

-    def __init__(self, collection_name=config.CHILD_COLLECTION):
+    def __init__(self, collection_name=config.CHILD_COLLECTION, normas_collection_name=config.NORMAS_COLLECTION):
         self.collection_name = collection_name
+        self.normas_collection_name = normas_collection_name
         self.vector_db = VectorDbManager()
         self.parent_store = ParentStoreManager()
         self.chunker = DocumentChunker()
         self.observability = Observability()
         self.agent_graph = None
         self.recursion_limit = config.GRAPH_RECURSION_LIMIT

     def initialize(self):
         self.vector_db.create_collection(self.collection_name)
+        self.vector_db.create_collection(self.normas_collection_name)
         collection = self.vector_db.get_collection(self.collection_name)
+        normas_collection = self.vector_db.get_collection(self.normas_collection_name)

         llm = ChatVertexAI(
             model=config.LLM_MODEL,
             temperature=config.LLM_TEMPERATURE,
             project=config.GCP_PROJECT,
             location=config.GCP_LLM_LOCATION
         )
-        tools = ToolFactory(collection).create_tools()
+        tools = ToolFactory(collection, normas_collection).create_tools()
         self.agent_graph = create_agent_graph(llm, tools)
```

---

### 3. `project/rag_agent/tools.py`

```diff
 class ToolFactory:
     
-    def __init__(self, collection):
+    def __init__(self, collection, normas_collection=None):
         self.collection = collection
+        self.normas_collection = normas_collection
         self.parent_store_manager = ParentStoreManager()
     
     def _search_child_chunks(self, query: str, limit: int) -> str:
-        """Search for the top K most relevant child chunks.
+        """Search in manually uploaded documents (PDFs, technical manuals, reports).
+        Use this tool for general document queries not related to Peruvian legal norms.
         
         Args:
             query: Search query string
             limit: Maximum number of results to return
         """
         try:
             results = self.collection.similarity_search(query, k=limit)
             if not results:
                 return "NO_RELEVANT_CHUNKS"

             return "\n\n".join([
                 f"Parent ID: {doc.metadata.get('parent_id', '')}\n"
                 f"File Name: {doc.metadata.get('source', '')}\n"
                 f"Content: {doc.page_content.strip()}"
                 for doc in results
             ])            

         except Exception as e:
             return f"RETRIEVAL_ERROR: {str(e)}"

+    def _search_normas_chunks(self, query: str, limit: int) -> str:
+        """Search exclusively in legal norms from El Peruano (Decretos Supremos,
+        Resoluciones Ministeriales, Leyes, Ordenanzas, etc.).
+        Use this tool when the user asks about Peruvian legislation, regulations,
+        ministerial entities (MINEM, MINAM, MEF, etc.), or publication dates.
+
+        Args:
+            query: Search query string
+            limit: Maximum number of results to return
+        """
+        if not self.normas_collection:
+            return "NORMAS_COLLECTION_NOT_CONFIGURED"
+        try:
+            results = self.normas_collection.similarity_search(query, k=limit)
+            if not results:
+                return "NO_RELEVANT_NORMAS"
+
+            return "\n\n".join([
+                f"Parent ID: {doc.metadata.get('parent_id', '')}\n"
+                f"Fuente: {doc.metadata.get('source', '')}\n"
+                f"Entidad: {doc.metadata.get('entidad_nombre', 'N/A')}\n"
+                f"Tipo: {doc.metadata.get('tipo_dispositivo', 'N/A')}\n"
+                f"Fecha: {doc.metadata.get('fecha_publicacion', 'N/A')}\n"
+                f"Content: {doc.page_content.strip()}"
+                for doc in results
+            ])
+
+        except Exception as e:
+            return f"RETRIEVAL_ERROR: {str(e)}"

     # ... (métodos _retrieve_many_parent_chunks y _retrieve_parent_chunks sin cambios)

     def create_tools(self) -> List:
         """Create and return the list of tools."""
         search_tool = tool("search_child_chunks")(self._search_child_chunks)
+        search_normas_tool = tool("search_normas_chunks")(self._search_normas_chunks)
         retrieve_tool = tool("retrieve_parent_chunks")(self._retrieve_many_parent_chunks)
         
-        return [search_tool, retrieve_tool]
+        return [search_tool, search_normas_tool, retrieve_tool]
```

---

### 4. `project/services/ingestion/routes.py`

```diff
 @router.post("/upload")
 async def upload_documents(
     files: List[UploadFile] = File(...),
     metadata_urls: str = Form(None),
+    source_collection: str = Form(default=None),
     api_key: str = Depends(verify_api_key)
 ):
     if not rag_system.agent_graph:
         rag_system.initialize()

-    doc_manager = DocumentManager(rag_system)
+    doc_manager = DocumentManager(rag_system, source_collection=source_collection)
```

---

### 5. `project/services/ingestion/manager.py`

```diff
+import config as cfg

 class DocumentManager:

-    def __init__(self, rag_system):
+    def __init__(self, rag_system, source_collection=None):
         self.rag_system = rag_system
-        self.markdown_dir = Path(config.MARKDOWN_DIR)
+        # Si source_collection es normas → usar colección y directorio de normas
+        self.is_normas = (source_collection == cfg.NORMAS_COLLECTION)
+        self.markdown_dir = Path(cfg.NORMAS_MARKDOWN_DIR if self.is_normas else cfg.MARKDOWN_DIR)
+        self.collection_name = source_collection or rag_system.collection_name
         self.markdown_dir.mkdir(parents=True, exist_ok=True)
         self.pdf_dir = Path(config.PDF_DIR)
         self.pdf_dir.mkdir(parents=True, exist_ok=True)
```

Y más abajo en `add_documents`, reemplazar la referencia a `self.rag_system.collection_name`:

```diff
-                collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
+                collection = self.rag_system.vector_db.get_collection(self.collection_name)
```

---

## Cambio en el ETL (lado scraper)

En `scripts/etl_normas_to_rag.py`, agregar `source_collection` al POST:

```diff
         response = requests.post(
             API_URL,
             files=files_payload,
-            data={"metadata_urls": json.dumps(metadata_dict)},
+            data={
+                "metadata_urls": json.dumps(metadata_dict),
+                "source_collection": "normas_child_chunks",
+            },
             headers={"x-api-key": API_KEY},
             timeout=600,
         )
```

---

## Resultado esperado en Qdrant

| Colección | Contenido | Metadata disponible |
|---|---|---|
| `document_child_chunks` | PDFs subidos manualmente | `source`, `parent_id` |
| `normas_child_chunks` | Normas de El Peruano | `source`, `parent_id`, `entidad_id`, `entidad_nombre`, `tipo_dispositivo`, `fecha_publicacion`, `fuente`, `op` |

---

## Comportamiento del agente después del deploy

| Pregunta del usuario | Tool que usa el LLM |
|---|---|
| "¿Qué dice el Decreto Supremo sobre vehículos del Estado?" | `search_normas_chunks` |
| "¿Qué dice el manual de procedimientos?" | `search_child_chunks` |
| "Dame el texto completo de la norma X" | `search_normas_chunks` → `retrieve_parent_chunks` |

---

## Orden de deploy

1. Aplicar los 5 diffs anteriores y hacer deploy a Cloud Run
2. Confirmar que la nueva colección `normas_child_chunks` fue creada en Qdrant
3. Avisarle al equipo scraper para ejecutar el ETL con el nuevo `source_collection`

