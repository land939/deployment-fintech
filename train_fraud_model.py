"""
train_fraud_model.py — Entraînement du détecteur de fraude FTK
Projet Fintech GTA

Remplace le modèle entraîné sur le dataset Kaggle `creditcard` (features
V1–V28 issues d'une PCA confidentielle, impossibles à calculer pour une
transaction FTK) par un modèle entraîné sur des features RÉELLEMENT
calculables en production à partir des tables `users` et `transactions` :

    amount                 montant de la transaction (FTK)
    hour                   heure de la journée (0–23)
    day_of_week            jour de la semaine (0 = lundi … 6 = dimanche)
    account_age_days       ancienneté du compte expéditeur (jours)
    tx_count_1h            nb de transactions de l'expéditeur dans la dernière heure
    tx_count_24h           nb de transactions de l'expéditeur dans les dernières 24 h
    amount_avg_ratio       montant / moyenne des montants LÉGITIMES de l'expéditeur
                           (les transactions bloquées sont exclues de la moyenne)
    seconds_since_last_tx  délai depuis la transaction précédente (plafonné à 7 jours)
    is_new_receiver        1 si l'expéditeur n'a jamais envoyé à ce destinataire
    unique_receivers_24h   nb de destinataires distincts sur 24 h
    past_fraud_count       nb de transactions déjà bloquées pour fraude (récidive)

Comme il n'existe pas de dataset public avec ces features pour un token
maison, le script GÉNÈRE UN DATASET SYNTHÉTIQUE : simulation de flux de
transactions par utilisateur (profils plausibles de montants, fréquences
et horaires), dans lequel sont injectés des scénarios de fraude étiquetés :

    S1  Rafale            compte compromis : 5–15 envois en quelques minutes
    S2  Montant aberrant  envoi à 10–80× la moyenne historique de l'utilisateur
    S3  Compte neuf       compte < 48 h hyperactif vers de nombreux destinataires
    S4  Vidage nocturne   gros envois répétés entre 1 h et 5 h vers un inconnu
    S5  Récidiviste       utilisateur déjà signalé qui recommence

Le pipeline de production reste identique : `models/scaler.pkl` +
`models/fraud_detector.pkl` + `models/feature_columns.json` — seules
les colonnes changent.

Usage : python train_fraud_model.py
"""

import json
import os
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

RNG = np.random.default_rng(42)

FEATURE_COLS = [
    "amount",
    "hour",
    "day_of_week",
    "account_age_days",
    "tx_count_1h",
    "tx_count_24h",
    "amount_avg_ratio",
    "seconds_since_last_tx",
    "is_new_receiver",
    "unique_receivers_24h",
    "past_fraud_count",
]

# Paramètres de simulation ─────────────────────────────────────
N_USERS = 300  # utilisateurs « normaux »
N_NEW_FRAUDSTERS = 18  # comptes neufs hyperactifs (scénario S3)
SIM_DAYS = 120  # fenêtre de simulation
SIM_START = datetime(2026, 1, 1)
CAP_SILENCE_S = 7 * 86400  # plafond du délai depuis la dernière tx

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
# Graphiques d'évaluation servis par le dashboard admin (fichiers statiques)
PLOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "models")


# ══════════════════════════════════════════════════════════════
# 1. SIMULATION DES PROFILS UTILISATEURS
# ══════════════════════════════════════════════════════════════
def _random_wallet(n):
    """n adresses hexadécimales factices (identifiants de destinataires)."""
    return [f"0x{RNG.integers(0, 2**32):08x}" for _ in range(n)]


def make_users():
    """Profils plausibles : montant moyen, fréquence, horaires, destinataires."""
    users = []
    receiver_pool = _random_wallet(1200)
    for uid in range(N_USERS):
        n_known = int(RNG.integers(3, 9))
        users.append(
            {
                "uid": uid,
                # certains comptes existent avant la fenêtre, d'autres sont créés pendant
                "created": SIM_START + timedelta(days=float(RNG.uniform(-360, SIM_DAYS - 5))),
                "avg_amount": float(RNG.lognormal(np.log(45), 0.9)),  # ~10–300 FTK
                "tx_per_day": float(RNG.gamma(2.0, 0.6)),  # ~0.2–4 tx/jour
                "pref_hour": float(RNG.normal(14, 4)) % 24,  # activité diurne
                "known_recv": list(RNG.choice(receiver_pool, n_known, replace=False)),
            }
        )
    return users, receiver_pool


