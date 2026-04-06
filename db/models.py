from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base

class Entidad(Base):
    __tablename__ = "entidades"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    codigo_peruano = Column(Integer, unique=True, index=True, nullable=False)
    
    normas = relationship("Norma", back_populates="entidad")
    scraping_logs = relationship("ScrapingLog", back_populates="entidad")

class Norma(Base):
    __tablename__ = "normas"

    op = Column(String(100), primary_key=True, index=True)
    entidad_id = Column(Integer, ForeignKey("entidades.id"), nullable=False)
    tipo_dispositivo = Column(String(255))
    nombre_dispositivo = Column(String(255), index=True)
    fecha_publicacion = Column(String(8)) # YYYYMMDD from El Peruano
    sumilla = Column(Text)
    texto_completo = Column(Text)
    url_web = Column(String(500))
    url_pdf = Column(String(500))
    creado_en = Column(DateTime, default=datetime.utcnow)
    fuente = Column(String(50)) # e.g., 'visor_html', 'pdf_fitz'

    entidad = relationship("Entidad", back_populates="normas")

class ScrapingLog(Base):
    __tablename__ = "scraping_logs"

    id = Column(Integer, primary_key=True, index=True)
    entidad_id = Column(Integer, ForeignKey("entidades.id"), nullable=True)
    fecha_inicio_filtro = Column(String(8))
    fecha_fin_filtro = Column(String(8))
    timestamp_ejecucion = Column(DateTime, default=datetime.utcnow)
    timestamp_fin = Column(DateTime, nullable=True)
    normas_encontradas = Column(Integer, default=0)
    normas_nuevas_insertadas = Column(Integer, default=0)
    estado = Column(String(50)) # 'EXITO', 'ERROR', 'PROCESANDO'
    mensaje_error = Column(Text, nullable=True)

    entidad = relationship("Entidad", back_populates="scraping_logs")
