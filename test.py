from core import obtener_texto_pdf
import os

url = "https://busquedas.elperuano.pe/api/media/http://172.20.0.101/file/7fOop9zAaFyByPWCvy6w9G/*/2501054-1.pdf/PDF"

texto, fuente = obtener_texto_pdf(url)

with open("output.txt", "w", encoding="utf-8") as f:
    f.write(f"Fuente: {fuente}\n\n")
    f.write(texto or "No se pudo obtener texto.")
    