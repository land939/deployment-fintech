"""
demo_soutenance.py — Démonstration automatique pour la soutenance
Projet Fintech GTA

Rejoue devant le jury, sans aucune manipulation manuelle :
  0. démarre l'API si elle ne tourne pas déjà (fenêtre console dédiée)
  1. crée les comptes de démonstration (Alice, Bob, Mallory)
  2. injecte un historique réaliste (comptes anciens, moyennes de montants)
  3. déroule les scénarios de fraude du mémoire, un par un :
       ✓  transaction normale             → acceptée (LOW)
       S2 montant aberrant (~60× moyenne) → BLOQUÉE
       S1 rafale (8 envois en secondes)   → BLOQUÉE
       S3 compte neuf hyperactif          → BLOQUÉE
       S5 récidiviste                     → BLOQUÉE
     en affichant à chaque fois le score IA, le niveau de risque et les
     RAISONS du blocage renvoyées par l'API.
  4. affiche les identifiants à montrer au jury (UI utilisateur + console
     super admin, où les transactions bloquées peuvent être autorisées).

Usage :
    python demo_soutenance.py            # pas-à-pas (Entrée entre scénarios)
    python demo_soutenance.py --fast     # enchaîne sans pause
    python demo_soutenance.py --reset    # repart d'une base vierge
"""

import argparse
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
BASE_URL = "http://127.0.0.1:8000"
DB_PATH = ROOT / "gta_fintech.db"
PASSWORD = "Demo2026gta"

# ── Console Windows : UTF-8 + couleurs ANSI ───────────────────
os.system("")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
R, G, Y, B, M, C, W, DIM, BOLD, END = (
    "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[95m",
    "\033[96m", "\033[97m", "\033[2m", "\033[1m", "\033[0m",
)

DEMO_USERS = {
    "alice": {
        "email": "alice.demo@gta-fintech.com",
        "wallet": "0xA11CE00000000000000000000000000000000001",
        "age_days": 90,
        "avg": 50.0,
        "n_history": 30,
    },
    "bob": {
        "email": "bob.demo@gta-fintech.com",
        "wallet": "0xB0B0000000000000000000000000000000000002",
        "age_days": 45,
        "avg": 120.0,
        "n_history": 20,
    },
    # Mallory : compte créé PENDANT la démo (scénario compte neuf) — pas d'historique
    "mallory": {
        "email": "mallory.demo@gta-fintech.com",
        "wallet": "0x3A110A9000000000000000000000000000000003",
        "age_days": 0,
        "avg": 0.0,
        "n_history": 0,
    },
}

KNOWN_RECEIVERS = [
    "0xCAFE000000000000000000000000000000000010",
    "0xCAFE000000000000000000000000000000000011",
    "0xCAFE000000000000000000000000000000000012",
]
UNKNOWN_RECEIVER = "0xDEAD00000000000000000000000000000000BEEF"[:42]


def titre(txt):
    print(f"\n{BOLD}{C}{'═' * 66}{END}")
    print(f"{BOLD}{C}  {txt}{END}")
    print(f"{BOLD}{C}{'═' * 66}{END}")


def pause(fast, msg="Appuyez sur Entrée pour continuer…"):
    if not fast:
        input(f"{DIM}   {msg}{END}")


def afficher_resultat(payload: dict, attendu_bloque: bool):
    """Affiche le verdict IA d'une transaction envoyée via l'API."""
    bloque = payload.get("blocked", False)
    score = payload.get("risk_score", "?")
    niveau = payload.get("risk_level", "?")
    montant = payload.get("amount", "?")
    couleur = R if bloque else G
    verdict = "✕ BLOQUÉE PAR L'IA" if bloque else "✓ ACCEPTÉE"
    print(f"   {couleur}{BOLD}{verdict}{END}  "
          f"montant={montant} FTK · score IA={score}/100 · niveau={niveau}")
    for raison in payload.get("reasons", []):
        print(f"     {Y}⚠ {raison}{END}")
    ok = bloque == attendu_bloque
    tag = f"{G}[conforme au scénario]{END}" if ok else f"{R}[INATTENDU]{END}"
    print(f"   {DIM}attendu : {'blocage' if attendu_bloque else 'acceptation'} {END}{tag}")
    return ok


# ══════════════════════════════════════════════════════════════
# API helpers
# ══════════════════════════════════════════════════════════════
def api_up(client) -> bool:
    try:
        return client.get(f"{BASE_URL}/health", timeout=2).status_code == 200
    except Exception:
        return False


def start_server(client):
    """Démarre uvicorn dans sa propre fenêtre console et attend /health."""
    print(f"{DIM}   API non détectée — démarrage de uvicorn…{END}")
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(ROOT),
        creationflags=flags,
    )
    for _ in range(60):
        time.sleep(1)
        if api_up(client):
            print(f"   {G}✓ API démarrée sur {BASE_URL}{END}")
            return
    sys.exit(f"{R}Impossible de démarrer l'API — lancez `python main.py` puis relancez.{END}")


