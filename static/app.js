/* ══════════════════════════════════════════════════════════════
   app.js — Helpers partagés du shell (sidebar, topbar, session)
   Chargé avant le script propre à chaque page.
   ══════════════════════════════════════════════════════════════ */

function logout() {
  ['token', 'wallet', 'email', 'role'].forEach(k => localStorage.removeItem(k));
  window.location.href = '/';
}

/* Affiche le wallet dans la sidebar, l'email dans la topbar,
   et maintient le badge d'état blockchain à jour. */
function initShell() {
  /* Cloisonnement des rôles : le super admin n'utilise pas les vues
     utilisateur — sa console dispose de ses propres outils (dont l'envoi
     de FTK). Redirection systématique vers /superadmin. */
  if (localStorage.getItem('role') === 'superadmin') {
    window.location.href = '/superadmin';
    return;
  }

  const wallet = localStorage.getItem('wallet');
  const email  = localStorage.getItem('email');

  const walletEl = document.getElementById('sidebarWallet') || document.getElementById('walletChip');
  if (walletEl && wallet) walletEl.textContent = wallet.slice(0, 6) + '…' + wallet.slice(-4);

  const emailEl = document.getElementById('topbarEmail');
  if (emailEl && email) emailEl.textContent = '· ' + email;

  refreshNetworkBadge();
  setInterval(refreshNetworkBadge, 30000);
}

async function refreshNetworkBadge() {
  const badge = document.getElementById('networkBadge');
  const label = document.getElementById('networkLabel');
  if (!badge || !label) return;
  try {
    const r = await fetch('/status');
    const d = await r.json();
    if (d.blockchain_connected) {
      badge.classList.remove('offline');
      label.textContent = 'Ganache · Chain ' + (d.chain_id ?? '—');
    } else {
      badge.classList.add('offline');
      label.textContent = 'Blockchain hors ligne';
    }
  } catch {
    badge.classList.add('offline');
    label.textContent = 'Serveur injoignable';
  }
}
