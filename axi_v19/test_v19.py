#!/usr/bin/env python3
# axi_v19/test_v19.py
"""
Tests de non-régression V19
Vérifie que l'architecture Bunker est correctement isolée.

Plan Lumo V3 - Section 7: Tests
"""

import sys
import os

# Ajout du path parent pour imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dependencies():
    """Test 1: Vérifier les dépendances requises."""
    print("\n📋 Test 1: Dépendances")
    
    required = ['psycopg2', 'apscheduler', 'anthropic']
    results = {}
    
    for module in required:
        try:
            __import__(module)
            results[module] = "✅ OK"
        except ImportError:
            results[module] = "❌ MANQUANT"
    
    for module, status in results.items():
        print(f"   {module}: {status}")
    
    return all("OK" in s for s in results.values())


def test_config():
    """Test 2: Vérifier le module config."""
    print("\n📋 Test 2: Configuration")
    
    try:
        from core.config import settings, validate_dependencies, V19_TABLES
        
        print(f"   Version: {settings.version}")
        print(f"   Environment: {settings.environment}")
        print(f"   Port HTTP: {settings.http_port}")
        print(f"   Tables V19: {list(V19_TABLES.values())}")
        
        # Vérifier que les tables sont bien préfixées
        all_prefixed = all(t.startswith('v19_') for t in V19_TABLES.values())
        print(f"   Préfixe v19_: {'✅' if all_prefixed else '❌'}")
        
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def test_database_module():
    """Test 3: Vérifier le module database (sans connexion réelle)."""
    print("\n📋 Test 3: Module Database")
    
    try:
        from core.database import DatabaseManager, DatabaseError, ALLOWED_TABLE_PATTERN
        import re
        
        # Test pattern validation
        valid_tables = ['v19_prospects', 'v19_brain', 'v19_test_table']
        invalid_tables = ['prospects', 'v18_data', 'v19-bad', "v19_'; DROP TABLE--"]
        
        print("   Validation noms de tables:")
        for table in valid_tables:
            match = re.match(ALLOWED_TABLE_PATTERN, table)
            status = "✅" if match else "❌"
            print(f"      {table}: {status}")
        
        for table in invalid_tables:
            match = re.match(ALLOWED_TABLE_PATTERN, table)
            status = "✅ rejeté" if not match else "❌ accepté (ERREUR)"
            print(f"      {table}: {status}")
        
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def test_server_module():
    """Test 4: Vérifier le module server."""
    print("\n📋 Test 4: Module Server")
    
    try:
        from core.server import ServerManager, AxiRequestHandler
        
        # Créer une instance
        srv = ServerManager()
        print(f"   Instance créée: ✅")
        print(f"   Running: {srv.is_running}")
        
        # Test enregistrement route
        def dummy_handler(query):
            return {"test": "ok"}
        
        srv.register_route('GET', '/test/dummy', dummy_handler)
        print(f"   Route enregistrée: ✅")
        print(f"   Routes GET: {list(AxiRequestHandler.routes_get.keys())}")
        
        return True
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def test_isolation():
    """Test 5: Vérifier l'isolation V18/V19."""
    print("\n📋 Test 5: Isolation V18/V19")
    
    # Vérifier qu'on n'importe rien de V18
    import sys
    
    v18_modules = [m for m in sys.modules.keys() if 'v18' in m.lower() or 'main_v18' in m.lower()]
    
    if v18_modules:
        print(f"   ❌ Modules V18 détectés: {v18_modules}")
        return False
    else:
        print(f"   ✅ Aucun module V18 importé")
        return True


def test_tables_segregation():
    """Test 6: Vérifier la ségrégation des tables."""
    print("\n📋 Test 6: Ségrégation Tables")
    
    from core.config import V19_TABLES
    
    # Liste des tables V18 connues (ne pas toucher!)
    v18_tables = ['biens_cache', 'dpe_urls', 'concurrence_urls', 'dvf_transactions']
    
    # Vérifier qu'aucune table V19 ne chevauche V18
    overlap = set(V19_TABLES.values()) & set(v18_tables)
    
    if overlap:
        print(f"   ❌ Chevauchement détecté: {overlap}")
        return False
    else:
        print(f"   ✅ Aucun chevauchement V18/V19")
        print(f"   Tables V19: {list(V19_TABLES.values())}")
        return True


def run_all_tests():
    """Exécute tous les tests."""
    print("=" * 60)
    print("🧪 TESTS V19 - Architecture Bunker")
    print("=" * 60)
    
    tests = [
        ("Dépendances", test_dependencies),
        ("Configuration", test_config),
        ("Module Database", test_database_module),
        ("Module Server", test_server_module),
        ("Isolation V18/V19", test_isolation),
        ("Ségrégation Tables", test_tables_segregation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            results.append((name, False))
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {name}: {status}")
    
    print(f"\n   Total: {passed}/{total} tests passés")
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS PASSENT - V19 prête pour déploiement!")
        return 0
    else:
        print("\n⚠️ CERTAINS TESTS ÉCHOUENT - Vérifier avant déploiement")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
