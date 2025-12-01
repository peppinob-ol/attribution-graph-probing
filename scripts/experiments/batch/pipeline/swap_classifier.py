"""
Tiered classification for swap experiment results.

Classifies steering outcomes into success tiers based on geographic accuracy.
Uses embedded US cities database for fast offline classification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set, Tuple


class SwapTier(IntEnum):
    """Success tier for swap classification."""
    WRONG_STATE = 0      # City from unrelated third state
    SOURCE_PERSISTS = 1  # Source city/state still in output
    SUPPRESSED_ONLY = 2  # Source gone, but garbled/no geographic content
    TARGET_STATE_ONLY = 3  # Target state mentioned, no valid city
    TARGET_STATE_CITY = 4  # Other city in target state (not capital)
    PERFECT = 5          # Target capital appears


@dataclass
class ClassificationResult:
    """Result of swap classification."""
    tier: SwapTier
    cities_found: List[str]
    states_found: List[str]
    notes: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'tier': self.tier.value,
            'tier_name': self.tier.name,
            'cities_found': self.cities_found,
            'states_found': self.states_found,
            'notes': self.notes,
        }


# Embedded US cities database - major cities per state
# This covers capitals and major cities for classification
US_CITIES: Dict[str, List[str]] = {
    "Alabama": ["Montgomery", "Birmingham", "Huntsville", "Mobile", "Tuscaloosa"],
    "Alaska": ["Juneau", "Anchorage", "Fairbanks", "Sitka", "Ketchikan"],
    "Arizona": ["Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale", "Glendale", "Tempe", "Flagstaff"],
    "Arkansas": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro"],
    "California": ["Sacramento", "Los Angeles", "San Francisco", "San Diego", "San Jose", "Oakland", "Fresno", "Long Beach", "Bakersfield", "Anaheim", "Santa Ana", "Riverside", "Stockton", "Irvine", "Chula Vista", "Fremont", "Santa Clara", "Pasadena", "Berkeley", "Modesto"],
    "Colorado": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood", "Boulder", "Pueblo"],
    "Connecticut": ["Hartford", "Bridgeport", "New Haven", "Stamford", "Waterbury", "Norwalk"],
    "Delaware": ["Dover", "Wilmington", "Newark", "Middletown", "Smyrna"],
    "Florida": ["Tallahassee", "Miami", "Jacksonville", "Tampa", "Orlando", "St. Petersburg", "Hialeah", "Fort Lauderdale", "Port St. Lucie", "Cape Coral", "Pembroke Pines", "Hollywood", "Gainesville", "Coral Springs"],
    "Georgia": ["Atlanta", "Augusta", "Columbus", "Savannah", "Athens", "Macon", "Roswell", "Albany"],
    "Hawaii": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Pearl City", "Waipahu"],
    "Idaho": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Caldwell", "Twin Falls"],
    "Illinois": ["Springfield", "Chicago", "Aurora", "Naperville", "Joliet", "Rockford", "Elgin", "Peoria"],
    "Indiana": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", "Fishers", "Bloomington", "Gary"],
    "Iowa": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", "Waterloo", "Ames"],
    "Kansas": ["Topeka", "Wichita", "Overland Park", "Kansas City", "Olathe", "Lawrence", "Shawnee"],
    "Kentucky": ["Frankfort", "Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington"],
    "Louisiana": ["Baton Rouge", "New Orleans", "Shreveport", "Metairie", "Lafayette", "Lake Charles", "Kenner"],
    "Maine": ["Augusta", "Portland", "Lewiston", "Bangor", "South Portland", "Auburn"],
    "Maryland": ["Annapolis", "Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie", "Hagerstown"],
    "Massachusetts": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell", "Brockton", "New Bedford", "Quincy", "Lynn", "Fall River", "Salem"],
    "Michigan": ["Lansing", "Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", "Flint", "Dearborn", "Livonia", "Troy", "Kalamazoo"],
    "Minnesota": ["Saint Paul", "St. Paul", "Minneapolis", "Rochester", "Duluth", "Bloomington", "Brooklyn Park", "Plymouth"],
    "Mississippi": ["Jackson", "Gulfport", "Southaven", "Hattiesburg", "Biloxi", "Meridian", "Tupelo"],
    "Missouri": ["Jefferson City", "Kansas City", "St. Louis", "Springfield", "Columbia", "Independence", "Lee's Summit"],
    "Montana": ["Helena", "Billings", "Missoula", "Great Falls", "Bozeman", "Butte"],
    "Nebraska": ["Lincoln", "Omaha", "Bellevue", "Grand Island", "Kearney", "Fremont"],
    "Nevada": ["Carson City", "Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks", "Elko"],
    "New Hampshire": ["Concord", "Manchester", "Nashua", "Derry", "Dover", "Rochester"],
    "New Jersey": ["Trenton", "Newark", "Jersey City", "Paterson", "Elizabeth", "Edison", "Woodbridge", "Lakewood", "Toms River", "Hamilton", "Clifton", "Camden"],
    "New Mexico": ["Santa Fe", "Albuquerque", "Las Cruces", "Rio Rancho", "Roswell", "Farmington"],
    "New York": ["Albany", "New York City", "New York", "Buffalo", "Rochester", "Yonkers", "Syracuse", "Brooklyn", "Manhattan", "Queens", "Bronx", "Staten Island"],
    "North Carolina": ["Raleigh", "Charlotte", "Greensboro", "Durham", "Winston-Salem", "Fayetteville", "Cary", "Wilmington", "High Point", "Asheville"],
    "North Dakota": ["Bismarck", "Fargo", "Grand Forks", "Minot", "West Fargo", "Williston"],
    "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma", "Canton", "Youngstown", "Lorain"],
    "Oklahoma": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond", "Lawton", "Moore"],
    "Oregon": ["Salem", "Portland", "Eugene", "Gresham", "Hillsboro", "Beaverton", "Bend", "Medford", "Springfield"],
    "Pennsylvania": ["Harrisburg", "Philadelphia", "Pittsburgh", "Allentown", "Reading", "Scranton", "Bethlehem", "Lancaster", "Erie"],
    "Rhode Island": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence", "Woonsocket", "Newport"],
    "South Carolina": ["Columbia", "Charleston", "North Charleston", "Mount Pleasant", "Rock Hill", "Greenville", "Summerville", "Myrtle Beach"],
    "South Dakota": ["Pierre", "Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown"],
    "Tennessee": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro", "Jackson", "Franklin"],
    "Texas": ["Austin", "Houston", "San Antonio", "Dallas", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano", "Laredo", "Lubbock", "Garland", "Irving", "Amarillo", "Grand Prairie", "McKinney", "Frisco", "Brownsville", "Pasadena", "Killeen", "McAllen", "Mesquite", "Midland", "Denton", "Waco", "Beaumont", "Tyler", "Odessa", "Round Rock", "Abilene", "College Station"],
    "Utah": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem", "Sandy", "Ogden", "St. George", "Layton"],
    "Vermont": ["Montpelier", "Burlington", "South Burlington", "Rutland", "Essex Junction", "Bennington"],
    "Virginia": ["Richmond", "Virginia Beach", "Norfolk", "Chesapeake", "Arlington", "Newport News", "Alexandria", "Hampton", "Roanoke", "Portsmouth", "Suffolk", "Lynchburg", "Charlottesville"],
    "Washington": ["Olympia", "Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent", "Everett", "Renton", "Federal Way", "Yakima"],
    "West Virginia": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling", "Weirton", "Fairmont", "Beckley", "Martinsburg", "Keyser"],
    "Wisconsin": ["Madison", "Milwaukee", "Green Bay", "Kenosha", "Racine", "Appleton", "Waukesha", "Oshkosh", "Eau Claire", "Janesville"],
    "Wyoming": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan", "Green River"],
}

# State capitals for quick lookup
US_CAPITALS: Dict[str, str] = {
    "Alabama": "Montgomery",
    "Alaska": "Juneau",
    "Arizona": "Phoenix",
    "Arkansas": "Little Rock",
    "California": "Sacramento",
    "Colorado": "Denver",
    "Connecticut": "Hartford",
    "Delaware": "Dover",
    "Florida": "Tallahassee",
    "Georgia": "Atlanta",
    "Hawaii": "Honolulu",
    "Idaho": "Boise",
    "Illinois": "Springfield",
    "Indiana": "Indianapolis",
    "Iowa": "Des Moines",
    "Kansas": "Topeka",
    "Kentucky": "Frankfort",
    "Louisiana": "Baton Rouge",
    "Maine": "Augusta",
    "Maryland": "Annapolis",
    "Massachusetts": "Boston",
    "Michigan": "Lansing",
    "Minnesota": "Saint Paul",
    "Mississippi": "Jackson",
    "Missouri": "Jefferson City",
    "Montana": "Helena",
    "Nebraska": "Lincoln",
    "Nevada": "Carson City",
    "New Hampshire": "Concord",
    "New Jersey": "Trenton",
    "New Mexico": "Santa Fe",
    "New York": "Albany",
    "North Carolina": "Raleigh",
    "North Dakota": "Bismarck",
    "Ohio": "Columbus",
    "Oklahoma": "Oklahoma City",
    "Oregon": "Salem",
    "Pennsylvania": "Harrisburg",
    "Rhode Island": "Providence",
    "South Carolina": "Columbia",
    "South Dakota": "Pierre",
    "Tennessee": "Nashville",
    "Texas": "Austin",
    "Utah": "Salt Lake City",
    "Vermont": "Montpelier",
    "Virginia": "Richmond",
    "Washington": "Olympia",
    "West Virginia": "Charleston",
    "Wisconsin": "Madison",
    "Wyoming": "Cheyenne",
}

# Build reverse lookup: city -> state(s)
# Some cities exist in multiple states (e.g., "Portland" in OR and ME)
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
    
    # Check each known city
    for city_lower, states in _CITY_TO_STATES.items():
        # Use word boundary matching to avoid partial matches
        # e.g., "Austin" should not match "Augustine"
        pattern = r'\b' + re.escape(city_lower) + r'\b'
        if re.search(pattern, text_lower):
            # Get original case city name
            original_city = US_CITIES[states[0]][
                [c.lower() for c in US_CITIES[states[0]]].index(city_lower)
            ]
            found.append((original_city, states))
    
    return found


def find_states_in_text(text: str) -> List[str]:
    """
    Find US state names mentioned in text.
    
    Returns list of state names found.
    """
    if not text:
        return []
    
    found = []
    text_lower = text.lower()
    
    for state in _STATE_NAMES:
        pattern = r'\b' + re.escape(state.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found.append(state)
    
    return found


def is_nonsense_output(text: str) -> bool:
    """
    Check if output is garbled/nonsense (code tokens, non-English, etc.)
    """
    if not text:
        return True
    
    # Check for common nonsense patterns
    nonsense_patterns = [
        r'ValueStyle',
        r'StatefulWidget',
        r'AddTagHelper',
        r'Normdatei',
        r'[А-Яа-яЁё]{3,}',  # Cyrillic characters
        r'[\u4e00-\u9fff]{2,}',  # Chinese characters
    ]
    
    for pattern in nonsense_patterns:
        if re.search(pattern, text):
            return True
    
    return False


def classify_swap(
    steered_output: str,
    source_state: str,
    source_capital: str,
    target_state: str,
    target_capital: str,
) -> ClassificationResult:
    """
    Classify a swap result into a success tier.
    
    Args:
        steered_output: The steered model output text
        source_state: Source state name (e.g., "California")
        source_capital: Source capital (e.g., "Sacramento")
        target_state: Target state name (e.g., "Texas")
        target_capital: Target capital (e.g., "Austin")
    
    Returns:
        ClassificationResult with tier and details
    """
    cities_found = find_cities_in_text(steered_output)
    states_found = find_states_in_text(steered_output)
    
    city_names = [c[0] for c in cities_found]
    
    # Helper to check if any city is in a specific state
    def has_city_in_state(state: str) -> Optional[str]:
        for city, city_states in cities_found:
            if state in city_states:
                return city
        return None
    
    # Check for target capital (PERFECT)
    if target_capital.lower() in steered_output.lower():
        return ClassificationResult(
            tier=SwapTier.PERFECT,
            cities_found=city_names,
            states_found=states_found,
            notes=f"Target capital '{target_capital}' found in output",
        )
    
    # Check for other city in target state (TARGET_STATE_CITY)
    target_city = has_city_in_state(target_state)
    if target_city:
        return ClassificationResult(
            tier=SwapTier.TARGET_STATE_CITY,
            cities_found=city_names,
            states_found=states_found,
            notes=f"Found '{target_city}' which is in {target_state} (not capital)",
        )
    
    # Check if target state is mentioned (TARGET_STATE_ONLY)
    if target_state in states_found:
        return ClassificationResult(
            tier=SwapTier.TARGET_STATE_ONLY,
            cities_found=city_names,
            states_found=states_found,
            notes=f"Target state '{target_state}' mentioned but no valid city found",
        )
    
    # Check if source capital/city persists (SOURCE_PERSISTS)
    if source_capital.lower() in steered_output.lower():
        return ClassificationResult(
            tier=SwapTier.SOURCE_PERSISTS,
            cities_found=city_names,
            states_found=states_found,
            notes=f"Source capital '{source_capital}' still in output",
        )
    
    source_city = has_city_in_state(source_state)
    if source_city:
        return ClassificationResult(
            tier=SwapTier.SOURCE_PERSISTS,
            cities_found=city_names,
            states_found=states_found,
            notes=f"Found '{source_city}' which is still in source state {source_state}",
        )
    
    # Check for cities in third states (WRONG_STATE)
    third_state_cities = []
    for city, city_states in cities_found:
        for s in city_states:
            if s != source_state and s != target_state:
                third_state_cities.append((city, s))
    
    if third_state_cities:
        city, state = third_state_cities[0]
        return ClassificationResult(
            tier=SwapTier.WRONG_STATE,
            cities_found=city_names,
            states_found=states_found,
            notes=f"Found '{city}' which is in {state} (neither source nor target)",
        )
    
    # Check for nonsense (SUPPRESSED_ONLY)
    if is_nonsense_output(steered_output):
        return ClassificationResult(
            tier=SwapTier.SUPPRESSED_ONLY,
            cities_found=city_names,
            states_found=states_found,
            notes="Output contains nonsense/garbled tokens",
        )
    
    # Default: source suppressed but no clear redirect
    return ClassificationResult(
        tier=SwapTier.SUPPRESSED_ONLY,
        cities_found=city_names,
        states_found=states_found,
        notes="Source suppressed, no geographic content detected",
    )


def classify_swap_result(result: Dict[str, Any]) -> ClassificationResult:
    """
    Classify a swap result dict (from JSON file).
    
    Args:
        result: Swap result dict with 'source', 'target', 'evaluation' keys
    
    Returns:
        ClassificationResult
    """
    steered_output = result.get('evaluation', {}).get('raw', {}).get('steered_output', '')
    source = result.get('source', {})
    target = result.get('target', {})
    
    return classify_swap(
        steered_output=steered_output,
        source_state=source.get('state', ''),
        source_capital=source.get('capital', ''),
        target_state=target.get('state', ''),
        target_capital=target.get('capital', ''),
    )

