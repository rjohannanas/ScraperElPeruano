import logging
import httpx
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(funcName)s → %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),  # Terminal
        logging.FileHandler("scraper.log", encoding="utf-8")  # Archivo
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────
ENTIDADES = {
    "MEF":     2069,
    "DEFENSA": None,
}

FECHA_INI = (datetime.today() - timedelta(days=7)).strftime("%Y%m%d")
FECHA_FIN  = datetime.today().strftime("%Y%m%d")

BASE_URL      = "https://busquedas.elperuano.pe"
VISOR_HTML    = f"{BASE_URL}/api/visor_html"
GRAPHQL_URL   = f"{BASE_URL}/api/graphql"
CACHE_DIR     = Path("./cache")
TEMP_DIR      = Path("./temp")

# Crear directorios si no existen
CACHE_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    BASE_URL,
}

QUERY = """
query BuscarNormas(
  $entidad: Int, $fechaIni: String, $fechaFin: String,
  $start: Int, $tipoDispositivo: String
) {
  results(
    entidad: $entidad fechaIni: $fechaIni fechaFin: $fechaFin
    start: $start tipoDispositivo: $tipoDispositivo tipoPublicacion: "NL"
  ) {
    totalHits start hasNext paginatedBy
    hits {
      clasificacion1 fechaPublicacion nombreDispositivo op paginas
      sector sumilla tipoDispositivo tipoPublicacion urlPDF
    }
  }
}
"""

# ─────────────────────────────────────────
# PASO 1: Lista de normas via Playwright + GraphQL
# ─────────────────────────────────────────

def obtener_normas_graphql(entidad_id, fecha_ini, fecha_fin):
    """
    Playwright carga la página iterativamente para extraer todas las páginas de resultados.
    """
    from playwright.sync_api import sync_playwright

    logger.info(f"Iniciando búsqueda para entidad_id={entidad_id}, "
                f"periodo={fecha_ini} a {fecha_fin}")

    todas_las_normas = []
    ids_vistos = set()
    cache_path = CACHE_DIR / f"graphql_{entidad_id}_{fecha_ini}_{fecha_fin}.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page    = context.new_page()
        
        total_en_servidor = -1

        def on_response(response):
            nonlocal total_en_servidor
            if "graphql" in response.url and response.status == 200:
                try:
                    data = response.json()
                    res  = data.get("data", {}).get("results", {})
                    hits = res.get("hits", [])
                    if hits:
                        # Append sólo si es una norma real (tiene OP) y no lo hemos visto
                        for h in hits:
                            op = h.get("op")
                            if op and op not in ids_vistos:
                                todas_las_normas.append(h)
                                ids_vistos.add(op)
                        total_en_servidor = res.get("totalHits", total_en_servidor)
                        logger.info(f"✓ GraphQL: normas en esta pag. "
                                   f"(total acumulado={len(todas_las_normas)} de {total_en_servidor})")
                except json.JSONDecodeError as e:
                    logger.warning(f"Error decodificando respuesta GraphQL: {e}")
                except Exception as e:
                    logger.error(f"Error procesando respuesta: {e}", exc_info=True)

        page.on("response", on_response)

        start = 0
        intentos_maximos = 10  # Seguridad para evitar loops infinitos
        intento = 0
        
        while intento < intentos_maximos:
            try:
                url = (f"{BASE_URL}/?start={start}&tipoDispositivo=&entidad={entidad_id}"
                       f"&tipoPublicacion=NL&fechaIni={fecha_ini}&fechaFin={fecha_fin}")
                logger.info(f"Navegando a {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(3) # Esperamos estabilización
                
                # Si falló la carga o no hay total, salimos
                if total_en_servidor == -1 or total_en_servidor == 0:
                    break
                    
                # Si ya cargamos todo, salimos
                if len(todas_las_normas) >= total_en_servidor:
                    break
                    
                start += 20 # Incrementar paginación
                intento += 1
            except Exception as e:
                logger.error(f"Error en iteración {intento}: {e}")
                break

        # Guardar cache de la última página vista (seguridad)
        try:
            cache_path.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass

        browser.close()

    logger.info(f"Búsqueda completada: {len(todas_las_normas)} normas totales extraídas.")
    return todas_las_normas


# ─────────────────────────────────────────
# PASO 2: Texto limpio via /api/visor_html/{op}
# ─────────────────────────────────────────

def obtener_html_norma(op: str, url_pdf: str = None) -> tuple[str | None, str]:
    """
    GET /api/visor_html/{op} → HTML limpio de la norma.
    Fallback: PDF si está disponible.
    """
    url = f"{VISOR_HTML}/{op}"
    
    try:
        logger.debug(f"Intentando obtener HTML de norma OP={op}")
        
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            r = client.get(url, headers=HEADERS)

        if r.status_code != 200:
            logger.warning(f"OP={op}: HTTP {r.status_code}")
            if url_pdf:
                logger.info(f"OP={op}: Cayendo a PDF")
                return obtener_texto_pdf(url_pdf, op)
            return None, f"http_{r.status_code}"

        if "En Breve" in r.text or len(r.text) < 200:
            logger.warning(f"OP={op}: Respuesta vacía o placeholder")
            if url_pdf:
                return obtener_texto_pdf(url_pdf, op)
            return None, "placeholder"

        # Extraer texto
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()

        body = soup.find("body") or soup
        texto = body.get_text(separator="\n")

        lineas = [l.rstrip() for l in texto.splitlines()]
        limpias = []
        prev_vacia = False
        for l in lineas:
            es_vacia = not l.strip()
            if es_vacia and prev_vacia:
                continue
            limpias.append(l)
            prev_vacia = es_vacia

        texto_final = "\n".join(limpias).strip()
        
        logger.info(f"OP={op}: ✓ HTML extraído ({len(texto_final)} caracteres)")
        return texto_final, "visor_html"

    except httpx.TimeoutException:
        logger.error(f"OP={op}: Timeout en solicitud HTTP")
        if url_pdf:
            return obtener_texto_pdf(url_pdf, op)
        return None, "timeout"
    
    except Exception as e:
        logger.error(f"OP={op}: Error inesperado: {e}", exc_info=True)
        if url_pdf:
            return obtener_texto_pdf(url_pdf, op)
        return None, f"error: {type(e).__name__}"


def obtener_texto_pdf(url_pdf: str, op: str = "?") -> tuple[str | None, str]:
    """
    Descargar y procesar PDF.
    """
    try:
        logger.info(f"OP={op}: Procesando PDF")
        
        with httpx.Client(timeout=20) as client:
            r = client.get(url_pdf)

        if r.status_code != 200:
            logger.error(f"OP={op}: PDF HTTP {r.status_code}")
            return None, f"http_{r.status_code}"

        temp_pdf = TEMP_DIR / f"temp_{op}.pdf"
        temp_pdf.write_bytes(r.content)
        logger.debug(f"OP={op}: PDF descargado ({len(r.content)} bytes)")

        import fitz

        doc = fitz.open(temp_pdf)
        texto_paginas = []

        for i, page in enumerate(doc):
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))
            page_text = "\n".join(b[4].strip() for b in blocks if b[4].strip())
            texto_paginas.append(page_text)
            logger.debug(f"OP={op}: Página {i+1} procesada")

        doc.close()
        temp_pdf.unlink()

        texto_final = "\n\n".join(texto_paginas).strip()

        if len(texto_final) < 50:
            logger.warning(f"OP={op}: PDF con poco texto ({len(texto_final)} chars)")
            return None, "pdf_insuficiente"

        logger.info(f"OP={op}: ✓ PDF extraído ({len(texto_final)} caracteres)")
        return texto_final, f"pdf_fitz"

    except ImportError:
        logger.error(f"OP={op}: PyMuPDF no instalado (pip install PyMuPDF)")
        return None, "fitz_not_installed"
    
    except Exception as e:
        logger.error(f"OP={op}: Error procesando PDF: {e}", exc_info=True)
        return None, f"error: {type(e).__name__}"


