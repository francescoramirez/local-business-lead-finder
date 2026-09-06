import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


HOTEL_SEARCH_TERMS = [
    "hotel",
    "hoteles",
    "apart hotel",
    "hotel boutique",
    "hosteria",
    "posada",
    "alojamiento",
]

LOW_COST_HOTEL_SEARCH_TERMS = ["hotel"]

BALANCED_HOTEL_SEARCH_TERMS = ["hotel", "apart hotel"]

BUSINESS_PRESETS = {
    "hotel": {
        "place_type": "lodging",
        "budget_terms": ["hotel"],
        "balanced_terms": ["hotel", "apart hotel"],
        "full_terms": HOTEL_SEARCH_TERMS,
    },
    "cafe": {
        "place_type": "cafe",
        "budget_terms": ["cafe"],
        "balanced_terms": ["cafe", "cafeteria"],
        "full_terms": ["cafe", "cafeteria", "coffee shop", "desayuno", "merienda"],
    },
    "restaurant": {
        "place_type": "restaurant",
        "budget_terms": ["restaurant"],
        "balanced_terms": ["restaurant", "parrilla", "pizzeria"],
        "full_terms": ["restaurant", "parrilla", "pizzeria", "hamburgueseria", "comida", "bodegon"],
    },
    "bar": {
        "place_type": "bar",
        "budget_terms": ["bar"],
        "balanced_terms": ["bar", "cerveceria"],
        "full_terms": ["bar", "cerveceria", "pub", "cocktail bar"],
    },
    "gym": {
        "place_type": "gym",
        "budget_terms": ["gimnasio"],
        "balanced_terms": ["gimnasio", "fitness"],
        "full_terms": ["gimnasio", "fitness", "crossfit", "pilates"],
    },
    "beauty_salon": {
        "place_type": "beauty_salon",
        "budget_terms": ["peluqueria"],
        "balanced_terms": ["peluqueria", "barberia"],
        "full_terms": ["peluqueria", "barberia", "centro de estetica", "salon de belleza"],
    },
    "dentist": {
        "place_type": "dentist",
        "budget_terms": ["dentista"],
        "balanced_terms": ["dentista", "odontologo"],
        "full_terms": ["dentista", "odontologo", "clinica dental"],
    },
    "real_estate_agency": {
        "place_type": "real_estate_agency",
        "budget_terms": ["inmobiliaria"],
        "balanced_terms": ["inmobiliaria", "real estate"],
        "full_terms": ["inmobiliaria", "real estate", "propiedades"],
    },
    "car_repair": {
        "place_type": "car_repair",
        "budget_terms": ["taller mecanico"],
        "balanced_terms": ["taller mecanico", "mecanico"],
        "full_terms": ["taller mecanico", "mecanico", "service automotor", "alineacion y balanceo"],
    },
    "technical_service": {
        "place_type": "",
        "budget_terms": ["servicio tecnico"],
        "balanced_terms": ["servicio tecnico", "reparacion celulares", "reparacion computadoras"],
        "full_terms": [
            "servicio tecnico",
            "reparacion celulares",
            "reparacion computadoras",
            "reparacion electrodomesticos",
            "service aire acondicionado",
            "reparacion aire acondicionado",
        ],
    },
    "electrician": {
        "place_type": "electrician",
        "budget_terms": ["electricista"],
        "balanced_terms": ["electricista", "electricista matriculado"],
        "full_terms": ["electricista", "electricista matriculado", "instalaciones electricas", "urgencias electricas"],
    },
    "plumber": {
        "place_type": "plumber",
        "budget_terms": ["plomero"],
        "balanced_terms": ["plomero", "gasista"],
        "full_terms": ["plomero", "gasista", "gasista matriculado", "destapaciones", "sanitarista"],
    },
    "locksmith": {
        "place_type": "locksmith",
        "budget_terms": ["cerrajero"],
        "balanced_terms": ["cerrajero", "cerrajeria"],
        "full_terms": ["cerrajero", "cerrajeria", "cerrajero 24 horas", "llaves codificadas"],
    },
    "painter": {
        "place_type": "painter",
        "budget_terms": ["pintor"],
        "balanced_terms": ["pintor", "pintura de casas"],
        "full_terms": ["pintor", "pintura de casas", "pintura de obra", "pintor profesional"],
    },
    "roofing_contractor": {
        "place_type": "roofing_contractor",
        "budget_terms": ["techista"],
        "balanced_terms": ["techista", "reparacion de techos"],
        "full_terms": ["techista", "reparacion de techos", "zingueria", "impermeabilizacion de techos"],
    },
    "laundry": {
        "place_type": "laundry",
        "budget_terms": ["lavanderia"],
        "balanced_terms": ["lavanderia", "tintoreria"],
        "full_terms": ["lavanderia", "tintoreria", "lavadero de ropa", "lavanderia industrial"],
    },
    "moving_company": {
        "place_type": "moving_company",
        "budget_terms": ["mudanzas"],
        "balanced_terms": ["mudanzas", "fletes"],
        "full_terms": ["mudanzas", "fletes", "empresa de mudanzas", "guardamuebles"],
    },
    "hardware_store": {
        "place_type": "hardware_store",
        "budget_terms": ["ferreteria"],
        "balanced_terms": ["ferreteria", "corralon"],
        "full_terms": ["ferreteria", "corralon", "materiales electricos", "materiales de construccion"],
    },
}

