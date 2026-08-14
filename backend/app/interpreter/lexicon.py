"""Music-domain lexicon for CUE's deterministic intent interpreter (M1).

This module is pure data plus the text normalisation that the matcher and the
lexicon keys must agree on. It is deliberately separate from ``rules.py`` so the
engine stays readable and the vocabulary can grow without touching logic.

Every categorical value emitted here must be a member of ``app.taxonomy``. The
engine re-validates anyway (and ``Intent.sanitized()`` is the final gate), but
``audit()`` below exists so a typo is caught in tests rather than silently
dropped.

Python 3.9 compatible: no ``X | Y`` annotations.
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from .. import taxonomy

# ---------------------------------------------------------------------------
# Normalisation -- shared by lexicon keys and incoming request text
# ---------------------------------------------------------------------------

# Codepoints that carry no lexical meaning for us: variation selectors, zero
# width joiner, skin-tone modifiers. Stripping them makes "❤️" == "❤".
_STRIP_CHARS = {
    "︎",
    "️",
    "‍",
    "​",
    "\U0001F3FB",
    "\U0001F3FC",
    "\U0001F3FD",
    "\U0001F3FE",
    "\U0001F3FF",
}

# Sentinel token emitted for clause boundaries. Never matches a lexicon key;
# used by the negation scoper to stop a "no ..." span at a clause break.
SEP = ","
_SEP_CHARS = ",;!?\n"

# Applied to the lowercased string before character filtering, so glued
# symbol forms survive as single tokens.
_PRE_REPLACEMENTS: List[Tuple[str, str]] = [
    ("r&b", " rnb "),
    ("r & b", " rnb "),
    ("r'n'b", " rnb "),
    ("rnb", " rnb "),
    ("hip-hop", " hip hop "),
    ("hip hop", " hip hop "),
    ("&", " and "),
    ("+", " and "),
]


def normalize(text: str) -> List[str]:
    """Lowercase, de-punctuate and tokenise, keeping emoji as their own tokens."""
    raw = (text or "").lower()
    for needle, replacement in _PRE_REPLACEMENTS:
        if needle in raw:
            raw = raw.replace(needle, replacement)

    out: List[str] = []
    for ch in raw:
        if ch in _STRIP_CHARS:
            continue
        if ch == "'" or ch == "’":
            continue  # don't -> dont, 90's -> 90s
        if ch.isalnum():
            out.append(ch)
        elif ch in _SEP_CHARS:
            out.append(" %s " % SEP)
        elif ord(ch) < 128:
            out.append(" ")
        else:
            # Emoji / non-ascii symbol: stand it up as its own token.
            out.append(" %s " % ch)
    return "".join(out).split()


def normalize_key(text: str) -> str:
    return " ".join(normalize(text))


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class Signal(NamedTuple):
    """What a matched surface form contributes to the intent."""

    languages: Tuple[str, ...] = ()
    genres: Tuple[str, ...] = ()
    moods: Tuple[str, ...] = ()
    eras: Tuple[str, ...] = ()
    artist: Optional[str] = None
    energy: Optional[float] = None
    dance: Optional[float] = None
    familiarity: Optional[float] = None
    tempo: Optional[str] = None
    weight: float = 1.0


def _split(value: str) -> Tuple[str, ...]:
    if not value:
        return ()
    return tuple(part for part in value.replace(",", " ").split() if part)


def S(
    lang: str = "",
    genre: str = "",
    mood: str = "",
    era: str = "",
    artist: Optional[str] = None,
    energy: Optional[float] = None,
    dance: Optional[float] = None,
    fam: Optional[float] = None,
    tempo: Optional[str] = None,
    w: float = 1.0,
) -> Signal:
    return Signal(
        languages=_split(lang),
        genres=_split(genre),
        moods=_split(mood),
        eras=_split(era),
        artist=artist,
        energy=energy,
        dance=dance,
        familiarity=fam,
        tempo=tempo,
        weight=w,
    )


LEXICON: Dict[str, Signal] = {}
COLLISIONS: List[str] = []


def add(keys: str, sig: Signal) -> None:
    """Register ``sig`` under every ``|``-separated surface form in ``keys``."""
    for key in keys.split("|"):
        norm = normalize_key(key)
        if not norm:
            continue
        if norm in LEXICON:
            COLLISIONS.append(norm)
        LEXICON[norm] = sig


# ---------------------------------------------------------------------------
# 1. Artists -> language + genre + era + energy priors
# ---------------------------------------------------------------------------

# --- Punjabi / desi hip-hop ---
add("diljit dosanjh|diljit|dosanjh",
    S("punjabi", "bhangra", "hype celebratory", "2020s", "Diljit Dosanjh",
      energy=0.86, dance=0.90, fam=0.88))
add("ap dhillon|dhillon",
    S("punjabi", "desi_hiphop", "hype", "2020s", "AP Dhillon",
      energy=0.72, dance=0.82, fam=0.80))
add("karan aujla|aujla",
    S("punjabi", "desi_hiphop bhangra", "hype", "2020s", "Karan Aujla",
      energy=0.85, dance=0.88, fam=0.82))
add("sidhu moose wala|sidhu moosewala|sidhu|moose wala|moosewala",
    S("punjabi", "desi_hiphop", "aggressive hype", "2020s", "Sidhu Moose Wala",
      energy=0.84, dance=0.78, fam=0.85))
add("shubh",
    S("punjabi", "desi_hiphop", "chill", "2020s", "Shubh",
      energy=0.60, dance=0.75, fam=0.75))
add("gurdas maan|gurdaas maan",
    S("punjabi", "bhangra sufi", "nostalgic", "1990s", "Gurdas Maan",
      energy=0.58, dance=0.65, fam=0.75))
add("honey singh|yo yo honey singh|yo yo",
    S("punjabi hindi", "desi_hiphop", "hype celebratory", "2010s", "Honey Singh",
      energy=0.88, dance=0.90, fam=0.90))
add("badshah",
    S("hindi", "desi_hiphop", "hype celebratory", "2010s", "Badshah",
      energy=0.86, dance=0.90, fam=0.86))
add("divine|gully gang",
    S("hindi", "desi_hiphop hiphop", "aggressive", "2010s", "Divine",
      energy=0.78, dance=0.72, fam=0.70))
add("raftaar",
    S("hindi", "desi_hiphop hiphop", "hype aggressive", "2010s", "Raftaar",
      energy=0.82, dance=0.78, fam=0.72))
add("daler mehndi|daler mehendi",
    S("punjabi", "bhangra", "celebratory nostalgic", "1990s", "Daler Mehndi",
      energy=0.88, dance=0.92, fam=0.88))
add("jazzy b", S("punjabi", "bhangra", "hype", "2000s", "Jazzy B",
                 energy=0.82, dance=0.88, fam=0.70))
add("malkit singh", S("punjabi", "bhangra", "celebratory nostalgic", "1990s",
                      "Malkit Singh", energy=0.80, dance=0.88))
add("ammy virk", S("punjabi", "bhangra", "romantic", "2020s", "Ammy Virk",
                   energy=0.60, dance=0.70))
add("jassie gill|jassi gill", S("punjabi", "bhangra", "romantic", "2010s",
                                "Jassie Gill", energy=0.62, dance=0.72))
add("garry sandhu", S("punjabi", "bhangra", "hype", "2010s", "Garry Sandhu",
                      energy=0.78, dance=0.85))
add("sharry mann", S("punjabi", "bhangra", "hype", "2010s", "Sharry Mann",
                     energy=0.76, dance=0.84))
add("amrit maan", S("punjabi", "desi_hiphop bhangra", "hype", "2020s",
                    "Amrit Maan", energy=0.82, dance=0.86))
add("tarsem jassar", S("punjabi", "desi_hiphop", "hype", "2020s",
                       "Tarsem Jassar", energy=0.78, dance=0.80))
add("satinder sartaaj", S("punjabi", "sufi", "romantic nostalgic", "2010s",
                          "Satinder Sartaaj", energy=0.32, dance=0.30))
add("b praak|bpraak", S("punjabi hindi", "bollywood", "sad", "2020s", "B Praak",
                        energy=0.30, dance=0.32, fam=0.80))
add("jasmine sandlas", S("punjabi", "desi_hiphop", "hype sensual", "2010s",
                         "Jasmine Sandlas", energy=0.78, dance=0.85))
add("nucleya", S("hindi", "desi_hiphop edm", "hype", "2010s", "Nucleya",
                 energy=0.90, dance=0.90))
add("sukhbir", S("punjabi", "bhangra disco", "celebratory", "2000s", "Sukhbir",
                 energy=0.82, dance=0.90))
add("guru randhawa", S("punjabi hindi", "bhangra", "hype", "2010s",
                       "Guru Randhawa", energy=0.80, dance=0.88, fam=0.85))
add("neha kakkar", S("hindi", "bollywood", "hype celebratory", "2010s",
                     "Neha Kakkar", energy=0.76, dance=0.85, fam=0.85))

# --- Song titles ---
# Everything above maps *artists*. Guests also shout song names, and when the
# DJ's own setlist is loaded those are the most actionable requests in the room
# -- "TAUBA TAUBA!!!" is a precise ask, but with titles absent from the lexicon
# it interpreted to nothing and fell into the vague bucket alongside "idk
# surprise me". Each title carries the same signal shape as its artist so the
# request lands in the right wave, and the artist attribution lets the ranker's
# ``artist_match`` boost fire on the actual track.
add("tauba tauba|tauba",
    S("punjabi", "desi_hiphop pop", "hype sensual", "2020s", "Karan Aujla",
      energy=0.82, dance=0.92, fam=0.94))
add("garmi",
    S("hindi", "desi_hiphop bollywood", "hype aggressive", "2020s", "Badshah",
      energy=0.90, dance=0.90, fam=0.90))
add("buzz",
    S("hindi", "desi_hiphop pop", "hype celebratory", "2010s", "Badshah",
      energy=0.84, dance=0.88, fam=0.86))
add("uyi amma",
    S("hindi", "bollywood", "hype sensual", "2020s", "Madhubanti Bagchi",
      energy=0.86, dance=0.90, fam=0.82))
add("akhiyaan gulaab|akhiyaan",
    S("hindi", "bollywood pop", "romantic", "2020s", "Mitraz",
      energy=0.54, dance=0.70, fam=0.88, tempo="slow"))
add("chaleya",
    S("hindi", "bollywood", "romantic celebratory", "2020s", "Arijit Singh",
      energy=0.62, dance=0.80, fam=0.92))
add("jhoome jo pathaan|jhoome",
    S("hindi", "bollywood", "hype celebratory", "2020s", "Arijit Singh",
      energy=0.86, dance=0.88, fam=0.90))


# --- Bollywood playback / sufi ---
add("arijit singh|arijit",
    S("hindi", "bollywood", "romantic sad", "2010s", "Arijit Singh",
      energy=0.30, dance=0.35, fam=0.92))
add("shreya ghoshal|shreya",
    S("hindi", "bollywood", "romantic", "2000s", "Shreya Ghoshal",
      energy=0.32, dance=0.38, fam=0.85))
add("atif aslam|atif",
    S("hindi", "bollywood", "romantic", "2010s", "Atif Aslam",
      energy=0.35, dance=0.40, fam=0.85))
add("kishore kumar|kishore",
    S("hindi", "bollywood", "nostalgic", "1980s", "Kishore Kumar",
      energy=0.48, dance=0.55, fam=0.88))
add("lata mangeshkar|lata",
    S("hindi", "bollywood", "nostalgic romantic", "1980s", "Lata Mangeshkar",
      energy=0.25, dance=0.28, fam=0.88))
add("mohammed rafi|mohd rafi|rafi",
    S("hindi", "bollywood", "nostalgic", "1980s", "Mohammed Rafi",
      energy=0.35, dance=0.40, fam=0.80))
add("a r rahman|ar rahman|rahman|arr",
    S("hindi tamil", "bollywood", "euphoric", "2000s", "A.R. Rahman",
      energy=0.60, dance=0.65, fam=0.88))
add("pritam", S("hindi", "bollywood", "romantic", "2010s", "Pritam",
                energy=0.55, dance=0.65, fam=0.82))
add("nusrat fateh ali khan|nusrat|nfak",
    S("hindi", "sufi", "euphoric nostalgic", "1990s", "Nusrat Fateh Ali Khan",
      energy=0.50, dance=0.40, fam=0.82))
add("rahat fateh ali khan|rahat",
    S("hindi", "sufi bollywood", "romantic", "2010s", "Rahat Fateh Ali Khan",
      energy=0.38, dance=0.38, fam=0.80))
add("abida parveen", S("hindi", "sufi", "euphoric", "1990s", "Abida Parveen",
                       energy=0.42, dance=0.30))
add("coke studio", S("hindi", "sufi", "euphoric", "2010s", "Coke Studio",
                     energy=0.55, dance=0.50, fam=0.75))
add("sonu nigam", S("hindi", "bollywood", "romantic", "2000s", "Sonu Nigam",
                    energy=0.42, dance=0.50, fam=0.82))
add("udit narayan", S("hindi", "bollywood", "romantic nostalgic", "1990s",
                      "Udit Narayan", energy=0.48, dance=0.58, fam=0.85))
add("kumar sanu", S("hindi", "bollywood", "nostalgic romantic", "1990s",
                    "Kumar Sanu", energy=0.42, dance=0.50, fam=0.85))
add("alka yagnik", S("hindi", "bollywood", "nostalgic romantic", "1990s",
                     "Alka Yagnik", energy=0.45, dance=0.55, fam=0.82))
add("sunidhi chauhan", S("hindi", "bollywood", "hype", "2000s",
                         "Sunidhi Chauhan", energy=0.75, dance=0.85))
add("jubin nautiyal", S("hindi", "bollywood", "romantic", "2020s",
                        "Jubin Nautiyal", energy=0.38, dance=0.45))
add("vishal shekhar|vishal dadlani", S("hindi", "bollywood", "hype", "2010s",
                                       "Vishal-Shekhar", energy=0.72, dance=0.82))
add("shankar ehsaan loy", S("hindi", "bollywood", "euphoric", "2000s",
                            "Shankar-Ehsaan-Loy", energy=0.62, dance=0.68))
add("amit trivedi", S("hindi", "bollywood", "euphoric", "2010s",
                      "Amit Trivedi", energy=0.62, dance=0.65))
add("ilaiyaraaja|ilayaraja", S("tamil", "pop", "nostalgic", "1980s",
                                "Ilaiyaraaja", energy=0.45, dance=0.50))
add("anirudh|anirudh ravichander|ani", S("tamil", "pop", "hype celebratory", "2020s",
                                      "Anirudh", energy=0.92, dance=0.90, w=2.0))
add("hukum|jailer|thalaivar", S("tamil", "pop", "hype celebratory", "2020s",
                                "Anirudh", energy=0.92, dance=0.88, w=2.0))
add("naa ready|na ready|leo|thalapathy vijay|thalapathy", S("tamil", "pop", "hype celebratory", "2020s",
                                                            "Anirudh", energy=0.94, dance=0.92, w=2.0))
add("vaathi coming|vaathi|master", S("tamil", "pop", "hype celebratory", "2020s",
                                     "Anirudh", energy=0.93, dance=0.92, w=2.0))
add("badass|vikram|vikram title track", S("tamil", "hiphop", "hype dark", "2020s",
                                          "Anirudh", energy=0.89, dance=0.87, w=2.0))
add("kaavaalaa|kavala|chellamma|arabic kuthu|kuthu", S("tamil", "pop", "hype celebratory", "2020s",
                                                       "Anirudh", energy=0.90, dance=0.90, w=2.0))
add("rowdy baby|dhanush|kolaveri|why this kolaveri", S("tamil", "pop", "celebratory hype", "2010s",
                                                       "Dhanush", energy=0.88, dance=0.90, w=2.0))
add("aaluma doluma|thala|ajith", S("tamil", "pop", "hype celebratory", "2010s",
                                   "Anirudh", energy=0.95, dance=0.92, w=2.0))
add("devi sri prasad|dsp", S("telugu", "pop", "hype celebratory", "2010s",
                              "Devi Sri Prasad", energy=0.82, dance=0.88))

# --- Bollywood actors (film-song requests) ---
add("shah rukh khan|shahrukh khan|shah rukh|shahrukh|srk|king khan",
    S("hindi", "bollywood", "romantic", "2000s", "Shah Rukh Khan",
      energy=0.50, dance=0.65, fam=0.92))
add("hrithik roshan|hrithik|hritik|rithik",
    S("hindi", "bollywood", "hype celebratory", "2000s", "Hrithik Roshan",
      energy=0.78, dance=0.90, fam=0.88))
add("salman khan|salman|bhai",
    S("hindi", "bollywood", "celebratory hype", "2010s", "Salman Khan",
      energy=0.76, dance=0.85, fam=0.88))
add("govinda",
    S("hindi", "bollywood", "nostalgic celebratory", "1990s", "Govinda",
      energy=0.78, dance=0.88, fam=0.85))
add("madhuri dixit|madhuri", S("hindi", "bollywood", "nostalgic celebratory",
                               "1990s", "Madhuri Dixit", energy=0.72,
                               dance=0.90, fam=0.85))
add("aamir khan|aamir", S("hindi", "bollywood", "nostalgic", "2000s",
                          "Aamir Khan", energy=0.58, dance=0.68, fam=0.85))
add("akshay kumar|akshay", S("hindi", "bollywood", "celebratory", "2010s",
                             "Akshay Kumar", energy=0.72, dance=0.82))
add("ranveer singh|ranveer", S("hindi", "bollywood", "hype celebratory",
                               "2010s", "Ranveer Singh", energy=0.82,
                               dance=0.88))
add("deepika padukone|deepika", S("hindi", "bollywood", "romantic", "2010s",
                                  "Deepika Padukone", energy=0.60, dance=0.75))
add("katrina kaif|katrina", S("hindi", "bollywood", "hype", "2010s",
                              "Katrina Kaif", energy=0.74, dance=0.85))
add("shahid kapoor|shahid", S("hindi", "bollywood", "romantic", "2010s",
                              "Shahid Kapoor", energy=0.58, dance=0.72))
add("tiger shroff", S("hindi", "bollywood", "hype", "2020s", "Tiger Shroff",
                      energy=0.82, dance=0.90))
add("ranbir kapoor|ranbir", S("hindi", "bollywood", "romantic", "2010s",
                              "Ranbir Kapoor", energy=0.55, dance=0.68))
add("amitabh bachchan|amitabh|big b", S("hindi", "bollywood", "nostalgic",
                                        "1980s", "Amitabh Bachchan",
                                        energy=0.60, dance=0.72, fam=0.85))

# --- Western hip-hop / pop / rnb ---
add("drake|drizzy", S("english", "hiphop rnb", "chill", "2010s", "Drake",
                      energy=0.62, dance=0.78, fam=0.92))
add("travis scott|travis|la flame", S("english", "hiphop", "dark aggressive",
                                      "2020s", "Travis Scott", energy=0.82,
                                      dance=0.78, fam=0.85))
add("kendrick lamar|kendrick|k dot", S("english", "hiphop", "aggressive",
                                       "2010s", "Kendrick Lamar", energy=0.72,
                                       dance=0.72, fam=0.88))
add("nicki minaj|nicki", S("english", "hiphop pop", "hype", "2010s",
                           "Nicki Minaj", energy=0.82, dance=0.88, fam=0.88))
add("beyonce|bey|queen b", S("english", "rnb pop", "celebratory hype", "2010s",
                             "Beyonce", energy=0.78, dance=0.88, fam=0.92))
add("rihanna|riri", S("english", "pop rnb", "sensual hype", "2010s", "Rihanna",
                      energy=0.72, dance=0.85, fam=0.92))
add("the weeknd|weeknd|abel", S("english", "rnb pop", "sensual dark", "2020s",
                               "The Weeknd", energy=0.68, dance=0.80, fam=0.90))
add("doja cat|doja", S("english", "pop rnb", "hype sensual", "2020s",
                       "Doja Cat", energy=0.76, dance=0.88, fam=0.88))
add("eminem|slim shady", S("english", "hiphop", "aggressive", "2000s",
                           "Eminem", energy=0.80, dance=0.62, fam=0.92))
add("kanye west|kanye|ye", S("english", "hiphop", "hype", "2010s",
                             "Kanye West", energy=0.74, dance=0.78, fam=0.90))
add("jay z|jayz", S("english", "hiphop", "hype", "2000s", "Jay-Z",
                    energy=0.72, dance=0.75, fam=0.88))
add("50 cent", S("english", "hiphop", "hype aggressive", "2000s", "50 Cent",
                 energy=0.78, dance=0.80, fam=0.88))
add("snoop dogg|snoop", S("english", "hiphop", "chill", "2000s", "Snoop Dogg",
                          energy=0.60, dance=0.75, fam=0.88))
add("cardi b", S("english", "hiphop", "hype", "2020s", "Cardi B", energy=0.84,
                 dance=0.90, fam=0.86))
add("megan thee stallion|megan", S("english", "hiphop", "hype", "2020s",
                                   "Megan Thee Stallion", energy=0.84,
                                   dance=0.90))
add("sza", S("english", "rnb", "sensual sad", "2020s", "SZA", energy=0.42,
             dance=0.60, fam=0.82))
add("frank ocean", S("english", "rnb", "chill sad", "2010s", "Frank Ocean",
                     energy=0.35, dance=0.50, fam=0.78))
add("usher", S("english", "rnb", "sensual", "2000s", "Usher", energy=0.65,
               dance=0.85, fam=0.88))
add("chris brown", S("english", "rnb pop", "sensual hype", "2010s",
                     "Chris Brown", energy=0.72, dance=0.88, fam=0.85))
add("taylor swift|taylor|swiftie", S("english", "pop", "romantic", "2020s",
                                     "Taylor Swift", energy=0.60, dance=0.72,
                                     fam=0.94))
add("dua lipa", S("english", "pop disco", "euphoric hype", "2020s", "Dua Lipa",
                  energy=0.80, dance=0.90, fam=0.90))
add("ariana grande|ariana", S("english", "pop rnb", "romantic", "2010s",
                              "Ariana Grande", energy=0.66, dance=0.80,
                              fam=0.90))
add("justin bieber|bieber", S("english", "pop rnb", "romantic", "2010s",
                              "Justin Bieber", energy=0.62, dance=0.80,
                              fam=0.92))
add("ed sheeran", S("english", "pop", "romantic", "2010s", "Ed Sheeran",
                    energy=0.45, dance=0.60, fam=0.92))
add("bruno mars", S("english", "pop rnb disco", "celebratory", "2010s",
                    "Bruno Mars", energy=0.78, dance=0.92, fam=0.92))
add("post malone|posty", S("english", "hiphop pop", "chill", "2010s",
                           "Post Malone", energy=0.58, dance=0.72, fam=0.88))
add("lil wayne", S("english", "hiphop", "hype", "2010s", "Lil Wayne",
                   energy=0.76, dance=0.78))
add("future", S("english", "hiphop", "dark", "2010s", "Future", energy=0.74,
                dance=0.80))
add("21 savage", S("english", "hiphop", "dark aggressive", "2020s",
                   "21 Savage", energy=0.74, dance=0.78))
add("playboi carti|carti", S("english", "hiphop", "aggressive dark", "2020s",
                             "Playboi Carti", energy=0.82, dance=0.80))
add("tyler the creator|tyler", S("english", "hiphop", "chill", "2020s",
                                 "Tyler, The Creator", energy=0.62, dance=0.72))
add("central cee|cench", S("english", "hiphop garage", "dark", "2020s",
                           "Central Cee", energy=0.70, dance=0.78))
add("stormzy|skepta", S("english", "hiphop garage", "aggressive", "2010s",
                        "Stormzy", energy=0.76, dance=0.78))
add("sabrina carpenter", S("english", "pop", "romantic", "2020s",
                           "Sabrina Carpenter", energy=0.62, dance=0.78))
add("olivia rodrigo", S("english", "pop rock", "sad", "2020s",
                        "Olivia Rodrigo", energy=0.58, dance=0.60))
add("the killers", S("english", "rock", "euphoric", "2000s", "The Killers",
                     energy=0.72, dance=0.70, fam=0.85))

# --- Spanish / reggaeton ---
add("bad bunny|benito", S("spanish", "reggaeton", "hype celebratory", "2020s",
                          "Bad Bunny", energy=0.80, dance=0.90, fam=0.88))
add("karol g", S("spanish", "reggaeton", "hype sensual", "2020s", "Karol G",
                 energy=0.78, dance=0.90, fam=0.84))
add("daddy yankee", S("spanish", "reggaeton", "hype nostalgic", "2000s",
                      "Daddy Yankee", energy=0.86, dance=0.92, fam=0.90))
add("j balvin|balvin", S("spanish", "reggaeton", "hype", "2010s", "J Balvin",
                         energy=0.78, dance=0.90, fam=0.85))
add("maluma", S("spanish", "reggaeton", "sensual", "2010s", "Maluma",
                energy=0.72, dance=0.88))
add("shakira", S("spanish", "pop reggaeton", "celebratory", "2000s", "Shakira",
                 energy=0.78, dance=0.90, fam=0.92))
add("ozuna", S("spanish", "reggaeton", "hype", "2010s", "Ozuna", energy=0.76,
               dance=0.88))
add("rauw alejandro|rauw", S("spanish", "reggaeton", "sensual", "2020s",
                             "Rauw Alejandro", energy=0.74, dance=0.90))
add("feid|ferxxo", S("spanish", "reggaeton", "chill sensual", "2020s", "Feid",
                     energy=0.66, dance=0.85))
add("don omar", S("spanish", "reggaeton", "hype nostalgic", "2000s",
                  "Don Omar", energy=0.82, dance=0.90))
add("luis fonsi|despacito", S("spanish", "reggaeton pop", "celebratory",
                              "2010s", "Luis Fonsi", energy=0.74, dance=0.90,
                              fam=0.94))
add("peso pluma", S("spanish", "reggaeton", "hype", "2020s", "Peso Pluma",
                    energy=0.72, dance=0.80))
add("rosalia", S("spanish", "pop reggaeton", "sensual", "2020s", "Rosalia",
                 energy=0.68, dance=0.82))

# --- Afrobeats / amapiano ---
add("burna boy|burna", S("afrobeats", "afrobeat", "chill celebratory", "2020s",
                         "Burna Boy", energy=0.68, dance=0.86, fam=0.85))
add("wizkid", S("afrobeats", "afrobeat", "chill sensual", "2020s", "Wizkid",
                energy=0.64, dance=0.86, fam=0.85))
add("rema", S("afrobeats", "afrobeat", "hype", "2020s", "Rema", energy=0.74,
              dance=0.90, fam=0.85))
add("davido", S("afrobeats", "afrobeat", "celebratory hype", "2020s", "Davido",
                energy=0.76, dance=0.88, fam=0.82))
add("asake", S("afrobeats", "afrobeat amapiano", "celebratory", "2020s",
               "Asake", energy=0.74, dance=0.88))
add("tems", S("afrobeats", "afrobeat rnb", "chill sensual", "2020s", "Tems",
              energy=0.45, dance=0.68))
add("ayra starr", S("afrobeats", "afrobeat", "hype", "2020s", "Ayra Starr",
                    energy=0.72, dance=0.86))
add("fireboy dml|fireboy", S("afrobeats", "afrobeat", "romantic", "2020s",
                             "Fireboy DML", energy=0.62, dance=0.82))
add("ckay", S("afrobeats", "afrobeat", "romantic", "2020s", "CKay",
              energy=0.58, dance=0.82, fam=0.82))
add("omah lay", S("afrobeats", "afrobeat", "chill", "2020s", "Omah Lay",
                  energy=0.58, dance=0.80))
add("tyla", S("afrobeats", "amapiano afrobeat", "sensual", "2020s", "Tyla",
              energy=0.68, dance=0.90, fam=0.85))
add("kabza de small|kabza", S("afrobeats", "amapiano house", "chill", "2020s",
                              "Kabza De Small", energy=0.66, dance=0.86))
add("dj maphorisa|maphorisa", S("afrobeats", "amapiano house", "hype", "2020s",
                                "DJ Maphorisa", energy=0.70, dance=0.88))
add("uncle waffles", S("afrobeats", "amapiano house", "hype", "2020s",
                       "Uncle Waffles", energy=0.74, dance=0.90))
add("black coffee", S("afrobeats english", "house amapiano", "dark euphoric",
                      "2020s", "Black Coffee", energy=0.70, dance=0.85))

# --- House / techno / EDM ---
add("fred again|fred again again|fred", S("english", "house", "euphoric",
                                          "2020s", "Fred again..",
                                          energy=0.80, dance=0.88, fam=0.78))
add("peggy gou", S("english", "house", "euphoric", "2020s", "Peggy Gou",
                   energy=0.78, dance=0.88))
add("calvin harris", S("english", "edm house", "euphoric hype", "2010s",
                       "Calvin Harris", energy=0.86, dance=0.90, fam=0.92))
add("david guetta|guetta", S("english", "edm house", "hype", "2010s",
                             "David Guetta", energy=0.86, dance=0.90,
                             fam=0.90))
add("swedish house mafia|shm", S("english", "house edm", "euphoric", "2010s",
                                 "Swedish House Mafia", energy=0.90,
                                 dance=0.88, fam=0.85))
add("skrillex", S("english", "edm", "aggressive hype", "2010s", "Skrillex",
                  energy=0.95, dance=0.82, fam=0.85))
add("avicii", S("english", "edm house", "euphoric nostalgic", "2010s",
                "Avicii", energy=0.84, dance=0.88, fam=0.92))
add("martin garrix|garrix", S("english", "edm", "euphoric", "2010s",
                              "Martin Garrix", energy=0.88, dance=0.86))
add("tiesto", S("english", "edm house", "hype", "2010s", "Tiesto",
                energy=0.88, dance=0.88, fam=0.88))
add("marshmello", S("english", "edm", "euphoric", "2010s", "Marshmello",
                    energy=0.84, dance=0.86))
add("diplo|major lazer", S("english", "edm house", "hype", "2010s", "Diplo",
                           energy=0.84, dance=0.88))
add("disclosure", S("english", "house garage", "euphoric", "2010s",
                    "Disclosure", energy=0.74, dance=0.88))
add("charlotte de witte", S("english", "techno", "dark aggressive", "2020s",
                            "Charlotte de Witte", energy=0.92, dance=0.80))
add("amelie lens", S("english", "techno", "dark", "2020s", "Amelie Lens",
                     energy=0.90, dance=0.80))
add("boris brejcha", S("english", "techno", "dark euphoric", "2020s",
                       "Boris Brejcha", energy=0.82, dance=0.82))
add("carl cox", S("english", "techno house", "dark", "2000s", "Carl Cox",
                  energy=0.86, dance=0.82))
add("keinemusik|adam port", S("english", "house", "euphoric", "2020s",
                              "Keinemusik", energy=0.74, dance=0.86))
add("anyma", S("english", "techno", "dark euphoric", "2020s", "Anyma",
               energy=0.80, dance=0.82))
add("john summit", S("english", "house", "hype euphoric", "2020s",
                     "John Summit", energy=0.84, dance=0.90))
add("chris lake", S("english", "house", "hype", "2020s", "Chris Lake",
                    energy=0.84, dance=0.90))
add("fisher", S("english", "house", "hype", "2020s", "Fisher", energy=0.86,
                dance=0.92))
add("daft punk", S("english", "house disco", "euphoric nostalgic", "2000s",
                   "Daft Punk", energy=0.80, dance=0.90, fam=0.92))

# --- Retro / disco / rock ---
add("abba", S("english", "disco pop", "nostalgic celebratory", "1980s", "ABBA",
              energy=0.74, dance=0.88, fam=0.95))
add("michael jackson|mj|jacko", S("english", "pop disco", "nostalgic hype",
                                  "1980s", "Michael Jackson", energy=0.80,
                                  dance=0.92, fam=0.96))
add("queen|freddie mercury", S("english", "rock", "nostalgic euphoric",
                               "1980s", "Queen", energy=0.76, dance=0.62,
                               fam=0.95))
add("bee gees", S("english", "disco", "nostalgic", "1980s", "Bee Gees",
                  energy=0.74, dance=0.88, fam=0.90))
add("donna summer", S("english", "disco", "nostalgic sensual", "1980s",
                      "Donna Summer", energy=0.74, dance=0.88))
add("elvis|elvis presley", S("english", "rock", "nostalgic", "1980s", "Elvis",
                             energy=0.62, dance=0.65, fam=0.90))
add("the beatles|beatles", S("english", "rock pop", "nostalgic", "1980s",
                             "The Beatles", energy=0.58, dance=0.55, fam=0.94))
add("ac dc|acdc", S("english", "rock", "aggressive", "1980s", "AC/DC",
                    energy=0.86, dance=0.55, fam=0.90))
add("guns n roses|gnr", S("english", "rock", "aggressive", "1990s",
                          "Guns N' Roses", energy=0.84, dance=0.55, fam=0.88))
add("nirvana", S("english", "rock", "aggressive dark", "1990s", "Nirvana",
                 energy=0.80, dance=0.50, fam=0.88))
add("linkin park", S("english", "rock", "aggressive", "2000s", "Linkin Park",
                     energy=0.84, dance=0.55, fam=0.90))
add("coldplay", S("english", "rock pop", "euphoric", "2000s", "Coldplay",
                  energy=0.56, dance=0.55, fam=0.92))
add("imagine dragons", S("english", "rock pop", "euphoric", "2010s",
                         "Imagine Dragons", energy=0.74, dance=0.62, fam=0.88))
add("bon jovi", S("english", "rock", "nostalgic euphoric", "1980s", "Bon Jovi",
                  energy=0.76, dance=0.58, fam=0.88))
add("eagles|hotel california", S("english", "rock", "nostalgic", "1980s",
                                 "Eagles", energy=0.50, dance=0.48, fam=0.90))

# ---------------------------------------------------------------------------
# 2. Genres and genre slang
# ---------------------------------------------------------------------------

add("bhangra|bhangda|bhangre", S("punjabi", "bhangra", "hype celebratory",
                                 energy=0.86, dance=0.92, w=1.6))
add("dhol|dhol beats|dholki", S("punjabi", "bhangra", "celebratory",
                                energy=0.85, dance=0.90, w=1.4))
add("gidda|giddha", S("punjabi", "bhangra", "celebratory",
                      energy=0.80, dance=0.90, w=1.4))
add("garba|dandiya|navratri", S("hindi", "bollywood", "celebratory",
                                energy=0.84, dance=0.92, w=1.5))
add("bollywood|bolly|filmi|filmy|hindi film|film songs|bollywood songs",
    S("hindi", "bollywood", energy=None, dance=0.72, w=1.6))
add("item song|item number|item songs", S("hindi", "bollywood",
                                          "hype celebratory", energy=0.86,
                                          dance=0.92, w=1.5))
add("hip hop|hiphop|rap|rappers|trap|drill",
    S("english", "hiphop", energy=0.72, dance=0.78, w=1.5))
add("desi hip hop|desi hiphop|desi rap|punjabi rap|indian rap|gully rap",
    S("punjabi", "desi_hiphop", "hype", energy=0.80, dance=0.82, w=1.6))
add("house|house music", S("", "house", energy=0.76, dance=0.88, w=1.5))
add("deep house", S("", "house", "chill", energy=0.62, dance=0.85, w=1.6))
add("tech house", S("", "house techno", "hype", energy=0.84, dance=0.90, w=1.6))
add("afro house", S("afrobeats", "house afrobeat", energy=0.74, dance=0.88,
                    w=1.6))
add("techno", S("", "techno", "dark", energy=0.88, dance=0.82, w=1.6))
add("melodic techno", S("", "techno", "dark euphoric", energy=0.80, dance=0.82,
                        w=1.6))
add("minimal", S("", "techno", "dark", energy=0.72, dance=0.80, w=1.2))
add("edm|electronic|electro|dance music|club music|rave",
    S("", "edm", "hype", energy=0.86, dance=0.90, w=1.5))
add("drop|drops|beat drop", S("", "edm", "hype", energy=0.90, dance=0.88,
                              w=1.3))
add("dubstep|bass|bass music|riddim", S("", "edm", "aggressive",
                                        energy=0.90, dance=0.78, w=1.4))
add("hardstyle", S("", "edm", "aggressive hype", energy=0.95, dance=0.82,
                   w=1.5))
add("trance|psytrance", S("", "edm", "euphoric", energy=0.84, dance=0.84,
                          w=1.5))
add("rnb|rhythm and blues", S("english", "rnb", "sensual", energy=0.48,
                              dance=0.70, w=1.6))
add("slow jams|slow jam|bedroom rnb", S("english", "rnb", "sensual",
                                        energy=0.28, dance=0.55, tempo="slow",
                                        w=1.6))
add("reggaeton|dembow|perreo|latin|latino|spanish music",
    S("spanish", "reggaeton", "hype", energy=0.78, dance=0.90, w=1.6))
add("afrobeats|afrobeat|afro|naija|amapiano vibes",
    S("afrobeats", "afrobeat", energy=0.70, dance=0.88, w=1.6))
add("amapiano|piano|yanos|log drum", S("afrobeats", "amapiano",
                                       energy=0.68, dance=0.88, w=1.6))
add("sufi|sufiyana", S("hindi", "sufi", "euphoric", energy=0.45, dance=0.40,
                       w=1.6))
add("qawwali|qawali", S("hindi", "sufi", "euphoric nostalgic", energy=0.52,
                        dance=0.40, w=1.6))
add("ghazal|ghazals", S("hindi", "sufi", "romantic sad", energy=0.25,
                        dance=0.25, tempo="slow", w=1.6))
add("disco|nightfever", S("english", "disco", "nostalgic celebratory",
                          energy=0.78, dance=0.90, w=1.5))
add("rock|rock music|metal|punk", S("english", "rock", "aggressive",
                                    energy=0.80, dance=0.55, w=1.5))
add("pop|pop music|top 40|charts", S("english", "pop", energy=0.68,
                                     dance=0.78, fam=0.88, w=1.4))
add("garage|uk garage|2 step|speed garage", S("english", "garage",
                                              energy=0.78, dance=0.88, w=1.6))
add("lofi|lo fi|jazz|acoustic|indie", S("english", "pop", "chill",
                                        energy=0.30, dance=0.40, tempo="slow",
                                        w=1.3))

# --- Languages / regions ---
add("punjabi|panjabi|punjab|pind|paaji", S("punjabi", energy=None, dance=0.72,
                                           w=1.6))
add("hindi|hindustani", S("hindi", energy=None, dance=0.65, w=1.5))
add("english|western|angrezi", S("english", w=1.2))
add("tamil|kollywood|tamizh", S("tamil", "pop", dance=0.88, w=2.0))
add("telugu|tollywood", S("telugu", "bollywood", dance=0.80, w=1.6))
add("spanish|espanol", S("spanish", w=1.4))
add("arabic|khaleeji|habibi", S("arabic", dance=0.72, w=1.5))
add("desi|indian|india|south asian", S("hindi punjabi", dance=0.75, w=1.1))

# ---------------------------------------------------------------------------
# 3. Moods
# ---------------------------------------------------------------------------

add("hype|hyped|lit|turnt|turnt up|crazy|chaos|chaotic|pump|pumped|energy|"
    "mad|fire|banger|bangers|bangin|going off|rager|wild|insane|mental|"
    "unhinged|nuts|hype it up|smasher",
    S("", "", "hype", energy=0.90, dance=0.88, w=1.5))
add("romantic|romance|love|love songs|couple|couples|slow dance|dil|pyaar|"
    "pyar|mohabbat|ishq|dilbar|lovey dovey|slow song|slow songs|serenade",
    S("", "", "romantic", energy=0.30, dance=0.45, w=1.5))
add("nostalgia|nostalgic|throwback|throwbacks|old school|oldschool|classic|"
    "classics|childhood|purane gaane|purane|purana|back in the day|vintage|"
    "school days|college days|memories|golden era|golden age",
    S("", "", "nostalgic", "1990s", energy=0.60, dance=0.70, fam=0.90, w=1.5))
add("chill|relax|relaxed|vibe|vibes|vibey|mellow|lofi vibes|laid back|"
    "easy|smooth|cruisy|background",
    S("", "", "chill", energy=0.35, dance=0.55, w=1.4))
add("sad|sadboi|sadgirl|heartbreak|heart break|breakup|break up|dard|"
    "emotional|crying|tears|depressing|melancholy|judaai|bewafa|feels",
    S("", "", "sad", energy=0.25, dance=0.35, tempo="slow", w=1.5))
add("dark|hard|heavy|grimy|gritty|moody|industrial|warehouse",
    S("", "", "dark", energy=0.82, dance=0.80, w=1.4))
# "underground" carries both a mood and a familiarity signal.
add("underground|for the heads",
    S("", "", "dark", energy=0.80, dance=0.80, fam=0.15, w=1.4))
add("euphoric|uplifting|anthem|anthems|epic|hands up|singalong|sing along|"
    "goosebumps|emotional drop",
    S("", "", "euphoric", energy=0.82, dance=0.85, fam=0.85, w=1.4))
add("sensual|sexy|slow grind|grind|seductive|steamy|sultry|body",
    S("", "", "sensual", energy=0.50, dance=0.78, w=1.4))
add("wedding|baraat|barat|sangeet|shaadi|shadi|mehendi|mehndi|celebration|"
    "celebrate|party|partying|birthday|reception|graduation|festive|"
    "cheers|toast",
    S("", "", "celebratory", energy=0.82, dance=0.88, w=1.5))
add("aggressive|gym|workout|beast mode|rage|angry|mosh|hard hitting|"
    "adrenaline|hype beast",
    S("", "", "aggressive", energy=0.90, dance=0.72, w=1.4))

# ---------------------------------------------------------------------------
# 4. Hinglish / desi slang
# ---------------------------------------------------------------------------

add("nachne wala|nachne|naach|nach|nachle|nachna|thumka|thumke|jhoom|"
    "nachna hai|dance karna",
    S("hindi punjabi", "", "celebratory", energy=0.82, dance=0.92, w=1.5))
add("gaana|gaane|gana|gaana bajao|koi gaana", S("hindi", w=0.9))
add("dhinchak|jhakaas|jhakkas|mast|masti|dhamaal|dhamaka|jhoom uthe",
    S("hindi", "bollywood", "hype celebratory", energy=0.86, dance=0.90, w=1.4))
add("bhangra paake|balle balle|balle|chak de|chakde|oye oye|shava shava|"
    "bruah|paa ji",
    S("punjabi", "bhangra", "celebratory hype", energy=0.88, dance=0.92, w=1.5))
add("dj waale babu|dj wale babu|dj babu", S("hindi", "desi_hiphop", "hype",
                                            energy=0.86, dance=0.90, w=1.3))
add("gully|gully gang rap|apna time aayega", S("hindi", "desi_hiphop",
                                               "aggressive", energy=0.78,
                                               dance=0.78, w=1.3))
add("swag|full swag", S("", "desi_hiphop", "hype", energy=0.80, dance=0.85,
                        w=1.0))

# ---------------------------------------------------------------------------
# 5. Eras
# ---------------------------------------------------------------------------

add("80s|1980s|eighties|80", S("", "", "nostalgic", "1980s", fam=0.85, w=1.5))
add("90s|1990s|nineties|90", S("", "", "nostalgic", "1990s", fam=0.85, w=1.5))
add("2000s|y2k|2k|noughties|two thousands|00s",
    S("", "", "nostalgic", "2000s", fam=0.85, w=1.5))
add("2010s|twenty tens|10s", S("", "", "", "2010s", w=1.5))
add("2020s|new|latest|current|recent|new stuff|fresh|nowadays|these days|"
    "modern|today|trending|this year",
    S("", "", "", "2020s", w=1.3))
add("old|oldies|olden|older|old songs|old gold|retro|retro vibes",
    S("", "", "nostalgic", "1990s", energy=0.62, fam=0.88, w=1.5))

# ---------------------------------------------------------------------------
# 6. Energy / tempo / danceability / familiarity modifiers
# ---------------------------------------------------------------------------

add("high energy|peak|peak time|peak hour|turn up|turn it up|turn up the heat|"
    "go crazy|go off|full send|max energy|bring the energy|amp it up|"
    "crank it|blow the roof|send it|no chill|full throttle",
    S("", "", "hype", energy=0.90, dance=0.88, tempo="fast", w=3.0))
add("slow it down|slow down|cool down|cooldown|breather|ballad|ballads|"
    "wind down|mellow out|calm|calm down|chill out|sit down|take it easy|"
    "slow burn|come down",
    S("", "", "", energy=0.20, dance=0.40, tempo="slow", w=3.0))
add("mid|midtempo|mid tempo|groovy|groove|medium|steady|bouncy|bounce",
    S("", "", "", energy=0.50, dance=0.80, tempo="mid", w=2.0))
add("fast|uptempo|up tempo|faster|speed|quick|high bpm|140 bpm",
    S("", "", "", energy=0.85, dance=0.85, tempo="fast", w=2.5))
add("slow|slower|low energy|soft|softer|quiet",
    S("", "", "", energy=0.22, dance=0.42, tempo="slow", w=2.2))

add("dance|dances|dancing|danceable|dance to it|dance floor|dancefloor|"
    "floor filler|floorfiller|move|moving|shuffle|two step|get down|shake|"
    "boogie|bust a move|footwork|dance to",
    S("", "", "", energy=0.65, dance=0.88, w=2.0))

add("everyone knows|everybody knows|everyone|everybody|popular|mainstream|"
    "hit|hits|big hit|chartbuster|viral|tiktok|famous|iconic|crowd pleaser|"
    "crowd pleaser songs|well known|the one everyone|sing along to",
    S("", "", "", fam=0.92, w=2.0))
add("deep cut|deep cuts|obscure|unknown|rare|b side|bside|"
    "hidden gem|niche|no one knows|lesser known",
    S("", "", "", fam=0.12, w=2.0))

# ---------------------------------------------------------------------------
# 7. Emoji
# ---------------------------------------------------------------------------

add("\U0001F525", S("", "", "hype", energy=0.88, dance=0.88, w=1.5))  # fire
add("\U0001F57A", S("", "", "hype celebratory", energy=0.85, dance=0.92,
                    w=1.5))  # man dancing
add("\U0001F483", S("", "", "hype celebratory", energy=0.85, dance=0.92,
                    w=1.5))  # woman dancing
add("\U0001F389|\U0001F38A|\U0001F973|\U0001F37E|\U0001F942",
    S("", "", "celebratory", energy=0.82, dance=0.88, w=1.4))
add("\U0001FAA9|⚡|\U0001F4A5",
    S("", "", "hype euphoric", energy=0.88, dance=0.88, w=1.4))
add("❤|\U0001F60D|\U0001F495|\U0001F496|\U0001F498|\U0001F970|"
    "\U0001F618|\U0001F49B|\U0001F49C",
    S("", "", "romantic", energy=0.35, dance=0.50, w=1.4))
add("\U0001F622|\U0001F494|\U0001F62D|\U0001F97A",
    S("", "", "sad", energy=0.25, dance=0.35, tempo="slow", w=1.4))
add("\U0001F60E|\U0001F30A|\U0001F319",
    S("", "", "chill", energy=0.40, dance=0.60, w=1.1))
add("\U0001F608|\U0001F5A4|\U0001F480",
    S("", "", "dark", energy=0.82, dance=0.80, w=1.3))
add("\U0001F3A7|\U0001F3B6|\U0001F3B5|\U0001F3B9", S("", w=0.6))


# ---------------------------------------------------------------------------
# Derived sets used by the engine's post-rules
# ---------------------------------------------------------------------------

DANCE_CUES: Set[str] = set()
for _k in (
    "dance dances dancing danceable|dance to it|dance floor|dancefloor|"
    "floor filler|floorfiller|move|moving|shuffle|two step|get down|shake|"
    "boogie|bust a move|footwork|dance to|nachne wala|nachne|naach|nach|"
    "nachle|nachna|thumka|thumke|groovy|groove|bouncy|bounce"
).split("|"):
    for _part in _k.split():
        DANCE_CUES.add(_part)
DANCE_CUES.update(
    {"dance to it", "dance floor", "floor filler", "two step", "get down",
     "bust a move", "dance to", "nachne wala"}
)

MAX_NGRAM: int = max(len(k.split()) for k in LEXICON)


def audit() -> List[str]:
    """Return every lexicon entry that references a non-taxonomy token."""
    problems: List[str] = []
    for key, sig in LEXICON.items():
        for block, values in (
            ("languages", sig.languages),
            ("genres", sig.genres),
            ("moods", sig.moods),
            ("eras", sig.eras),
        ):
            for value in values:
                if not taxonomy.is_valid(block, value):
                    problems.append("%s -> %s:%s" % (key, block, value))
        if sig.tempo is not None and sig.tempo not in taxonomy.TEMPO_HINTS:
            problems.append("%s -> tempo:%s" % (key, sig.tempo))
    return problems


def size() -> int:
    return len(LEXICON)