# ─────────────────────────────────────────
# PASO 3: HTML parseado del cache
# ─────────────────────────────────────────

def parsear_html_cache(html_path: Path):
    """Parsear HTML cacheado."""
    logger.info(f"Parseando cache: {html_path}")
    
    try:
        soup  = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        cards = soup.select("div.card.mb-3")
        normas = []
        
        logger.debug(f"Encontradas {len(cards)} tarjetas en HTML")
        
        for i, card in enumerate(cards):
            try:
                subtitles = card.select("h6.card-sub-title")
                tipo   = subtitles[0].get_text(strip=True) if len(subtitles) > 0 else ""
                numero = subtitles[1].get_text(strip=True) if len(subtitles) > 1 else ""
                bodies = card.select("div.card-body")
                sumilla = ""
                if len(bodies) > 1:
                    link = bodies[1].select_one("a.nav-link")
                    sumilla = link.get_text(strip=True) if link else ""
                footer_op    = card.select_one("div.card-footer:last-of-type span.float-start")
                footer_fecha = card.select_one("div.card-footer:last-of-type span.float-end")
                op = footer_op.get_text(strip=True) if footer_op else ""
                fecha_pub = ""
                if footer_fecha:
                    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", footer_fecha.get_text())
                    if m:
                        fecha_pub = f"{m.group(3)}{m.group(2)}{m.group(1)}"
                if op:
                    normas.append({
                        "op": op, "tipoDispositivo": tipo,
                        "nombreDispositivo": numero, "sumilla": sumilla,
                        "fechaPublicacion": fecha_pub,
                        "sector": "", "paginas": "", "urlPDF": None,
                    })
                    logger.debug(f"Norma {i+1}: OP={op} {tipo}")
            except Exception as e:
                logger.warning(f"Error en tarjeta {i}: {e}")
                continue
        
        logger.info(f"✓ {len(normas)} normas parseadas del cache")
        return normas
    
    except FileNotFoundError:
        logger.error(f"Cache no encontrado: {html_path}")
        return []
    except Exception as e:
        logger.error(f"Error parseando cache: {e}", exc_info=True)
        return []