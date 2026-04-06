import httpx
import json

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
      fechaPublicacion nombreDispositivo op sumilla tipoDispositivo urlPDF
    }
  }
}
"""

variables = {
    "entidad": 2069,
    "fechaIni": "20260327",
    "fechaFin": "20260403",
    "start": 20,
    "tipoDispositivo": ""
}

try:
    with httpx.Client() as client:
        res = client.post(
            "https://busquedas.elperuano.pe/api/graphql",
            json={"query": QUERY, "variables": variables},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        print(res.status_code)
        if res.status_code == 200:
            print(json.dumps(res.json(), indent=2))
except Exception as e:
    print(e)