# Modo barato: ciudades grandes, turisticas o cabeceras comerciales. Evita
# pueblos y partidos con baja probabilidad de volumen hotelero para gastar
# muchos menos requests.
CAPITAL_FEDERAL_BUDGET_LOCATIONS = [
    "Ciudad Autonoma de Buenos Aires",
]

CAPITAL_FEDERAL_BALANCED_LOCATIONS = [
    *CAPITAL_FEDERAL_BUDGET_LOCATIONS,
    "Palermo, Ciudad Autonoma de Buenos Aires",
    "Recoleta, Ciudad Autonoma de Buenos Aires",
    "Retiro, Ciudad Autonoma de Buenos Aires",
    "Microcentro, Ciudad Autonoma de Buenos Aires",
    "Puerto Madero, Ciudad Autonoma de Buenos Aires",
    "San Telmo, Ciudad Autonoma de Buenos Aires",
    "Belgrano, Ciudad Autonoma de Buenos Aires",
    "Almagro, Ciudad Autonoma de Buenos Aires",
    "Caballito, Ciudad Autonoma de Buenos Aires",
    "Villa Crespo, Ciudad Autonoma de Buenos Aires",
]

BUENOS_AIRES_COAST_LOCATIONS = [
    "Mar del Plata",
    "Chapadmalal",
    "Miramar",
    "Mar del Sur",
    "Villa Gesell",
    "Pinamar",
    "Carilo",
    "Valeria del Mar",
    "Ostende",
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
    "Monte Hermoso",
    "Pehuen Co",
    "Claromeco",
    "Reta",
    "Orense",
    "Mar Chiquita",
]

BUENOS_AIRES_AMBA_LOCATIONS = [
    "La Plata",
    "Tigre",
    "Pilar",
    "Escobar",
    "San Isidro",
    "Vicente Lopez",
    "Moron",
    "Ramos Mejia",
    "San Justo",
    "Quilmes",
    "Avellaneda",
    "Lanus",
    "Lomas de Zamora",
    "Ezeiza",
    "Campana",
    "Zarate",
    "San Miguel",
    "Moreno",
    "Merlo",
    "Berazategui",
    "Florencio Varela",
    "Almirante Brown",
]

BUENOS_AIRES_INTERIOR_IMPORTANT_LOCATIONS = [
    "Bahia Blanca",
    "Tandil",
    "Sierra de la Ventana",
    "Lujan",
    "San Antonio de Areco",
    "San Pedro",
    "San Nicolas de los Arroyos",
    "Pergamino",
    "Junin",
    "Olavarria",
    "Azul",
    "Chascomus",
    "Mercedes",
    "Chivilcoy",
    "Trenque Lauquen",
    "Tres Arroyos",
    "Dolores",
    "Bragado",
    "Balcarce",
    "Nueve de Julio",
    "Veinticinco de Mayo",
    "Lincoln",
    "Chacabuco",
    "Saladillo",
    "Bolivar",
    "Pehuajo",
    "Coronel Suarez",
    "Coronel Pringles",
    "Coronel Dorrego",
    "Chascomus",
    "Lobos",
    "Campana",
    "Zarate",
]

