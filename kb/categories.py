"""
Document categories for the incident-response knowledge base.

Every document gets exactly one primary category:
  1. filename rules, in order (first match wins);
  2. otherwise a keyword score over the first pages of text;
  3. otherwise `other_rules`.
The rule that decided is recorded in the manifest, so every classification
can be checked and corrected by adding a filename rule.
"""

from __future__ import annotations

import re

CATEGORIES = (
    "law_and_acts",
    "cyber_incident_rules",
    "gpp_security",
    "gpp_architecture",
    "threat_frameworks",
    "data_protection",
    "spectrum_licensing_row",
    "trai_consultations",
    "other_rules",
)

# (category, filename regex) — checked in order; case-insensitive
FILENAME_RULES: list[tuple[str, str]] = [
    # Gazette downloads named by hash, identified from their text:
    #   53450e… DPDP Rules 2025 (G.S.R. 846(E)); 2bf1f0… DPDP Act 2023;
    #   3c7ebbae… corrigendum to G.S.R. 846(E); cc217843… Data Protection Board
    #   established (G.S.R. 844(E)); f6c08379… Board composition (G.S.R. 845(E))
    ("data_protection", r"^(53450e6e|2bf1f0e9|3c7ebbae|cc217843|f6c08379)"),
    #   c56ceae6… DPDP Act commencement notification (G.S.R. 843(E))
    ("law_and_acts", r"^c56ceae6"),
    #   092d793d… DoT 6G spectrum roadmap; CBuD… S.O. 1339(E) under the Right of Way Rules
    ("spectrum_licensing_row", r"^(092d793d|cbud cg-dl-e-21032025)"),
    #   G.S.R_20(E) (scanned; OCR) IT (CERT-In and Manner of Performing Functions
    #   and Duties) Rules, 2013
    ("cyber_incident_rules", r"^g\.s\.r_20\(e\)"),
    #   743514e6… NCCS research-associate recruitment notice
    ("other_rules", r"^743514e6"),
    # 3GPP / ETSI specifications: TS 33.xxx security, TS/TR 2x.xxx architecture
    ("gpp_security", r"^ts_133\d{3}"),
    ("gpp_architecture", r"^(ts_12[23]\d{3}|tr_121\d{3})"),
    # Incident / security rules
    ("cyber_incident_rules", r"cert-?in|cybersecurity-rules|telecom-cyber-security|critical telecommunication infrastructure|icdr-portal"),
    # Threat frameworks and international security guidance
    ("threat_frameworks", r"enisa|controls matrix|^nist\.ai|cloud security guide|^t-rec-y\.31|proof-of-concept|architect-guide|responsible-ai|principles-point-of-focus|^381137eng"),
    # Data protection
    ("data_protection", r"dpdp|privacy|personal.data"),
    # Acts and their commencement
    ("law_and_acts", r"telegraph_act|wireless_telegraphy_act|trai_act|trai_\(amendment\)|telecom-act-2023|^telecommunications_0101|enforcement of sections"),
    # Spectrum, licensing, right of way, equipment, infrastructure rules
    ("spectrum_licensing_row", r"right of way|right-of-way|row-rules|row rules|bharatnet|bharat nidhi|spectrum|ifmc|wireless|radio|amateur|licen[cs]e|mtcte|low-power|flight-and-maritime|telecommunications_(17092024|30082024)|migration-rules|captive-telecom|network-services-rules|principal-telecom|misc-telecom|rtr-rules"),
    # TRAI consultation material and press releases
    ("trai_consultations", r"^cp[_-]|consult|consul|cpaper|conpaper|conspap|pre-?consultation|draft|^pr_?no|press[-_ ]release|extension|recom|synopsis|^qos_|rating_manual|^ott-cp|^ucc_cp|^em_\d|^notice_|preconsultation"),
]

# Keyword fallback: (category, words). Scored over the first pages.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "law_and_acts": ("an act to", "be it enacted", "act, 2023", "act, 1885", "act, 1933", "act, 1997",
                     "appoints the", "shall come into force", "parliament"),
    "cyber_incident_rules": ("cyber security", "security incident", "cert-in", "incident reporting"),
    "gpp_security": ("3gpp ts 33", "security architecture"),
    "gpp_architecture": ("3gpp ts 23", "system architecture"),
    "threat_frameworks": ("threat landscape", "risk management framework", "enisa", "nist"),
    "data_protection": ("personal data", "data principal", "data fiduciary", "data protection"),
    "spectrum_licensing_row": ("spectrum", "right of way", "licence", "license", "frequency band", "6g"),
    "trai_consultations": ("consultation paper", "stakeholders", "comments", "telecom regulatory authority of india"),
}


def classify(filename: str, head_text: str) -> tuple[str, str]:
    """(category, rule that decided)."""
    name = filename.lower()
    for category, pattern in FILENAME_RULES:
        if re.search(pattern, name):
            return category, f"filename:{pattern}"
    text = " ".join(head_text.lower().split())
    scores = {c: sum(text.count(w) for w in words) for c, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best, f"keywords:{best}={scores[best]}"
    return "other_rules", "default"
