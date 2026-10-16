"""geo.py: the little geography the product needs: which state a coordinate falls in when
Google returned no address, and which timezone a lead's business hours are in. Countries
not listed here keep whatever state the data has and use the project's default timezone."""
from __future__ import annotations

COUNTRIES = {
    "AU": {
        # coarse boxes, territories first
        "boxes": [("ACT", -35.95, -35.10, 148.75, 149.45), ("TAS", -43.70, -39.50, 143.80, 148.60),
                  ("VIC", -39.20, -33.98, 140.95, 150.10), ("NSW", -37.55, -28.15, 140.95, 153.70),
                  ("QLD", -29.20, -10.00, 137.95, 153.60), ("SA", -38.10, -25.95, 129.00, 141.05),
                  ("NT", -26.05, -10.90, 129.00, 138.05), ("WA", -35.20, -13.60, 112.90, 129.05)],
        "tz": {"NSW": "Australia/Sydney", "VIC": "Australia/Melbourne", "ACT": "Australia/Sydney",
               "TAS": "Australia/Hobart", "QLD": "Australia/Brisbane", "SA": "Australia/Adelaide",
               "NT": "Australia/Darwin", "WA": "Australia/Perth"},
    },
}


def state_from_coords(country: str, lat, lng):
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return None
    for name, la0, la1, lo0, lo1 in COUNTRIES.get(country, {}).get("boxes", []):
        if la0 <= lat <= la1 and lo0 <= lng <= lo1:
            return name
    return None


def tz_for(country: str, state, default_tz: str) -> str:
    return COUNTRIES.get(country, {}).get("tz", {}).get(state, default_tz)
