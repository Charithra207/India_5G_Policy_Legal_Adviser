"""
Regions and roles of sources (build-a-thon brief: gaps are examined for the
host country "and the expanded region with neighbouring countries", with
"relevant global policy examples").

A manifest entry may state `region` and `role` (src/rag/manifest.py); when
it does not, the region is derived from the jurisdiction.  International
material is always a reference point, never Indian law.
"""

from __future__ import annotations

REGIONS = ("india", "south_asia", "asia_pacific", "middle_east", "europe", "americas", "africa", "global")
ROLES = ("indian_law", "indian_policy", "indian_guidance", "standard", "global_example",
         "regional_example", "reference")

# India's neighbourhood (SAARC members plus Myanmar)
SOUTH_ASIA = ("Afghanistan", "Bangladesh", "Bhutan", "Maldives", "Myanmar", "Nepal", "Pakistan", "Sri Lanka")

_BY_JURISDICTION = {
    **{c.lower(): "south_asia" for c in SOUTH_ASIA},
    "india": "india",
    "european union": "europe", "eu": "europe", "united kingdom": "europe", "uk": "europe",
    "germany": "europe", "france": "europe",
    "singapore": "asia_pacific", "australia": "asia_pacific", "japan": "asia_pacific",
    "republic of korea": "asia_pacific", "south korea": "asia_pacific", "new zealand": "asia_pacific",
    "saudi arabia": "middle_east", "kingdom of saudi arabia": "middle_east", "ksa": "middle_east",
    "united arab emirates": "middle_east", "uae": "middle_east",
    "united states": "americas", "usa": "americas", "canada": "americas", "brazil": "americas",
    "south africa": "africa", "kenya": "africa", "nigeria": "africa",
    "international": "global",
}

_LABEL = {
    "south_asia": "Neighbouring-region example",
    "asia_pacific": "Global example",
    "middle_east": "Global example",
    "europe": "Global example",
    "americas": "Global example",
    "africa": "Global example",
    "global": "International reference",
}


def region_of(jurisdiction: str, region: str = "") -> str:
    """The stated region if valid, else the one implied by the jurisdiction ("global" if unknown)."""
    if region in REGIONS:
        return region
    j = (jurisdiction or "").strip().lower()
    if j in _BY_JURISDICTION:
        return _BY_JURISDICTION[j]
    for name, reg in _BY_JURISDICTION.items():           # e.g. "European Union (ENISA)"
        if len(name) > 3 and name in j:
            return reg
    return "global"


def comparator_tag(jurisdiction: str, region: str = "") -> str:
    """'[Global example — European Union]' / '[Neighbouring-region example — Sri Lanka]' ('' for India)."""
    reg = region_of(jurisdiction, region)
    if reg == "india":
        return ""
    where = (jurisdiction or "").strip() or "international"
    return f"[{_LABEL[reg]} — {where}]"