def normal_amount(user):
    """Montant habituel, avec une queue de gros achats légitimes (~2 %)."""
    amount = float(RNG.lognormal(np.log(user["avg_amount"]), 0.5))
    if RNG.random() < 0.02:
        amount *= float(RNG.uniform(3, 6))
    return round(max(amount, 1.0), 2)


def normal_timestamp(user, day):
    """Timestamp dans la journée `day`, centré sur l'heure préférée."""
    hour = (RNG.normal(user["pref_hour"], 3.0)) % 24
    return SIM_START + timedelta(
        days=int(day),
        hours=float(hour),
        minutes=float(RNG.uniform(0, 59)),
        seconds=float(RNG.uniform(0, 59)),
    )


def pick_receiver(user, receiver_pool):
    """90 % vers un destinataire connu, 10 % vers un nouveau (légitime)."""
    if RNG.random() < 0.90 and user["known_recv"]:
        return str(RNG.choice(user["known_recv"]))
    return str(RNG.choice(receiver_pool))


def simulate_normal_events(users, receiver_pool):
    """Flux de transactions légitimes (label 0), avec sessions multi-envois."""
    events = []
    for user in users:
        first_day = max(0.0, (user["created"] - SIM_START).total_seconds() / 86400)

        # Onboarding : un utilisateur légitime fraîchement inscrit essaie
        # souvent 1 à 3 petits envois dans les minutes/heures qui suivent
        # (il vient de recevoir ses 1000 FTK). Sans ces exemples, le modèle
        # apprendrait « compte de quelques minutes = fraude » et bloquerait
        # la première transaction de chaque nouvel inscrit.
        if user["created"] >= SIM_START and RNG.random() < 0.75:
            for _ in range(int(RNG.integers(1, 4))):
                ts = user["created"] + timedelta(minutes=float(RNG.uniform(2, 360)))
                amount = round(min(normal_amount(user), 200.0), 2)
                events.append((user["uid"], ts, amount, pick_receiver(user, receiver_pool), 0))
        for day in range(int(first_day), SIM_DAYS):
            for _ in range(RNG.poisson(user["tx_per_day"])):
                ts = normal_timestamp(user, day)
                if ts < user["created"]:
                    continue
                events.append(
                    (user["uid"], ts, normal_amount(user), pick_receiver(user, receiver_pool), 0)
                )
                # sessions légitimes : parfois 1–3 envois rapprochés
                # (loyers, remboursements de groupe…) — évite que la seule
                # fréquence horaire suffise à séparer les classes
                if RNG.random() < 0.15:
                    for _ in range(int(RNG.integers(1, 4))):
                        ts2 = ts + timedelta(minutes=float(RNG.uniform(2, 30)))
                        events.append(
                            (
                                user["uid"],
                                ts2,
                                normal_amount(user),
                                pick_receiver(user, receiver_pool),
                                0,
                            )
                        )
    return events


