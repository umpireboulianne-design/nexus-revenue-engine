function switchTab(tabId, btnEl) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
  btnEl.classList.add('active');
}

async function runSingleAudit() {
  const urlInput = document.getElementById('audit-url-input');
  const statusEl = document.getElementById('audit-status');
  const resultEl = document.getElementById('audit-result');
  const target = urlInput.value.trim();
  if (!target) return;

  statusEl.textContent = "Analyse B2B en cours (SSL, Headers, Stack, SEO, Emails & Pitch)...";
  resultEl.style.display = "none";

  try {
    const resp = await fetch('/api/v1/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: target, save_lead: true })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Erreur API');

    statusEl.textContent = "";
    resultEl.style.display = "block";

    const emails = (data.contacts.emails || []).join(', ') || 'Aucun email public direct sur la page d\'accueil';
    const stack = (data.tech_stack || []).join(', ') || 'Stack standard';
    const weaknesses = (data.sales_intelligence.critical_weaknesses || []).map(w => `<li>${w}</li>`).join('');

    resultEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
        <div>
          <h3 style="margin:0;font-size:20px;">Résultat pour ${data.domain}</h3>
          <div style="color:#94a3b8;font-size:13px;">URL finale : ${data.final_url} • Temps : ${data.performance.response_time_ms} ms</div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <a class="btn btn-outline" href="/api/v1/audit/report-html?url=${encodeURIComponent(data.domain)}" target="_blank">
            1. Rapport d'Audit (Pour Prospecter)
          </a>
          <a class="btn btn-emerald" href="/api/v1/audit/remediation-html?url=${encodeURIComponent(data.domain)}" target="_blank">
            2. Livrable Correctif Clé-en-Main (Vendable ${data.sales_intelligence.estimated_fix_fee_usd} $)
          </a>
        </div>
      </div>

      <div class="kpi-grid" style="margin-bottom:16px;">
        <div class="kpi-card"><div class="kpi-label">Score Global</div><div class="kpi-value">${data.scores.overall}/100</div></div>
        <div class="kpi-card"><div class="kpi-label">Score SEO</div><div class="kpi-value">${data.scores.seo}/100</div></div>
        <div class="kpi-card"><div class="kpi-label">Score Sécurité</div><div class="kpi-value">${data.scores.security}/100</div></div>
        <div class="kpi-card"><div class="kpi-label">Valeur Forfait Estimée</div><div class="kpi-value" style="color:#10b981;">${data.sales_intelligence.estimated_fix_fee_usd} $</div></div>
      </div>

      <p><strong>Stack Technologique détectée :</strong> ${stack}</p>
      <p><strong>Emails B2B extraits :</strong> ${emails}</p>
      <p><strong>Failles critiques à facturer :</strong></p>
      <ul>${weaknesses}</ul>

      <div style="margin-top:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong>Email de Prospection B2B Prêt à Envoyer (Cold Pitch) :</strong>
          <button class="btn btn-outline" onclick="copyText('pitch-text-area')">Copier l'Email</button>
        </div>
        <div id="pitch-text-area" class="pitch-box">Objet : ${data.sales_intelligence.cold_email_pitch.subject}\n\n${data.sales_intelligence.cold_email_pitch.body}</div>
      </div>
    `;
  } catch (err) {
    statusEl.textContent = "Erreur : " + err.message;
  }
}

async function scanLiveBounties() {
  const filterInput = document.getElementById('bounty-filter-input').value.trim();
  const minUsd = document.getElementById('bounty-min-input').value || 25;
  const statusEl = document.getElementById('bounty-status');
  const tbody = document.getElementById('bounty-tbody');

  statusEl.textContent = "Interrogation de GitHub / Algora / Opire en temps réel...";
  try {
    const url = `/api/v1/bounties/live?min_reward_usd=${encodeURIComponent(minUsd)}&query_filter=${encodeURIComponent(filterInput)}`;
    const resp = await fetch(url);
    const data = await resp.json();
    statusEl.textContent = `${data.count} primes actives détectées pour un total cumulé de ${data.total_pool_usd} $ USD.`;

    tbody.innerHTML = "";
    (data.bounties || []).forEach((b, idx) => {
      const promptId = `bounty-prompt-${idx}`;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="badge badge-green" style="font-size:14px;">${b.reward_usd} $</span></td>
        <td><span class="badge badge-blue">${b.source_platform}</span><div style="font-size:12px;color:#94a3b8;margin-top:4px;">${b.language}</div></td>
        <td>
          <a href="${b.html_url}" target="_blank" style="color:#60a5fa;font-weight:600;text-decoration:none;">${b.title}</a>
          <div style="font-size:12px;color:#94a3b8;">${b.repo_full_name} • ${b.comments_count} commentaire(s) • Score ROI: ${b.roi_score}</div>
          <textarea id="${promptId}" style="display:none;">${b.antigravity_prompt}</textarea>
        </td>
        <td>
          <button class="btn btn-outline" onclick="copyPrompt('${promptId}')">Copier Brief Antigravity</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    statusEl.textContent = "Erreur lors du scan : " + err.message;
  }
}

async function runBatchAudit() {
  const raw = document.getElementById('batch-urls-input').value;
  const urls = raw.split('\n').map(u => u.trim()).filter(Boolean);
  const statusEl = document.getElementById('batch-status');
  const tbody = document.getElementById('batch-tbody');
  if (!urls.length) return;

  statusEl.textContent = `Analyse parallèle de ${urls.length} domaine(s) en cours...`;
  try {
    const resp = await fetch('/api/v1/audit/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls })
    });
    const data = await resp.json();
    statusEl.textContent = `Terminé : ${data.scanned_count} sites audités • Potentiel de facturation B2B : ${data.total_estimated_pipeline_usd} $ USD.`;
    tbody.innerHTML = "";
    (data.results || []).forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${r.domain}</strong><div style="font-size:12px;color:#94a3b8;">${(r.tech_stack || []).slice(0,3).join(', ')}</div></td>
        <td>${r.scores.overall}/100 (SEO ${r.scores.seo} / Sec ${r.scores.security})</td>
        <td>${(r.contacts.emails || []).slice(0,2).join(', ') || 'Via formulaire'}</td>
        <td><span class="badge badge-green">${r.sales_intelligence.estimated_fix_fee_usd} $</span></td>
        <td>
          <a class="btn btn-outline" href="/api/v1/audit/report-html?url=${encodeURIComponent(r.domain)}" target="_blank">Audit</a>
          <a class="btn btn-emerald" href="/api/v1/audit/remediation-html?url=${encodeURIComponent(r.domain)}" target="_blank">Livrable</a>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    statusEl.textContent = "Erreur : " + err.message;
  }
}

async function simulateWebhookSale() {
  const email = document.getElementById('sim-email').value || 'client.pro@entreprise.fr';
  const plan = document.getElementById('sim-plan').value || 'pro';
  const amount = parseFloat(document.getElementById('sim-amount').value || '29');
  const resEl = document.getElementById('sim-result');

  const resp = await fetch('/api/v1/webhooks/payment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      provider: 'Stripe/LemonSqueezy',
      customer_email: email,
      plan_code: plan,
      amount_usd: amount
    })
  });
  const data = await resp.json();
  resEl.textContent = `Clé API générée automatiquement : ${data.api_key_provisioned.api_key} (+${amount} $ enregistrés). Rechargez la page pour voir les KPIs mis à jour.`;
}

function copyText(elId) {
  const text = document.getElementById(elId).innerText;
  navigator.clipboard.writeText(text);
  alert("Copié dans le presse-papiers !");
}

function copyPrompt(elId) {
  const text = document.getElementById(elId).value;
  navigator.clipboard.writeText(text);
  alert("Brief d'exécution copié ! Collez-le directement dans Antigravity pour que je code la solution et prépare la Pull Request.");
}