BUENOS_AIRES_BUDGET_LOCATIONS = [
    *CAPITAL_FEDERAL_BALANCED_LOCATIONS,
    *BUENOS_AIRES_COAST_LOCATIONS,
    *BUENOS_AIRES_AMBA_LOCATIONS,
    *BUENOS_AIRES_INTERIOR_IMPORTANT_LOCATIONS,
]

BUENOS_AIRES_BALANCED_LOCATIONS = [
    *CAPITAL_FEDERAL_BALANCED_LOCATIONS,
    *BUENOS_AIRES_BUDGET_LOCATIONS,
    "Batan",
    "Sierra de los Padres",
    "La Matanza",
    "Jose C. Paz",
    "Malvinas Argentinas",
    "Hurlingham",
    "Ituzaingo",
    "Tres de Febrero",
    "Esteban Echeverria",
    "Canuelas",
    "Ensenada",
    "Berisso",
    "Baradero",
    "Ramallo",
    "Arrecifes",
    "Salto",
    "Colon",
    "Rojas",
    "General Villegas",
    "Carlos Casares",
    "Daireaux",
    "Tapalque",
    "Laprida",
    "Benito Juarez",
    "Ayacucho",
    "Maipu",
    "Patagones",
    "Carmen de Patagones",
]

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

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.internationalPhoneNumber,"
    "places.websiteUri,"
    "places.googleMapsUri,"
    "places.businessStatus,"
    "places.types,"
    "nextPageToken"
)

MINIMAL_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.websiteUri,"
    "nextPageToken"
)


@dataclass(frozen=True)
class Business:
    business_preset: str
    place_type: str
    place_id: str
    name: str
    phone: str
    website: str
    website_status: str
    address: str
    business_status: str
    types: str
    google_maps_url: str
    source_query: str
    source_location: str
    search_term: str


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def split_csv_arg(value: str) -> list[str]:
    return unique(value.split(","))


def build_query(search_term: str, location: str) -> str:
    normalized_location = location.lower()
    if "ciudad autonoma de buenos aires" in normalized_location or "caba" in normalized_location:
        return f"{search_term} en {location}, Argentina"
    return f"{search_term} en {location}, provincia de Buenos Aires, Argentina"


def get_preset(args: argparse.Namespace) -> dict[str, list[str] | str]:
    return BUSINESS_PRESETS[args.business_preset]


