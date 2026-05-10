import time
import subprocess
from datetime import datetime, timedelta
import os

# Configuración
LIMA_OFFSET = -5
START_HOUR = 4
START_MINUTE = 30
END_HOUR = 23
END_MINUTE = 59
INTERVAL_SECONDS = 1800  # 30 minutos

LOG_FILE = "/home/gcp_setel_oee/ScraperElPeruano/watcher.log"
PROJECT_DIR = "/home/gcp_setel_oee/ScraperElPeruano"

def log(message):
    timestamp = datetime.utcnow() + timedelta(hours=LIMA_OFFSET)
    msg = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')} Lima] {message}"
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

def is_active_window():
    # Obtener hora actual en Lima
    now_lima = datetime.utcnow() + timedelta(hours=LIMA_OFFSET)
    current_time = now_lima.hour * 60 + now_lima.minute
    
    start_time = START_HOUR * 60 + START_MINUTE
    end_time = END_HOUR * 60 + END_MINUTE
    
    return start_time <= current_time <= end_time

def run_scraper():
    log("Iniciando ejecución programada del scraper...")
    try:
        # Ejecutar el script bash
        result = subprocess.run(
            ["/bin/bash", "./correr_todas.sh"], 
            cwd=PROJECT_DIR, 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            log("Scraper completado con éxito.")
        else:
            log(f"Error en el scraper (Código {result.returncode}): {result.stderr}")
    except Exception as e:
        log(f"Excepción al ejecutar scraper: {str(e)}")

def main():
    log("Iniciando servicio Watcher (4:30 AM - 12:00 AM Lima)")
    while True:
        if is_active_window():
            run_scraper()
            log(f"Esperando {INTERVAL_SECONDS // 60} minutos para el siguiente ciclo...")
        else:
            log("Fuera de horario de operación. Durmiendo hasta el próximo ciclo...")
        
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
