#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisi delle feature che rispondono ai prompt sonda
"""

import json
import sys
import io

# Fix encoding per Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Feature chiave dai prompt sonda
probe_features = {
    "24_13277": {"Capital": 80.5, "Dallas": 39.75, "State": 72.0, "Texas": 71.5},
    "4_13154": {"Capital": 26.25, "Dallas": 15.5, "State": -0.0, "Texas": 23.875},
    "14_2268": {"Capital": 27.875, "Dallas": 13.9375, "State": -0.0, "Texas": 15.9375},
    "20_15589": {"Capital": 51.25, "Dallas": 34.25, "State": -0.0, "Texas": 53.5},
    "7_3099": {"Capital": 36.25, "Dallas": 32.5, "State": 35.0, "Texas": 33.5},
    "23_57": {"Capital": 29.375, "Dallas": 29.0, "State": 39.5, "Texas": 37.25},
    "25_4717": {"Capital": 180.0, "Dallas": -0.0, "State": 20.875, "Texas": -0.0},
}

# Carica feature personalities
with open("output/feature_personalities_corrected.json", 'r', encoding='utf-8') as f:
    personalities = json.load(f)

# Carica archetipi
with open("output/narrative_archetypes.json", 'r', encoding='utf-8') as f:
    archetypes = json.load(f)

# Trova in quale archetipo è ciascuna feature
def find_archetype(feature_key):
    for archetype_name, features in archetypes.items():
        for item in features:
            if item['feature_key'] == feature_key:
                return archetype_name
    return "not_found"

print("=" * 80)
print("ANALISI FEATURE SEMANTICHE DAI PROMPT SONDA")
print("=" * 80)

for feature_key, probe_values in probe_features.items():
    if feature_key not in personalities:
        print(f"\n❌ {feature_key}: NON TROVATA in personalities")
        continue
    
    p = personalities[feature_key]
    archetype = find_archetype(feature_key)
    
    print(f"\n{'='*80}")
    print(f"Feature: {feature_key} (Layer {p['layer']})")
    print(f"{'='*80}")
    
    print(f"\n📊 ATTIVAZIONI SUI PROMPT SONDA:")
    for prompt, value in probe_values.items():
        print(f"   {prompt:15s}: {value:8.2f}")
    
    # Calcola media e consistenza delle attivazioni
    vals = [v for v in probe_values.values() if v > 0]
    if vals:
        avg_activation = sum(vals) / len(vals)
        n_active = len([v for v in probe_values.values() if v > 0])
        print(f"\n   Media attivazione: {avg_activation:.2f}")
        print(f"   Prompt attivi: {n_active}/4")
    
    print(f"\n🎭 METRICHE ANTROPOLOGICHE:")
    print(f"   Mean consistency:      {p['mean_consistency']:.3f}")
    print(f"   Max affinity:          {p['max_affinity']:.3f}")
    print(f"   Conditional consist.:  {p['conditional_consistency']:.3f}")
    print(f"   Label affinity:        {p['label_affinity']:.3f}")
    
    print(f"\n🔗 METRICHE CAUSALI:")
    print(f"   Node influence:        {p.get('node_influence', 0):.3f}")
    print(f"   Causal in-degree:      {p.get('causal_in_degree', 0)}")
    print(f"   Causal out-degree:     {p.get('causal_out_degree', 0)}")
    print(f"   Output impact:         {p['output_impact']:.3f}")
    
    print(f"\n📈 COMPORTAMENTO:")
    print(f"   Peak token:            {p['most_common_peak']}")
    print(f"   Activation stability:  {p['activation_stability']:.3f}")
    
    print(f"\n🏛️  CLASSIFICAZIONE:")
    print(f"   Archetipo:             {archetype.upper()}")
    
    # Interpretazione
    print(f"\n💡 INTERPRETAZIONE:")
    
    if p['mean_consistency'] > 0.7 and p['max_affinity'] > 0.7:
        print(f"   ✅ Feature SEMANTIC ANCHOR: alta consistenza e affinità")
    elif p['mean_consistency'] > 0.7:
        print(f"   ✅ Feature STABLE CONTRIBUTOR: alta consistenza ma affinità media")
    elif p['max_affinity'] > 0.7:
        print(f"   ⚠️  Feature SPECIALIST: specializzata su pochi contesti")
    elif p['mean_consistency'] == 0 and p['output_impact'] > 0.08:
        print(f"   ⚠️  Feature COMPUTAZIONALE: alta influenza ma bassa semantica")
    else:
        print(f"   ⚠️  Feature con comportamento instabile o outlier")
    
    if p['label_affinity'] > 0.5:
        print(f"   ✅ Si attiva fortemente sul label target")
    
    if p.get('node_influence', 0) > 0.1:
        print(f"   ✅ Alto impatto causale sulla predizione finale")

print("\n" + "="*80)
print("STATISTICHE COMPLESSIVE")
print("="*80)

# Conta archetipi
archetype_counts = {}
for feature_key in probe_features.keys():
    arch = find_archetype(feature_key)
    archetype_counts[arch] = archetype_counts.get(arch, 0) + 1

print("\nDistribuzione archetipi:")
for arch, count in archetype_counts.items():
    print(f"   {arch:25s}: {count}")

# Conta feature semantiche vs computazionali
n_semantic = len([fk for fk in probe_features.keys() 
                  if fk in personalities and personalities[fk]['mean_consistency'] > 0.5])
n_specialists = len([fk for fk in probe_features.keys() 
                     if fk in personalities and personalities[fk]['max_affinity'] > 0.7 
                     and personalities[fk]['mean_consistency'] < 0.5])
n_computational = len([fk for fk in probe_features.keys() 
                       if fk in personalities and personalities[fk]['mean_consistency'] == 0])

print(f"\nTipologie:")
print(f"   Semantic (mean_cons > 0.5):  {n_semantic}/{len(probe_features)}")
print(f"   Specialist (max_aff > 0.7):  {n_specialists}/{len(probe_features)}")
print(f"   Computational (mean_cons=0): {n_computational}/{len(probe_features)}")

