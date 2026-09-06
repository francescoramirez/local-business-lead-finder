"""UNSUPPORTED. Historical Google Maps UI scraper.

This module is not part of leadfinder. Use `leadfinder search` and Places API (New).
"""

import argparse
import csv
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus, urlsplit, urlunsplit

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
except ModuleNotFoundError:
    PlaywrightTimeoutError = TimeoutError

Page = Any


HOTEL_SEARCH_TERMS = [
    "hotel",
    "hoteles",
    "alojamiento",
    "hosteria",
    "apart hotel",
    "hotel boutique",
    "posada",
]

# Partidos/municipios de la provincia de Buenos Aires. Se usan como malla base
# para no depender de una unica busqueda provincial, que Google Maps suele capar.
BUENOS_AIRES_LOCATIONS = [
    "Adolfo Alsina",
    "Adolfo Gonzales Chaves",
    "Alberti",
    "Almirante Brown",
    "Arrecifes",
    "Avellaneda",
    "Ayacucho",
    "Azul",
    "Bahia Blanca",
    "Balcarce",
    "Baradero",
    "Benito Juarez",
    "Berazategui",
    "Berisso",
    "Bolivar",
    "Bragado",
    "Brandsen",
    "Campana",
    "Canuelas",
    "Capitan Sarmiento",
    "Carlos Casares",
    "Carlos Tejedor",
    "Carmen de Areco",
    "Castelli",
    "Chacabuco",
    "Chascomus",
    "Chivilcoy",
    "Colon",
    "Coronel Dorrego",
    "Coronel Pringles",
    "Coronel Rosales",
    "Coronel Suarez",
    "Daireaux",
    "Dolores",
    "Ensenada",
    "Escobar",
    "Esteban Echeverria",
    "Exaltacion de la Cruz",
    "Ezeiza",
    "Florencio Varela",
    "Florentino Ameghino",
    "General Alvarado",
    "General Alvear",
    "General Arenales",
    "General Belgrano",
    "General Guido",
    "General Juan Madariaga",
    "General La Madrid",
    "General Las Heras",
    "General Lavalle",
    "General Paz",
    "General Pinto",
    "General Pueyrredon",
    "General Rodriguez",
    "General San Martin",
    "General Viamonte",
    "General Villegas",
    "Guamini",
    "Hipolito Yrigoyen",
    "Hurlingham",
    "Ituzaingo",
    "Jose C. Paz",
    "Junin",
    "La Costa",
    "La Matanza",
    "La Plata",
    "Lanus",
    "Laprida",
    "Las Flores",
    "Leandro N. Alem",
    "Lezama",
    "Lincoln",
    "Loberia",
    "Lobos",
    "Lomas de Zamora",
    "Lujan",
    "Magdalena",
    "Maipu",
    "Malvinas Argentinas",
    "Mar Chiquita",
    "Marcos Paz",
    "Mercedes",
    "Merlo",
    "Monte",
    "Monte Hermoso",
    "Moreno",
    "Moron",
    "Navarro",
    "Necochea",
    "Nueve de Julio",
    "Olavarria",
    "Patagones",
    "Pehuajo",
    "Pellegrini",
    "Pergamino",
    "Pila",
    "Pilar",
    "Pinamar",
    "Presidente Peron",
    "Puan",
    "Punta Indio",
    "Quilmes",
    "Ramallo",
    "Rauch",
    "Rivadavia",
    "Rojas",
    "Roque Perez",
    "Saavedra",
    "Saladillo",
    "Salliquelo",
    "Salto",
    "San Andres de Giles",
    "San Antonio de Areco",
    "San Cayetano",
    "San Fernando",
    "San Isidro",
    "San Miguel",
    "San Nicolas",
    "San Pedro",
    "San Vicente",
    "Suipacha",
    "Tandil",
    "Tapalque",
    "Tigre",
    "Tordillo",
    "Tornquist",
    "Trenque Lauquen",
    "Tres Arroyos",
    "Tres de Febrero",
    "Tres Lomas",
    "Veinticinco de Mayo",
    "Vicente Lopez",
    "Villa Gesell",
    "Villarino",
    "Zarate",
]

