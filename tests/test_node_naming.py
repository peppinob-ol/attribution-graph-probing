"""
Test unitari per naming supernodi (Step 3)

Test per le funzioni di naming in scripts/02_node_grouping.py:
- normalize_token_for_naming
- name_relationship_node
- name_semantic_node
- name_sayx_node
"""

import sys
from pathlib import Path
import pandas as pd
import json

# Aggiungi root al path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import diretto dal file (senza package)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "node_grouping",
    Path(__file__).parent.parent / "scripts" / "02_node_grouping.py"
)
node_grouping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_grouping)

normalize_token_for_naming = node_grouping.normalize_token_for_naming
name_relationship_node = node_grouping.name_relationship_node
name_semantic_node = node_grouping.name_semantic_node
name_sayx_node = node_grouping.name_sayx_node


# ============================================================================
# TEST: normalize_token_for_naming
# ============================================================================

def test_normalize_token_lowercase():
    """Test normalizzazione con solo lowercase"""
    token = "texas"
    all_occurrences = ["texas", "texas", "texas"]
    result = normalize_token_for_naming(token, all_occurrences)
    assert result == "texas", f"Expected 'texas', got '{result}'"
    print("OK test_normalize_token_lowercase")


def test_normalize_token_uppercase():
    """Test normalizzazione con maiuscola presente"""
    token = "texas"
    all_occurrences = ["texas", "Texas", "texas"]
    result = normalize_token_for_naming(token, all_occurrences)
    assert result == "Texas", f"Expected 'Texas', got '{result}'"
    print("OK test_normalize_token_uppercase")


def test_normalize_token_trailing_punct():
    """Test rimozione punteggiatura trailing"""
    token = "entity:"
    all_occurrences = ["entity:", "entity"]
    result = normalize_token_for_naming(token, all_occurrences)
    assert result == "entity", f"Expected 'entity', got '{result}'"
    print("OK test_normalize_token_trailing_punct")


def test_normalize_token_whitespace():
    """Test strip whitespace"""
    token = "  Texas  "
    all_occurrences = ["  Texas  ", "Texas"]
    result = normalize_token_for_naming(token, all_occurrences)
    assert result == "Texas", f"Expected 'Texas', got '{result}'"
    print("OK test_normalize_token_whitespace")


# ============================================================================
# TEST: name_semantic_node
# ============================================================================

def test_name_semantic_node_basic():
    """Test naming Semantic base"""
    df = pd.DataFrame({
        'peak_token': ['Texas', 'texas', 'Texas'],
        'activation_max': [100.0, 80.0, 90.0]
    })
    result = name_semantic_node('0_1861', df)
    assert result == "Texas", f"Expected 'Texas', got '{result}'"
    print("OK test_name_semantic_node_basic")


def test_name_semantic_node_punctuation():
    """Test naming Semantic con punteggiatura"""
    df = pd.DataFrame({
        'peak_token': [',', ',', ','],
        'activation_max': [50.0, 60.0, 55.0]
    })
    result = name_semantic_node('0_12345', df)
    assert result == "punctuation", f"Expected 'punctuation', got '{result}'"
    print("OK test_name_semantic_node_punctuation")


def test_name_semantic_node_empty():
    """Test naming Semantic con token vuoto"""
    df = pd.DataFrame({
        'peak_token': ['', '', ''],
        'activation_max': [10.0, 20.0, 15.0]
    })
    result = name_semantic_node('0_99999', df)
    assert result == "Semantic (unknown)", f"Expected 'Semantic (unknown)', got '{result}'"
    print("OK test_name_semantic_node_empty")


# ============================================================================
# TEST: name_sayx_node
# ============================================================================

def test_name_sayx_node_single_target():
    """Test naming Say X con singolo target"""
    df = pd.DataFrame({
        'activation_max': [100.0, 80.0],
        'target_tokens': [
            '[{"token": "Austin", "distance": 1, "direction": "forward"}]',
            '[{"token": "Dallas", "distance": 1, "direction": "forward"}]'
        ]
    })
    result = name_sayx_node('17_98126', df)
    assert result == "Say (Austin)", f"Expected 'Say (Austin)', got '{result}'"
    print("OK test_name_sayx_node_single_target")


