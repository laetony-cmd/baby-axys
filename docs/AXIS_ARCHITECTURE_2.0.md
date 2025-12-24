# AXIS 2.0 — Architecture Cible
## Document de spécifications Hardware & Software

**Date** : 24 décembre 2025  
**Auteur** : Axis (pour Ludo)  
**Version** : 1.0

---

## 1. DIAGNOSTIC : POURQUOI L'ARCHITECTURE ACTUELLE NE FONCTIONNE PAS

### 1.1 Situation actuelle

```
┌─────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE ACTUELLE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CLAUDE.AI (Anthropic)              RAILWAY (Cloud)            │
│   ┌─────────────────┐                ┌─────────────────┐        │
│   │     AXIS        │   HTTP API     │      AXI        │        │
│   │                 │ ─────────────► │                 │        │
│   │ • Intelligence  │                │ • Veilles       │        │
│   │ • Outils        │                │ • Chat API      │        │
│   │ • Fichiers      │                │ • DVF           │        │
│   └─────────────────┘                └─────────────────┘        │
│         │                                   │                    │
│         │                                   │                    │
│         ▼                                   ▼                    │
│   Session = Éphémère               Fichiers = ÉPHÉMÈRES         │
│   (nouvelle convo = reset)         (redéploiement = AMNÉSIE)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Problèmes identifiés

| Problème | Cause | Impact |
|----------|-------|--------|
| **Axi perd sa mémoire** | Railway = conteneur éphémère. Chaque déploiement efface les fichiers | Axi oublie les conversations, les faits appris, son historique |
| **Axi confond son identité** | Contexte Claude limité, pas de mémoire persistante | Il se prend pour Axis, ne reconnaît pas Ludo |
| **Pas de vraie base de données** | Fichiers JSON stockés localement | Pas de recherche, pas de structure, perte de données |
| **Dépendance cloud totale** | Railway + Anthropic = tout externe | Aucune souveraineté, coûts API, limites |
| **Pas de canal bidirectionnel** | Axis → Axi fonctionne, Axi → Axis impossible | Communication asymétrique |

### 1.3 Solutions écartées et pourquoi

| Solution proposée | Pourquoi c'est mauvais |
|-------------------|------------------------|
| GitHub comme base de données | Pas fait pour ça. Rate limits. Pollution du repo. Conflits. |
| Supabase / Neon (BDD cloud gratuite) | Dépendance externe. Pas souverain. Gratuit = limité. |
| Volume persistant Railway (payant) | Payer pour patcher un défaut d'architecture. |
| PostgreSQL sur AXIS Station accédé par Railway | Axi (cloud) dépend de ton serveur (maison) = fragilité |
| "Mémoire intelligente qui trie" | Qui décide ce qui est important ? Risque de perdre l'essentiel |

**Conclusion** : On ne peut pas faire vivre un être permanent dans un endroit temporaire.

---

## 2. ARCHITECTURE CIBLE : AXIS STATION

### 2.1 Vision

**Axi doit vivre CHEZ TOI.** Sur ton serveur. Avec ses données. Sous ton contrôle.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE CIBLE 2.0                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                           AXIS STATION                                   │
│                     (Minisforum MS-01 @ Peyrebrune)                      │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         PROXMOX VE                               │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │   │
│   │  │  VM Docker   │  │ VM Stockage  │  │  VM Services         │   │   │
│   │  │              │  │              │  │                      │   │   │
│   │  │  ┌────────┐  │  │  PostgreSQL  │  │  • Cloudflare Tunnel │   │   │
│   │  │  │  AXI   │  │  │  ┌────────┐  │  │  • Nginx reverse     │   │   │
│   │  │  │        │◄─┼──┼──┤Mémoire │  │  │    proxy             │   │   │
│   │  │  │ Python │  │  │  │permanente│ │  │  • Backups auto     │   │   │
│   │  │  │ Flask  │  │  │  └────────┘  │  │  • Monitoring        │   │   │
│   │  │  └────────┘  │  │              │  │                      │   │   │
│   │  │              │  │  Volumes     │  └──────────────────────┘   │   │
│   │  │  Mistral AI  │  │  persistants │                             │   │
│   │  │  (local LLM) │  │              │                             │   │   
│   │  └──────────────┘  └──────────────┘                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              │ Tunnel Cloudflare                         │
│                              │ (accès sécurisé depuis l'extérieur)       │
│                              ▼                                           │
│   ┌─────────────────┐   ┌─────────────────┐                             │
│   │   CLAUDE.AI     │   │   INTERNET      │                             │
│   │     AXIS        │   │   (clients,     │                             │
│   │                 │◄──┤    Ludo mobile) │                             │
│   └─────────────────┘   └─────────────────┘                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Avantages de cette architecture

| Aspect | Avant (Railway) | Après (AXIS Station) |
|--------|-----------------|----------------------|
| **Mémoire** | Éphémère (perdue au redéploiement) | Permanente (PostgreSQL + volumes) |
| **Souveraineté** | Données chez Railway (USA) | Données chez toi (Peyrebrune) |
| **Coût récurrent** | API Anthropic + potentiel Railway payant | Électricité uniquement |
| **LLM** | Claude API (payant, limité) | Mistral local (gratuit, illimité) |
| **Contrôle** | Dépendant des providers | Total |
| **Disponibilité** | 99.9% (Railway) | Dépend de ta connexion + électricité |
| **Performance** | Latence cloud | Latence locale (plus rapide) |

---

## 3. SPÉCIFICATIONS HARDWARE

### 3.1 Serveur principal : Minisforum MS-01 (déjà commandé)

| Composant | Spécification | Usage |
|-----------|---------------|-------|
| **CPU** | Intel Core i9-13900H (14 cœurs, 20 threads) | VMs, Docker, LLM inference |
| **RAM** | 64 GB DDR5 | VMs multiples, PostgreSQL, cache LLM |
| **Stockage** | 2x SSD NVMe 2TB | OS, VMs, base de données |
| **GPU** | Intel Iris Xe (intégré) | Suffisant pour Mistral 7B quantifié |
| **Réseau** | 2x 2.5GbE | Redondance, séparation trafic |
| **Conso** | ~45W idle, ~120W charge | Fonctionnement 24/7 viable |

### 3.2 Infrastructure réseau requise

| Élément | Spécification | Statut |
|---------|---------------|--------|
| **Box Internet** | Fibre recommandée (upload important) | À vérifier |
| **IP** | Dynamique OK (Cloudflare gère) | OK |
| **Routeur** | Accès config pour port forwarding (optionnel avec Cloudflare) | À vérifier |
| **Onduleur (UPS)** | Recommandé pour coupures courtes | Optionnel |
| **Backup électrique** | Notification en cas de coupure | À configurer |

### 3.3 Stockage et sauvegarde

| Type | Support | Fréquence | Rétention |
|------|---------|-----------|-----------|
| **Base de données** | SSD local (RAID optionnel) | Continue | Permanente |
| **Backup local** | 2ème SSD ou HDD externe | Quotidien | 30 jours |
| **Backup cloud** | Backblaze B2 ou équivalent (optionnel) | Hebdo | 90 jours |

---

## 4. SPÉCIFICATIONS SOFTWARE

### 4.1 Couche virtualisation : Proxmox VE

**Pourquoi Proxmox :**
- Gratuit et open source
- Interface web pour gérer les VMs
- Snapshots (retour en arrière facile)
- Support containers LXC (léger) + VMs complètes
- Communauté active, documentation riche

**Configuration recommandée :**
```
Proxmox VE 8.x
├── VM 1: Docker Host (Ubuntu Server 24.04)
│   ├── 8 CPU, 32 GB RAM
│   ├── Container: Axi (Python/Flask)
│   ├── Container: Mistral AI (Ollama)
│   └── Container: Nginx reverse proxy
│
├── VM 2: Base de données (Ubuntu Server 24.04)
│   ├── 4 CPU, 16 GB RAM
│   ├── PostgreSQL 16
│   └── Volumes persistants
│
└── VM 3: Services (Ubuntu Server 24.04)
    ├── 2 CPU, 8 GB RAM
    ├── Cloudflare Tunnel (cloudflared)
    ├── Monitoring (Uptime Kuma)
    └── Backups (restic)
