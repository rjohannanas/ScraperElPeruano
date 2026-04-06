import logging
import sys
from pathlib import Path
from core import obtener_normas_graphql, obtener_texto_pdf, obtener_html_norma

# ─────────────────────────────────────────
# CONFIGURAR LOGGING PARA TEST
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,  # Mostrar TODO (DEBUG, INFO, WARNING, ERROR)
    format="%(asctime)s [%(levelname)-8s] %(funcName)s → %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Terminal
        logging.FileHandler("test2.log", encoding="utf-8", mode="w")  # Archivo nuevo cada vez
    ]
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────
BASE_URL = "https://busquedas.elperuano.pe"
ENTIDAD_ID = 2069
FECHA_INI = "20260330"
FECHA_FIN = "20260330"

# ─────────────────────────────────────────
# TEST PRINCIPAL
# ─────────────────────────────────────────

def main():
    logger.info("=" * 70)
    logger.info("INICIANDO TEST DE SCRAPER")
    logger.info("=" * 70)
    logger.info(f"Parámetros: entidad_id={ENTIDAD_ID}, "
                f"periodo={FECHA_INI} a {FECHA_FIN}")
    
    try:
        # PASO 1: Obtener normas via GraphQL
        logger.info("\n[PASO 1] Obteniendo normas via GraphQL...")
        normas = obtener_normas_graphql(ENTIDAD_ID, FECHA_INI, FECHA_FIN)
        
        if not normas:
            logger.warning("❌ No se obtuvieron normas")
            return False
        
        logger.info(f"✓ Obtenidas {len(normas)} normas")
        
        # PASO 2: Procesar cada norma
        logger.info(f"\n[PASO 2] Procesando {len(normas)} normas...")
        extracted = []
        
        for idx, norma in enumerate(normas, 1):
            logger.info(f"\n  [{idx}/{len(normas)}] Procesando norma...")
            
            try:
                op = norma.get("op")
                tipo = norma.get("tipoDispositivo", "?")
                numero = norma.get("nombreDispositivo", "?")
                fecha = norma.get("fechaPublicacion", "?")
                sumilla = norma.get("sumilla", "")
                url_pdf = norma.get("urlPDF")
                
                logger.debug(f"  OP={op}, Tipo={tipo}, Número={numero}")
                
                # Intentar obtener HTML
                logger.debug(f"  Intentando obtener HTML...")
                texto, fuente = obtener_html_norma(op, url_pdf)
                
                # Fallback a PDF si HTML es insuficiente
                if (not texto or len(texto) < 300) and url_pdf:
                    logger.info(f"  HTML insuficiente ({len(texto) if texto else 0} chars) "
                               f"→ intentando PDF...")
                    texto_pdf, fuente_pdf = obtener_texto_pdf(url_pdf, op)
                    if texto_pdf:
                        texto = texto_pdf
                        fuente = fuente_pdf
                        logger.info(f"  ✓ PDF obtenido ({len(texto_pdf)} chars)")
                    else:
                        logger.warning(f"  ❌ PDF también falló: {fuente_pdf}")
                else:
                    logger.info(f"  ✓ Fuente: {fuente} ({len(texto) if texto else 0} chars)")
                
                # Guardar resultado
                entry = {
                    "op": op,
                    "tipo": tipo,
                    "numero": numero,
                    "fecha": fecha,
                    "sumilla": sumilla,
                    "texto_completo": texto,
                    "fuente": fuente,
                    "url_web": f"{BASE_URL}/dispositivo/NL/{op}" if op else None,
                }
                extracted.append(entry)
                logger.debug(f"  ✓ Norma agregada a resultados")
                
            except Exception as e:
                logger.error(f"  ❌ Error procesando norma {idx}: {e}", exc_info=True)
                continue
        
        # PASO 3: Guardar resultados
        logger.info(f"\n[PASO 3] Guardando {len(extracted)} normas extraídas...")
        
        try:
            # Archivo de resumen
            with open("normas.txt", "w", encoding="utf-8") as f:
                for i, entry in enumerate(extracted, 1):
                    f.write(f"\n{'='*70}\n")
                    f.write(f"NORMA {i}/{len(extracted)}\n")
                    f.write(f"{'='*70}\n")
                    f.write(f"Nombre:      {entry['numero']}\n")
                    f.write(f"Tipo:        {entry['tipo']}\n")
                    f.write(f"OP:          {entry['op']}\n")
                    f.write(f"Fecha:       {entry['fecha']}\n")
                    f.write(f"Sumilla:     {entry['sumilla']}\n")
                    f.write(f"URL Web:     {entry['url_web']}\n")
                    f.write(f"Fuente:      {entry['fuente']}\n")
                    f.write(f"Texto:       {entry['texto_completo'][:500] if entry['texto_completo'] else 'N/A'}...\n")
            
            logger.info(f"✓ Archivo 'normas.txt' creado")
            
            # Archivo de texto completo
            with open("extracted.txt", "w", encoding="utf-8") as f:
                for i, entry in enumerate(extracted, 1):
                    f.write(f"\n{'='*70}\n")
                    f.write(f"NORMA {i}: {entry['numero']}\n")
                    f.write(f"{'='*70}\n")
                    f.write(f"{entry['texto_completo'] or '[SIN CONTENIDO]'}\n")
            
            logger.info(f"✓ Archivo 'extracted.txt' creado")
            
        except Exception as e:
            logger.error(f"Error guardando archivos: {e}", exc_info=True)
            return False
        
        # CONCLUSIÓN
        logger.info("\n" + "=" * 70)
        logger.info(f"TEST COMPLETADO: {len(extracted)}/{len(normas)} normas procesadas")
        logger.info(f"Archivos generados: normas.txt, extracted.txt, test2.log")
        logger.info("=" * 70)
        
        return len(extracted) > 0

    except Exception as e:
        logger.critical(f"ERROR CRÍTICO: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    try:
        success = main()
        exit_code = 0 if success else 1
    except KeyboardInterrupt:
        logger.warning("\nTest interrumpido por usuario")
        exit_code = 2
    except Exception as e:
        logger.critical(f"Error no capturado: {e}", exc_info=True)
        exit_code = 1
    
    logger.info(f"Saliendo con código: {exit_code}")
    sys.exit(exit_code)