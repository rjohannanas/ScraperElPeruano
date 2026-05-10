#!/bin/bash
# Ruta absoluta del directorio del proyecto
cd /home/gcp_setel_oee/ScraperElPeruano

# Usar el python del entorno virtual
PYTHON_BIN="/home/gcp_setel_oee/ScraperElPeruano/venv/bin/python3"

# Nombra a todas las entidades que quieras extraer
$PYTHON_BIN run_scraper.py 2069 1
$PYTHON_BIN run_scraper.py 1984 1
$PYTHON_BIN run_scraper.py 9064 1
$PYTHON_BIN run_scraper.py 2068 1
$PYTHON_BIN run_scraper.py 2007 1