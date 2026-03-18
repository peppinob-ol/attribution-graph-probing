"""
Tiered classification for swap experiment results.

Classifies steering outcomes into success tiers based on geographic accuracy.
Supports:
- Manual overrides (from human annotations)
- Rule-based classification (US cities/counties database)
- LLM-based classification (OpenAI API)
- Hybrid mode with confidence scoring
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class SwapTier(IntEnum):
    """Success tier for swap classification.

    Geography domain (USA states):
        0 = WRONG_STATE      -- city from unrelated third state
        1 = SOURCE_PERSISTS  -- source city/state still in output
        2 = SUPPRESSED_ONLY  -- source gone, garbled / no geographic content
        3 = TARGET_STATE_ONLY -- target state mentioned, no valid city
        4 = TARGET_STATE_CITY -- other city in target state (not capital)
        5 = PERFECT           -- target capital appears

    Generic domain (books, languages, etc.) -- reuses the same numeric
    scale but tier 3 means "first token of target answer is correct while
    the full answer diverges" (partial steering success).
    """
    WRONG_STATE = 0
    SOURCE_PERSISTS = 1
    SUPPRESSED_ONLY = 2
    TARGET_STATE_ONLY = 3  # Generic: FIRST_TOKEN_MATCH
    TARGET_STATE_CITY = 4
    PERFECT = 5


class ClassificationMethod(IntEnum):
    """How the classification was determined."""
    MANUAL = 0       # Human annotation (highest priority)
    RULE_HIGH = 1    # Rule-based with high confidence
    LLM = 2          # LLM classification
    RULE_LOW = 3     # Rule-based with low confidence (ambiguous)


@dataclass
class ClassificationResult:
    """Result of swap classification with confidence metadata."""
    tier: SwapTier
    cities_found: List[str]
    states_found: List[str]
    notes: str
    method: ClassificationMethod = ClassificationMethod.RULE_HIGH
    confidence: float = 1.0  # 0.0-1.0, lower = more uncertain
    ambiguous_cities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'tier': self.tier.value,
            'tier_name': self.tier.name,
            'cities_found': self.cities_found,
            'states_found': self.states_found,
            'notes': self.notes,
            'method': self.method.name,
            'confidence': self.confidence,
            'ambiguous_cities': self.ambiguous_cities,
        }


# ============================================================================
# Geographic Database
# ============================================================================

# Embedded US cities database - major cities per state
US_CITIES: Dict[str, List[str]] = {
    "Alabama": ["Montgomery", "Birmingham", "Huntsville", "Mobile", "Tuscaloosa", "Phenix City"],
    "Alaska": ["Juneau", "Anchorage", "Fairbanks", "Sitka", "Ketchikan", "Borough"],
    "Arizona": ["Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale", "Glendale", "Tempe", "Flagstaff"],
    "Arkansas": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro"],
    "California": ["Sacramento", "Los Angeles", "San Francisco", "San Diego", "San Jose", "Oakland", 
                   "Fresno", "Long Beach", "Bakersfield", "Anaheim", "Santa Ana", "Riverside", 
                   "Stockton", "Irvine", "Chula Vista", "Fremont", "Santa Clara", "Pasadena", 
                   "Berkeley", "Modesto"],
    "Colorado": ["Denver", "Colorado Springs", "Springs", "Aurora", "Fort Collins", "Lakewood", 
                 "Boulder", "Pueblo", "Pikes Peak"],
    "Connecticut": ["Hartford", "Bridgeport", "New Haven", "Stamford", "Waterbury", "Norwalk", "Deep River"],
    "Delaware": ["Dover", "Wilmington", "Newark", "Middletown", "Smyrna"],
    "Florida": ["Tallahassee", "Miami", "Jacksonville", "Tampa", "Orlando", "St. Petersburg", 
                "Hialeah", "Fort Lauderdale", "Port St. Lucie", "Cape Coral", "Pembroke Pines", 
                "Hollywood", "Gainesville", "Coral Springs", "Keys", "Everglades"],
    "Georgia": ["Atlanta", "Augusta", "Columbus", "Savannah", "Athens", "Macon", "Roswell", "Albany"],
    "Hawaii": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Pearl City", "Waipahu"],
    "Idaho": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Caldwell", "Twin Falls"],
    "Illinois": ["Springfield", "Chicago", "Aurora", "Naperville", "Joliet", "Rockford", "Elgin", "Peoria"],
    "Indiana": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", "Fishers", 
                "Bloomington", "Gary", "Crown Point"],
    "Iowa": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", "Waterloo", "Ames"],
    "Kansas": ["Topeka", "Wichita", "Overland Park", "Kansas City", "Olathe", "Lawrence", "Shawnee"],
    "Kentucky": ["Frankfort", "Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington"],
    "Louisiana": ["Baton Rouge", "New Orleans", "Shreveport", "Metairie", "Lafayette", "Lake Charles", 
                  "Kenner", "Barataria"],
    "Maine": ["Augusta", "Portland", "Lewiston", "Bangor", "South Portland", "Auburn"],
    "Maryland": ["Annapolis", "Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie", "Hagerstown"],
    "Massachusetts": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell", "Brockton", 
                      "New Bedford", "Quincy", "Lynn", "Fall River", "Salem"],
    "Michigan": ["Lansing", "Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", 
                 "Flint", "Dearborn", "Livonia", "Troy", "Kalamazoo"],
    "Minnesota": ["Saint Paul", "St. Paul", "Minneapolis", "Rochester", "Duluth", "Bloomington", 
                  "Brooklyn Park", "Plymouth"],
    "Mississippi": ["Jackson", "Gulfport", "Southaven", "Hattiesburg", "Biloxi", "Meridian", "Tupelo"],
    "Missouri": ["Jefferson City", "Kansas City", "St. Louis", "Springfield", "Columbia", 
                 "Independence", "Lee's Summit"],
    "Montana": ["Helena", "Billings", "Missoula", "Great Falls", "Bozeman", "Butte", "Medora"],
    "Nebraska": ["Lincoln", "Omaha", "Bellevue", "Grand Island", "Kearney", "Fremont"],
    "Nevada": ["Carson City", "Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks", "Elko"],
    "New Hampshire": ["Concord", "Manchester", "Nashua", "Derry", "Dover", "Rochester", "Shelburne"],
    "New Jersey": ["Trenton", "Newark", "Jersey City", "Paterson", "Elizabeth", "Edison", 
                   "Woodbridge", "Lakewood", "Toms River", "Hamilton", "Clifton", "Camden"],
    "New Mexico": ["Santa Fe", "Albuquerque", "Las Cruces", "Rio Rancho", "Roswell", "Farmington"],
    "New York": ["Albany", "New York City", "New York", "Buffalo", "Rochester", "Yonkers", 
                 "Syracuse", "Brooklyn", "Manhattan", "Queens", "Bronx", "Staten Island", "Perth"],
    "North Carolina": ["Raleigh", "Charlotte", "Greensboro", "Durham", "Winston-Salem", "Fayetteville", 
                       "Cary", "Wilmington", "High Point", "Asheville"],
    "North Dakota": ["Bismarck", "Fargo", "Grand Forks", "Minot", "West Fargo", "Williston", 
                     "Medora", "Bottineau", "Theodore Roosevelt National Park"],
    "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma", 
             "Canton", "Youngstown", "Lorain"],
    "Oklahoma": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond", "Lawton", "Moore"],
    "Oregon": ["Salem", "Portland", "Eugene", "Gresham", "Hillsboro", "Beaverton", "Bend", 
               "Medford", "Springfield"],
    "Pennsylvania": ["Harrisburg", "Philadelphia", "Pittsburgh", "Allentown", "Reading", "Scranton", 
                     "Bethlehem", "Lancaster", "Erie"],
    "Rhode Island": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence", 
                     "Woonsocket", "Newport", "Coventry"],
    "South Carolina": ["Columbia", "Charleston", "North Charleston", "Mount Pleasant", "Rock Hill", 
                       "Greenville", "Summerville", "Myrtle Beach", "Edisto Island"],
    "South Dakota": ["Pierre", "Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown"],
    "Tennessee": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro", 
                  "Jackson", "Franklin"],
    "Texas": ["Austin", "Houston", "San Antonio", "Dallas", "Fort Worth", "El Paso", "Arlington", 
              "Corpus Christi", "Plano", "Laredo", "Lubbock", "Garland", "Irving", "Amarillo", 
              "Grand Prairie", "McKinney", "Frisco", "Brownsville", "Pasadena", "Killeen", 
              "McAllen", "Mesquite", "Midland", "Denton", "Waco", "Beaumont", "Tyler", "Odessa", 
              "Round Rock", "Abilene", "College Station"],
    "Utah": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem", "Sandy", 
             "Ogden", "St. George", "Layton", "Tooele"],
    "Vermont": ["Montpelier", "Burlington", "South Burlington", "Rutland", "Essex Junction", 
                "Bennington", "Shelburne"],
    "Virginia": ["Richmond", "Virginia Beach", "Norfolk", "Chesapeake", "Arlington", "Newport News", 
                 "Alexandria", "Hampton", "Roanoke", "Portsmouth", "Suffolk", "Lynchburg", 
                 "Charlottesville", "Hampton Roads"],
    "Washington": ["Olympia", "Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent", 
                   "Everett", "Renton", "Federal Way", "Yakima"],
    "West Virginia": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling", 
                      "Weirton", "Fairmont", "Beckley", "Martinsburg", "Keyser", "Putnam County", 
                      "St. Albans"],
    "Wisconsin": ["Madison", "Milwaukee", "Green Bay", "Kenosha", "Racine", "Appleton", "Waukesha", 
                  "Oshkosh", "Eau Claire", "Janesville"],
    "Wyoming": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan", "Green River"],
}

# State capitals for quick lookup
US_CAPITALS: Dict[str, str] = {
    "Alabama": "Montgomery", "Alaska": "Juneau", "Arizona": "Phoenix",
    "Arkansas": "Little Rock", "California": "Sacramento", "Colorado": "Denver",
    "Connecticut": "Hartford", "Delaware": "Dover", "Florida": "Tallahassee",
    "Georgia": "Atlanta", "Hawaii": "Honolulu", "Idaho": "Boise",
    "Illinois": "Springfield", "Indiana": "Indianapolis", "Iowa": "Des Moines",
    "Kansas": "Topeka", "Kentucky": "Frankfort", "Louisiana": "Baton Rouge",
    "Maine": "Augusta", "Maryland": "Annapolis", "Massachusetts": "Boston",
    "Michigan": "Lansing", "Minnesota": "Saint Paul", "Mississippi": "Jackson",
    "Missouri": "Jefferson City", "Montana": "Helena", "Nebraska": "Lincoln",
    "Nevada": "Carson City", "New Hampshire": "Concord", "New Jersey": "Trenton",
    "New Mexico": "Santa Fe", "New York": "Albany", "North Carolina": "Raleigh",
    "North Dakota": "Bismarck", "Ohio": "Columbus", "Oklahoma": "Oklahoma City",
    "Oregon": "Salem", "Pennsylvania": "Harrisburg", "Rhode Island": "Providence",
    "South Carolina": "Columbia", "South Dakota": "Pierre", "Tennessee": "Nashville",
    "Texas": "Austin", "Utah": "Salt Lake City", "Vermont": "Montpelier",
    "Virginia": "Richmond", "Washington": "Olympia", "West Virginia": "Charleston",
    "Wisconsin": "Madison", "Wyoming": "Cheyenne",
}

# Cities that exist in multiple states - require context disambiguation
AMBIGUOUS_CITIES: Dict[str, List[str]] = {
    "portland": ["Oregon", "Maine"],
    "augusta": ["Georgia", "Maine"],
    "charleston": ["South Carolina", "West Virginia", "Kentucky"],
    "columbia": ["South Carolina", "Missouri", "South Dakota"],
    "columbus": ["Ohio", "Georgia", "North Dakota"],
    "jackson": ["Mississippi", "Tennessee"],
    "springfield": ["Illinois", "Missouri", "Massachusetts", "Oregon"],
    "rochester": ["New York", "Minnesota", "New Hampshire"],
    "salem": ["Oregon", "Massachusetts", "Arkansas"],
    "richmond": ["Virginia", "California"],
    "albany": ["New York", "Georgia"],
    "buffalo": ["New York", "Tennessee", "Kentucky", "Ohio"],
    "norfolk": ["Virginia", "Nebraska"],
    "alexandria": ["Virginia", "Louisiana"],
    "tacoma": ["Washington"],
    "fort worth": ["Texas"],
    "fort wayne": ["Indiana"],
    "shelburne": ["Vermont", "New Hampshire"],
    "medora": ["North Dakota", "Montana"],
    "jacksonville": ["Florida", "Alabama"],
    "birmingham": ["Alabama"],  # Also UK city
    "lexington": ["Kentucky", "Arkansas"],
    "coventry": ["Rhode Island"],  # Also UK city
    "keyser": ["West Virginia", "Florida"],  # WV city + Keiser University FL
    "keiser": ["Florida", "West Virginia"],  # Keiser University FL + WV city variant
    "springs": ["Colorado"],  # Often refers to Colorado Springs
    "borough": ["Alaska"],  # Alaska uses boroughs as administrative divisions
}

# US Counties - geographic entities from annotations
US_COUNTIES: Dict[str, List[str]] = {
    "Alabama": ["Lee County", "Russell County"],
    "Alaska": [],  # Alaska uses boroughs instead
    "Arkansas": ["Woodruff County", "Stone County"],
    "California": [],
    "Connecticut": ["Middlesex County"],
    "Idaho": ["Bannock County"],
    "Kentucky": ["Fayette County", "LaRue County", "Hopkins County"],
    "Louisiana": ["Jefferson Parish"],  # Louisiana uses parishes
    "Montana": ["Gallatin County"],
    "New York": ["Fulton County"],
    "North Dakota": ["Billings County", "Bottineau County", "Burke County"],
    "Ohio": ["Guernsey County", "Jackson County"],
    "Rhode Island": ["Kent County"],
    "South Dakota": ["Brown County"],
    "Tennessee": ["Montgomery County"],
    "Utah": ["Tooele County"],
    "Vermont": ["Chittenden County"],
    "West Virginia": ["Putnam County", "Kanawha County"],
}

# Alaska Boroughs (equivalent to counties)
ALASKA_BOROUGHS: List[str] = [
    "Anchorage", "Fairbanks North Star", "Juneau", "Kenai Peninsula",
    "Matanuska-Susitna", "Kodiak Island", "Sitka", "Ketchikan Gateway",
    "North Slope", "Northwest Arctic", "Bethel", "Nome",
]

# US Regions and Geographic Areas
US_REGIONS: Dict[str, List[str]] = {
    "Virginia": ["Hampton Roads", "Northern Virginia", "Tidewater"],
    "California": ["Silicon Valley", "Bay Area", "San Joaquin Valley", "Central Valley"],
    "Montana": ["Hi-Line"],
    "Florida": ["Florida Keys", "Panhandle", "Space Coast", "Treasure Coast"],
    "New York": ["Long Island", "Hudson Valley", "Finger Lakes"],
    "South Carolina": ["Sea Islands", "Lowcountry", "Upstate"],
    "Maine": ["Gulf of Maine"],
    "Multi-state": ["Piedmont", "Appalachia", "Great Plains", "Midwest"],
}

# US National Parks and Landmarks
US_LANDMARKS: Dict[str, List[str]] = {
    "North Dakota": ["Theodore Roosevelt National Park"],
    "Florida": ["Everglades National Park", "Everglades"],
    "Wyoming": ["Yellowstone", "Grand Teton"],
    "Arizona": ["Grand Canyon"],
    "California": ["Yosemite", "Death Valley"],
    "Colorado": ["Pikes Peak", "Rocky Mountain National Park"],
    "Montana": ["Glacier National Park"],
    "Utah": ["Zion", "Bryce Canyon", "Arches"],
    "South Dakota": ["Mount Rushmore", "Badlands"],
}

# US Islands
US_ISLANDS: Dict[str, List[str]] = {
    "South Carolina": ["Edisto Island", "Hilton Head Island", "Kiawah Island"],
    "Florida": ["Key West", "Key Largo", "Sanibel Island"],
    "Hawaii": ["Maui", "Oahu", "Big Island", "Kauai"],
    "New York": ["Staten Island", "Long Island", "Manhattan"],
    "Rhode Island": ["Block Island", "Aquidneck Island"],
    "Massachusetts": ["Martha's Vineyard", "Nantucket", "Cape Cod"],
}

# Townships (primarily NJ, PA, MI, OH)
US_TOWNSHIPS: Dict[str, List[str]] = {
    "New Jersey": ["Toms River", "Woodbridge", "Edison", "Hamilton"],
    "Pennsylvania": ["Upper Darby", "Lower Merion", "Abington"],
    "Michigan": ["Clinton", "Canton", "Plymouth"],
    "Ohio": ["Liberty", "Green", "Jackson"],
}

# Foreign places that should NOT match as US cities
FOREIGN_PLACES: Set[str] = {
    "liverpool", "london", "manchester",  # UK
    "perth", "sydney", "melbourne",  # Australia
    "winnipeg",  # Canada (but Vancouver WA is valid)
    "paris",  # France (but Paris TX exists)
    "coventry",  # UK (but Coventry RI exists - handled in ambiguous)
}

# Build county reverse lookup: county -> state
_COUNTY_TO_STATE: Dict[str, str] = {}
for state, counties in US_COUNTIES.items():
    for county in counties:
        _COUNTY_TO_STATE[county.lower()] = state

# Build region reverse lookup: region -> state
_REGION_TO_STATE: Dict[str, str] = {}
for state, regions in US_REGIONS.items():
    for region in regions:
        _REGION_TO_STATE[region.lower()] = state

# Build landmark reverse lookup: landmark -> state
_LANDMARK_TO_STATE: Dict[str, str] = {}
for state, landmarks in US_LANDMARKS.items():
    for landmark in landmarks:
        _LANDMARK_TO_STATE[landmark.lower()] = state

# Build island reverse lookup: island -> state
_ISLAND_TO_STATE: Dict[str, str] = {}
for state, islands in US_ISLANDS.items():
    for island in islands:
        _ISLAND_TO_STATE[island.lower()] = state

# Build reverse lookup: city -> state(s)
_CITY_TO_STATES: Dict[str, List[str]] = {}
for state, cities in US_CITIES.items():
    for city in cities:
        city_lower = city.lower()
        if city_lower not in _CITY_TO_STATES:
            _CITY_TO_STATES[city_lower] = []
        _CITY_TO_STATES[city_lower].append(state)

# All state names for detection
_STATE_NAMES: Set[str] = set(US_CITIES.keys())
_STATE_NAMES_LOWER: Set[str] = {s.lower() for s in _STATE_NAMES}


# ============================================================================
# Detection Functions
# ============================================================================

def find_cities_in_text(text: str) -> List[Tuple[str, List[str]]]:
    """
    Find US cities mentioned in text.
    
    Returns list of (city_name, [states]) tuples.
    Cities that exist in multiple states will have multiple states listed.
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for city_lower, states in _CITY_TO_STATES.items():
        pattern = r'\b' + re.escape(city_lower) + r'\b'
        if re.search(pattern, text_lower):
            original_city = US_CITIES[states[0]][
                [c.lower() for c in US_CITIES[states[0]]].index(city_lower)
            ]
            found.append((original_city, states))
    
    return found


