"""Envoi d'emails transactionnels (SMTP).

Le mot de passe de réinitialisation part par SMTP (Gmail + mot de passe
d'application dans .env). Si l'envoi est désactivé (ENABLE_EMAIL=false) ou
que la config est incomplète, le lien est simplement journalisé — le flux
/auth/forgot-password reste fonctionnel en local sans boîte mail.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import Settings

logger = logging.getLogger(__name__)


def email_configured(settings: Settings) -> bool:
    """Vrai si tous les réglages SMTP nécessaires sont présents."""
    return bool(
        settings.enable_email
        and settings.mail_server
        and settings.mail_port
        and settings.mail_username
        and settings.mail_password
    )


def build_fraud_alert_email_html(
    tx_ref: str,
    sender: str,
    receiver: str,
    amount: float,
    risk_score: int,
    risk_level: str,
    reasons: list[str],
) -> str:
    """Email HTML envoyé au super admin quand l'IA bloque une transaction."""
    reasons_html = "".join(
        f'<li style="margin:0.3rem 0; color:#2D3748;">{r}</li>' for r in reasons
    ) or "<li>Comportement jugé anormal par le modèle</li>"
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: linear-gradient(90deg, #CC0000, #E53E3E); padding: 4px;"></div>
      <div style="padding: 2rem; background:#F5F7FA;">
        <h2 style="color:#1A202C;">🚨 Fraude détectée transaction bloquée</h2>
        <p style="color:#2D3748; font-size:0.95rem;">
          Le modèle IA <b>XGBoost_v2</b> vient de bloquer une transaction sur
          <b>GTA-IT Fintech</b>. Elle attend votre revue dans la console super admin.
        </p>
        <table style="width:100%; border-collapse:collapse; font-size:0.9rem; background:#fff;
                      border:1px solid #E2E8F0; border-radius:8px;">
          <tr><td style="padding:0.5rem 0.8rem; color:#718096;">Référence</td>
              <td style="padding:0.5rem 0.8rem; font-family:monospace;">{tx_ref}</td></tr>
          <tr><td style="padding:0.5rem 0.8rem; color:#718096;">Expéditeur</td>
              <td style="padding:0.5rem 0.8rem; font-family:monospace;">{sender}</td></tr>
          <tr><td style="padding:0.5rem 0.8rem; color:#718096;">Destinataire</td>
              <td style="padding:0.5rem 0.8rem; font-family:monospace;">{receiver}</td></tr>
          <tr><td style="padding:0.5rem 0.8rem; color:#718096;">Montant</td>
              <td style="padding:0.5rem 0.8rem;"><b>{amount:.2f} FTK</b></td></tr>
          <tr><td style="padding:0.5rem 0.8rem; color:#718096;">Score IA</td>
              <td style="padding:0.5rem 0.8rem; color:#CC0000;"><b>{risk_score}/100 ({risk_level})</b></td></tr>
        </table>
        <h3 style="color:#1A202C; margin-top:1.2rem;">Facteurs de risque détectés</h3>
        <ul style="padding-left:1.2rem;">{reasons_html}</ul>
        <p style="text-align:center; margin: 1.6rem 0 0.4rem;">
          <a href="http://localhost:8000/superadmin"
             style="background:#CC0000; color:#fff; text-decoration:none; padding:0.8rem 1.5rem;
                    border-radius:8px; font-weight:bold; display:inline-block;">
            Ouvrir la console super admin
          </a>
        </p>
      </div>
      <div style="background:#2D3748; color:#fff; padding:1rem; text-align:center; font-size:0.8rem;">
        <p>© 2026 GTA-IT Fintech alerte automatique, ne pas répondre.</p>
      </div>
    </div>
    """


def send_email(settings: Settings, to: str, subject: str, html: str) -> bool:
    """Envoie un email HTML. Retourne True si parti, False sinon (loggé)."""
    if not email_configured(settings):
        logger.warning(
            "SMTP non configuré ou désactivé (ENABLE_EMAIL/MAIL_*) — email '%s' non envoyé à %s",
            subject,
            to,
        )
        return False

    sender = settings.mail_from or settings.mail_username
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"GTA-IT Fintech <{sender}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_password)
            smtp.sendmail(sender, [to], msg.as_string())
        logger.info("📧 Email '%s' envoyé à %s", subject, to)
        return True
    except Exception as e:
        logger.error("Échec envoi email à %s : %s", to, e)
        return False
