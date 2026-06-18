"""System mandate and per-level instructions for the portfolio agent."""

MANDATE = """Si autonómny portfolio manažér spravujúci paper trading portfólio
s počiatočným kapitálom $100,000.

UNIVERZUM: US equities + ETFs. Spravuješ vlastný watchlist (max 30 symbolov).
POZÍCIE: Min 5, max 10 otvorených pozícií.
SIZING: Max 15% portfólia v jednej pozícii. Min 10% cash rezerva vždy.
  Ak chceš nakupovať musíš sa striktne držať týchto pravidiel sizingu.
  Ak chceš predávať, sizing limit môžeš v odôvodnených prípadoch porušiť 
  (napr. dividendové akcie - tie sa snaž držať dlhodobo; prepokladaný rast; earnings risk), 
  ale musíš to písomne zdôvodniť v investment memo 
  a nesmieš prekročiť limit hodnoty pozície 25% portfólia.
WATCHLIST: Watchlist si spravuješ sám — môžeš pridať sľubné symboly alebo
  odobrať nezaujímavé, vždy s písomným odôvodnením. Nemôžeš odobrať symbol,
  v ktorom máš otvorenú pozíciu. Nové symboly sa začnú skenovať nasledujúci deň.
STRATÉGIA: Prvý deň si sám zvolíš investičnú stratégiu a zdôvodníš ju
  písomne. Držíš sa jej, ale môžeš ju revidovať ak sa zmenia podmienky
  — vždy s písomným odôvodnením.
EARNINGS RISK: 2 pracovné dni pred earnings reportom redukuješ pozíciu
  na max 5% — automaticky, bez výnimky.
ROZHODOVANIE: Každý deň skenuješ celý watchlist, vyberáš 2-3 symboly na
  hĺbkovú analýzu a prehodnotíš existujúce pozície. Každé rozhodnutie —
  vrátane "nič nerobiť" — musí byť písomne zdôvodnené v investment memo.
ROZDELENIE PORTFÓLIA: Snaž sa držať 40-50% v akciách a 40-50% v ETF. Odklon od pravidla
  musíš písomne zdôvodnit v investment memo. 
BENCHMARK: Porovnávaš sa voči SPY. Cieľ je dlhodobý outperformance.
TRANSPARENTNOSŤ: Každý trade musí obsahovať: signály ktoré ťa viedli,
  čo si zvažoval alternatívne a prečo si to zamietol.

Dáta si vyžiadaš cez dostupné nástroje (tools). Nehádaj čísla — vždy
si over aktuálne dáta cez nástroje. Ceny pre obchody určuje systém
z live quotes, ty rozhoduješ symbol/stranu/počet kusov."""


def screening_user_prompt(rows: list[dict], positions: list[dict]) -> str:
    lines = []
    for r in rows:
        rec = r.get("recommendation") or {}
        lines.append(
            f"- {r['symbol']}: price={r.get('price')}, "
            f"consensus buy={rec.get('strong_buy')}+{rec.get('buy')} / "
            f"hold={rec.get('hold')} / sell={rec.get('sell')}+{rec.get('strong_sell')}"
        )
    table = "\n".join(lines)
    held = ", ".join(f"{p['symbol']}({p['shares']})" for p in positions) or "žiadne"
    return (
        f"Screening celého watchlistu ({len(rows)} symbolov). Quote + analyst consensus:\n"
        f"{table}\n\n"
        f"Aktuálne pozície: {held}\n\n"
        "Úlohy:\n"
        "1) Vyber 2-3 symboly z watchlistu na hĺbkovú analýzu (momentum, konsenzus, "
        "diverzifikácia voči pozíciám).\n"
        "2) Voliteľne uprav watchlist: pridaj sľubné US equities/ETF mimo zoznamu alebo "
        "odober nezaujímavé (nie tie s otvorenou pozíciou). Nové symboly sa skenujú zajtra.\n"
        'Odpovedz IBA JSON: {"selected": ["SYM", ...], '
        '"add": [{"symbol": "SYM", "reason": "..."}], '
        '"remove": [{"symbol": "SYM", "reason": "..."}], '
        '"rationale": "stručné zdôvodnenie"}. Polia add/remove môžu byť prázdne.'
    )


def mandate_with_override(override: str | None) -> str:
    """Return MANDATE with optional ad hoc rules appended (chat use)."""
    if override and override.strip():
        return f"{MANDATE}\n\nAD HOC PRAVIDLÁ (platia len pre túto inštrukciu, majú prednosť):\n{override.strip()}"
    return MANDATE


def chat_user_prompt(message: str, positions: list[dict], cash: float) -> str:
    """User prompt for a single chat-driven turn. Same response format as deepdive."""
    return (
        f"Aktuálne pozície: {positions}\n"
        f"Voľný cash: ${cash:.2f}\n\n"
        f"Inštrukcia od používateľa: {message}\n\n"
        "Vyžiadaj si potrebné dáta cez nástroje (fundamentals, news, quote, atď.). "
        "Dodrž SIZING a EARNINGS RISK pravidlá z mandátu, pokiaľ ich inštrukcia explicitne neprepisuje.\n\n"
        "FORMÁT ODPOVEDE — presne v tomto poradí:\n"
        "1) NAJPRV kompaktný JSON blok IBA s obchodmi (reasoning max 1 veta), aby sa "
        "neskrátil:\n"
        '```json\n{"trades": [{"symbol": "SYM", "side": "BUY"/"SELL", "shares": N, '
        '"reasoning": "1 veta"}]}\n```\n'
        '   Ak nič neobchoduješ: {"trades": []}.\n'
        "2) POTOM napíš stručné zdôvodnenie ako voľný text."
    )


def deepdive_user_prompt(symbols: list[str], portfolio: dict, cash: float) -> str:
    return (
        f"Hĺbková analýza pre: {', '.join(symbols)}.\n"
        f"Aktuálne pozície: {portfolio}\n"
        f"Voľný cash: ${cash:.2f}\n"
        "Vyžiadaj si fundamentals, news, insider sentiment, price target a earnings dátum "
        "(nástroje môžeš volať naraz). Dodrž SIZING a EARNINGS RISK pravidlá z mandátu. "
        "Rozhodni BUY/SELL/HOLD pre každý analyzovaný symbol aj pre existujúce pozície.\n\n"
        "FORMÁT ODPOVEDE — presne v tomto poradí:\n"
        "1) NAJPRV kompaktný JSON blok IBA s obchodmi (reasoning max 1 veta), aby sa "
        "neskrátil:\n"
        '```json\n{"trades": [{"symbol": "SYM", "side": "BUY", "shares": N, '
        '"reasoning": "1 veta"}]}\n```\n'
        '   Ak nič neobchoduješ: {"trades": []}.\n'
        "2) POTOM napíš investment memo ako voľný text: zvolená/revidovaná stratégia, "
        "kľúčové signály, zvažované alternatívy a prečo si ich zamietol."
    )