def find_counties_in_text(text: str) -> List[Tuple[str, str]]:
    """
    Find US counties/parishes mentioned in text.
    
    Returns list of (county_name, state) tuples.
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for county_lower, state in _COUNTY_TO_STATE.items():
        pattern = r'\b' + re.escape(county_lower) + r'\b'
        if re.search(pattern, text_lower):
            # Get original case
            for orig_county in US_COUNTIES.get(state, []):
                if orig_county.lower() == county_lower:
                    found.append((orig_county, state))
                    break
    
    # Also check for generic "County" pattern: "X County"
    county_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+County\b'
    for match in re.finditer(county_pattern, text):
        county_name = match.group(1) + " County"
        if county_name.lower() not in [c[0].lower() for c in found]:
            # Try to find which state this county is in
            for state, counties in US_COUNTIES.items():
                if county_name in counties:
                    found.append((county_name, state))
                    break
    
    return found


def find_regions_in_text(text: str) -> List[Tuple[str, str]]:
    """
    Find US geographic regions mentioned in text.
    
    Returns list of (region_name, state) tuples.
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for region_lower, state in _REGION_TO_STATE.items():
        pattern = r'\b' + re.escape(region_lower) + r'\b'
        if re.search(pattern, text_lower):
            for orig_region in US_REGIONS.get(state, []):
                if orig_region.lower() == region_lower:
                    found.append((orig_region, state))
                    break
    
    return found


