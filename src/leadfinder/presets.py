from __future__ import annotations

from dataclasses import dataclass

from leadfinder.errors import ConfigError
from leadfinder.place_types import is_table_a_type


@dataclass(frozen=True)
class BusinessPreset:
    name: str
    included_type: str
    budget_terms: tuple[str, ...]
    balanced_terms: tuple[str, ...]
    full_terms: tuple[str, ...]
    description: str

    def terms_for(self, coverage: str) -> list[str]:
        if coverage == "budget":
            return list(self.budget_terms)
        if coverage == "balanced":
            return list(self.balanced_terms)
        if coverage == "full":
            return list(self.full_terms)
        raise ConfigError(f"Unknown coverage '{coverage}'. Choose budget, balanced, or full.")


def _preset(
    name: str,
    included_type: str,
    budget: list[str],
    balanced: list[str],
    full: list[str],
    description: str,
) -> BusinessPreset:
    if included_type and not is_table_a_type(included_type):
        raise ConfigError(
            f"Preset '{name}' uses includedType '{included_type}', "
            "which is not a Places API (New) Table A type."
        )
    return BusinessPreset(
        name=name,
        included_type=included_type,
        budget_terms=tuple(budget),
        balanced_terms=tuple(balanced),
        full_terms=tuple(full),
        description=description,
    )


PRESETS: dict[str, BusinessPreset] = {
    preset.name: preset
    for preset in (
        _preset(
            "hotel",
            "lodging",
            ["hotel"],
            ["hotel", "apart hotel"],
            [
                "hotel",
                "hoteles",
                "apart hotel",
                "hotel boutique",
                "hosteria",
                "posada",
                "alojamiento",
            ],
            "Hotels and lodging.",
        ),
        _preset(
            "cafe",
            "cafe",
            ["cafe"],
            ["cafe", "cafeteria"],
            ["cafe", "cafeteria", "coffee shop", "desayuno", "merienda"],
            "Cafes and coffee shops.",
        ),
        _preset(
            "restaurant",
            "restaurant",
            ["restaurant"],
            ["restaurant", "parrilla", "pizzeria"],
            [
                "restaurant",
                "parrilla",
                "pizzeria",
                "hamburgueseria",
                "comida",
                "bodegon",
            ],
            "Restaurants and similar food venues.",
        ),
        _preset(
            "bar",
            "bar",
            ["bar"],
            ["bar", "cerveceria"],
            ["bar", "cerveceria", "pub", "cocktail bar"],
            "Bars and pubs.",
        ),
        _preset(
            "gym",
            "gym",
            ["gimnasio"],
            ["gimnasio", "fitness"],
            ["gimnasio", "fitness", "crossfit", "pilates"],
            "Gyms and fitness studios.",
        ),
        _preset(
            "beauty_salon",
            "beauty_salon",
            ["peluqueria"],
            ["peluqueria", "barberia"],
            ["peluqueria", "barberia", "centro de estetica", "salon de belleza"],
            "Salons and barbershops.",
        ),
        _preset(
            "dentist",
            "dentist",
            ["dentista"],
            ["dentista", "odontologo"],
            ["dentista", "odontologo", "clinica dental"],
            "Dentists and dental clinics.",
        ),
        _preset(
            "real_estate_agency",
            "real_estate_agency",
            ["inmobiliaria"],
            ["inmobiliaria", "real estate"],
            ["inmobiliaria", "real estate", "propiedades"],
            "Real estate agencies.",
        ),
        _preset(
            "car_repair",
            "car_repair",
            ["taller mecanico"],
            ["taller mecanico", "mecanico"],
            [
                "taller mecanico",
                "mecanico",
                "service automotor",
                "alineacion y balanceo",
            ],
            "Auto repair shops.",
        ),
        _preset(
            "technical_service",
            "",
            ["servicio tecnico"],
            ["servicio tecnico", "reparacion celulares", "reparacion computadoras"],
            [
                "servicio tecnico",
                "reparacion celulares",
                "reparacion computadoras",
                "reparacion electrodomesticos",
                "service aire acondicionado",
                "reparacion aire acondicionado",
            ],
            "General repair shops. No single Table A type covers this category.",
        ),
        _preset(
            "electrician",
            "electrician",
            ["electricista"],
            ["electricista", "electricista matriculado"],
            [
                "electricista",
                "electricista matriculado",
                "instalaciones electricas",
                "urgencias electricas",
            ],
            "Electricians.",
        ),
        _preset(
            "plumber",
            "plumber",
            ["plomero"],
            ["plomero", "gasista"],
            ["plomero", "gasista", "gasista matriculado", "destapaciones", "sanitarista"],
            "Plumbers and related home services.",
        ),
        _preset(
            "locksmith",
            "locksmith",
            ["cerrajero"],
            ["cerrajero", "cerrajeria"],
            ["cerrajero", "cerrajeria", "cerrajero 24 horas", "llaves codificadas"],
            "Locksmiths.",
        ),
        _preset(
            "painter",
            "painter",
            ["pintor"],
            ["pintor", "pintura de casas"],
            ["pintor", "pintura de casas", "pintura de obra", "pintor profesional"],
            "Painters.",
        ),
        _preset(
            "roofing_contractor",
            "roofing_contractor",
            ["techista"],
            ["techista", "reparacion de techos"],
            [
                "techista",
                "reparacion de techos",
                "zingueria",
                "impermeabilizacion de techos",
            ],
            "Roofing contractors.",
        ),
        _preset(
            "laundry",
            "laundry",
            ["lavanderia"],
            ["lavanderia", "tintoreria"],
            ["lavanderia", "tintoreria", "lavadero de ropa", "lavanderia industrial"],
            "Laundries and dry cleaners.",
        ),
        _preset(
            "moving_company",
            "moving_company",
            ["mudanzas"],
            ["mudanzas", "fletes"],
            ["mudanzas", "fletes", "empresa de mudanzas", "guardamuebles"],
            "Moving companies.",
        ),
        _preset(
            "hardware_store",
            "hardware_store",
            ["ferreteria"],
            ["ferreteria", "corralon"],
            [
                "ferreteria",
                "corralon",
                "materiales electricos",
                "materiales de construccion",
            ],
            "Hardware stores and building-supply shops.",
        ),
    )
}


def get_preset(name: str) -> BusinessPreset:
    key = name.strip().lower()
    if key not in PRESETS:
        known = ", ".join(sorted(PRESETS))
        raise ConfigError(f"Unknown business preset '{name}'. Choose one of: {known}.")
    return PRESETS[key]


def list_presets() -> list[BusinessPreset]:
    return [PRESETS[name] for name in sorted(PRESETS)]
