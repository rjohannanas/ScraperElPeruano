import logging
from datetime import datetime, timedelta
from scraper.core import obtener_normas_graphql, obtener_html_norma, BASE_URL
from db.database import SessionLocal
from db.models import Entidad, Norma, ScrapingLog

logger = logging.getLogger(__name__)

def run_scraping_task(entidad_id: int, dias_atras: int = 1):
    """
    Ejecuta el proceso de scraping para una entidad y un rango de días.
    Guarda los resultados directamente en la Base de Datos.
    """
    db = SessionLocal()
    
    # 1. Asegurar que la entidad existe
    entidad = db.query(Entidad).filter(Entidad.codigo_peruano == entidad_id).first()
    if not entidad:
        entidad = Entidad(codigo_peruano=entidad_id, nombre=f"Entidad {entidad_id}")
        db.add(entidad)
        db.commit()
        db.refresh(entidad)

    fecha_ini = (datetime.today() - timedelta(days=dias_atras)).strftime("%Y%m%d")
    fecha_fin = datetime.today().strftime("%Y%m%d")

    # Crear Log de Scraping
    log = ScrapingLog(
        entidad_id=entidad.id,
        fecha_inicio_filtro=fecha_ini,
        fecha_fin_filtro=fecha_fin,
        estado="PROCESANDO"
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    normas_insertadas = 0
    total_encontradas = 0

    try:
        normas_raw = obtener_normas_graphql(entidad_id, fecha_ini, fecha_fin)
        total_encontradas = len(normas_raw)

        for n in normas_raw:
            op = n.get("op")
            if not op:
                continue
                
            # Evitar procesar si la norma ya existe y está completa
            existe = db.query(Norma).filter(Norma.op == op).first()
            if existe:
                if not existe.texto_completo:
                    url_pdf = n.get("urlPDF")
                    texto, fuente = obtener_html_norma(op, url_pdf)
                    if texto:
                        existe.texto_completo = texto
                        existe.fuente = fuente
                        db.commit()
                        logger.info(f"Norma OP={op} recuperada: texto PDF/HTML llenado en reintento.")
                    else:
                        logger.info(f"Norma OP={op} sigue vacía (requiere revisión manual).")
                else:
                    logger.info(f"Norma OP={op} ya existe en DB y está completa, ignorando...")
                continue

            # Extraer contenido de web/pdf
            url_pdf = n.get("urlPDF")
            texto, fuente = obtener_html_norma(op, url_pdf)
            
            nueva_norma = Norma(
                op=op,
                entidad_id=entidad.id,
                tipo_dispositivo=n.get("tipoDispositivo"),
                nombre_dispositivo=n.get("nombreDispositivo"),
                fecha_publicacion=n.get("fechaPublicacion"),
                sumilla=n.get("sumilla"),
                texto_completo=texto,
                url_web=f"{BASE_URL}/dispositivo/NL/{op}",
                url_pdf=url_pdf,
                fuente=fuente
            )
            db.add(nueva_norma)
            db.commit()
            normas_insertadas += 1

        log.estado = "EXITO"

    except Exception as e:
        logger.error(f"Error en scraping task: {e}")
        db.rollback()
        log.estado = "ERROR"
        log.mensaje_error = str(e)
    finally:
        log.timestamp_fin = datetime.utcnow()
        log.normas_encontradas = total_encontradas
        log.normas_nuevas_insertadas = normas_insertadas
        db.commit()
        db.close()
    
    return total_encontradas, normas_insertadas
