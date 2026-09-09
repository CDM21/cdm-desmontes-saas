# Catálogo automotivo inicial para o mercado brasileiro.
# Mantido no próprio CDM para o cadastro funcionar mesmo sem API externa.
# O usuário ainda pode digitar um modelo personalizado no frontend.

VEHICLE_CATALOG = {
    "Agrale": ["Marruá", "AM100", "AM200"],
    "Alfa Romeo": ["145", "147", "156", "159", "Giulia", "Stelvio"],
    "Audi": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q5", "Q7", "Q8", "TT", "e-tron"],
    "BMW": ["Série 1", "Série 2", "Série 3", "Série 4", "Série 5", "Série 7", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "Z4", "i3", "iX"],
    "BYD": ["Dolphin", "Dolphin Mini", "Dolphin Plus", "Song Plus", "Song Pro", "Yuan Plus", "Seal", "Han", "Tan", "King", "Shark"],
    "CAOA Chery": ["Arrizo 5", "Arrizo 6", "Tiggo 2", "Tiggo 3X", "Tiggo 5X", "Tiggo 7", "Tiggo 8"],
    "Chery": ["Celer", "Face", "QQ", "Tiggo", "Tiggo 2"],
    "Chevrolet": ["Agile", "Astra", "Blazer", "Camaro", "Captiva", "Celta", "Classic", "Cobalt", "Corsa", "Cruze", "Equinox", "Joy", "Meriva", "Montana", "Monza", "Onix", "Prisma", "S10", "Spin", "Tracker", "Trailblazer", "Vectra", "Zafira"],
    "Chrysler": ["300C", "Caravan", "Pacifica", "PT Cruiser", "Town & Country"],
    "Citroën": ["Aircross", "Basalt", "Berlingo", "C3", "C3 Aircross", "C4", "C4 Cactus", "C4 Lounge", "C5", "C5 Aircross", "Jumpy", "Xsara Picasso"],
    "Dodge": ["Challenger", "Charger", "Dakota", "Durango", "Journey", "Ram"],
    "Fiat": ["500", "Argo", "Bravo", "Cronos", "Doblo", "Ducato", "Fastback", "Fiorino", "Freemont", "Grand Siena", "Idea", "Linea", "Marea", "Mobi", "Palio", "Pulse", "Punto", "Siena", "Stilo", "Strada", "Tempra", "Toro", "Uno"],
    "Ford": ["Bronco Sport", "Courier", "EcoSport", "Edge", "Escort", "Expedition", "Explorer", "F-1000", "F-250", "Fiesta", "Focus", "Fusion", "Ka", "Maverick", "Mondeo", "Mustang", "Ranger", "Territory", "Transit", "Verona"],
    "Geely": ["Coolray", "EX5", "GC2", "EC7"],
    "GWM": ["Haval H6", "Haval H6 GT", "Ora 03", "Tank 300"],
    "Honda": ["Accord", "City", "City Hatchback", "Civic", "CR-V", "Fit", "HR-V", "WR-V", "ZR-V"],
    "Hyundai": ["Azera", "Creta", "Elantra", "HB20", "HB20S", "HR", "i30", "ix35", "Kona", "Santa Fe", "Sonata", "Tucson", "Veracruz"],
    "Iveco": ["Daily", "Daily City", "Eurocargo", "Hi-Way", "S-Way", "Tector"],
    "JAC": ["E-JS1", "E-JS4", "iEV20", "J2", "J3", "J5", "J6", "T40", "T50", "T60", "T80"],
    "Jaguar": ["E-Pace", "F-Pace", "F-Type", "I-Pace", "XE", "XF", "XJ"],
    "Jeep": ["Cherokee", "Commander", "Compass", "Gladiator", "Grand Cherokee", "Renegade", "Wrangler"],
    "Kia": ["Bongo", "Carnival", "Cerato", "Mohave", "Niro", "Optima", "Picanto", "Sorento", "Soul", "Sportage", "Stonic"],
    "Land Rover": ["Defender", "Discovery", "Discovery Sport", "Freelander", "Range Rover", "Range Rover Evoque", "Range Rover Sport", "Range Rover Velar"],
    "Lexus": ["ES", "NX", "RX", "UX"],
    "Mercedes-Benz": ["Classe A", "Classe B", "Classe C", "Classe E", "Classe S", "CLA", "CLS", "GLA", "GLB", "GLC", "GLE", "GLS", "Sprinter"],
    "Mini": ["Cooper", "Cooper Cabrio", "Countryman", "Clubman", "Paceman"],
    "Mitsubishi": ["ASX", "Eclipse Cross", "L200", "L200 Triton", "Lancer", "Outlander", "Pajero", "Pajero Dakar", "Pajero Full", "Pajero Sport"],
    "Nissan": ["Altima", "Frontier", "Grand Livina", "Kicks", "Leaf", "Livina", "March", "Pathfinder", "Sentra", "Tiida", "Versa", "X-Trail"],
    "Peugeot": ["2008", "206", "207", "208", "3008", "307", "308", "408", "5008", "Boxer", "Expert", "Hoggar", "Partner"],
    "Porsche": ["718", "911", "Cayenne", "Macan", "Panamera", "Taycan"],
    "RAM": ["1500", "2500", "3500", "Classic", "Rampage"],
    "Renault": ["Captur", "Clio", "Duster", "Fluence", "Kangoo", "Kardian", "Kwid", "Logan", "Master", "Megane", "Oroch", "Sandero", "Scenic", "Symbol"],
    "Subaru": ["Forester", "Impreza", "Legacy", "Outback", "Tribeca", "WRX", "XV"],
    "Suzuki": ["Grand Vitara", "Jimny", "Jimny Sierra", "S-Cross", "Swift", "Vitara"],
    "Toyota": ["Bandeirante", "Camry", "Corolla", "Corolla Cross", "Etios", "Fielder", "Hilux", "Hilux SW4", "Land Cruiser", "Prius", "RAV4", "SW4", "Yaris", "Yaris Cross"],
    "Volkswagen": ["Amarok", "Bora", "CrossFox", "Fox", "Fusca", "Gol", "Golf", "Jetta", "Kombi", "Nivus", "Parati", "Passat", "Polo", "Saveiro", "SpaceFox", "T-Cross", "Taos", "Tiguan", "Touareg", "Up", "Virtus", "Voyage"],
    "Volvo": ["C30", "C40", "EX30", "S40", "S60", "S90", "V40", "V60", "XC40", "XC60", "XC90"],
}

# Aliases úteis para o usuário localizar a marca do jeito que costuma falar.
BRAND_ALIASES = {
    "GM": "Chevrolet",
    "VW": "Volkswagen",
    "Mercedes": "Mercedes-Benz",
    "Caoa Chery": "CAOA Chery",
    "Mitsu": "Mitsubishi",
}


def brands():
    return sorted(VEHICLE_CATALOG.keys(), key=lambda x: x.casefold())


def models_for(brand: str):
    name = BRAND_ALIASES.get((brand or "").strip(), (brand or "").strip())
    return VEHICLE_CATALOG.get(name, [])
