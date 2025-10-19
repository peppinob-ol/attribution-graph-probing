#!/usr/bin/env python3
"""
Test per il nuovo sistema Probe Prompts con API Neuronpedia.

Esegui con:
    python tests/test_probe_prompts_api.py
"""

import sys
from pathlib import Path

# Setup path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import con importlib per gestire nome file con numero
import importlib.util

script_path = parent_dir / "scripts" / "01_probe_prompts.py"
spec = importlib.util.spec_from_file_location("probe_prompts", script_path)
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)

filter_features_by_influence = probe_module.filter_features_by_influence
find_subsequence = probe_module.find_subsequence
tokenize_simple = probe_module.tokenize_simple
NeuronpediaAPI = probe_module.NeuronpediaAPI


def test_filter_features_by_influence():
    """Test filtraggio features per cumulative influence"""
    print("\n" + "="*60)
    print("TEST: filter_features_by_influence")
    print("="*60)
    
    # Mock features
    features = [
        {"layer": 0, "feature": 0, "influence": 0.5},
        {"layer": 0, "feature": 1, "influence": 0.3},
        {"layer": 0, "feature": 2, "influence": 0.15},
        {"layer": 0, "feature": 3, "influence": 0.05},
    ]
    
    # Test con 90% cumulative
    filtered, threshold, num_sel, num_tot = filter_features_by_influence(
        features, cumulative_contribution=0.90
    )
    
    print(f"\nInput features: {num_tot}")
    print(f"Cumulative target: 90%")
    print(f"Selected: {num_sel}")
    print(f"Threshold influence: {threshold:.4f}")
    
    # Verifica
    assert num_tot == 4, "Numero totale features errato"
    # Con 90% cumulative: 0.5 + 0.3 = 0.8 (80%), serve anche 0.15 → 0.95 (95%) per superare 90%
    assert num_sel == 3, f"Dovrebbero essere selezionate 3 features per 90% cumulative, ma sono {num_sel}"
    assert abs(filtered[0]["influence"]) == 0.5, "Prima feature dovrebbe avere influence 0.5"
    
    print("\n[OK] Test filter_features_by_influence: PASSED")
    return True


def test_find_subsequence():
    """Test ricerca sottosequenza"""
    print("\n" + "="*60)
    print("TEST: find_subsequence")
    print("="*60)
    
    haystack = ["The", "quick", "brown", "fox", "jumps"]
    needle = ["brown", "fox"]
    
    result = find_subsequence(haystack, needle)
    print(f"\nHaystack: {haystack}")
    print(f"Needle: {needle}")
    print(f"Found at index: {result}")
    
    assert result == 2, f"Dovrebbe trovare a index 2, trovato: {result}"
    
    # Test non trovato
    needle2 = ["red", "fox"]
    result2 = find_subsequence(haystack, needle2)
    print(f"\nNeedle (not present): {needle2}")
    print(f"Result: {result2}")
    
    assert result2 is None, "Dovrebbe ritornare None se non trovato"
    
    print("\n[OK] Test find_subsequence: PASSED")
    return True


def test_tokenize_simple():
    """Test tokenizzazione semplice"""
    print("\n" + "="*60)
    print("TEST: tokenize_simple")
    print("="*60)
    
    text = "Hello World  Test"
    tokens = tokenize_simple(text)
    
    print(f"\nText: '{text}'")
    print(f"Tokens: {tokens}")
    
    assert tokens == ["Hello", "World", "Test"], f"Tokenizzazione errata: {tokens}"
    
    print("\n[OK] Test tokenize_simple: PASSED")
    return True


def test_neuronpedia_api_init():
    """Test inizializzazione API client"""
    print("\n" + "="*60)
    print("TEST: NeuronpediaAPI init")
    print("="*60)
    
    # Senza API key
    api1 = NeuronpediaAPI()
    print(f"\nAPI without key: {api1}")
    assert api1.api_key is None
    assert api1.session is not None
    
    # Con API key
    api2 = NeuronpediaAPI(api_key="test-key-123")
    print(f"API with key: {api2}")
    assert api2.api_key == "test-key-123"
    assert "x-api-key" in api2.session.headers
    
    print("\n[OK] Test NeuronpediaAPI init: PASSED")
    return True


def test_mock_graph_json_parsing():
    """Test parsing di un mock graph JSON"""
    print("\n" + "="*60)
    print("TEST: Mock Graph JSON Parsing")
    print("="*60)
    
    # Mock graph JSON
    mock_graph = {
        "metadata": {
            "scan": "gemma-2-2b",
            "prompt": "Test prompt for analysis",
            "info": {
                "transcoder_set": "gemmascope"
            }
        },
        "nodes": [
            {
                "feature_type": "cross layer transcoder",
                "layer": 5,
                "feature": 1234,
                "activation": 0.85,
                "ctx_idx": 3,
                "influence": 0.42
            },
            {
                "feature_type": "cross layer transcoder",
                "layer": 7,
                "feature": 5678,
                "activation": 0.65,
                "ctx_idx": 2,
                "influence": 0.38
            },
            {
                "feature_type": "embedding",  # Non-feature, should be skipped
                "layer": 0,
                "feature": None,
                "activation": 0.1,
                "ctx_idx": 0,
                "influence": 0.01
            }
        ]
    }
    
    # Estrai features (simula logica dello script)
    metadata = mock_graph.get("metadata", {})
    model_id = metadata.get("scan")
    prompt = metadata.get("prompt")
    
    print(f"\nModel ID: {model_id}")
    print(f"Prompt: {prompt}")
    
    assert model_id == "gemma-2-2b"
    assert prompt == "Test prompt for analysis"
    
    # Estrai features
    nodes = mock_graph.get("nodes", [])
    features = []
    
    for node in nodes:
        if node.get("feature_type") != "cross layer transcoder":
            continue
        
        layer = node.get("layer")
        feature_idx = node.get("feature")
        
        if layer is None or feature_idx is None:
            continue
        
        features.append({
            "layer": int(layer),
            "feature": int(feature_idx),
            "influence": float(node.get("influence", 0))
        })
    
    print(f"\nExtracted features: {len(features)}")
    for f in features:
        print(f"  Layer {f['layer']}, Feature {f['feature']}, Influence {f['influence']}")
    
    assert len(features) == 2, f"Dovrebbero essere estratte 2 features, estratte: {len(features)}"
    assert features[0]["layer"] == 5
    assert features[1]["feature"] == 5678
    
    print("\n[OK] Test Mock Graph JSON Parsing: PASSED")
    return True


def run_all_tests():
    """Esegui tutti i test"""
    print("\n" + "="*60)
    print("PROBE PROMPTS API - TEST SUITE")
    print("="*60)
    
    tests = [
        test_filter_features_by_influence,
        test_find_subsequence,
        test_tokenize_simple,
        test_neuronpedia_api_init,
        test_mock_graph_json_parsing,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {test_func.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] {test_func.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RISULTATI: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n[SUCCESS] Tutti i test sono passati!")
        return True
    else:
        print(f"\n[WARNING] {failed} test falliti")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