def build_place_type(args: argparse.Namespace) -> str:
    if args.place_type:
        return args.place_type.strip()
    return str(get_preset(args)["place_type"])


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    if path.is_dir():
        print(f"Cache ignorado porque es una carpeta: {path}")
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(cache, file, ensure_ascii=False, indent=2)
        temp_path.replace(path)
    except PermissionError:
        fallback_path = Path("cache") / "places_cache_fallback.json"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = fallback_path.with_suffix(fallback_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(cache, file, ensure_ascii=False, indent=2)
        temp_path.replace(fallback_path)
        print(f"No pude escribir {path}. Guarde el cache en {fallback_path}.")


def build_field_mask(include_lead_fields: bool) -> str:
    if include_lead_fields:
        return FIELD_MASK
    return MINIMAL_FIELD_MASK


def post_json(url: str, api_key: str, payload: dict[str, Any], field_mask: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Error Google Places API {error.code}: {detail}") from error


def search_places(
    api_key: str,
    query: str,
    place_type: str,
    page_size: int,
    max_pages: int,
    field_mask: str,
) -> tuple[list[dict[str, Any]], int]:
    places: list[dict[str, Any]] = []
    api_requests = 0
    payload: dict[str, Any] = {
        "textQuery": query,
        "languageCode": "es-419",
        "regionCode": "AR",
        "pageSize": min(page_size, 20),
    }
    if place_type:
        payload["includedType"] = place_type

    for page_number in range(max_pages):
        data = post_json(SEARCH_URL, api_key, payload, field_mask)
        api_requests += 1
        places.extend(data.get("places", []))
        token = data.get("nextPageToken")
        if not token:
            break
        payload = {"pageToken": token}
        if page_number < max_pages - 1:
            time.sleep(2.5)

    return places, api_requests


def place_to_business(
    place: dict[str, Any],
    source_query: str,
    location: str,
    search_term: str,
    business_preset: str,
    place_type: str,
) -> Business:
    name = place.get("displayName", {}).get("text", "")
    phone = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber") or ""
    website = place.get("websiteUri", "")
    return Business(
        business_preset=business_preset,
        place_type=place_type,
        place_id=place.get("id", ""),
        name=name,
        phone=phone,
        website=website,
        website_status="con_sitio" if website else "sin_sitio",
        address=place.get("formattedAddress", ""),
        business_status=place.get("businessStatus", ""),
        types=";".join(place.get("types", [])),
        google_maps_url=place.get("googleMapsUri", ""),
        source_query=source_query,
        source_location=location,
        search_term=search_term,
    )


def save_csv(rows: list[Business], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(Business.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def save_phone_list(rows: list[Business], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as txt_file:
        for row in rows:
            if row.phone:
                txt_file.write(f"{row.phone} ({row.name})\n")


def build_locations(args: argparse.Namespace) -> list[str]:
    if args.test:
        return [args.test_location]
    if args.all_buenos_aires_hotels or not args.locations.strip():
        if args.coverage == "budget":
            return unique(BUENOS_AIRES_BUDGET_LOCATIONS)
        if args.coverage == "balanced":
            return unique(BUENOS_AIRES_BALANCED_LOCATIONS)
        return unique(BUENOS_AIRES_LOCATIONS + BUENOS_AIRES_CITY_LOCATIONS)
    locations = split_csv_arg(args.locations)
    if args.buenos_aires:
        if args.coverage == "budget":
            locations += BUENOS_AIRES_BUDGET_LOCATIONS
        elif args.coverage == "balanced":
            locations += BUENOS_AIRES_BALANCED_LOCATIONS
        else:
            locations += BUENOS_AIRES_LOCATIONS + BUENOS_AIRES_CITY_LOCATIONS
    return unique(locations)


def build_search_terms(args: argparse.Namespace) -> list[str]:
    if args.search_terms:
        return split_csv_arg(args.search_terms)

    preset = get_preset(args)
    if args.test:
        return list(preset["budget_terms"])
    if args.coverage == "budget":
        return list(preset["budget_terms"])
    if args.coverage == "balanced":
        return list(preset["balanced_terms"])
    return list(preset["full_terms"])


def scrape(args: argparse.Namespace) -> tuple[list[Business], list[Business]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit("Falta GOOGLE_MAPS_API_KEY. En PowerShell: $env:GOOGLE_MAPS_API_KEY='TU_KEY'")

    cache_path = Path(args.cache)
    cache = load_cache(cache_path)
    checked: dict[str, Business] = {}
    request_count = 0
    field_mask = build_field_mask(args.include_lead_fields)
    place_type = build_place_type(args)

    for location in build_locations(args):
        for search_term in build_search_terms(args):
            if request_count >= args.max_api_requests:
                print("Corte por limite de seguridad --max-api-requests.")
                save_cache(cache_path, cache)
                rows = list(checked.values())
                return [row for row in rows if not row.website], rows

            query = build_query(search_term, location)
            print(f"Buscando: {query}")
            cache_key = (
                f"search::{query}::type={place_type}::pages={args.max_pages}"
                f"::size={args.page_size}::lead={args.include_lead_fields}"
            )

            if cache_key in cache:
                places = cache[cache_key]["places"]
            else:
                remaining_requests = args.max_api_requests - request_count
                pages_to_fetch = min(args.max_pages, remaining_requests)
                places, api_requests = search_places(
                    args.api_key or api_key,
                    query,
                    place_type,
                    args.page_size,
                    pages_to_fetch,
                    field_mask,
                )
                cache[cache_key] = {"places": places, "api_requests": api_requests}
                save_cache(cache_path, cache)
                request_count += api_requests
                time.sleep(args.delay)

            print(f"Resultados recibidos: {len(places)}")
            for place in places:
                place_id = place.get("id")
                if not place_id or place_id in checked:
                    continue
                business = place_to_business(
                    place,
                    query,
                    location,
                    search_term,
                    args.business_preset,
                    place_type,
                )
                checked[place_id] = business

    rows = list(checked.values())
    return [row for row in rows if not row.website], rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Busca negocios sin sitio web usando Google Places API New.")
    parser.add_argument("--test", action="store_true", help="Prueba chica y barata: solo una localidad y el preset elegido.")
    parser.add_argument("--test-location", default="Mar del Plata", help="Localidad usada con --test.")
    parser.add_argument(
        "--all-buenos-aires-hotels",
        action="store_true",
        help="Alias legacy. Busca en CABA y ciudades importantes de provincia de Buenos Aires.",
    )
    parser.add_argument(
        "--business-preset",
        choices=tuple(BUSINESS_PRESETS.keys()),
        default="hotel",
        help="Preset de rubro. Define place-type y keywords por cobertura.",
    )
    parser.add_argument(
        "--place-type",
        default="",
        help="Tipo de Google Places. Si se omite, usa el tipo del preset.",
    )
    parser.add_argument("--buenos-aires", action="store_true", help="Agrega CABA y ciudades importantes de provincia de Buenos Aires.")
    parser.add_argument(
        "--coverage",
        choices=("budget", "balanced", "full"),
        default="budget",
        help="budget gasta menos; balanced suma ciudades/keywords; full recorre casi todos los partidos.",
    )
    parser.add_argument(
        "--locations",
        default="",
        help="Localidades separadas por coma. Si se omite, usa CABA + Buenos Aires en modo budget.",
    )
    parser.add_argument(
        "--search-terms",
        default="",
        help="Terminos separados por coma. Si se omite, usa los del preset.",
    )
    parser.add_argument("--page-size", type=int, default=20, help="Resultados por pagina. Maximo API: 20.")
    parser.add_argument("--max-pages", type=int, default=1, help="Paginas por busqueda. 1 es lo mas barato; maximo util: 3.")
    parser.add_argument(
        "--max-api-requests",
        type=int,
        default=100,
        help="Limite de seguridad de requests nuevas no cacheadas. Cada pagina cuenta como 1.",
    )
    parser.add_argument(
        "--max-search-requests",
        type=int,
        help="Alias viejo de --max-api-requests.",
    )
    parser.add_argument(
        "--include-lead-fields",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Incluye telefono, Maps URL, estado y tipos. Usa --no-include-lead-fields para minimizar campos.",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Pausa entre requests nuevas.")
    parser.add_argument("--cache", default="cache/places_cache.json", help="Cache local para no pagar dos veces.")
    parser.add_argument("--output", default="negocios_sin_web_api.csv", help="CSV de negocios sin sitio web.")
    parser.add_argument("--checked-output", default="negocios_revisados_api.csv", help="CSV de auditoria.")
    parser.add_argument("--phones-output", default="negocios_sin_web_api.txt", help="TXT telefono (nombre).")
    parser.add_argument("--print-locations", action="store_true", help="Muestra ubicaciones a buscar sin gastar API.")
    parser.add_argument("--api-key", default="", help="Opcional. Mejor usar GOOGLE_MAPS_API_KEY.")
    args = parser.parse_args()
    if args.max_search_requests is not None:
        args.max_api_requests = args.max_search_requests
    args.max_pages = max(1, min(args.max_pages, 3))
    args.page_size = max(1, min(args.page_size, 20))
    return args


def main() -> None:
    args = parse_args()
    if args.print_locations:
        locations = build_locations(args)
        search_terms = build_search_terms(args)
        place_type = build_place_type(args)
        print(f"Preset: {args.business_preset}")
        print(f"Place type: {place_type or 'sin filtro'}")
        print(f"Ubicaciones: {len(locations)}")
        print(f"Terminos: {', '.join(search_terms)}")
        print(f"Requests maximas estimadas con max-pages={args.max_pages}: {len(locations) * len(search_terms) * args.max_pages}")
        for location in locations:
            print(f"- {location}")
        return

    missing_website, checked = scrape(args)
    save_csv(missing_website, Path(args.output))
    save_csv(checked, Path(args.checked_output))
    save_phone_list(missing_website, Path(args.phones_output))
    print(f"\nListo. Negocios revisados: {len(checked)}")
    print(f"Negocios sin sitio web: {len(missing_website)}")
    print(f"CSV sin sitio: {args.output}")
    print(f"CSV auditoria: {args.checked_output}")
    print(f"Telefonos: {args.phones_output}")


if __name__ == "__main__":
    main()
