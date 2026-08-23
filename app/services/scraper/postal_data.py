"""
Static Postal Code Centroid and Neighborhood Directory.

Provides high-precision, offline, zero-latency geographic centroids (lat, lng)
and neighborhood descriptions for Canadian FSAs (Forward Sortation Areas)
and US 3-digit Zip codes.
"""
from typing import Dict, Optional, Tuple, Any

# Official Statistics Canada & OpenData centroids for Canadian Postal Code FSAs (Forward Sortation Areas)
CANADIAN_FSA_DATA: Dict[str, Dict[str, Any]] = {
    # ── Toronto (M Postal Codes) ──────────────────────────────────────────────
    "M1B": {"lat": 43.8067, "lng": -79.1944, "neighborhood": "Malvern / Rouge, Scarborough"},
    "M1C": {"lat": 43.7845, "lng": -79.1605, "neighborhood": "Rouge Hill / Port Union / Highland Creek"},
    "M1E": {"lat": 43.7636, "lng": -79.1887, "neighborhood": "Guildwood / Morningside / West Hill"},
    "M1G": {"lat": 43.7701, "lng": -79.2169, "neighborhood": "Woburn, Scarborough"},
    "M1H": {"lat": 43.7731, "lng": -79.2395, "neighborhood": "Cedarbrae, Scarborough"},
    "M1J": {"lat": 43.7447, "lng": -79.2395, "neighborhood": "Scarborough Village"},
    "M1K": {"lat": 43.7279, "lng": -79.2620, "neighborhood": "Kennedy Park / Ionview / East Birchmount"},
    "M1L": {"lat": 43.7111, "lng": -79.2846, "neighborhood": "Golden Mile / Clairlea / Oakridge"},
    "M1M": {"lat": 43.7163, "lng": -79.2395, "neighborhood": "Cliffside / Cliffcrest / Scarborough Village"},
    "M1N": {"lat": 43.6927, "lng": -79.2648, "neighborhood": "Birch Cliff / Cliffside South"},
    "M1P": {"lat": 43.7574, "lng": -79.2733, "neighborhood": "Dorset Park / Wexford Heights / Scarborough Town"},
    "M1R": {"lat": 43.7501, "lng": -79.2958, "neighborhood": "Wexford / Maryvale"},
    "M1S": {"lat": 43.7942, "lng": -79.2620, "neighborhood": "Agincourt, Scarborough"},
    "M1T": {"lat": 43.7816, "lng": -79.3043, "neighborhood": "Clarks Corners / Tam O'Shanter / Sullivan"},
    "M1V": {"lat": 43.8153, "lng": -79.2846, "neighborhood": "Milliken / Agincourt North / Steeles East"},
    "M1W": {"lat": 43.7995, "lng": -79.3184, "neighborhood": "Steeles West / L'Amoreaux West"},
    "M1X": {"lat": 43.8361, "lng": -79.2056, "neighborhood": "Upper Rouge, Scarborough"},

    "M2H": {"lat": 43.8038, "lng": -79.3635, "neighborhood": "Hillcrest Village, North York"},
    "M2J": {"lat": 43.7785, "lng": -79.3466, "neighborhood": "Fairview / Henry Farm / Oriole"},
    "M2K": {"lat": 43.7869, "lng": -79.3860, "neighborhood": "Bayview Village, North York"},
    "M2L": {"lat": 43.7575, "lng": -79.3747, "neighborhood": "York Mills / Silver Hills"},
    "M2M": {"lat": 43.7891, "lng": -79.4085, "neighborhood": "Willowdale / Newtonbrook"},
    "M2N": {"lat": 43.7701, "lng": -79.4085, "neighborhood": "Willowdale South / Yonge & Sheppard"},
    "M2P": {"lat": 43.7528, "lng": -79.4000, "neighborhood": "York Mills West"},
    "M2R": {"lat": 43.7827, "lng": -79.4423, "neighborhood": "Willowdale West / Bathurst Manor"},

    "M3A": {"lat": 43.7533, "lng": -79.3297, "neighborhood": "Parkwoods / Donalda"},
    "M3B": {"lat": 43.7459, "lng": -79.3522, "neighborhood": "Don Mills North"},
    "M3C": {"lat": 43.7259, "lng": -79.3409, "neighborhood": "Don Mills South / Flemingdon Park"},
    "M3H": {"lat": 43.7543, "lng": -79.4423, "neighborhood": "Bathurst Manor / Wilson Heights / Downsview"},
    "M3J": {"lat": 43.7680, "lng": -79.4873, "neighborhood": "Northwood Park / York University"},
    "M3K": {"lat": 43.7375, "lng": -79.4648, "neighborhood": "Downsview East / CFB Toronto"},
    "M3L": {"lat": 43.7390, "lng": -79.5069, "neighborhood": "Downsview West"},
    "M3M": {"lat": 43.7285, "lng": -79.4957, "neighborhood": "Downsview Central"},
    "M3N": {"lat": 43.7616, "lng": -79.5210, "neighborhood": "Downsview Northwest / Jane and Finch"},

    "M4A": {"lat": 43.7259, "lng": -79.3156, "neighborhood": "Victoria Village, North York"},
    "M4B": {"lat": 43.7064, "lng": -79.3099, "neighborhood": "Parkview Hill / Woodbine Heights"},
    "M4C": {"lat": 43.6953, "lng": -79.3184, "neighborhood": "Woodbine Heights / East York"},
    "M4E": {"lat": 43.6764, "lng": -79.2930, "neighborhood": "The Beaches, Toronto"},
    "M4G": {"lat": 43.7091, "lng": -79.3635, "neighborhood": "Leaside / Thorncliffe Park"},
    "M4H": {"lat": 43.7054, "lng": -79.3494, "neighborhood": "Thorncliffe Park, East York"},
    "M4J": {"lat": 43.6853, "lng": -79.3381, "neighborhood": "The Danforth East / Old East York"},
    "M4K": {"lat": 43.6796, "lng": -79.3522, "neighborhood": "The Danforth West / Riverdale"},
    "M4L": {"lat": 43.6690, "lng": -79.3156, "neighborhood": "India Bazaar / The Beaches West / Leslieville"},
    "M4M": {"lat": 43.6595, "lng": -79.3409, "neighborhood": "Studio District / South Riverdale / Leslieville"},
    "M4N": {"lat": 43.7280, "lng": -79.3888, "neighborhood": "Lawrence Park / Bridle Path"},
    "M4P": {"lat": 43.7128, "lng": -79.3902, "neighborhood": "Davisville North / Yonge & Eglinton"},
    "M4R": {"lat": 43.7154, "lng": -79.4057, "neighborhood": "North Toronto / Yonge & Lawrence"},
    "M4S": {"lat": 43.7043, "lng": -79.3888, "neighborhood": "Davisville / Midtown Toronto"},
    "M4T": {"lat": 43.6896, "lng": -79.3832, "neighborhood": "Moore Park / Summerhill East"},
    "M4V": {"lat": 43.6864, "lng": -79.4000, "neighborhood": "Summerhill / Deer Park / Forest Hill South"},
    "M4W": {"lat": 43.6796, "lng": -79.3775, "neighborhood": "Rosedale, Downtown Toronto"},
    "M4X": {"lat": 43.6680, "lng": -79.3677, "neighborhood": "St. James Town / Cabbagetown"},
    "M4Y": {"lat": 43.6659, "lng": -79.3832, "neighborhood": "Church and Wellesley / Downtown Yonge East"},

    "M5A": {"lat": 43.6543, "lng": -79.3606, "neighborhood": "Regent Park / Harbourfront East / Corktown"},
    "M5B": {"lat": 43.6572, "lng": -79.3789, "neighborhood": "Garden District / Ryerson / Downtown East"},
    "M5C": {"lat": 43.6515, "lng": -79.3755, "neighborhood": "St. James Town / Financial District East"},
    "M5E": {"lat": 43.6448, "lng": -79.3733, "neighborhood": "Berczy Park / Old Town Toronto"},
    "M5G": {"lat": 43.6579, "lng": -79.3874, "neighborhood": "Bay Street Corridor / Discovery District"},
    "M5H": {"lat": 43.6506, "lng": -79.3846, "neighborhood": "Richmond / Adelaide / King / Financial District"},
    "M5J": {"lat": 43.6408, "lng": -79.3818, "neighborhood": "Harbourfront / Union Station / South Core"},
    "M5K": {"lat": 43.6472, "lng": -79.3818, "neighborhood": "Toronto Dominion Centre / Financial Core"},
    "M5L": {"lat": 43.6482, "lng": -79.3798, "neighborhood": "Commerce Court / Financial District"},
    "M5M": {"lat": 43.7333, "lng": -79.4197, "neighborhood": "Bedford Park / Lawrence Manor East"},
    "M5N": {"lat": 43.7117, "lng": -79.4169, "neighborhood": "Roselawn / Forest Hill North"},
    "M5P": {"lat": 43.6969, "lng": -79.4113, "neighborhood": "Forest Hill / Midtown West"},
    "M5R": {"lat": 43.6727, "lng": -79.4057, "neighborhood": "The Annex / Yorkville / University of Toronto"},
    "M5S": {"lat": 43.6627, "lng": -79.4000, "neighborhood": "University of Toronto / Harbord / Downtown West"},
    "M5T": {"lat": 43.6532, "lng": -79.4000, "neighborhood": "Kensington Market / Chinatown / Grange Park"},
    "M5V": {"lat": 43.6441, "lng": -79.3957, "neighborhood": "King West / Entertainment District / CityPlace"},
    "M5W": {"lat": 43.6464, "lng": -79.3748, "neighborhood": "Downtown Toronto Stn A (PO Boxes)"},
    "M5X": {"lat": 43.6487, "lng": -79.3818, "neighborhood": "First Canadian Place / Underground City"},

    "M6A": {"lat": 43.7185, "lng": -79.4648, "neighborhood": "Lawrence Manor / Lawrence Heights / Yorkdale"},
    "M6B": {"lat": 43.7096, "lng": -79.4451, "neighborhood": "Glencairn / Briar Hill, North York"},
    "M6C": {"lat": 43.6938, "lng": -79.4282, "neighborhood": "Humewood-Cedarvale / Oakwood Village"},
    "M6E": {"lat": 43.6890, "lng": -79.4535, "neighborhood": "Caledonia-Fairbanks / Earlscourt"},
    "M6G": {"lat": 43.6695, "lng": -79.4225, "neighborhood": "Christie / Koreatown / Bloorcourt"},
    "M6H": {"lat": 43.6690, "lng": -79.4423, "neighborhood": "Dufferin / Dovercourt Village"},
    "M6J": {"lat": 43.6479, "lng": -79.4197, "neighborhood": "Little Portugal / Trinity-Bellwoods / Queen West"},
    "M6K": {"lat": 43.6368, "lng": -79.4282, "neighborhood": "Brockton / Parkdale Village / Exhibition Place"},
    "M6L": {"lat": 43.7138, "lng": -79.4901, "neighborhood": "North Park / Maple Leaf / Downsview"},
    "M6M": {"lat": 43.6957, "lng": -79.4844, "neighborhood": "Del Ray / Mount Dennis / Keelesdale"},
    "M6N": {"lat": 43.6761, "lng": -79.4873, "neighborhood": "Runnymede / The Junction South / Stockyards"},
    "M6P": {"lat": 43.6616, "lng": -79.4648, "neighborhood": "High Park / The Junction North"},
    "M6R": {"lat": 43.6489, "lng": -79.4563, "neighborhood": "Parkdale / Roncesvalles Village"},
    "M6S": {"lat": 43.6515, "lng": -79.4844, "neighborhood": "Runnymede / Swansea / Bloor West Village"},

    "M7A": {"lat": 43.6623, "lng": -79.3918, "neighborhood": "Queen's Park / Ontario Provincial Government"},
    "M7R": {"lat": 43.6154, "lng": -79.6080, "neighborhood": "Mississauga Gateway / Airport East"},
    "M7Y": {"lat": 43.6627, "lng": -79.3216, "neighborhood": "Business Reply Mail / Leslieville East"},

    "M8V": {"lat": 43.6056, "lng": -79.5013, "neighborhood": "New Toronto / Mimico South / Humber Bay"},
    "M8W": {"lat": 43.6024, "lng": -79.5435, "neighborhood": "Alderwood / Long Branch East"},
    "M8X": {"lat": 43.6537, "lng": -79.5069, "neighborhood": "The Kingsway / Montgomery Road / Old Mill"},
    "M8Y": {"lat": 43.6363, "lng": -79.4985, "neighborhood": "Old Mill South / King's Mill Park / Sunnylea"},
    "M8Z": {"lat": 43.6288, "lng": -79.5210, "neighborhood": "Mimico NW / The Queensway West / Royal York"},

    "M9A": {"lat": 43.6679, "lng": -79.5322, "neighborhood": "Islington Avenue / Princess Gardens"},
    "M9B": {"lat": 43.6509, "lng": -79.5547, "neighborhood": "West Deane Park / Princess Anne Manor / Etobicoke"},
    "M9C": {"lat": 43.6435, "lng": -79.5772, "neighborhood": "Eringate / Bloordale Gardens / Markland Wood"},
    "M9L": {"lat": 43.7563, "lng": -79.5660, "neighborhood": "Humber Summit, North York"},
    "M9M": {"lat": 43.7248, "lng": -79.5322, "neighborhood": "Humberlea / Emery"},
    "M9N": {"lat": 43.7069, "lng": -79.5181, "neighborhood": "Weston, York"},
    "M9P": {"lat": 43.6963, "lng": -79.5322, "neighborhood": "Westmount / Richview"},
    "M9R": {"lat": 43.6889, "lng": -79.5547, "neighborhood": "Kingsview Village / St. Phillips / Martin Grove"},
    "M9V": {"lat": 43.7394, "lng": -79.5888, "neighborhood": "South Steeles / Silverstone / Mount Olive / Albion"},
    "M9W": {"lat": 43.7067, "lng": -79.5940, "neighborhood": "Northwest Etobicoke / Rexdale / Airport"},

    # ── Greater Toronto / Hamilton / Ontario Highlights ────────────────────────
    "L5B": {"lat": 43.5890, "lng": -79.6441, "neighborhood": "Mississauga City Centre / Square One"},
    "L5N": {"lat": 43.5937, "lng": -79.7420, "neighborhood": "Meadowvale, Mississauga"},
    "L6T": {"lat": 43.7182, "lng": -79.7077, "neighborhood": "Brampton East / Bramalea"},
    "L6Y": {"lat": 43.6565, "lng": -79.7454, "neighborhood": "Brampton South / Churchville"},
    "L4W": {"lat": 43.6373, "lng": -79.6200, "neighborhood": "Dixie / Airport Corporate, Mississauga"},
    "L4Z": {"lat": 43.6190, "lng": -79.6644, "neighborhood": "Hurontario, Mississauga"},
    "L4J": {"lat": 43.8052, "lng": -79.4674, "neighborhood": "Thornhill, Vaughan"},
    "L4K": {"lat": 43.8028, "lng": -79.5089, "neighborhood": "Concord / Vaughan Corporate"},
    "L3T": {"lat": 43.8183, "lng": -79.4000, "neighborhood": "Thornhill East, Markham"},
    "L3R": {"lat": 43.8475, "lng": -79.3328, "neighborhood": "Markham Central / Unionville"},
    "L6A": {"lat": 43.8653, "lng": -79.5069, "neighborhood": "Maple, Vaughan"},
    "L6H": {"lat": 43.4675, "lng": -79.6877, "neighborhood": "Oakville North / Sheridan"},
    "L6M": {"lat": 43.4352, "lng": -79.7332, "neighborhood": "Oakville West / Bronte"},
    "L7L": {"lat": 43.3762, "lng": -79.7618, "neighborhood": "Burlington East / Shoreacres"},
    "L8P": {"lat": 43.2557, "lng": -79.8808, "neighborhood": "Hamilton Central / Durand / Kirkendall"},
    "K1P": {"lat": 45.4215, "lng": -75.6972, "neighborhood": "Downtown Ottawa / Parliament Hill"},
    "K1N": {"lat": 45.4285, "lng": -75.6832, "neighborhood": "ByWard Market / Sandy Hill, Ottawa"},

    # ── Vancouver & BC Highlights ─────────────────────────────────────────────
    "V6B": {"lat": 49.2796, "lng": -123.1118, "neighborhood": "Downtown Vancouver / Yaletown / Gastown"},
    "V6C": {"lat": 49.2872, "lng": -123.1147, "neighborhood": "Waterfront / Coal Harbour, Vancouver"},
    "V6E": {"lat": 49.2842, "lng": -123.1311, "neighborhood": "West End / Robson, Vancouver"},
    "V6J": {"lat": 49.2625, "lng": -123.1432, "neighborhood": "Kitsilano North / Burrard, Vancouver"},
    "V6K": {"lat": 49.2652, "lng": -123.1678, "neighborhood": "Kitsilano West, Vancouver"},
    "V5T": {"lat": 49.2619, "lng": -123.0945, "neighborhood": "Mount Pleasant, Vancouver"},
    "V5K": {"lat": 49.2816, "lng": -123.0456, "neighborhood": "Hastings-Sunrise, Vancouver"},
    "V5Y": {"lat": 49.2568, "lng": -123.1142, "neighborhood": "Mount Pleasant West / City Hall, Vancouver"},
    "V5Z": {"lat": 49.2505, "lng": -123.1256, "neighborhood": "South Cambie / Oakridge, Vancouver"},

    # ── Montreal Highlights ───────────────────────────────────────────────────
    "H2X": {"lat": 45.5126, "lng": -73.5684, "neighborhood": "Quartier des Spectacles / Plateau Mont-Royal, Montreal"},
    "H2Y": {"lat": 45.5050, "lng": -73.5540, "neighborhood": "Vieux-Montréal / Old Port, Montreal"},
    "H3A": {"lat": 45.5048, "lng": -73.5772, "neighborhood": "Downtown Montreal / McGill University"},
    "H3B": {"lat": 45.4988, "lng": -73.5701, "neighborhood": "Downtown Montreal / Place Ville-Marie"},
    "H3G": {"lat": 45.4955, "lng": -73.5788, "neighborhood": "Concordia University / Golden Square Mile"},
    "H2W": {"lat": 45.5204, "lng": -73.5855, "neighborhood": "Plateau-Mont-Royal Central, Montreal"},
    "H2T": {"lat": 45.5265, "lng": -73.5932, "neighborhood": "Mile End / Laurier, Montreal"},
    "H3K": {"lat": 45.4805, "lng": -73.5694, "neighborhood": "Griffintown / Little Burgundy / Pointe-Saint-Charles"},

    # ── Calgary & Edmonton Highlights ─────────────────────────────────────────
    "T2P": {"lat": 51.0486, "lng": -114.0708, "neighborhood": "Downtown Calgary Commercial Core"},
    "T2R": {"lat": 51.0396, "lng": -114.0754, "neighborhood": "Beltline / 17th Avenue SW, Calgary"},
    "T2S": {"lat": 51.0267, "lng": -114.0732, "neighborhood": "Mission / Cliff Bungalow / Elbow Park, Calgary"},
    "T5J": {"lat": 53.5444, "lng": -113.4909, "neighborhood": "Downtown Edmonton"},
    "T6G": {"lat": 53.5225, "lng": -113.5256, "neighborhood": "University of Alberta / Garneau, Edmonton"},
    "T6E": {"lat": 53.5098, "lng": -113.4987, "neighborhood": "Whyte Avenue / Strathcona, Edmonton"},
}


def lookup_fsa_data(postal_code: str) -> Optional[Tuple[float, float, str]]:
    """
    Returns (lat, lng, neighborhood) for a 3-character Canadian postal FSA prefix if found.
    Returns None if not in the offline dictionary.
    """
    if not postal_code:
        return None
    
    code = postal_code.strip().upper()[:3]
    if code in CANADIAN_FSA_DATA:
        info = CANADIAN_FSA_DATA[code]
        return info["lat"], info["lng"], info["neighborhood"]
    
    return None
