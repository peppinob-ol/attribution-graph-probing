"""Verify cross-prompt robustness claims."""
import pandas as pd
from pathlib import Path

# Load data
base = Path(__file__).parent.parent.parent
df = pd.read_csv(base / "output/validation/supernode_transfer_20251027_183408.csv")

print("="*60)
print("CLAIM VERIFICATION: Cross-Prompt Robustness")
print("="*60)

# 1. Universal concepts
print("\n1. UNIVERSAL CONCEPTS TRANSFER")
print("-"*60)
universal = df[df['category'] == 'universal']
print(f"Total universal supernodes: {len(universal)}")
print(f"Present in Dallas: {universal['Dallas_present'].sum()}")
print(f"Present in Oakland: {universal['Oakland_present'].sum()}")
both = (universal['Dallas_present'] & universal['Oakland_present']).sum()
print(f"Present in BOTH: {both}")
print(f"Transfer rate: {both}/{len(universal)} = {both/len(universal)*100:.1f}%")

print("\nDetails:")
for _, row in universal.iterrows():
    d = "Y" if row['Dallas_present'] else "N"
    o = "Y" if row['Oakland_present'] else "N"
    status = "TRANSFERRED" if (row['Dallas_present'] and row['Oakland_present']) else "FAILED"
    print(f"  {row['supernode_name']:20s} Dallas:{d} Oakland:{o} -> {status}")

# 2. Entity-specific
print("\n2. ENTITY-SPECIFIC CONCEPTS (Should NOT Transfer)")
print("-"*60)
entity = df[df['category'] == 'entity_specific']
print(f"Total entity-specific supernodes: {len(entity)}")

# Count appropriate non-transfers (in one but not both)
appropriate = ((entity['Dallas_present'] & ~entity['Oakland_present']) | 
               (~entity['Dallas_present'] & entity['Oakland_present'])).sum()
inappropriate = (entity['Dallas_present'] & entity['Oakland_present']).sum()

print(f"Appropriate non-transfer (one probe only): {appropriate}")
print(f"Inappropriate transfer (both probes): {inappropriate}")
print(f"Success rate: {appropriate}/{len(entity)} = {appropriate/len(entity)*100:.1f}%")

print("\nDetails:")
for _, row in entity.iterrows():
    d = "Y" if row['Dallas_present'] else "N"
    o = "Y" if row['Oakland_present'] else "N"
    if row['Dallas_present'] and row['Oakland_present']:
        status = "WRONG: in both!"
    elif row['Dallas_present'] or row['Oakland_present']:
        status = "CORRECT: probe-specific"
    else:
        status = "ERROR: in neither"
    print(f"  {row['supernode_name']:20s} Dallas:{d} Oakland:{o} -> {status}")

# 3. Feature overlap
print("\n3. FEATURE OVERLAP")
print("-"*60)
df_sim = pd.read_csv(base / "output/validation/activation_similarity_20251027_183408.csv")
print(f"Shared features: {len(df_sim)}")
print(f"Mean activation relative diff: {df_sim['activation_max_rel_diff'].mean():.3f}")
print(f"Mean sparsity diff: {df_sim['sparsity_diff'].mean():.3f}")
print(f"Peak token same: {df_sim['peak_token_same'].sum()}/{len(df_sim)} ({df_sim['peak_token_same'].sum()/len(df_sim)*100:.1f}%)")
print(f"Peak type same: {df_sim['peak_type_same'].sum()}/{len(df_sim)} ({df_sim['peak_type_same'].sum()/len(df_sim)*100:.1f}%)")

# 4. Grouping consistency
print("\n4. GROUPING CONSISTENCY (Shared Features)")
print("-"*60)
# Count how many shared features have equivalent supernodes
consistent = 0
inconsistent = 0
for _, row in df_sim.iterrows():
    sn1 = row['Dallas_supernode']
    sn2 = row['Oakland_supernode']
    
    # Check if equivalent
    if pd.isna(sn1) and pd.isna(sn2):
        consistent += 1
    elif pd.isna(sn1) or pd.isna(sn2):
        inconsistent += 1
    elif sn1 == sn2:
        consistent += 1
    else:
        # Check if semantically equivalent
        # Simple check: same category words
        if any(word in str(sn1).lower() and word in str(sn2).lower() 
               for word in ['is', 'capital', 'of', 'seat', 'containing', 'related']):
            consistent += 1
        else:
            inconsistent += 1

print(f"Consistent grouping: {consistent}/{len(df_sim)} ({consistent/len(df_sim)*100:.1f}%)")
print(f"Inconsistent grouping: {inconsistent}/{len(df_sim)} ({inconsistent/len(df_sim)*100:.1f}%)")

# 5. Show some inconsistent cases
print("\nInconsistent cases (for review):")
for _, row in df_sim.iterrows():
    sn1 = row['Dallas_supernode']
    sn2 = row['Oakland_supernode']
    if pd.notna(sn1) and pd.notna(sn2) and sn1 != sn2:
        if not any(word in str(sn1).lower() and word in str(sn2).lower() 
                   for word in ['is', 'capital', 'of', 'seat', 'containing', 'related']):
            print(f"  {row['feature_key']}: {sn1} vs {sn2}")

print("\n" + "="*60)
print("VERIFICATION COMPLETE")
print("="*60)