# Localidades turisticas y cabeceras importantes. Cubren casos donde buscar por
# partido no trae todos los resultados, por ejemplo Mar del Plata dentro de
# General Pueyrredon.
BUENOS_AIRES_CITY_LOCATIONS = [
    "Mar del Plata",
    "Batan",
    "Sierra de los Padres",
    "Chapadmalal",
    "La Plata",
    "Bahia Blanca",
    "Tandil",
    "Villa Gesell",
    "Pinamar",
    "Carilo",
    "Valeria del Mar",
    "Ostende",
    "Mar de Ostende",
    "San Clemente del Tuyu",
    "Las Toninas",
    "Santa Teresita",
    "Mar del Tuyu",
    "Costa del Este",
    "Aguas Verdes",
    "Lucila del Mar",
    "San Bernardo",
    "Mar de Ajo",
    "Nueva Atlantis",
    "Necochea",
    "Quequen",
    "Miramar",
    "Mar del Sur",
    "Monte Hermoso",
    "Pehuen Co",
    "Claromeco",
    "Reta",
    "Orense",
    "Sierra de la Ventana",
    "Tornquist",
    "Balcarce",
    "Chascomus",
    "San Antonio de Areco",
    "Lujan",
    "Tigre",
    "San Pedro",
    "San Nicolas de los Arroyos",
    "Junin",
    "Olavarria",
    "Azul",
    "Dolores",
    "Pergamino",
    "Mercedes",
    "Bragado",
    "Chivilcoy",
    "Trenque Lauquen",
    "Carmen de Patagones",
]


@dataclass(frozen=True)
class Hotel:
    search_term: str
    location: str
    name: str
    phone: str
    website: str
    website_status: str
    address: str
    category: str
    maps_url: str
    source_query: str