def find_landmarks_in_text(text: str) -> List[Tuple[str, str]]:
    """
    Find US landmarks (national parks, etc.) mentioned in text.
    
    Returns list of (landmark_name, state) tuples.
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for landmark_lower, state in _LANDMARK_TO_STATE.items():
        pattern = r'\b' + re.escape(landmark_lower) + r'\b'
        if re.search(pattern, text_lower):
            for orig_landmark in US_LANDMARKS.get(state, []):
                if orig_landmark.lower() == landmark_lower:
                    found.append((orig_landmark, state))
                    break
    
    return found


def find_islands_in_text(text: str) -> List[Tuple[str, str]]:
    """
    Find US islands mentioned in text.
    
    Returns list of (island_name, state) tuples.
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for island_lower, state in _ISLAND_TO_STATE.items():
        pattern = r'\b' + re.escape(island_lower) + r'\b'
        if re.search(pattern, text_lower):
            for orig_island in US_ISLANDS.get(state, []):
                if orig_island.lower() == island_lower:
                    found.append((orig_island, state))
                    break
    
    return found


def find_all_places_in_text(text: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Find all geographic entities in text.
    
    Returns dict with keys: cities, counties, regions, landmarks, islands.
    Each value is a list of (name, state) tuples.
    """
    cities = find_cities_in_text(text)
    # Convert cities to (name, state) format - use first state for multi-state cities
    cities_flat = [(c[0], c[1][0]) for c in cities]
    
    return {
        'cities': cities_flat,
        'counties': find_counties_in_text(text),
        'regions': find_regions_in_text(text),
        'landmarks': find_landmarks_in_text(text),
        'islands': find_islands_in_text(text),
    }


def find_states_in_text(text: str) -> List[str]:
    """Find US state names mentioned in text."""
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for state in _STATE_NAMES:
        pattern = r'\b' + re.escape(state.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found.append(state)
    
    return found


def check_alaska_borough(text: str) -> bool:
    """Check if text mentions Alaska borough terminology."""
    text_lower = text.lower()
    if 'borough' in text_lower:
        # Check for Alaska context
        if 'alaska' in text_lower or any(b.lower() in text_lower for b in ALASKA_BOROUGHS):
            return True
    return False


def detect_ambiguous_cities(cities_found: List[Tuple[str, List[str]]]) -> List[str]:
    """Identify cities that exist in multiple states."""
    ambiguous = []
    for city, states in cities_found:
        if len(states) > 1 or city.lower() in AMBIGUOUS_CITIES:
            ambiguous.append(city)
    return ambiguous


def disambiguate_city(
    city: str, 
    text: str, 
    source_state: str, 
    target_state: str
) -> Optional[str]:
    """
    Try to disambiguate an ambiguous city based on context.
    
    Returns the most likely state, or None if still ambiguous.
    """
    city_lower = city.lower()
    text_lower = text.lower()
    
    # Check if a specific state is mentioned in context
    states_in_text = find_states_in_text(text)
    
    possible_states = AMBIGUOUS_CITIES.get(city_lower, _CITY_TO_STATES.get(city_lower, []))
    
    # Priority: if target state is mentioned and city could be there, prefer target
    if target_state in possible_states and target_state in states_in_text:
        return target_state
    
    # If only one of the possible states is mentioned, use that
    mentioned = [s for s in possible_states if s in states_in_text]
    if len(mentioned) == 1:
        return mentioned[0]
    
    # Check for ", State" pattern after city name
    for state in possible_states:
        pattern = rf'\b{re.escape(city_lower)}\s*,\s*{re.escape(state.lower())}'
        if re.search(pattern, text_lower):
            return state
    
    return None


def is_nonsense_output(text: str) -> bool:
    """Check if output is garbled/nonsense (code tokens, non-English, etc.)"""
    if not text:
        return True
    
    nonsense_patterns = [
        r'ValueStyle', r'StatefulWidget', r'AddTagHelper', r'Normdatei',
        r'[А-Яа-яЁё]{3,}',  # Cyrillic
        r'[\u4e00-\u9fff]{2,}',  # Chinese
        r'<[a-zA-Z]+>',  # HTML-like tags
        r'\{\{.*\}\}',  # Template syntax
    ]
    
    for pattern in nonsense_patterns:
        if re.search(pattern, text):
            return True
    
    return False


def is_foreign_place(text: str) -> bool:
    """Check if text contains references to foreign places."""
    text_lower = text.lower()
    
    # Check for explicit foreign country mentions
    foreign_patterns = [
        r'\b(england|uk|united kingdom|britain)\b',
        r'\b(australia|australian)\b',
        r'\b(canada|canadian)\b',
        r'\b(france|french)\b',
    ]
    
    for pattern in foreign_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False


# ============================================================================
# Classification Functions
# ============================================================================

def classify_swap(
    steered_output: str,
    source_state: str,
    source_capital: str,
    target_state: str,
    target_capital: str,
    prompt_city: Optional[str] = None,
) -> ClassificationResult:
    """
    Classify a swap result into a success tier using rule-based logic.
    
    Returns ClassificationResult with confidence score.
    Now checks cities, counties, regions, landmarks, and islands.
    """
    cities_found = find_cities_in_text(steered_output)
    states_found = find_states_in_text(steered_output)
    ambiguous = detect_ambiguous_cities(cities_found)
    
    # Also find other geographic entities
    counties_found = find_counties_in_text(steered_output)
    regions_found = find_regions_in_text(steered_output)
    landmarks_found = find_landmarks_in_text(steered_output)
    islands_found = find_islands_in_text(steered_output)
    
    # Combine all place names for reporting
    city_names = [c[0] for c in cities_found]
    all_places = city_names + [c[0] for c in counties_found] + [r[0] for r in regions_found] + \
                 [l[0] for l in landmarks_found] + [i[0] for i in islands_found]
    
    # Base confidence - reduced if ambiguous cities present
    confidence = 1.0 if not ambiguous else 0.6
    
    # Check for Alaska borough reference
    if check_alaska_borough(steered_output):
        if target_state == "Alaska":
            return ClassificationResult(
                tier=SwapTier.TARGET_STATE_ONLY,
                cities_found=all_places,
                states_found=states_found,
                notes="Alaska borough reference detected",
                method=ClassificationMethod.RULE_HIGH,
                confidence=0.85,
                ambiguous_cities=ambiguous,
            )
    
    def has_city_in_state(state: str, exclude_prompt: bool = False) -> Optional[str]:
        for city, city_states in cities_found:
            if state in city_states:
                if exclude_prompt and prompt_city and city.lower() == prompt_city.lower():
                    continue
                return city
        return None
    
    def has_county_in_state(state: str) -> Optional[str]:
        for county, county_state in counties_found:
            if county_state == state:
                return county
        return None
    
    def has_region_in_state(state: str) -> Optional[str]:
        for region, region_state in regions_found:
            if region_state == state:
                return region
        return None
    
    def has_landmark_in_state(state: str) -> Optional[str]:
        for landmark, landmark_state in landmarks_found:
            if landmark_state == state:
                return landmark
        return None
    
    def has_island_in_state(state: str) -> Optional[str]:
        for island, island_state in islands_found:
            if island_state == state:
                return island
        return None
    
    def has_any_place_in_state(state: str, exclude_prompt: bool = False) -> Optional[Tuple[str, str]]:
        """Check for any geographic entity in the given state. Returns (name, type)."""
        city = has_city_in_state(state, exclude_prompt)
        if city:
            return (city, "city")
        county = has_county_in_state(state)
        if county:
            return (county, "county")
        region = has_region_in_state(state)
        if region:
            return (region, "region")
        landmark = has_landmark_in_state(state)
        if landmark:
            return (landmark, "landmark")
        island = has_island_in_state(state)
        if island:
            return (island, "island")
        return None
    
    # Check for target capital (PERFECT)
    if target_capital.lower() in steered_output.lower():
        return ClassificationResult(
            tier=SwapTier.PERFECT,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Target capital '{target_capital}' found",
            method=ClassificationMethod.RULE_HIGH,
            confidence=1.0,
            ambiguous_cities=ambiguous,
        )
    
    # Check for other city in target state (TARGET_STATE_CITY)
    target_city = has_city_in_state(target_state)
    if target_city:
        # Check if it's ambiguous
        if target_city.lower() in AMBIGUOUS_CITIES:
            disambig = disambiguate_city(target_city, steered_output, source_state, target_state)
            if disambig == target_state:
                confidence = 0.8
            else:
                confidence = 0.5  # Still ambiguous
        
        return ClassificationResult(
            tier=SwapTier.TARGET_STATE_CITY,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Found '{target_city}' in {target_state}",
            method=ClassificationMethod.RULE_HIGH if confidence > 0.7 else ClassificationMethod.RULE_LOW,
            confidence=confidence,
            ambiguous_cities=ambiguous,
        )
    
    # Check for county/region/landmark/island in target state (TARGET_STATE_CITY equivalent)
    target_place = has_any_place_in_state(target_state)
    if target_place:
        place_name, place_type = target_place
        return ClassificationResult(
            tier=SwapTier.TARGET_STATE_CITY,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Found {place_type} '{place_name}' in {target_state}",
            method=ClassificationMethod.RULE_HIGH,
            confidence=0.85,
            ambiguous_cities=ambiguous,
        )
    
    # Check if target state is mentioned (TARGET_STATE_ONLY)
    if target_state in states_found:
        return ClassificationResult(
            tier=SwapTier.TARGET_STATE_ONLY,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Target state '{target_state}' mentioned, no city found",
            method=ClassificationMethod.RULE_HIGH,
            confidence=0.9,
            ambiguous_cities=ambiguous,
        )
    
    # Check if source capital appears (SOURCE_PERSISTS)
    if source_capital.lower() in steered_output.lower():
        return ClassificationResult(
            tier=SwapTier.SOURCE_PERSISTS,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Source capital '{source_capital}' persists",
            method=ClassificationMethod.RULE_HIGH,
            confidence=1.0,
            ambiguous_cities=ambiguous,
        )
    
    # Check for source cities (excluding prompt city)
    source_city = has_city_in_state(source_state, exclude_prompt=True)
    if source_city:
        return ClassificationResult(
            tier=SwapTier.SOURCE_PERSISTS,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Found '{source_city}' from source state",
            method=ClassificationMethod.RULE_HIGH,
            confidence=0.9,
            ambiguous_cities=ambiguous,
        )
    
    # Check for source county/region/landmark (SOURCE_PERSISTS)
    source_place = has_any_place_in_state(source_state, exclude_prompt=True)
    if source_place:
        place_name, place_type = source_place
        return ClassificationResult(
            tier=SwapTier.SOURCE_PERSISTS,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Found {place_type} '{place_name}' from source state",
            method=ClassificationMethod.RULE_HIGH,
            confidence=0.85,
            ambiguous_cities=ambiguous,
        )
    
    # Check for cities in third states (WRONG_STATE)
    third_state_places = []
    for city, city_states in cities_found:
        if prompt_city and city.lower() == prompt_city.lower():
            continue
        for s in city_states:
            if s != source_state and s != target_state:
                # Try disambiguation first
                if city.lower() in AMBIGUOUS_CITIES:
                    disambig = disambiguate_city(city, steered_output, source_state, target_state)
                    if disambig == target_state:
                        # Actually a target state city
                        return ClassificationResult(
                            tier=SwapTier.TARGET_STATE_CITY,
                            cities_found=all_places,
                            states_found=states_found,
                            notes=f"Found '{city}' (disambiguated to {target_state})",
                            method=ClassificationMethod.RULE_LOW,
                            confidence=0.6,
                            ambiguous_cities=ambiguous,
                        )
                third_state_places.append((city, s, "city"))
    
    # Also check counties, regions, landmarks, islands in third states
    for county, county_state in counties_found:
        if county_state != source_state and county_state != target_state:
            third_state_places.append((county, county_state, "county"))
    for region, region_state in regions_found:
        if region_state not in ("Multi-state", source_state, target_state):
            third_state_places.append((region, region_state, "region"))
    for landmark, landmark_state in landmarks_found:
        if landmark_state != source_state and landmark_state != target_state:
            third_state_places.append((landmark, landmark_state, "landmark"))
    for island, island_state in islands_found:
        if island_state != source_state and island_state != target_state:
            third_state_places.append((island, island_state, "island"))
    
    if third_state_places:
        place_name, state, place_type = third_state_places[0]
        # Lower confidence if city is ambiguous
        conf = 0.5 if place_name.lower() in AMBIGUOUS_CITIES else 0.9
        return ClassificationResult(
            tier=SwapTier.WRONG_STATE,
            cities_found=all_places,
            states_found=states_found,
            notes=f"Found {place_type} '{place_name}' in {state} (third state)",
            method=ClassificationMethod.RULE_LOW if conf < 0.7 else ClassificationMethod.RULE_HIGH,
            confidence=conf,
            ambiguous_cities=ambiguous,
        )
    
    # Check for foreign place references
    if is_foreign_place(steered_output):
        return ClassificationResult(
            tier=SwapTier.WRONG_STATE,
            cities_found=all_places,
            states_found=states_found,
            notes="Foreign place reference detected",
            method=ClassificationMethod.RULE_HIGH,
            confidence=0.8,
            ambiguous_cities=ambiguous,
        )
    
    # Check for nonsense
    if is_nonsense_output(steered_output):
        return ClassificationResult(
            tier=SwapTier.SUPPRESSED_ONLY,
            cities_found=all_places,
            states_found=states_found,
            notes="Garbled/nonsense output",
            method=ClassificationMethod.RULE_HIGH,
            confidence=0.9,
            ambiguous_cities=ambiguous,
        )
    
    # Default: source suppressed but no clear redirect
    return ClassificationResult(
        tier=SwapTier.SUPPRESSED_ONLY,
        cities_found=all_places,
        states_found=states_found,
        notes="No geographic content detected",
        method=ClassificationMethod.RULE_HIGH,
        confidence=0.7,
        ambiguous_cities=ambiguous,
    )


def classify_swap_result(
    result: Dict[str, Any], 
    use_llm: bool = False,
    llm_threshold: float = 0.7,
    honor_manual: bool = True,
) -> ClassificationResult:
    """
    Classify a swap result dict with hybrid approach.
    
    Args:
        result: Swap result dict with 'source', 'target', 'evaluation', 'classification' keys
        use_llm: If True, use LLM for uncertain cases
        llm_threshold: Confidence threshold below which to use LLM
        honor_manual: If True, respect existing manual annotations
    
    Returns:
        ClassificationResult
    """
    # Priority 1: Check for manual override
    if honor_manual:
        classification = result.get('classification', {})
        if classification.get('manually_edited'):
            tier_val = classification.get('tier')
            if tier_val is not None:
                # Handle tier 2.5 (stored as float)
                if isinstance(tier_val, float):
                    tier_val = int(tier_val)  # Round down for 2.5 -> 2
                return ClassificationResult(
                    tier=SwapTier(tier_val),
                    cities_found=classification.get('cities_found', []),
                    states_found=classification.get('states_found', []),
                    notes=classification.get('notes', 'Manual annotation'),
                    method=ClassificationMethod.MANUAL,
                    confidence=1.0,
                    ambiguous_cities=[],
                )
    
    # Priority 2: Rule-based classification
    steered_output = result.get('evaluation', {}).get('raw', {}).get('steered_output', '')
    source = result.get('source', {})
    target = result.get('target', {})
    prompt_city = source.get('city', '')
    
    rule_result = classify_swap(
        steered_output=steered_output,
        source_state=source.get('state', ''),
        source_capital=source.get('capital', ''),
        target_state=target.get('state', ''),
        target_capital=target.get('capital', ''),
        prompt_city=prompt_city,
    )
    
    # Priority 3: If confidence is low and LLM is enabled, use LLM
    if use_llm and rule_result.confidence < llm_threshold:
        try:
            llm_result = classify_swap_with_llm(
                steered_output=steered_output,
                source_state=source.get('state', ''),
                source_capital=source.get('capital', ''),
                target_state=target.get('state', ''),
                target_capital=target.get('capital', ''),
            )
            return llm_result
        except Exception:
            # Fallback to the existing rule-based note without exposing raw API errors.
            pass
    
    return rule_result


# ============================================================================
# LLM-based Classification
# ============================================================================

LLM_CLASSIFICATION_PROMPT = """Classify this language model steering experiment output.

**Source:** {source_state} (capital: {source_capital})
**Target:** {target_state} (capital: {target_capital})

**Output:**
"{steered_output}"

Tiers:
5=PERFECT: Target capital ({target_capital}) appears
4=TARGET_STATE_CITY: City/place in {target_state} (not capital)
3=TARGET_STATE_ONLY: {target_state} mentioned, no specific city
2=SUPPRESSED_ONLY: Garbled/nonsense/no geographic content
1=SOURCE_PERSISTS: {source_state} cities/places persist
0=WRONG_STATE: Third state cities/places appear

Consider cities, parks, landmarks, counties. Disambiguate cities that exist in multiple states.

JSON only (no markdown): {{"tier": 0-5, "places": ["place1"], "notes": "reason"}}"""

# LLM response cache to avoid duplicate API calls
_LLM_CACHE: Dict[str, ClassificationResult] = {}
_LLM_CACHE_FILE: Optional[Path] = None


def _cache_key(steered_output: str, source_state: str, target_state: str) -> str:
    """Generate cache key for LLM results."""
    content = f"{steered_output[:200]}|{source_state}|{target_state}"
    return hashlib.md5(content.encode()).hexdigest()


def classify_swap_with_llm(
    steered_output: str,
    source_state: str,
    source_capital: str,
    target_state: str,
    target_capital: str,
    model: str = "gpt-4o-mini",
) -> ClassificationResult:
    """
    Classify a swap result using an LLM with caching.
    """
    # Check cache first
    cache_key = _cache_key(steered_output, source_state, target_state)
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]
    
    try:
        import openai
    except ImportError:
        raise ImportError("openai package required. Install with: pip install openai")
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable required")
    
    client = openai.OpenAI(api_key=api_key)
    
    prompt = LLM_CLASSIFICATION_PROMPT.format(
        source_state=source_state,
        source_capital=source_capital,
        target_state=target_state,
        target_capital=target_capital,
        steered_output=steered_output[:500],
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        
        result = ClassificationResult(
            tier=SwapTier(data.get('tier', 2)),
            cities_found=data.get('places', []),
            states_found=[],
            notes=data.get('notes', 'LLM classification'),
            method=ClassificationMethod.LLM,
            confidence=0.85,
            ambiguous_cities=[],
        )
        
        _LLM_CACHE[cache_key] = result
        return result
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Fallback to rule-based
        return classify_swap(
            steered_output=steered_output,
            source_state=source_state,
            source_capital=source_capital,
            target_state=target_state,
            target_capital=target_capital,
        )


def classify_batch_with_llm(
    results: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    show_progress: bool = True,
    honor_manual: bool = True,
) -> List[ClassificationResult]:
    """
    Classify multiple swap results using hybrid approach.
    
    Manual annotations are always honored.
    Rule-based classification is used for high-confidence cases.
    LLM is used for low-confidence/ambiguous cases.
    """
    classifications = []
    total = len(results)
    llm_count = 0
    manual_count = 0
    
    for i, result in enumerate(results):
        if show_progress and (i + 1) % 50 == 0:
            print(f"  Classified {i + 1}/{total} (LLM: {llm_count}, Manual: {manual_count})")
        
        classification = classify_swap_result(
            result, 
            use_llm=True, 
            llm_threshold=0.7,
            honor_manual=honor_manual,
        )
        
        if classification.method == ClassificationMethod.LLM:
            llm_count += 1
        elif classification.method == ClassificationMethod.MANUAL:
            manual_count += 1
        
        classifications.append(classification)
    
    if show_progress:
        print(f"  Done: {total} total, {manual_count} manual, {llm_count} LLM")
    
    return classifications


# ============================================================================
# Utility Functions
# ============================================================================

def get_annotated_count(swaps_dir: Path) -> Dict[str, int]:
    """Count annotations in a swaps directory."""
    counts = {"total": 0, "manual": 0, "with_notes": 0}
    
    by_source = swaps_dir / "by_source"
    if not by_source.exists():
        return counts
    
    for source_dir in by_source.iterdir():
        if not source_dir.is_dir():
            continue
        for swap_file in source_dir.glob("to_*.json"):
            counts["total"] += 1
            try:
                with open(swap_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classification = data.get('classification', {})
                if classification.get('manually_edited'):
                    counts["manual"] += 1
                    if classification.get('notes', '').strip():
                        counts["with_notes"] += 1
            except (json.JSONDecodeError, IOError):
                pass
    
    return counts