# ══════════════════════════════════════════════════════════════
# 2. INJECTION DES SCÉNARIOS DE FRAUDE (label 1)
# ══════════════════════════════════════════════════════════════
def fraud_timestamp(user, night=False):
    first_day = max(0, int((user["created"] - SIM_START).total_seconds() // 86400) + 1)
    day = int(RNG.uniform(min(first_day, SIM_DAYS - 1), SIM_DAYS))
    hour = float(RNG.uniform(1, 5)) if night else float(RNG.uniform(0, 24))
    return SIM_START + timedelta(days=day, hours=hour, minutes=float(RNG.uniform(0, 59)))


def inject_frauds(users, receiver_pool):
    events = []

    # S1 — Rafale : compte compromis, 5–15 envois en quelques minutes
    for user in RNG.choice(users, 30, replace=False):
        ts0 = fraud_timestamp(user)
        for i in range(int(RNG.integers(5, 16))):
            ts = ts0 + timedelta(minutes=float(RNG.uniform(0.5, 4)) * i)
            amount = round(float(RNG.lognormal(np.log(user["avg_amount"] * 2), 0.6)), 2)
            events.append((user["uid"], ts, amount, str(RNG.choice(receiver_pool)), 1))

    # S2 — Montant aberrant : 10–80× la moyenne de l'utilisateur
    for user in RNG.choice(users, 60, replace=False):
        ts = fraud_timestamp(user, night=RNG.random() < 0.5)
        amount = round(user["avg_amount"] * float(RNG.uniform(10, 80)), 2)
        events.append((user["uid"], ts, amount, str(RNG.choice(receiver_pool)), 1))

    # S4 — Vidage nocturne : 2–4 gros envois entre 1 h et 5 h vers le même inconnu
    for user in RNG.choice(users, 25, replace=False):
        ts0 = fraud_timestamp(user, night=True)
        receiver = str(RNG.choice(receiver_pool))
        for i in range(int(RNG.integers(2, 5))):
            ts = ts0 + timedelta(minutes=float(RNG.uniform(3, 15)) * i)
            amount = round(user["avg_amount"] * float(RNG.uniform(5, 20)), 2)
            events.append((user["uid"], ts, amount, receiver, 1))

    # S5 — Récidiviste : une première fraude, puis de nouvelles tentatives
    for user in RNG.choice(users, 20, replace=False):
        ts0 = fraud_timestamp(user)
        events.append(
            (user["uid"], ts0, round(user["avg_amount"] * 15, 2), str(RNG.choice(receiver_pool)), 1)
        )
        for _ in range(int(RNG.integers(2, 5))):
            ts = ts0 + timedelta(days=float(RNG.uniform(1, 20)))
            amount = round(user["avg_amount"] * float(RNG.uniform(4, 12)), 2)
            events.append((user["uid"], ts, amount, str(RNG.choice(receiver_pool)), 1))

    return events


def make_new_fraudster_events(receiver_pool, start_uid):
    """S3 — Comptes neufs hyperactifs : créés depuis < 48 h, 10–30 tx/jour."""
    users, events = [], []
    for k in range(N_NEW_FRAUDSTERS):
        uid = start_uid + k
        created = SIM_START + timedelta(days=float(RNG.uniform(5, SIM_DAYS - 4)))
        user = {
            "uid": uid,
            "created": created,
            "avg_amount": float(RNG.lognormal(np.log(60), 0.5)),
            "tx_per_day": 0.0,
            "pref_hour": 14.0,
            "known_recv": [],
        }
        users.append(user)
        active_days = float(RNG.uniform(0.5, 2.5))
        n_tx = int(RNG.integers(15, 50))
        for _ in range(n_tx):
            ts = created + timedelta(days=float(RNG.uniform(0.01, active_days)))
            amount = round(float(RNG.lognormal(np.log(user["avg_amount"] * 3), 0.7)), 2)
            events.append((uid, ts, amount, str(RNG.choice(receiver_pool)), 1))
    return users, events


# ══════════════════════════════════════════════════════════════
# 3. CALCUL DES FEATURES (même logique qu'en production)
# ══════════════════════════════════════════════════════════════
def compute_features(all_users, events):
    """
    Parcourt les événements de chaque utilisateur en ordre chronologique et
    calcule, pour chaque transaction, les features telles qu'elles seraient
    calculées en production à partir de l'historique en base.
    """
    users_by_id = {u["uid"]: u for u in all_users}
    by_user = {}
    for ev in events:
        by_user.setdefault(ev[0], []).append(ev)

    rows = []
    for uid, evs in by_user.items():
        evs.sort(key=lambda e: e[1])
        user = users_by_id[uid]
        history = []  # [(ts, amount, receiver, label), ...]
        for _, ts, amount, receiver, label in evs:
            prev_1h = [h for h in history if (ts - h[0]).total_seconds() <= 3600]
            prev_24h = [h for h in history if (ts - h[0]).total_seconds() <= 86400]
            # Moyenne sur l'historique LÉGITIME uniquement : une fraude déjà
            # bloquée ne définit pas le comportement normal de l'utilisateur
            # (sinon un gros montant bloqué gonfle la moyenne et camoufle
            # les fraudes suivantes). Même définition dans services/ml/features.py.
            legit = [h[1] for h in history if h[3] == 0]
            avg_amt = float(np.mean(legit)) if legit else amount

            rows.append(
                {
                    "amount": amount,
                    "hour": ts.hour,
                    "day_of_week": ts.weekday(),
                    "account_age_days": max(0.0, (ts - user["created"]).total_seconds() / 86400),
                    "tx_count_1h": len(prev_1h),
                    "tx_count_24h": len(prev_24h),
                    "amount_avg_ratio": amount / avg_amt if avg_amt > 0 else 1.0,
                    "seconds_since_last_tx": min(
                        (ts - history[-1][0]).total_seconds(), CAP_SILENCE_S
                    )
                    if history
                    else CAP_SILENCE_S,
                    "is_new_receiver": 0 if any(h[2] == receiver for h in history) else 1,
                    "unique_receivers_24h": len({h[2] for h in prev_24h}),
                    "past_fraud_count": sum(1 for h in history if h[3] == 1),
                    "label": label,
                }
            )
            history.append((ts, amount, receiver, label))
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════
# 4. ENTRAÎNEMENT + ÉVALUATION
# ══════════════════════════════════════════════════════════════
def evaluate(name, model, X_test, y_test):
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    print(f"\n--- {name} " + "-" * (50 - len(name)))
    print(
        f"ROC-AUC : {roc_auc_score(y_test, proba):.4f}   "
        f"PR-AUC : {average_precision_score(y_test, proba):.4f}"
    )
    print(confusion_matrix(y_test, pred))
    print(classification_report(y_test, pred, target_names=["normal", "fraude"], digits=3))
    # Taux de blocage aux seuils utilisés en production (bloqué si proba >= 0.60)
    blocked = proba >= 0.60
    frauds = y_test.values == 1
    print(
        f"Seuil production (0.60) : {blocked[frauds].mean() * 100:.1f}% des fraudes bloquées, "
        f"{blocked[~frauds].mean() * 100:.2f}% de faux positifs bloqués"
    )
    return roc_auc_score(y_test, proba)


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("1/4  Génération du dataset synthétique…")
    users, receiver_pool = make_users()
    events = simulate_normal_events(users, receiver_pool)
    events += inject_frauds(users, receiver_pool)
    new_users, new_events = make_new_fraudster_events(receiver_pool, start_uid=N_USERS)
    events += new_events

    df = compute_features(users + new_users, events)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    n_fraud = int(df["label"].sum())
    print(f"     {len(df)} transactions, dont {n_fraud} fraudes ({n_fraud / len(df) * 100:.2f}%)")

    dataset_path = os.path.join(MODELS_DIR, "synthetic_fraud_dataset.csv")
    df.to_csv(dataset_path, index=False)
    print(f"     Dataset sauvegardé : {dataset_path}")

    print("2/4  Préparation train/test…")
    X = df[FEATURE_COLS]
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42
    )

    # Les arbres n'exigent pas de normalisation, mais le pipeline de
    # production (scaler + modèle) est conservé à l'identique.
    scaler = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train), columns=FEATURE_COLS)
    X_test_s = pd.DataFrame(scaler.transform(X_test), columns=FEATURE_COLS)

    print("3/5  Entraînement XGBoost + RandomForest…")
    spw = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    xgb = XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=spw,
        eval_metric=["logloss", "error"],
        random_state=42,
    )
    # eval_set : suivi de la log-loss et de l'erreur à chaque itération de
    # boosting, sur le train ET la validation → courbes accuracy/loss
    xgb.fit(X_train_s, y_train, eval_set=[(X_train_s, y_train), (X_test_s, y_test)], verbose=False)
    history = xgb.evals_result()

    rf = RandomForestClassifier(
        n_estimators=300, class_weight="balanced_subsample", random_state=42, n_jobs=-1
    )
    rf.fit(X_train_s, y_train)

    auc_xgb = evaluate("XGBoost", xgb, X_test_s, y_test)
    auc_rf = evaluate("RandomForest", rf, X_test_s, y_test)

    print("\n4/5  Calcul des indicateurs de performance…")
    proba = xgb.predict_proba(X_test_s)[:, 1]
    pred = (proba >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()
    metrics = {
        "modele": "XGBoost_v2",
        "entraine_le": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "part_fraude_pct": round(float(y.mean()) * 100, 2),
        "exactitude": round(float((tp + tn) / (tp + tn + fp + fn)), 4),
        "precision": round(float(precision_score(y_test, pred)), 4),
        "sensibilite": round(float(recall_score(y_test, pred)), 4),
        "specificite": round(float(tn / (tn + fp)), 4),
        "f1_score": round(float(f1_score(y_test, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_test, proba)), 4),
        "matrice": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "hyperparametres": {
            "n_estimators": 400,
            "max_depth": 6,
            "learning_rate": 0.08,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "scale_pos_weight": round(spw, 1),
            "optimisation": "Gradient boosting — descente de gradient sur la log-loss",
        },
    }
    with open(os.path.join(MODELS_DIR, "model_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    for k in ("exactitude", "precision", "sensibilite", "specificite", "f1_score", "roc_auc"):
        print(f"     {k:<12}: {metrics[k]}")

    print("\n5/5  Sauvegarde des artefacts et graphiques…")
    joblib.dump(xgb, os.path.join(MODELS_DIR, "xgboost.pkl"))
    joblib.dump(rf, os.path.join(MODELS_DIR, "random_forest.pkl"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler.pkl"))
    # Modèle de production : XGBoost (features réellement calculables)
    joblib.dump(xgb, os.path.join(MODELS_DIR, "fraud_detector.pkl"))
    with open(os.path.join(MODELS_DIR, "feature_columns.json"), "w") as f:
        json.dump(FEATURE_COLS, f, indent=2)

    try:
        make_plots(xgb, history, tn, fp, fn, tp, metrics)
        print(f"     Graphiques : {PLOTS_DIR}")
    except ImportError:
        print("     matplotlib absent — graphiques non générés")

    print(
        f"\nTerminé. Modèle de production : XGBoost (ROC-AUC {auc_xgb:.4f}) "
        f"vs RandomForest ({auc_rf:.4f})"
    )
    print(
        "Artefacts : models/fraud_detector.pkl, models/scaler.pkl, "
        "models/feature_columns.json, models/model_metrics.json"
    )


# ══════════════════════════════════════════════════════════════
# 5. GRAPHIQUES D'ÉVALUATION (dashboard admin + rapport)
# ══════════════════════════════════════════════════════════════
def make_plots(xgb, history, tn, fp, fn, tp, metrics):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    os.makedirs(PLOTS_DIR, exist_ok=True)
    ROUGE, BLEU, GRIS = "#CC0000", "#2B6CB0", "#4A5568"

    # ── Courbes accuracy / loss (entraînement vs validation) ──
    it = range(1, len(history["validation_0"]["logloss"]) + 1)
    acc_train = [1 - e for e in history["validation_0"]["error"]]
    acc_val = [1 - e for e in history["validation_1"]["error"]]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax1.plot(it, acc_train, color=BLEU, label="Entraînement")
    ax1.plot(it, acc_val, color=ROUGE, label="Validation")
    ax1.set_title("Exactitude (accuracy) par itération de boosting")
    ax1.set_xlabel("Itération (arbre ajouté)")
    ax1.set_ylabel("Exactitude")
    ax1.legend()
    ax1.grid(alpha=0.25)
    ax2.plot(it, history["validation_0"]["logloss"], color=BLEU, label="Entraînement")
    ax2.plot(it, history["validation_1"]["logloss"], color=ROUGE, label="Validation")
    ax2.set_title("Perte (log-loss) par itération de boosting")
    ax2.set_xlabel("Itération (arbre ajouté)")
    ax2.set_ylabel("Log-loss")
    ax2.legend()
    ax2.grid(alpha=0.25)
    fig.suptitle("XGBoost_v2 — courbes d'apprentissage", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "training_curves.png"), dpi=120)
    plt.close(fig)

    # ── Matrice de confusion ──
    fig, ax = plt.subplots(figsize=(5.5, 4.8))
    cm = np.array([[tn, fp], [fn, tp]])
    im = ax.imshow(cm, cmap="Reds")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Prédit : normal", "Prédit : fraude"])
    ax.set_yticklabels(["Réel : normal", "Réel : fraude"])
    for i in range(2):
        for j in range(2):
            ax.text(
                j,
                i,
                f"{cm[i, j]:,}".replace(",", " "),
                ha="center",
                va="center",
                fontsize=15,
                fontweight="bold",
                color="white" if cm[i, j] > cm.max() / 2 else "#1A202C",
            )
    ax.set_title("Matrice de confusion — jeu de test", fontweight="bold")
    fig.colorbar(im, shrink=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "confusion_matrix.png"), dpi=120)
    plt.close(fig)

    # ── Importance des features ──
    order = np.argsort(xgb.feature_importances_)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(np.array(FEATURE_COLS)[order], xgb.feature_importances_[order], color=ROUGE)
    ax.set_title("Importance des features — XGBoost_v2 (fraude FTK)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "feature_importance.png"), dpi=120)
    fig.savefig(os.path.join(MODELS_DIR, "feature_importance.png"), dpi=120)
    plt.close(fig)

    # ── Schéma explicatif global du pipeline ──
    fig, ax = plt.subplots(figsize=(13, 5.4))
    ax.axis("off")

    def boite(x, y, w, h, titre, corps, couleur):
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.012",
                facecolor=couleur,
                edgecolor="none",
                alpha=0.12,
            )
        )
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.012",
                facecolor="none",
                edgecolor=couleur,
                linewidth=1.6,
            )
        )
        ax.text(
            x + w / 2,
            y + h - 0.075,
            titre,
            ha="center",
            va="top",
            fontsize=9.5,
            fontweight="bold",
            color=couleur,
        )
        ax.text(
            x + w / 2,
            y + h / 2 - 0.05,
            corps,
            ha="center",
            va="center",
            fontsize=7.6,
            color="#1A202C",
            linespacing=1.5,
        )

    def fleche(x1, y1, x2, y2, couleur=GRIS):
        ax.add_patch(
            FancyArrowPatch(
                (x1, y1),
                (x2, y2),
                arrowstyle="-|>",
                mutation_scale=16,
                color=couleur,
                linewidth=1.5,
            )
        )

    boite(
        0.01,
        0.55,
        0.16,
        0.38,
        "TRANSACTION FTK",
        "montant, destinataire,\nheure d'envoi\n(POST /transactions/send)",
        GRIS,
    )
    boite(
        0.21,
        0.55,
        0.18,
        0.38,
        "FEATURES (x11)",
        "historique du wallet en base :\nfréquence 1h/24h, ratio montant,\nancienneté, récidive…",
        BLEU,
    )
    boite(
        0.43, 0.55, 0.13, 0.38, "STANDARDSCALER", "normalisation\n(moyenne 0, écart-type 1)", BLEU
    )
    boite(
        0.60,
        0.55,
        0.19,
        0.38,
        "XGBOOST_v2",
        "400 arbres · profondeur 6 · lr 0.08\nGradient boosting : descente de\ngradient sur la log-loss\n(scale_pos_weight pour le déséquilibre)",
        ROUGE,
    )
    boite(0.83, 0.55, 0.16, 0.38, "PROBABILITÉ", "p(fraude) ∈ [0, 1]\nscore = p × 100", ROUGE)
    boite(
        0.30,
        0.04,
        0.40,
        0.36,
        "SEUILS DE DÉCISION",
        "p < 0.30 : LOW · p < 0.60 : MEDIUM  →  transaction acceptée\n"
        "p ≥ 0.60 : HIGH · p ≥ 0.85 : CRITICAL  →  TRANSACTION BLOQUÉE",
        GRIS,
    )
    boite(
        0.74,
        0.04,
        0.25,
        0.36,
        "SI BLOQUÉE",
        "FraudRegistry on-chain (Ganache)\n+ bloc d'audit immuable\n+ email au super admin\n→ revue manuelle : Autoriser",
        ROUGE,
    )

    fleche(0.17, 0.74, 0.21, 0.74)
    fleche(0.39, 0.74, 0.43, 0.74)
    fleche(0.56, 0.74, 0.60, 0.74)
    fleche(0.79, 0.74, 0.83, 0.74)
    fleche(0.91, 0.55, 0.62, 0.40)
    fleche(0.70, 0.22, 0.74, 0.22)

    ax.set_title(
        "Schéma global — pipeline de détection de fraude IA → Blockchain (GTA-IT Fintech)",
        fontweight="bold",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "model_schema.png"), dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