def split_csv_arg(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def normalize_phone(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit() or ch == "+").strip()


def normalize_maps_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def hotel_key(hotel: Hotel) -> str:
    if hotel.phone:
        return f"phone:{hotel.phone}"
    return f"name-address:{normalize_text(hotel.name)}|{normalize_text(hotel.address)}"


def close_google_consent(page: Page) -> None:
    for text in ("Aceptar todo", "Aceptar", "Accept all", "Accept"):
        try:
            page.get_by_role("button", name=text).click(timeout=2500)
            return
        except PlaywrightTimeoutError:
            continue


def wait_for_maps(page: Page) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except PlaywrightTimeoutError:
        pass


def open_maps_search(page: Page, query: str) -> None:
    url = f"https://www.google.com/maps/search/{quote_plus(query)}"
    for attempt in range(3):
        try:
            page.goto(url, timeout=60_000)
            wait_for_maps(page)
            close_google_consent(page)
            return
        except PlaywrightTimeoutError:
            if attempt == 2:
                raise
            print(f"Reintentando busqueda: {query}")
            time.sleep(4)


def collect_place_urls(page: Page, max_results: int, scroll_rounds: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    stable_rounds = 0

    for _ in range(scroll_rounds):
        anchors = page.locator('a[href*="/maps/place/"], a[href*="/place/"]')
        count = anchors.count()

        for index in range(count):
            try:
                href = anchors.nth(index).get_attribute("href", timeout=1000)
            except PlaywrightTimeoutError:
                continue

            if not href:
                continue

            normalized = normalize_maps_url(href)
            if normalized not in seen:
                seen.add(normalized)
                urls.append(href)
                if len(urls) >= max_results:
                    return urls

        previous_count = len(urls)
        if reached_end_of_results(page):
            break

        scroll_results(page)
        time.sleep(1.2)

        if len(urls) == previous_count:
            stable_rounds += 1
            if stable_rounds >= 6:
                break
        else:
            stable_rounds = 0

    return urls[:max_results]


def reached_end_of_results(page: Page) -> bool:
    end_messages = (
        "Llegaste al final de la lista",
        "Has llegado al final de la lista",
        "You've reached the end of the list",
    )
    for message in end_messages:
        try:
            if page.get_by_text(message).first.is_visible(timeout=500):
                return True
        except PlaywrightTimeoutError:
            continue
    return False


def scroll_results(page: Page) -> None:
    feed = page.locator('div[role="feed"]').first
    try:
        feed.hover(timeout=1500)
    except PlaywrightTimeoutError:
        pass
    page.mouse.wheel(0, 6000)


def first_text(page: Page, selectors: Iterable[str], timeout: int = 1500) -> str:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            text = locator.inner_text(timeout=timeout).strip()
            if text:
                return text
        except PlaywrightTimeoutError:
            continue
    return ""


def first_attribute(page: Page, selectors: Iterable[str], attribute: str, timeout: int = 1500) -> str:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            value = locator.get_attribute(attribute, timeout=timeout)
            if value:
                return value.strip()
        except PlaywrightTimeoutError:
            continue
    return ""


def extract_website(page: Page) -> str:
    selectors = [
        'a[data-item-id="authority"]',
        'a[data-item-id^="authority"]',
        'a[aria-label*="Sitio web"]',
        'a[aria-label*="Website"]',
        'a[href^="http"]:has-text("Sitio web")',
        'a[href^="http"]:has-text("Website")',
    ]
    website = first_attribute(page, selectors, "href", timeout=2500)
    if website and "google.com" not in website:
        return website
    return ""


def extract_hotel(page: Page, maps_url: str, search_term: str, location: str, source_query: str) -> Hotel | None:
    try:
        page.goto(maps_url, timeout=60_000)
        wait_for_maps(page)
    except PlaywrightTimeoutError:
        print(f"No se pudo abrir: {maps_url}")
        return None

    name = first_text(page, ["h1"], timeout=4000)
    if not name:
        return None

    phone = first_text(
        page,
        [
            'button[data-item-id^="phone:tel:"]',
            'button[data-tooltip*="Copiar numero"]',
            'button[data-tooltip*="Copiar n\\u00famero"]',
            'button[data-tooltip*="Copy phone"]',
            'button[aria-label*="Telefono"]',
            'button[aria-label*="Tel\\u00e9fono"]',
            'button[aria-label*="Phone"]',
        ],
    )
    website = extract_website(page)
    address = first_text(
        page,
        [
            'button[data-item-id="address"]',
            'button[aria-label*="Direccion"]',
            'button[aria-label*="Direcci\\u00f3n"]',
            'button[aria-label*="Address"]',
        ],
    )
    category = first_text(
        page,
        [
            'button[jsaction*="category"]',
            'button[aria-label*="Categoria"]',
            'button[aria-label*="Categor\\u00eda"]',
            'button[aria-label*="Category"]',
        ],
        timeout=1000,
    )

    return Hotel(
        search_term=search_term,
        location=location,
        name=name,
        phone=normalize_phone(phone),
        website=website,
        website_status="con_sitio" if website else "sin_sitio",
        address=address,
        category=category,
        maps_url=maps_url,
        source_query=source_query,
    )


def build_locations(args: argparse.Namespace) -> list[str]:
    if args.all_buenos_aires_hotels:
        locations = BUENOS_AIRES_LOCATIONS + BUENOS_AIRES_CITY_LOCATIONS
    else:
        locations = split_csv_arg(args.locations)
        if args.buenos_aires:
            locations += BUENOS_AIRES_LOCATIONS + BUENOS_AIRES_CITY_LOCATIONS
    return list(dict.fromkeys(locations))


def build_search_terms(args: argparse.Namespace) -> list[str]:
    if args.all_buenos_aires_hotels:
        return HOTEL_SEARCH_TERMS
    return split_csv_arg(args.business_types)


def scrape(args: argparse.Namespace) -> tuple[list[Hotel], list[Hotel]]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        raise SystemExit(
            "Falta instalar Playwright. Ejecuta: "
            ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        ) from error

    search_terms = build_search_terms(args)
    locations = build_locations(args)

    missing_website: list[Hotel] = []
    checked_hotels: list[Hotel] = []
    seen_urls: set[str] = set()
    seen_hotels: set[str] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless, slow_mo=args.slow_mo)
        context = browser.new_context(locale="es-AR")
        page = context.new_page()

        try:
            for location in locations:
                for search_term in search_terms:
                    query = f"{search_term} en {location}, provincia de Buenos Aires"
                    print(f"\nBuscando: {query}")
                    open_maps_search(page, query)
                    place_urls = collect_place_urls(page, args.max_results, args.scroll_rounds)
                    print(f"Fichas encontradas para revisar: {len(place_urls)}")

                    for index, place_url in enumerate(place_urls, start=1):
                        normalized_url = normalize_maps_url(place_url)
                        if normalized_url in seen_urls:
                            continue
                        seen_urls.add(normalized_url)

                        hotel = extract_hotel(page, place_url, search_term, location, query)
                        if not hotel:
                            continue

                        key = hotel_key(hotel)
                        if key in seen_hotels:
                            continue
                        seen_hotels.add(key)

                        checked_hotels.append(hotel)
                        if not hotel.website:
                            missing_website.append(hotel)
                            phone_label = hotel.phone or "sin telefono"
                            print(f"[SIN WEB] {phone_label} ({hotel.name})")
                        else:
                            print(f"[CON WEB] {index}/{len(place_urls)} {hotel.name}")
        finally:
            browser.close()

    return missing_website, checked_hotels


def save_csv(rows: list[Hotel], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(Hotel.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def save_phone_list(rows: list[Hotel], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as txt_file:
        for row in rows:
            if row.phone:
                txt_file.write(f"{row.phone} ({row.name})\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta hoteles o negocios publicados en Google Maps que no tienen sitio web cargado."
    )
    parser.add_argument(
        "--all-buenos-aires-hotels",
        action="store_true",
        help="Modo intensivo: busca hoteles en partidos y localidades importantes de toda la provincia.",
    )
    parser.add_argument(
        "--business-types",
        default="hotel",
        help='Rubros separados por coma. Ejemplo: "hotel,cafeteria,restaurant"',
    )
    parser.add_argument(
        "--locations",
        default="Mar del Plata",
        help='Localidades separadas por coma. Ejemplo: "Mar del Plata,Tandil,La Plata"',
    )
    parser.add_argument(
        "--buenos-aires",
        action="store_true",
        help="Agrega partidos y localidades importantes de la provincia de Buenos Aires.",
    )
    parser.add_argument("--max-results", type=int, default=180, help="Maximo de resultados por busqueda.")
    parser.add_argument("--scroll-rounds", type=int, default=45, help="Cantidad maxima de scrolls por busqueda.")
    parser.add_argument("--output", default="hoteles_sin_web.csv", help="CSV con hoteles sin sitio web.")
    parser.add_argument(
        "--checked-output",
        default="hoteles_revisados.csv",
        help="CSV de auditoria con todos los hoteles revisados, tengan o no sitio web.",
    )
    parser.add_argument(
        "--phones-output",
        default="hoteles_sin_web.txt",
        help="TXT simple: telefono (nombre), solo para hoteles sin sitio web.",
    )
    parser.add_argument("--headless", action="store_true", help="Ejecuta el navegador sin ventana visible.")
    parser.add_argument("--slow-mo", type=int, default=60, help="Demora entre acciones de Playwright en ms.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    missing_website, checked_hotels = scrape(args)
    save_csv(missing_website, Path(args.output))
    save_csv(checked_hotels, Path(args.checked_output))
    save_phone_list(missing_website, Path(args.phones_output))
    print(f"\nListo. Hoteles revisados: {len(checked_hotels)}")
    print(f"Hoteles sin sitio web: {len(missing_website)}")
    print(f"CSV sin sitio: {args.output}")
    print(f"CSV auditoria: {args.checked_output}")
    print(f"Telefonos: {args.phones_output}")


if __name__ == "__main__":
    main()
