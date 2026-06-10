# WireMetry — Fiche Technique

**Plateforme de supervision et d'analyse des réseaux Wi-Fi d'entreprise**
*Wireless Intelligence — multi-constructeur*

---

## 1. Présentation

**WireMetry** est une solution de supervision, de diagnostic et d'aide à la décision pour
les infrastructures Wi-Fi pilotées par contrôleur (WLC). Elle agrège en temps réel l'état
des points d'accès, des clients et de l'environnement radio, détecte les anomalies de
sécurité et de performance, et fournit des recommandations concrètes d'optimisation.

Conçue pour être **agnostique du constructeur**, WireMetry supervise aujourd'hui les
contrôleurs **Cisco Catalyst 9800** et **Ruckus SmartZone** à partir d'une interface unique.

| | |
|---|---|
| **Type de produit** | Application web de supervision Wi-Fi (on-premise) |
| **Déploiement** | Conteneurisé (Docker) sur serveur Linux / VM |
| **Accès** | Navigateur web — HTTPS |
| **Constructeurs supportés** | Cisco Catalyst 9800, Ruckus SmartZone / vSZ |
| **Langue de l'interface** | Anglais (thème clair / sombre) |

---

## 2. Fonctionnalités principales

### 2.1 Supervision en temps réel
- **Tableau de bord** : synthèse contrôleur (CPU, mémoire, interfaces, version), nombre de
  points d'accès et de clients, état des WLAN.
- **Inventaire des points d'accès** : modèle, état, version logicielle, canal, bande,
  charge radio, nombre de clients.
- **Clients** : liste détaillée (RSSI, SNR, canal, type radio), recherche et statistiques.
- **Indicateur de connectivité** du contrôleur (connecté / dégradé / injoignable).

### 2.2 Cartographie des sites (AP Map)
- Importation de **plans d'étage** et placement des points d'accès.
- Superpositions : **état en direct**, **carte de chaleur du signal**, **trajets de
  roaming**, **couverture / canaux**, **localisation de client**.

### 2.3 Diagnostic radio (RF Troubleshooting)
- Détection des **conflits de canaux** : co-canal, interférence adjacente/chevauchante.
- **Utilisation de la bande passante (airtime)** et **niveau de bruit** par radio.
- **Analyseur de spectre** graphique par bande (2,4 / 5 GHz) avec **largeur de canal**.

### 2.4 Journal des événements de sécurité
- Détection : **points d'accès pirates (rogue)**, événements RF, **chute de SNR client**,
  **adresses dupliquées**, alertes **aWIPS**, **AP hors-ligne**.
- **Persistance** des événements en base, **acquittement** et historique.

### 2.5 Tendances & Capacité
- Évolution dans le temps de la charge, des clients et de l'occupation radio.
- Aide au **dimensionnement** et à l'anticipation de la saturation.

### 2.6 Cycle de vie & conformité firmware
- Suivi des **redémarrages** et **flaps** des points d'accès.
- **Conformité firmware** par rapport à une version cible définie.

### 2.7 Conseiller réseau (Network Advisor)
- **Recommandations priorisées** : conflits RF, saturation (airtime), AP hors-ligne,
  firmware non conforme, clients faibles, déséquilibre 2,4 GHz, charge contrôleur.

### 2.8 Suivi & roaming
- Historique de connexion et de **roaming** des clients, avec **purge programmable**
  (toutes les 5 min / horaire / quotidienne / hebdomadaire / mensuelle).

---

## 3. Architecture technique

```
                 HTTPS (8443)
   Navigateur ───────────────▶  nginx (TLS)  ──▶  Backend (API + SPA)  ──▶  MongoDB
                                                   │
                                                   └──▶  Contrôleur WLC
                                                        (Cisco RESTCONF /
                                                         Ruckus REST API)
```

| Couche | Technologie |
|---|---|
| **Frontend** | Angular 17 (SPA), Chart.js, D3 |
| **Backend** | Python 3.12 / Flask, Gunicorn |
| **Base de données** | MongoDB 7 |
| **Reverse proxy / TLS** | nginx (HTTP/2, TLS 1.2/1.3) |
| **Conteneurisation** | Docker / Docker Compose |
| **Intégration WLC** | Cisco IOS-XE RESTCONF (YANG) · Ruckus SmartZone Public REST API |

---

## 4. Sécurité

- **Authentification** par jeton **JWT** signé, avec expiration.
- **Rôles** : administrateur / observateur (contrôle d'accès par rôle).
- **Mots de passe** hachés (bcrypt) ; rotation forcée au premier accès.
- **Protection anti-force brute** : limitation du nombre de tentatives de connexion.
- **Chiffrement au repos** du mot de passe du contrôleur (Fernet).
- **Base de données authentifiée** et non exposée publiquement.
- **En-têtes de sécurité** HTTP (HSTS, CSP, anti-clickjacking, anti-MIME-sniffing).
- **Chiffrement TLS** de bout en bout (certificat auto-signé ou signé par une AC).
- **Conteneur applicatif non-root** (défense en profondeur).
- **Contrôle de configuration durci** : refus de démarrage en production si les secrets
  ne sont pas correctement définis.

---

## 5. Prérequis & dimensionnement

### 5.1 Serveur / VM (Linux, ex. Ubuntu 22.04+)
| Profil | Points d'accès | Clients | vCPU | RAM | Disque (SSD) |
|---|---|---|---|---|---|
| **Petit** | ≤ 250 | ≤ 1 000 | 2 | 4 Go | 40 Go |
| **Moyen** | ≤ 1 500 | ≤ 3 000 | 4 | 8 Go | 80 Go |
| **Grand** | ≤ 6 000 | ≤ 5 000 | 4–8 | 16 Go | 150–200 Go |

> Le disque dépend principalement de la durée de rétention de l'historique de suivi/roaming
> (purge programmable pour maîtriser la volumétrie).

### 5.2 Logiciels
- Docker Engine + Docker Compose
- Accès réseau **HTTPS/443** (Cisco) ou **port API** (Ruckus) vers le contrôleur

### 5.3 Poste client
- Navigateur web moderne (Chrome, Edge, Firefox)

---

## 6. Déploiement

- Installation **clé en main** via Docker Compose (3 conteneurs : reverse proxy, application,
  base de données).
- **Frontend intégré** au backend (build unique) — aucune dépendance d'hébergement séparée.
- Accès immédiat via **HTTPS sur le port 8443**.
- Configuration du contrôleur (constructeur, hôte, identifiants) directement depuis
  l'interface d'administration, **sans redémarrage**.

---

## 7. Points forts

- ✅ **Multi-constructeur** : Cisco & Ruckus depuis une seule interface.
- ✅ **Diagnostic radio avancé** (conflits de canaux, spectre, airtime, bruit).
- ✅ **Sécurité Wi-Fi** : détection des rogues et anomalies, journal acquittable.
- ✅ **Aide à la décision** : recommandations priorisées et tendances de capacité.
- ✅ **Déploiement on-premise** : vos données restent chez vous.
- ✅ **Sécurisé par conception** (chiffrement, RBAC, durcissement).

---

*WireMetry — Wireless Intelligence. Document technique — usage commercial.*