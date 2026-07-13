"""
ETL: PostgreSQL (normas) → API RAG con metadata enriquecida.
Carga histórica de una sola vez — lee todas las normas con texto_completo.

Uso:
    /home/gcp_setel_oee/agente-batch/venv/bin/python scripts/etl_normas_to_rag.py
    (lee DATABASE_URL y ADMIN_API_KEY desde el .env del proyecto)
"""
import os
import json
import logging
import tempfile
import shutil
import time
import requests
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_PATH = Path(__file__).parent.parent / "logs" / "etl_normas_to_rag.log"
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),  # también imprime en consola
    ]
)
log = logging.getLogger(__name__)

# Cargar .env desde la raíz del proyecto (ScraperElPeruano/.env)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ["DATABASE_URL"]
API_URL = os.environ.get("API_URL", "https://agentic-rag-800690522557.us-central1.run.app/api/documents/upload")
API_KEY = os.environ.get("ADMIN_API_KEY", "admin5124")

# ── Extracción ────────────────────────────────────────────────────────────────
def fetch_normas(cur):
    cur.execute("""
        SELECT n.op, n.texto_completo, n.url_pdf, n.url_web,
               n.tipo_dispositivo, n.fecha_publicacion, n.fuente,
               e.codigo_peruano AS entidad_id, e.nombre AS entidad_nombre
        FROM normas n
        JOIN entidades e ON e.codigo_peruano = n.entidad_id
        WHERE n.texto_completo IS NOT NULL
          AND n.texto_completo != ''
        ORDER BY n.op
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

# ── Carga ─────────────────────────────────────────────────────────────────────
def ingest_all(normas):
    temp_dir = Path(tempfile.mkdtemp())
    files_payload = []
    metadata_dict = {}

    log.info(f"Preparando archivos temporales en {temp_dir}")

    try:
        for norma in normas:
            file_name = f"{norma['op']}.md"
            file_path = temp_dir / file_name

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(norma["texto_completo"])

            metadata_dict[file_name] = {
                "source_url": norma["url_web"] or norma["url_pdf"] or norma["op"],
                "entidad_id": norma["entidad_id"],
                "entidad_nombre": norma["entidad_nombre"],
                "tipo_dispositivo": norma["tipo_dispositivo"] or "Desconocido",
                "fecha_publicacion": str(norma["fecha_publicacion"]) if norma["fecha_publicacion"] else None,
                "fuente": norma["fuente"] or "desconocida",
                "op": norma["op"],
            }

        # Log muestra de los primeros 5 ops que se van a enviar
        sample_ops = [n["op"] for n in normas[:5]]
        log.info(f"Muestra de ops a enviar: {sample_ops} ...")

        for file_path in sorted(temp_dir.glob("*.md")):
            files_payload.append(
                ("files", (file_path.name, open(file_path, "rb"), "text/markdown"))
            )

        log.info(f"📤 Enviando {len(files_payload)} archivos a {API_URL}...")
        t0 = time.time()

        response = requests.post(
            API_URL,
            files=files_payload,
            data={
                "metadata_urls": json.dumps(metadata_dict),
                "source_collection": "normas_child_chunks",
            },
            headers={"x-api-key": API_KEY},
            timeout=600,
        )

        elapsed = round(time.time() - t0, 1)
        log.info(f"Respuesta en {elapsed}s — HTTP {response.status_code}")

        if response.status_code == 200:
            body = response.json()
            stats = body.get("stats", {})
            added   = stats.get("added", "?")
            skipped = stats.get("skipped", "?")
            rejected = stats.get("rejected", [])
            log.info(f"✅ Resultado — added: {added} | skipped: {skipped} | rejected: {rejected}")

            if skipped == len(normas):
                log.warning(
                    "⚠️  TODAS las normas fueron saltadas. "
                    "Probablemente el MARKDOWN_DIR del RAG ya tiene los archivos .md "
                    "de una ingesta previa. El equipo RAG debe ejecutar 'clear_all()' "
                    "o eliminar los archivos del bucket para forzar reingesta."
                )
        else:
            log.error(f"❌ Error API ({response.status_code}): {response.text[:500]}")

    finally:
        for _, ft in files_payload:
            ft[1].close()
        shutil.rmtree(temp_dir)
        log.info(f"🧹 Directorio temporal eliminado.")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info(f"ETL iniciado — {datetime.utcnow().isoformat()}Z")
    log.info(f"API destino: {API_URL}")

    log.info("🔌 Conectando a PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        normas = fetch_normas(cur)
        if not normas:
            log.info("ℹ️  No hay normas con texto_completo para ingestar.")
            return

        log.info(f"📦 {len(normas)} normas encontradas en DB.")
        ingest_all(normas)

    finally:
        cur.close()
        conn.close()
        log.info(f"ETL finalizado — {datetime.utcnow().isoformat()}Z")
        log.info("=" * 60)

if __name__ == "__main__":
    main()
