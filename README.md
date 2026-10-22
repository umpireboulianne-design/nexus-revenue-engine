# Nexus Pulse — Entreprise en Ligne Autonome (API B2B, SaaS & Chasseur de Primes)

Système complet de génération de revenus à **triple moteur**, conçu pour tourner à **0 $ de frais d'API externes** sur votre VPS et générer à la fois des **revenus récurrents (MRR)**, des **montants forfaitaires B2B (150 $ – 490 $)** et des **primes Open-Source en dollars (Cash Bounties)**.

---

## Les 3 Moteurs de Revenus Intégrés

1. **Moteur 1 — API Commerciale d'Intelligence B2B (`DomainPulse API`)**
   - **Monétisation passive sur Marketplaces** :
     - **RapidAPI Hub** : Importez directement [`deploy/openapi_rapidapi.json`](./deploy/openapi_rapidapi.json) sur RapidAPI. La plateforme gère la facturation mensuelle des abonnés (ex: 19 $/mois, 49 $/mois) et vous reverse les revenus.
     - **Apify Store** : Publiez l'outil comme Actor payant au résultat (`apify push`) grâce à [`.actor/actor.json`](./.actor/actor.json) et [`apify_main.py`](./apify_main.py).
2. **Moteur 2 — Chasseur de Primes Cash en Temps Réel (`BountyHunter Radar`)**
   - Scanne en direct GitHub / Algora / Opire pour identifier les issues ouvertes offrant des primes en dollars (`$50` à `$8,000+`).
   - Génère en 1 clic le **Brief d'Exécution Antigravity** : copiez-le et collez-le dans le chat Antigravity pour que l'IA clone le dépôt, code la solution, vérifie les tests et prépare la Pull Request gagnante.
3. **Moteur 3 — Vente Directe de Rapports d'Audit en Marque Blanche & Abonnements SaaS**
   - Génère un rapport exécutif HTML/PDF imprimable (`/api/v1/audit/report-html?url=...`) + l'email de prospection personnalisé prêt à envoyer aux entreprises dont le site présente des failles SEO ou Sécurité.
   - Webhook universel (`POST /api/v1/webhooks/payment`) compatible **Stripe** et **LemonSqueezy** qui crée et active automatiquement la clé API du client dès réception du paiement.

---

## Démarrage Rapide

### 1. En local (déjà préconfiguré avec `uv`)
```powershell
cd C:\Users\Utilisateur\.gemini\antigravity\scratch\nexus-revenue-engine
uv run python cli.py serve --port 8000
```
- **Tableau de bord SaaS & Radar de Primes** : http://localhost:8000
- **Documentation interactive Swagger / OpenAPI** : http://localhost:8000/docs

### 2. Sur votre VPS (Déploiement 1-Clic avec HTTPS automatique)
Copiez ce dossier sur votre VPS Ubuntu/Debian et lancez :
```bash
bash deploy/deploy_vps.sh
```
*(Modifiez [`deploy/Caddyfile`](./deploy/Caddyfile) avec votre nom de domaine pour activer automatiquement le certificat SSL Let's Encrypt).*
