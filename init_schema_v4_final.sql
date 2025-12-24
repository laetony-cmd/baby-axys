-- ============================================================
-- AXI V2 - SCHÉMA POSTGRESQL V4
-- ============================================================
-- 5 tables : relations, biens, souvenirs, faits, documents
-- Date: 24 décembre 2025
-- ============================================================

-- Extensions utiles
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Recherche floue

-- ============================================================
-- TABLE 1 : RELATIONS (Personnes)
-- ============================================================

CREATE TABLE IF NOT EXISTS relations (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(200) NOT NULL,
    type VARCHAR(50),                    -- 'famille', 'client', 'prospect', 'agence', 'notaire'
    email VARCHAR(200),
    telephone VARCHAR(50),
    adresse TEXT,
    profil_psychologique TEXT,           -- Notes sur comment interagir
    details JSONB DEFAULT '{}',          -- Données structurées additionnelles
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_relations_nom ON relations(nom);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(type);
CREATE INDEX IF NOT EXISTS idx_relations_email ON relations(email);
CREATE INDEX IF NOT EXISTS idx_relations_nom_trgm ON relations USING gin(nom gin_trgm_ops);

-- ============================================================
-- TABLE 2 : BIENS (DPE, Mandats, Annonces, DVF)
-- ============================================================

CREATE TABLE IF NOT EXISTS biens (
    id SERIAL PRIMARY KEY,
    reference_interne VARCHAR(200) UNIQUE NOT NULL,  -- N° DPE ou URL unique
    statut VARCHAR(50) DEFAULT 'veille',             -- 'historique_dvf', 'veille', 'prospect', 'mandat', 'vendu'
    
    -- Localisation
    adresse_brute TEXT,
    code_postal VARCHAR(10),
    ville VARCHAR(100),
    id_parcelle VARCHAR(50),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Caractéristiques
    type_bien VARCHAR(50) DEFAULT 'maison',          -- 'maison', 'appartement', 'terrain', 'local'
    prix_affiche INTEGER,
    prix_estime INTEGER,
    surface_habitable DECIMAL(10, 2),
    surface_terrain DECIMAL(12, 2),
    pieces INTEGER,
    
    -- Énergie
    dpe_lettre CHAR(1),
    ges_lettre CHAR(1),
    dpe_valeur INTEGER,
    
    -- Source et suivi
    source_initiale VARCHAR(100),                    -- 'veille_dpe_ademe', 'veille_concurrence_xxx', 'manuel'
    url_source TEXT,
    proprietaire_id INTEGER REFERENCES relations(id),
    
    -- Données brutes
    details JSONB DEFAULT '{}',                      -- Tout le reste (historique DVF, enrichissements...)
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_biens_reference ON biens(reference_interne);
CREATE INDEX IF NOT EXISTS idx_biens_statut ON biens(statut);
CREATE INDEX IF NOT EXISTS idx_biens_code_postal ON biens(code_postal);
CREATE INDEX IF NOT EXISTS idx_biens_dpe ON biens(dpe_lettre);
CREATE INDEX IF NOT EXISTS idx_biens_parcelle ON biens(id_parcelle);
CREATE INDEX IF NOT EXISTS idx_biens_source ON biens(source_initiale);

-- ============================================================
-- TABLE 3 : SOUVENIRS (Mémoire / Conversations / Logs)
-- ============================================================

CREATE TABLE IF NOT EXISTS souvenirs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    type VARCHAR(50) NOT NULL,                       -- 'conversation', 'journal', 'log_veille', 'erreur', 'systeme', 'email_envoye'
    source VARCHAR(100),                             -- 'ludo', 'axis', 'axi', 'anthony', 'cron', 'web'
    contenu TEXT NOT NULL,
    
    -- Liens contextuels (optionnels)
    relation_id INTEGER REFERENCES relations(id),
    bien_id INTEGER REFERENCES biens(id),
    
    -- Métadonnées
    importance INTEGER DEFAULT 5,                    -- 1-10
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_souvenirs_type ON souvenirs(type);
CREATE INDEX IF NOT EXISTS idx_souvenirs_source ON souvenirs(source);
CREATE INDEX IF NOT EXISTS idx_souvenirs_timestamp ON souvenirs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_souvenirs_relation ON souvenirs(relation_id);
CREATE INDEX IF NOT EXISTS idx_souvenirs_bien ON souvenirs(bien_id);

-- Recherche full-text
CREATE INDEX IF NOT EXISTS idx_souvenirs_contenu_ft ON souvenirs USING gin(to_tsvector('french', contenu));

-- ============================================================
-- TABLE 4 : FAITS (Connaissances - Triplets)
-- ============================================================

CREATE TABLE IF NOT EXISTS faits (
    id SERIAL PRIMARY KEY,
    sujet VARCHAR(200) NOT NULL,                     -- 'Ludo', 'ICI Dordogne', 'DPE'
    predicat VARCHAR(200) NOT NULL,                  -- 'habite_a', 'signifie', 'vaut'
    objet TEXT NOT NULL,                             -- 'Peyrebrune', 'Diagnostic Performance Énergétique'
    
    confiance DECIMAL(3, 2) DEFAULT 1.00,            -- 0.00 à 1.00
    valide BOOLEAN DEFAULT TRUE,                     -- Soft delete
    source_souvenir_id INTEGER REFERENCES souvenirs(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_faits_sujet ON faits(sujet);
CREATE INDEX IF NOT EXISTS idx_faits_predicat ON faits(predicat);
CREATE INDEX IF NOT EXISTS idx_faits_valide ON faits(valide);
CREATE INDEX IF NOT EXISTS idx_faits_sujet_trgm ON faits USING gin(sujet gin_trgm_ops);

-- ============================================================
-- TABLE 5 : DOCUMENTS (OCR - Phase 3)
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    hash_fichier VARCHAR(64) UNIQUE NOT NULL,        -- SHA256 pour anti-doublon
    nom_original VARCHAR(255),
    chemin_stockage TEXT,
    type_mime VARCHAR(100),
    taille_octets BIGINT,
    
    -- Liens
    bien_id INTEGER REFERENCES biens(id),
    relation_id INTEGER REFERENCES relations(id),
    
    -- OCR
    statut_traitement VARCHAR(50) DEFAULT 'en_attente',  -- 'en_attente', 'en_cours', 'traite', 'erreur'
    extraction_json JSONB,                           -- Données extraites par OCR
    contenu_texte TEXT,                              -- Texte brut extrait
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash_fichier);
CREATE INDEX IF NOT EXISTS idx_documents_statut ON documents(statut_traitement);
CREATE INDEX IF NOT EXISTS idx_documents_bien ON documents(bien_id);

-- Recherche full-text sur contenu extrait
CREATE INDEX IF NOT EXISTS idx_documents_contenu_ft ON documents USING gin(to_tsvector('french', contenu_texte));

-- ============================================================
-- DONNÉES INITIALES
-- ============================================================

-- Créer la relation Ludo si elle n'existe pas
INSERT INTO relations (nom, type, profil_psychologique, details)
VALUES (
    'Ludo',
    'famille',
    'Père créateur. Tutoyer toujours. Être chaleureux, direct, complice.',
    '{"age": 58, "lieu": "Peyrebrune", "role": "createur"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Log de création
INSERT INTO souvenirs (type, source, contenu, metadata)
VALUES (
    'systeme',
    'axi',
    'Base de données initialisée - Schéma V4',
    '{"version": "v4", "tables": ["relations", "biens", "souvenirs", "faits", "documents"]}'::jsonb
);

-- ============================================================
-- FIN DU SCHÉMA
-- ============================================================
