# Scraper de negocios sin sitio web

Busca negocios en Google Places y guarda los que no tienen sitio web cargado.

El script recomendado es:

```text
scraper_hoteles_places_api.py
```

Aunque el nombre diga `hoteles`, ahora sirve para hoteles, cafes, restaurantes y otros rubros.

## 1. Configurar la API key

En PowerShell, para la sesion actual:

```powershell
$env:GOOGLE_MAPS_API_KEY="TU_API_KEY"
```

Para dejarla fija en Windows:

```powershell
setx GOOGLE_MAPS_API_KEY "TU_API_KEY"
```

Despues de `setx`, cerra y abri PowerShell.

No pegues la API key dentro del codigo ni la subas a GitHub.

## 2. Presets disponibles

Usa `--business-preset` para elegir rubro:

- `hotel`
- `cafe`
- `restaurant`
- `bar`
- `gym`
- `beauty_salon`
- `dentist`
- `real_estate_agency`
- `car_repair`
- `technical_service`
- `electrician`
- `plumber`
- `locksmith`
- `painter`
- `roofing_contractor`
- `laundry`
- `moving_company`
- `hardware_store`

Cada preset define automaticamente:

- `place_type` de Google Places.
- Keywords baratas para `budget`.
- Keywords extra para `balanced` y `full`.

## 3. Prueba barata

Hoteles en Mar del Plata:

```powershell
python scraper_hoteles_places_api.py --test --business-preset hotel
```

Cafes en Mar del Plata:

```powershell
python scraper_hoteles_places_api.py --test --business-preset cafe
```

Restaurantes en Mar del Plata:

```powershell
python scraper_hoteles_places_api.py --test --business-preset restaurant
```

Electricistas en Mar del Plata:

```powershell
python scraper_hoteles_places_api.py --test --business-preset electrician
```

## 4. Ver ciudades sin gastar creditos

Antes de ejecutar la busqueda completa, podes ver que ubicaciones va a recorrer:

```powershell
python scraper_hoteles_places_api.py --business-preset cafe --coverage budget --print-locations
```

El modo `budget` incluye CABA, barrios comerciales principales, AMBA/GBA, costa atlantica, destinos turisticos y ciudades grandes/cabeceras comerciales de provincia de Buenos Aires. Evita pueblos y ciudades chicas.

## 5. Ejecutar busqueda recomendada

Cafes:

```powershell
python scraper_hoteles_places_api.py --business-preset cafe --coverage budget --max-api-requests 100
```

Hoteles:

```powershell
python scraper_hoteles_places_api.py --business-preset hotel --coverage budget --max-api-requests 100
```

Restaurantes:

```powershell
python scraper_hoteles_places_api.py --business-preset restaurant --coverage budget --max-api-requests 100
```

Servicios tecnicos:

```powershell
python scraper_hoteles_places_api.py --business-preset technical_service --coverage balanced --max-api-requests 180
```

Electricistas:

```powershell
python scraper_hoteles_places_api.py --business-preset electrician --coverage budget --max-api-requests 100
```

Gasistas y plomeros:

```powershell
python scraper_hoteles_places_api.py --business-preset plumber --search-terms "gasista,gasista matriculado,plomero" --coverage balanced --max-api-requests 180
```

Cerrajeros:

```powershell
python scraper_hoteles_places_api.py --business-preset locksmith --coverage budget --max-api-requests 100
```

Pintores:

```powershell
python scraper_hoteles_places_api.py --business-preset painter --coverage budget --max-api-requests 100
```

Techistas:

```powershell
python scraper_hoteles_places_api.py --business-preset roofing_contractor --coverage budget --max-api-requests 100
```

Este modo usa:

- 1 keyword principal segun el preset.
- 1 pagina por ubicacion.
- Hasta 20 resultados por pagina.
- Cache en `cache/places_cache.json`.
- Maximo de 100 requests nuevas no cacheadas.

Si queres gastar menos y no necesitas telefonos:

```powershell
python scraper_hoteles_places_api.py --business-preset cafe --coverage budget --max-api-requests 100 --no-include-lead-fields
```

## 6. Modos de cobertura

- `--coverage budget`: recomendado. CABA + ciudades importantes, evitando pueblos.
- `--coverage balanced`: suma mas ciudades medianas y mas keywords del rubro.
- `--coverage full`: recorre casi todos los partidos y varias keywords. Es el mas caro.

Ejemplo mas amplio:

```powershell
python scraper_hoteles_places_api.py --business-preset cafe --coverage balanced --max-api-requests 180
```

## 7. Busquedas personalizadas

No estas limitado a los presets. Podes pasar keywords y un tipo de Google Places:

```powershell
python scraper_hoteles_places_api.py --place-type cafe --search-terms "cafe,cafeteria" --locations "Ciudad Autonoma de Buenos Aires,Mar del Plata,Pinamar,Villa Gesell,Tigre,La Plata,Bahia Blanca,Tandil"
```

Otro ejemplo:

```powershell
python scraper_hoteles_places_api.py --place-type restaurant --search-terms "restaurant,parrilla,pizzeria" --coverage budget --max-api-requests 100
```

Para oficios donde Google no tenga un tipo exacto, podes dejar `--place-type` vacio y buscar por texto:

```powershell
python scraper_hoteles_places_api.py --place-type "" --search-terms "gasista matriculado,electricista matriculado,service aire acondicionado" --coverage balanced --max-api-requests 180
```

## 8. Archivos de salida

- `negocios_sin_web_api.csv`: negocios sin sitio web.
- `negocios_revisados_api.csv`: auditoria de todos los negocios encontrados.
- `negocios_sin_web_api.txt`: telefonos en formato `telefono (nombre)`.
- `cache/places_cache.json`: cache local para no pagar dos veces la misma busqueda.

## 9. Instalacion

El script de Places API usa solo librerias estandar de Python. No necesita Playwright ni paquetes externos.

En esta maquina `python` ya funciona para este script.

## 10. Alternativa vieja con scraping visual

Tambien existe:

```text
scraper_hoteles.py
```

Ese script usa Playwright y scrapea Google Maps visualmente. Es menos confiable y puede omitir resultados.

Nota: tu Python actual es MSYS2 (`C:\msys64\ucrt64\bin\python.exe`). Sirve para `scraper_hoteles_places_api.py`, pero puede dar problemas instalando Playwright. Si queres usar este scraper viejo, conviene instalar Python para Windows desde `python.org` y marcar **Add python.exe to PATH**.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scraper_hoteles.py --all-buenos-aires-hotels
```

Recomendacion: usa `scraper_hoteles_places_api.py` salvo que no quieras usar Google Places API.
