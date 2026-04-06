from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        def on_response(response):
            if "graphql" in response.url:
                print("GRAPHQL URL ACTUAL:", response.url)
        page.on("response", on_response)
        page.goto("https://busquedas.elperuano.pe/?start=0&tipoDispositivo=&entidad=2069&tipoPublicacion=NL&fechaIni=20260327&fechaFin=20260403")
        page.wait_for_timeout(2000)
        browser.close()
run()
