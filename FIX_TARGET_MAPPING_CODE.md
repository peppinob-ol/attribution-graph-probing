# Quick Guide: Fix Target-Token Mapping in Code

**Time Required**: 5 minutes  
**Files to Modify**: 1 file (`scripts/02_node_grouping.py`)  
**Lines to Change**: 2 fixes (lines 47 and after 44)

---

## FIXES NEEDED

### Fix 1: Correct 'of' Directionality ❌→✅

**Line 47** in `scripts/02_node_grouping.py`

**Current (WRONG)**:
```python
"of": "forward",
```

**Fix to**:
```python
"of": "backward",  # Possessive: "capital of Texas" looks back to "capital"
```

**Why**: The word "of" indicates possession/relation and should look backward.
- Example: "capital **of** Texas" → should find "capital" (backward), not forward tokens
- Current code looks forward, which is semantically wrong

---

### Fix 2: Add ''s' Possessive Token ❌→✅

**After line 44** in `scripts/02_node_grouping.py`

**Current**:
```python
# Articoli
"the": "forward",
"a": "forward",
"an": "forward",

# Preposizioni comuni  ← INSERT HERE
"of": "backward",  # (after fixing above)
```

**Add**:
```python
# Articoli
"the": "forward",
"a": "forward",
"an": "forward",

# Possessive markers
"'s": "backward",  # Possessive: "Texas's capital" looks back to "Texas"

# Preposizioni comuni
"of": "backward",  # (after fixing above)
```

**Why**: Possessive "'s" should look backward to the owner.
- Example: "Texas**'s** capital" → should find "Texas" (backward)
- Currently missing from vocabulary

---

## COMMANDS TO APPLY FIXES

### Option A: Manual Edit (Recommended)

Open `scripts/02_node_grouping.py` and:

1. **Line 47**: Change `"of": "forward",` to `"of": "backward",`
2. **After line 44**: Add:
   ```python
   # Possessive markers
   "'s": "backward",  # Possessive: "Texas's capital" looks back
   ```

### Option B: Automated with sed/PowerShell

**PowerShell** (Windows):
```powershell
# Backup first
Copy-Item scripts/02_node_grouping.py scripts/02_node_grouping.py.backup

# Fix 1: Change 'of' from forward to backward
(Get-Content scripts/02_node_grouping.py) -replace '"of": "forward"', '"of": "backward"  # Possessive' | Set-Content scripts/02_node_grouping.py

# Fix 2: Add 's (more complex, do manually or with script below)
```

---

## VERIFICATION

After making changes, verify:

```python
# Check Fix 1: 'of' is now backward
python -c "from scripts.node_grouping_02 import FUNCTIONAL_TOKEN_MAP; print(FUNCTIONAL_TOKEN_MAP['of'])"
# Should output: backward

# Check Fix 2: ''s' is in the map
python -c "from scripts.node_grouping_02 import FUNCTIONAL_TOKEN_MAP; print(\"'s\" in FUNCTIONAL_TOKEN_MAP)"
# Should output: True
```

Or simply search:
```bash
grep '"of":' scripts/02_node_grouping.py
# Should show: "of": "backward"

grep "'s':" scripts/02_node_grouping.py  
# Should show: "'s": "backward"
```

---

## TEST THE FIXES

Run on example data:

```bash
python scripts/02_node_grouping.py \
  --input output/examples/Dallas/Dallas_2024-10-28T11-30_export.csv \
  --graph output/examples/Dallas/Dallas_attribution_graph_2024-10-28T11-29.json \
  --output output/test_mapping_fixed.csv \
  --window 7
```

**What to check**:
1. Features peaking on "of" should now map backward correctly
2. No errors about missing tokens
3. Say-X naming should be more accurate for possessive constructions

---

## EXPECTED IMPACT

### Before Fixes:
- ❌ "capital **of** Texas" → looks forward, misses entity
- ❌ "Texas**'s** capital" → "'s" not recognized, might be classified as semantic
- ❌ Say-X naming incorrect for possessive features

### After Fixes:
- ✅ "capital **of** Texas" → looks backward, finds "capital"
- ✅ "Texas**'s** capital" → looks backward, finds "Texas"
- ✅ Say-X naming correct for possessive constructions

---

## COMPLETE FIXED SECTION

Here's what the fixed section should look like:

```python
FUNCTIONAL_TOKEN_MAP = {
    # Articoli
    "the": "forward",
    "a": "forward",
    "an": "forward",
    
    # Possessive markers
    "'s": "backward",  # Possessive: "Texas's capital" looks back to "Texas"
    
    # Preposizioni comuni
    "of": "backward",  # Possessive: "capital of Texas" looks back to "capital"
    "in": "forward",
    "to": "forward",
    "for": "forward",
    "with": "forward",
    "on": "forward",
    "at": "forward",
    "from": "forward",
    "by": "forward",
    "about": "forward",
    "as": "forward",
    "over": "forward",
    "under": "forward",
    "between": "forward",
    "through": "forward",
    
    # Verbi ausiliari e copule
    "is": "forward",
    "are": "forward",
    "was": "forward",
    # ... rest unchanged
}
```

---

## REGRESSION TESTING

After fixes, re-run baseline experiments:

```bash
# Test Dallas circuit
python scripts/02_node_grouping.py \
  --input output/examples/Dallas/activations.csv \
  --graph output/examples/Dallas/graph.json \
  --output output/validation/dallas_fixed_mapping.csv

# Compare with previous results
# Check that Say-X features with 'of' peaks now have correct target_tokens
```

---

**Time to apply**: 5 minutes  
**Risk**: Low (only affects possessive token handling)  
**Testing**: Run on Dallas example circuit  
**Validation**: Check Say-X naming for features peaking on 'of' or ''s'

