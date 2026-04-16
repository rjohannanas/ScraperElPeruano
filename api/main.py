from fastapi import FastAPI, Query, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from db.database import get_db, Base, engine
from db.models import Norma, Entidad, ScrapingLog
from scraper.tasks import run_scraping_task

# Crear tablas en el inicio (Si no usas Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Scraper El Peruano API (Local DB)")

@app.get("/normas")
def get_normas(
    entidad_id: int = Query(None, description="Filtrar por Entidad ID"),
    limite: int = Query(50, description="Límite de resultados"),
    db: Session = Depends(get_db)
):
    query = db.query(Norma)
    if entidad_id:
        query = query.filter(Norma.entidad_id == entidad_id)
            
    normas = query.order_by(Norma.fecha_publicacion.desc()).limit(limite).all()
    return {"total": len(normas), "data": normas}

@app.post("/scraper/run")
def trigger_scraper(
    background_tasks: BackgroundTasks,
    entidad: int = Query(2069, description="ID entidad a buscar (ej: 2069 MEF)"),
    dias: int = Query(1, description="Días hacia atrás a buscar")
):
    """
    Desencadena la recolección de normas en segundo plano.
    Esto evitará que el request HTTP se quede colgado.
    """
    background_tasks.add_task(run_scraping_task, entidad, dias)
    return {
        "status": "Iniciado en segundo plano",
        "entidad_buscada": entidad,
        "dias_atras": dias,
        "mensaje": "Revisa los logs o consulta /normas en un momento para ver los resultados."
    }

@app.get("/scraper/logs")
def get_logs(db: Session = Depends(get_db), limite: int = 10):
    logs = db.query(ScrapingLog).order_by(ScrapingLog.timestamp_ejecucion.desc()).limit(limite).all()
    return logs
