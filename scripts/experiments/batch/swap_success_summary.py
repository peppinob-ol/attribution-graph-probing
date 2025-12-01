"""Summarize swap success rates."""
import csv
from pathlib import Path

# Load detailed results
detailed = Path('output/usa_states_batch/_swaps/_analysis_v3/detailed_results.csv')
with open(detailed, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    results = list(reader)

# Categorize
successful = []      # tier 3, 4, 5 (target state info present)
just_ablated = []    # tier 2 (suppressed only)
unsuccessful = []    # tier 1 (source persists)

for r in results:
    tier = int(r['tier'])
    if tier >= 3:
        successful.append(r)
    elif tier == 2:
        just_ablated.append(r)
    else:
        unsuccessful.append(r)

total = len(results)
print('=' * 70)
print('FULL SWAP RESULTS (all states)')
print('=' * 70)
print(f'Total swaps: {total}')
print()
print(f'SUCCESSFUL (tier 3-5, target state info):  {len(successful):3d}  ({len(successful)/total*100:.1f}%)')
print(f'JUST ABLATED (tier 2, no target info):     {len(just_ablated):3d}  ({len(just_ablated)/total*100:.1f}%)')
print(f'UNSUCCESSFUL (tier 1, source persists):    {len(unsuccessful):3d}  ({len(unsuccessful)/total*100:.1f}%)')

# Breakdown of successful
perfect = [r for r in successful if int(r['tier']) == 5]
city = [r for r in successful if int(r['tier']) == 4]
state_only = [r for r in successful if int(r['tier']) == 3]
print()
print('Successful breakdown:')
print(f'  PERFECT (exact capital):     {len(perfect):3d}')
print(f'  TARGET_STATE_CITY:           {len(city):3d}')
print(f'  TARGET_STATE_ONLY:           {len(state_only):3d}')

# Now exclude problematic states (CO, NV, NY)
problem_states = ['Colorado', 'Nevada', 'New York']
clean_results = [r for r in results 
                 if r['from_state'] not in problem_states 
                 and r['to_state'] not in problem_states]

clean_successful = [r for r in clean_results if int(r['tier']) >= 3]
clean_ablated = [r for r in clean_results if int(r['tier']) == 2]
clean_unsuccessful = [r for r in clean_results if int(r['tier']) == 1]

clean_total = len(clean_results)
print()
print('=' * 70)
print('EXCLUDING CO, NV, NY (problematic prompt design)')
print('=' * 70)
print(f'Total swaps: {clean_total}')
print()
print(f'SUCCESSFUL (tier 3-5, target state info):  {len(clean_successful):3d}  ({len(clean_successful)/clean_total*100:.1f}%)')
print(f'JUST ABLATED (tier 2, no target info):     {len(clean_ablated):3d}  ({len(clean_ablated)/clean_total*100:.1f}%)')
print(f'UNSUCCESSFUL (tier 1, source persists):    {len(clean_unsuccessful):3d}  ({len(clean_unsuccessful)/clean_total*100:.1f}%)')

clean_perfect = [r for r in clean_successful if int(r['tier']) == 5]
clean_city = [r for r in clean_successful if int(r['tier']) == 4]
clean_state = [r for r in clean_successful if int(r['tier']) == 3]
print()
print('Successful breakdown:')
print(f'  PERFECT (exact capital):     {len(clean_perfect):3d}')
print(f'  TARGET_STATE_CITY:           {len(clean_city):3d}')
print(f'  TARGET_STATE_ONLY:           {len(clean_state):3d}')

# Show which pairs failed in clean set
print()
print('=' * 70)
print('UNSUCCESSFUL PAIRS IN CLEAN SET (tier 1: source persists)')
print('=' * 70)
for r in clean_unsuccessful:
    print(f"  {r['from_state']:12} -> {r['to_state']:12}")

print()
print('=' * 70)
print('JUST ABLATED PAIRS IN CLEAN SET (tier 2: no target info)')
print('=' * 70)
for r in clean_ablated:
    print(f"  {r['from_state']:12} -> {r['to_state']:12}")