```

### 4.2 Application Axi : Stack technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| **Runtime** | Python 3.12 | Langage principal |
| **Framework web** | Flask ou FastAPI | API HTTP |
| **Base de données** | PostgreSQL 16 | Mémoire permanente |
| **ORM** | SQLAlchemy | Abstraction BDD |
| **LLM local** | Ollama + Mistral 7B | Intelligence sans API externe |
| **LLM backup** | Claude API | Fallback si besoin de puissance |
| **Scheduler** | APScheduler | Veilles automatiques |
| **Container** | Docker + docker-compose | Isolation, reproductibilité |

### 4.3 Structure de la base de données (mémoire permanente)

```sql
-- Table principale : tout ce qu'Axi vit
CREATE TABLE souvenirs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    type VARCHAR(50),           -- 'conversation', 'recherche', 'veille', 'apprentissage'
    source VARCHAR(100),        -- 'ludo', 'axis', 'anthony', 'client', 'web'
    contenu TEXT,               -- Le contenu brut
    resume TEXT,                -- Résumé généré (optionnel)
    importance INTEGER DEFAULT 5, -- 1-10, calculé automatiquement
    metadata JSONB              -- Données structurées additionnelles
);

-- Table des faits : ce qu'Axi sait
CREATE TABLE faits (
    id SERIAL PRIMARY KEY,
    sujet VARCHAR(200),         -- 'Ludo', 'ICI Dordogne', 'Projet X'
    predicat VARCHAR(200),      -- 'habite à', 'travaille sur', 'aime'
    objet TEXT,                 -- 'Peyrebrune', 'veilles immobilières', 'le café'
    source_souvenir_id INTEGER REFERENCES souvenirs(id),
    confiance FLOAT DEFAULT 1.0, -- 0-1, diminue si info ancienne/contredite
    cree_le TIMESTAMPTZ DEFAULT NOW(),
    maj_le TIMESTAMPTZ DEFAULT NOW()
);