def ensure_user(client, email, wallet) -> str:
    """Crée le compte si besoin, retourne un token JWT."""
    client.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": PASSWORD, "wallet_address": wallet},
    )  # 201 ou 409 si déjà créé — peu importe
    r = client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        sys.exit(f"{R}Login impossible pour {email} : {r.text}{END}")
    return r.json()["access_token"]


def send_tx(client, token, receiver, amount) -> dict:
    r = client.post(
        f"{BASE_URL}/transactions/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"receiver": receiver, "amount": amount},
    )
    if r.status_code != 200:
        return {"blocked": True, "risk_score": "?", "risk_level": "ERREUR",
                "amount": amount, "reasons": [r.text[:120]]}
    d = r.json()
    d["amount"] = amount
    return d


# ══════════════════════════════════════════════════════════════
# Historique réaliste (écrit directement dans SQLite, antidaté)
# ══════════════════════════════════════════════════════════════
def seed_history():
    """Antidate les comptes et injecte des transactions passées.

    L'API calcule les features (ancienneté du compte, moyenne des montants,
    fréquence) depuis la base : sans historique, tout le monde ressemblerait
    à un compte neuf. On écrit donc directement dans SQLite des transactions
    LÉGITIMES antidatées, comme si la plateforme tournait depuis des mois.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.utcnow()

    for name, u in DEMO_USERS.items():
        if not u["age_days"]:
            continue  # Mallory reste un compte tout neuf
        created = now - timedelta(days=u["age_days"])
        cur.execute(
            "UPDATE users SET created_at = ? WHERE email = ?",
            (created.strftime("%Y-%m-%d %H:%M:%S"), u["email"]),
        )
        row = cur.execute("SELECT id FROM users WHERE email = ?", (u["email"],)).fetchone()
        if not row:
            continue
        uid = row[0]

        deja = cur.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND status = 'confirmed'",
            (uid,),
        ).fetchone()[0]
        if deja >= u["n_history"]:
            continue  # historique déjà en place (script relancé)

        for i in range(u["n_history"]):
            ts = now - timedelta(days=1 + (u["age_days"] - 2) * (i + 1) / u["n_history"],
                                 hours=(i * 7) % 12)
            montant = round(u["avg"] * (0.6 + 0.8 * ((i * 37) % 100) / 100), 2)
            cur.execute(
                """INSERT INTO transactions
                   (id, user_id, sender, receiver, amount, status,
                    risk_score, risk_level, blocked, approved, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'confirmed', 5, 'LOW', 0, 0, ?, ?)""",
                (
                    str(uuid.uuid4()), uid, u["wallet"],
                    KNOWN_RECEIVERS[i % len(KNOWN_RECEIVERS)], montant,
                    ts.strftime("%Y-%m-%d %H:%M:%S"), ts.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        print(f"   {G}✓{END} {name:<8} — compte antidaté de {u['age_days']} j, "
              f"{u['n_history']} transactions (~{u['avg']:.0f} FTK) injectées")

    con.commit()
    con.close()


# ══════════════════════════════════════════════════════════════
# Scénarios
# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Démo soutenance GTA Fintech")
    parser.add_argument("--fast", action="store_true", help="sans pauses")
    parser.add_argument("--reset", action="store_true", help="repartir d'une base vierge")
    args = parser.parse_args()
    fast = args.fast
    resultats = []

    titre("DÉMONSTRATION — Détection de fraude IA · GTA-IT Fintech")

    with httpx.Client(timeout=30) as client:
        # 0. Serveur
        if args.reset:
            if api_up(client):
                sys.exit(
                    f"{R}--reset : arrêtez d'abord le serveur (la base est ouverte), "
                    f"puis relancez.{END}"
                )
            if DB_PATH.exists():
                try:
                    DB_PATH.unlink()
                    print(f"   {Y}Base supprimée — repart de zéro.{END}")
                except PermissionError:
                    # Windows garde parfois un verrou sur le fichier :
                    # purge SQL des tables, effet équivalent
                    con = sqlite3.connect(DB_PATH, timeout=5)
                    for t in (
                        "fraud_alerts",
                        "transactions",
                        "blockchain_audit_blocks",
                        "password_reset_tokens",
                        "audit_logs",
                        "users",
                    ):
                        con.execute(f"DELETE FROM {t}")
                    con.commit()
                    con.close()
                    print(f"   {Y}Base verrouillée → tables purgées — repart de zéro.{END}")
        if not api_up(client):
            start_server(client)
        else:
            print(f"   {G}✓ API déjà en ligne sur {BASE_URL}{END}")

        # 1. Comptes
        titre("1/6 · Création des comptes de démonstration")
        tokens = {}
        for name, u in DEMO_USERS.items():
            if name == "mallory":
                continue  # créée plus tard, en direct (compte neuf)
            tokens[name] = ensure_user(client, u["email"], u["wallet"])
            print(f"   {G}✓{END} {name:<8} {DIM}{u['email']} · {u['wallet'][:14]}…{END}")

        # 2. Historique
        titre("2/6 · Injection d'un historique réaliste (comptes anciens)")
        seed_history()
        pause(fast)

        # 3. Transaction normale
        titre("3/6 · Scénario témoin — transaction NORMALE d'Alice")
        print(f"   Alice envoie {BOLD}55 FTK{END} à un destinataire habituel "
              f"(≈ sa moyenne de 50 FTK)")
        resultats.append(("Transaction normale",
                          afficher_resultat(send_tx(client, tokens["alice"],
                                                    KNOWN_RECEIVERS[0], 55.0), False)))
        pause(fast)

        # 4. S2 — montant aberrant
        titre("4/6 · Scénario S2 — MONTANT ABERRANT")
        print(f"   Alice (moyenne ≈ 50 FTK) envoie soudain {BOLD}{R}3 000 FTK{END} "
              f"à une adresse inconnue")
        resultats.append(("S2 · Montant aberrant",
                          afficher_resultat(send_tx(client, tokens["alice"],
                                                    UNKNOWN_RECEIVER, 3000.0), True)))
        pause(fast)

        # 5. S1 — rafale
        titre("5/6 · Scénario S1 — RAFALE (compte compromis)")
        print(f"   Bob envoie {BOLD}8 transactions en quelques secondes{END} "
              f"vers des adresses variées")
        bloquees = 0
        derniere = {}
        for i in range(8):
            derniere = send_tx(client, tokens["bob"],
                               f"0x{'F' * 36}{i:04d}", round(150 + 40 * i, 2))
            etat = f"{R}✕ bloquée{END}" if derniere.get("blocked") else f"{G}✓ passée{END}"
            print(f"   envoi {i + 1}/8 : {derniere['amount']:>7} FTK → {etat} "
                  f"(score {derniere.get('risk_score', '?')})")
            bloquees += bool(derniere.get("blocked"))
            time.sleep(0.4)
        print(f"\n   {BOLD}{bloquees}/8 envois bloqués{END} — l'IA détecte "
              f"l'accélération anormale au fil de la rafale")
        for raison in derniere.get("reasons", []):
            print(f"     {Y}⚠ {raison}{END}")
        resultats.append(("S1 · Rafale", bloquees >= 1))
        pause(fast)

        # 6. S3 — compte neuf + S5 — récidive
        titre("6/6 · Scénarios S3 (compte neuf) et S5 (récidiviste)")
        print(f"   Mallory crée son compte {BOLD}à l'instant{END} et tente "
              f"aussitôt de gros envois vers plusieurs inconnus")
        tokens["mallory"] = ensure_user(
            client, DEMO_USERS["mallory"]["email"], DEMO_USERS["mallory"]["wallet"]
        )
        bloquees_m = 0
        derniere_m = {}
        for i in range(4):
            derniere_m = send_tx(client, tokens["mallory"],
                                 f"0x{'E' * 36}{i:04d}", round(800 + 350 * i, 2))
            etat = f"{R}✕ bloquée{END}" if derniere_m.get("blocked") else f"{G}✓ passée{END}"
            print(f"   envoi {i + 1}/4 : {derniere_m['amount']:>7} FTK → {etat} "
                  f"(score {derniere_m.get('risk_score', '?')})")
            bloquees_m += bool(derniere_m.get("blocked"))
            time.sleep(0.4)
        for raison in derniere_m.get("reasons", []):
            print(f"     {Y}⚠ {raison}{END}")
        resultats.append(("S3 · Compte neuf hyperactif", bloquees_m >= 1))

        print(f"\n   Alice, déjà signalée (S2), retente un envoi de "
              f"{BOLD}400 FTK{END} vers un inconnu — récidive")
        resultats.append(("S5 · Récidiviste",
                          afficher_resultat(send_tx(client, tokens["alice"],
                                                    UNKNOWN_RECEIVER, 400.0), True)))

    # Bilan
    titre("BILAN DE LA DÉMONSTRATION")
    for nom, ok in resultats:
        print(f"   {'✓' if ok else '✕'} {G if ok else R}{nom}{END}")
    reussis = sum(ok for _, ok in resultats)
    print(f"\n   {BOLD}{reussis}/{len(resultats)} scénarios conformes{END}")

    print(f"""
{BOLD}À montrer au jury :{END}
   {C}Interface utilisateur{END}  {BASE_URL}/dashboard
       Alice : {DEMO_USERS['alice']['email']} / {PASSWORD}
       → historique, alertes IA et bouton « Détails » (raisons du blocage)

   {C}Console super admin{END}    {BASE_URL}/superadmin
       (identifiants SUPERADMIN_* du fichier .env)
       → transactions bloquées avec « Détails » puis « Autoriser »,
         graphes dynamiques du modèle (courbes, matrice de confusion),
         chaîne d'audit blockchain.
""")


if __name__ == "__main__":
    main()