def test_name_sayx_node_no_target():
    """Test naming Say X senza target"""
    df = pd.DataFrame({
        'activation_max': [50.0],
        'target_tokens': ['[]']
    })
    result = name_sayx_node('18_3623', df)
    assert result == "Say (?)", f"Expected 'Say (?)', got '{result}'"
    print("OK test_name_sayx_node_no_target")


def test_name_sayx_node_tie_break_backward():
    """Test naming Say X con tie-break backward"""
    df = pd.DataFrame({
        'activation_max': [100.0],
        'target_tokens': [
            '[{"token": "Texas", "distance": 1, "direction": "backward"}, '
            '{"token": "USA", "distance": 1, "direction": "forward"}]'
        ]
    })
    result = name_sayx_node('17_1822', df)
    assert result == "Say (Texas)", f"Expected 'Say (Texas)', got '{result}' (backward should win)"
    print("OK test_name_sayx_node_tie_break_backward")


def test_name_sayx_node_distance_priority():
    """Test naming Say X con distance priority"""
    df = pd.DataFrame({
        'activation_max': [100.0],
        'target_tokens': [
            '[{"token": "city", "distance": 2, "direction": "backward"}, '
            '{"token": "Texas", "distance": 1, "direction": "forward"}]'
        ]
    })
    result = name_sayx_node('17_9999', df)
    assert result == "Say (Texas)", f"Expected 'Say (Texas)', got '{result}' (distance 1 should win)"
    print("OK test_name_sayx_node_distance_priority")


# ============================================================================
# TEST: name_relationship_node
# ============================================================================

def test_name_relationship_node_fallback():
    """Test naming Relationship con fallback (no JSON)"""
    df = pd.DataFrame({
        'peak_token': ['entity', 'attribute', 'entity'],
        'activation_max': [100.0, 80.0, 90.0]
    })
    result = name_relationship_node('1_12928', df, activations_data=None)
    assert result == "(entity) related", f"Expected '(entity) related', got '{result}'"
    print("OK test_name_relationship_node_fallback")


def test_name_relationship_node_with_json():
    """Test naming Relationship con JSON attivazioni"""
    df = pd.DataFrame({
        'peak_token': ['entity', 'entity'],
        'activation_max': [100.0, 90.0]
    })
    
    # Mock JSON data
    activations_data = {
        'tokens': ['<bos>', 'entity', ':', ' A', ' city', ' in', ' Texas'],
        'counts': [50.0, 100.0, 10.0, 5.0, 80.0, 20.0, 120.0]  # Texas ha max
    }
    
    result = name_relationship_node('1_12928', df, activations_data)
    assert result == "(Texas) related", f"Expected '(Texas) related', got '{result}'"
    print("OK test_name_relationship_node_with_json")


def test_name_relationship_node_skip_bos():
    """Test naming Relationship esclude <bos>"""
    df = pd.DataFrame({
        'peak_token': ['entity'],
        'activation_max': [100.0]
    })
    
    # Mock JSON data con <bos> che ha max activation
    activations_data = {
        'tokens': ['<bos>', 'entity', ':', ' city'],
        'counts': [200.0, 100.0, 10.0, 80.0]  # <bos> ha max ma deve essere escluso
    }
    
    result = name_relationship_node('1_12928', df, activations_data)
    # Dovrebbe prendere 'entity' (primo semantico dopo <bos>)
    assert result == "(entity) related", f"Expected '(entity) related', got '{result}'"
    print("OK test_name_relationship_node_skip_bos")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Esegui tutti i test"""
    print("\n=== Test Normalizzazione ===")
    test_normalize_token_lowercase()
    test_normalize_token_uppercase()
    test_normalize_token_trailing_punct()
    test_normalize_token_whitespace()
    
    print("\n=== Test Naming Semantic ===")
    test_name_semantic_node_basic()
    test_name_semantic_node_punctuation()
    test_name_semantic_node_empty()
    
    print("\n=== Test Naming Say X ===")
    test_name_sayx_node_single_target()
    test_name_sayx_node_no_target()
    test_name_sayx_node_tie_break_backward()
    test_name_sayx_node_distance_priority()
    
    print("\n=== Test Naming Relationship ===")
    test_name_relationship_node_fallback()
    test_name_relationship_node_with_json()
    test_name_relationship_node_skip_bos()
    
    print("\n=== Tutti i test passati! ===")


if __name__ == "__main__":
    run_all_tests()