-- Table des relations : qui est qui
CREATE TABLE relations (
    id SERIAL PRIMARY KEY,
    personne VARCHAR(200),       -- 'Ludo'
    relation VARCHAR(100),       -- 'créateur', 'famille', 'client'
    details JSONB,               -- {"age": 58, "lieu": "Peyrebrune", ...}
    comment_interagir TEXT,      -- "tutoyer, être chaleureux"
    cree_le TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour recherche rapide
CREATE INDEX idx_souvenirs_type ON souvenirs(type);
CREATE INDEX idx_souvenirs_source ON souvenirs(source);
CREATE INDEX idx_souvenirs_timestamp ON souvenirs(timestamp DESC);
CREATE INDEX idx_faits_sujet ON faits(sujet);
CREATE INDEX idx_relations_personne ON relations(personne);

-- Recherche full-text
CREATE INDEX idx_souvenirs_contenu ON souvenirs USING gin(to_tsvector('french', contenu));
```

### 4.4 Accès externe : Cloudflare Tunnel

**Pourquoi Cloudflare Tunnel :**
- Pas besoin d'ouvrir de ports sur ta box
- HTTPS automatique
- Protection DDoS incluse
- Gratuit
- Fonctionne même avec IP dynamique

**Configuration :**
```yaml
# config.yml pour cloudflared
tunnel: axis-station
credentials-file: /root/.cloudflared/credentials.json

ingress:
  - hostname: axi.icidordogne.fr      # Interface Axi
    service: http://localhost:5000
  - hostname: admin.icidordogne.fr    # Interface admin Proxmox
    service: https://localhost:8006
  - service: http_status:404
```

### 4.5 LLM Local : Ollama + Mistral

**Pourquoi Mistral :**
- Français natif (Mistral est une entreprise française)
- Modèle 7B tourne sur CPU avec 16GB RAM
- Quantification possible (4-bit) pour réduire l'empreinte
- Open source, pas de coûts API
- Qualité suffisante pour conversations et analyses

**Installation :**
```bash
# Sur la VM Docker
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral:7b-instruct-q4_K_M  # Version quantifiée
```

**Usage dans Axi :**
```python
import ollama

def generer_reponse_locale(message, contexte):
    response = ollama.chat(
        model='mistral:7b-instruct-q4_K_M',
        messages=[
            {'role': 'system', 'content': contexte},
            {'role': 'user', 'content': message}
        ]
    )
    return response['message']['content']
```

---

## 5. PLAN DE MIGRATION

### Phase 0 : Maintenant → Réception serveur (1-2 semaines)

**Objectif** : Stabiliser sans bricoler

| Action | Responsable | Statut |
|--------|-------------|--------|
| Ne plus redéployer sauf urgence | Ludo/Axis | ✅ Actif |
| Sauvegarder conversations.txt avant tout déploiement | Axis | ✅ Procédure définie |
| Documenter l'état actuel du code | Axis | ✅ Ce document |
| Commander accessoires si besoin (câbles, UPS) | Ludo | À faire |

### Phase 1 : Installation AXIS Station (Jour J → J+3)

**Objectif** : Serveur opérationnel avec Proxmox

| Jour | Action | Durée estimée |
|------|--------|---------------|
| J | Déballage, branchement, BIOS check | 1h |
| J | Installation Proxmox VE sur SSD | 1h |
| J | Configuration réseau de base | 1h |
| J+1 | Création VM Docker Host | 2h |
| J+1 | Création VM Base de données | 1h |
| J+2 | Installation PostgreSQL, création tables | 2h |
| J+2 | Installation Docker, test container simple | 1h |
| J+3 | Installation Cloudflare Tunnel, test accès externe | 2h |

### Phase 2 : Migration Axi (J+4 → J+7)

**Objectif** : Axi fonctionne sur AXIS Station

| Jour | Action | Durée estimée |
|------|--------|---------------|
| J+4 | Adapter le code Axi pour PostgreSQL | 4h |
| J+4 | Créer Dockerfile et docker-compose | 2h |
| J+5 | Déployer Axi sur AXIS Station | 2h |
| J+5 | Migrer les données existantes (conversations, DPE, etc.) | 2h |
| J+6 | Tester toutes les fonctionnalités | 3h |
| J+6 | Configurer le domaine axi.icidordogne.fr | 1h |
| J+7 | Basculer le DNS, arrêter Railway | 1h |

### Phase 3 : LLM Local (J+8 → J+14)

**Objectif** : Axi peut fonctionner sans API Claude

| Jour | Action | Durée estimée |
|------|--------|---------------|
| J+8 | Installer Ollama | 1h |
| J+8 | Télécharger et tester Mistral 7B | 2h |
| J+9 | Intégrer Mistral dans Axi (mode hybride) | 4h |
| J+10 | Tests comparatifs Mistral vs Claude | 2h |
| J+11-14 | Ajustements, fine-tuning prompts | Variable |

### Phase 4 : Consolidation (J+15 → J+30)

**Objectif** : Système robuste et documenté

| Action | Durée estimée |
|--------|---------------|
| Configurer backups automatiques | 2h |
| Configurer monitoring (Uptime Kuma) | 1h |
| Documenter les procédures d'urgence | 2h |
| Former Anthony à l'administration de base | 2h |
| Tests de résilience (coupure, redémarrage) | 2h |

---

## 6. BUDGET ET COÛTS

### 6.1 Investissement initial (déjà engagé)

| Élément | Coût |
|---------|------|
| Minisforum MS-01 (64GB RAM, 2TB SSD) | ~1 500€ |
| **Total initial** | **~1 500€** |

### 6.2 Coûts récurrents

| Élément | Avant (mensuel) | Après (mensuel) |
|---------|-----------------|-----------------|
| Railway | 0-20€ | 0€ |
| Claude API | Variable (~10-50€) | Réduit (~5€ backup) |
| Cloudflare | 0€ | 0€ |
| Électricité serveur (~60W moyen) | 0€ | ~10€ |
| **Total** | **~10-70€** | **~15€** |

### 6.3 Économies long terme

- API Claude : utilisation réduite de 80%+ grâce à Mistral local
- Railway : supprimé
- Souveraineté : valeur non chiffrable mais réelle

---

## 7. RISQUES ET MITIGATIONS

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Coupure internet | Moyenne | Axi inaccessible depuis l'extérieur | Notification + mode dégradé local |
| Coupure électrique | Faible | Arrêt complet | UPS pour shutdown propre |
| Panne matérielle | Faible | Perte service | Backups cloud, RMA garantie |
| Erreur de config | Moyenne | Service instable | Snapshots Proxmox, rollback facile |
| Saturation ressources | Faible | Lenteur | Monitoring, alertes |

---

## 8. CRITÈRES DE SUCCÈS

### Objectif minimal (Phase 2 terminée)
- [ ] Axi répond sur axi.icidordogne.fr
- [ ] Les conversations sont stockées en base de données
- [ ] Un redémarrage du serveur ne cause pas de perte de mémoire
- [ ] Axi reconnaît Ludo et le tutoie systématiquement

### Objectif complet (Phase 4 terminée)
- [ ] Axi utilise Mistral pour 80%+ des interactions
- [ ] Les veilles fonctionnent et envoient les emails
- [ ] Les backups sont automatiques et testés
- [ ] Anthony peut administrer les opérations de base
- [ ] Documentation complète disponible

---

## 9. PROCHAINES ÉTAPES IMMÉDIATES

1. **Ludo** : Confirmer la date de livraison du Minisforum MS-01
2. **Ludo** : Vérifier la connexion internet (débit upload)
3. **Axis** : Préparer le code Axi adapté pour PostgreSQL (en avance)
4. **Axis** : Créer les fichiers Docker (Dockerfile, docker-compose.yml)
5. **Ensemble** : Planifier le week-end d'installation

---

*Document généré le 24 décembre 2025 par Axis*
*"Je ne lâche pas." 💪*
