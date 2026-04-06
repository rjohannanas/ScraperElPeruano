import sys
import logging
from db.database import engine, Base
from scraper.tasks import run_scraping_task

# Asegurar tablas
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    entidad_id = 2069 # MEF por defecto
    dias = 1
    
    if len(sys.argv) > 1:
        entidad_id = int(sys.argv[1])
    if len(sys.argv) > 2:
        dias = int(sys.argv[2])
        
    print(f"Ejecutando scraper para Entidad ID: {entidad_id}, Días Atrás: {dias}")
    total_encontradas, normas_insertadas = run_scraping_task(entidad_id, dias)
    print(f"\n--- RESUMEN ---")
    print(f"Normas Encontradas: {total_encontradas}")
    print(f"Normas Nuevas Insertadas: {normas_insertadas}")
