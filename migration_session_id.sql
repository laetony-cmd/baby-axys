-- ============================================================
-- MIGRATION: Ajout session_id à la table souvenirs
-- À exécuter UNE FOIS sur le MS-01
-- Date: 24 décembre 2025
-- ============================================================

-- 1. Ajouter la colonne session_id
ALTER TABLE souvenirs ADD COLUMN IF NOT EXISTS session_id VARCHAR(20);

-- 2. Index pour performance des requêtes par session
CREATE INDEX IF NOT EXISTS idx_souvenirs_session ON souvenirs(session_id);

-- 3. Index composite pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_souvenirs_type_session ON souvenirs(type, session_id);

-- 4. Marquer les anciennes conversations avec session "legacy"
UPDATE souvenirs 
SET session_id = 'legacy' 
WHERE type = 'conversation' AND session_id IS NULL;

-- 5. Log de migration
INSERT INTO souvenirs (type, source, contenu, metadata)
VALUES (
    'systeme',
    'migration',
    'Migration session_id appliquée - Conversations existantes marquées legacy',
    '{"version": "session_v1", "date": "2025-12-24"}'::jsonb
);

-- ============================================================
-- VÉRIFICATION
-- ============================================================
-- SELECT COUNT(*) as total, session_id FROM souvenirs WHERE type='conversation' GROUP BY session_id;
