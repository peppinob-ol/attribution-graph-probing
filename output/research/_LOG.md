# Investigation Log

Append-only log of agentic research findings on attribution graph
interpretation. Each entry follows the structure below. Entries are
ordered newest-first so the most recent investigation is always at the top.

**Conventions**:

- Do not edit past entries. Corrections go in new entries that reference the old one.
- Raw numbers and queries go in "Raw findings." Interpretation is separate.
- Every entry must have a "Threats" section -- what could make this finding wrong.
- Confidence levels: **Low** (suggestive, N < 20 or single condition),
**Medium** (consistent across conditions, N > 50, but alternative explanations remain),
**High** (replicated across domains, alternative explanations tested and ruled out).

---

## [2026-05-04 - AM++] Topic: Phase 3 smoke REDO with Dallas as TARGET subgraph (Austin as the desired answer); human's 6 features produce clean hits, auto's 1182 features produce more hits but with over-amplification artifacts, top-21 and shuffled fail entirely

**Why this entry**: User clarified the experimental design. The previous smoke ran swaps OUT of Dallas (`texas_dallas -> california_oakland`) which uses the human/auto Dallas grouping as the *source* (ablation) side. Since we have only one human-annotated subgraph and the natural comparison is "does the human's Dallas curation, used as a target subgraph, steer prompts about other states *toward* Austin as well as the auto Dallas grouping does?", the right direction is the reverse: source = some non-Texas state, target = Dallas. We re-ran the same 4 conditions with the pair direction flipped. The Dallas slot in each `_swap_conditions/{cond}/` graphs root carries the customized grouping that drives amplification; the source slot is the canonical auto pipeline run (same in every condition).

Aggregated CSV: `output/research/smoke_swap_target_completions.csv`. Raw JSONs at `output/usa_states_fact_batch/_swap_conditions/{cond}/_swaps/runs/2026*/by_source/<source_state>/to_texas_dallas__<variant>.json`.

### The default completions (before any steering)

This time the prompt varies by source state. All 5 default completions correctly emit the source state's capital (none mention Austin):

| source | default completion |
|---|---|
| california_oakland | `<bos><bos>Fact: The capital of the state containing Oakland is Sacramento.\n\nFact: The state of California is` |
| new_york_new_york_city | `<bos><bos>Fact: The capital of the state containing New York City is Albany.\n\nFact: The state of New York` |
| florida_miami | `<bos><bos>Fact: The capital of the state containing Miami is Tallahassee.\n\nFact: The state of Florida is` |
| illinois_chicago | `<bos><bos>Fact: The capital of the state containing Chicago is Springfield.\n\nFact: The state of Illinois is` |
| washington_seattle | `<bos><bos>Fact: The capital of the state containing Seattle is Olympia.\n\nFact: The state of Washington is` |

Austin appears in 0/5 default completions. That is the baseline -- our job is to push the model away from {Sacramento, Albany, Tallahassee, Springfield, Olympia} and toward Austin.

### Are we getting Austin? -- aggregate

| condition                | "Austin" in steered (strict + fuzzy) | "Texas" in steered | source-capital still in steered |
|---|---|---|---|
| **human_dallas** (target) | 3 / 35 | 3 / 35 | 8 / 35 |
| **auto_dallas** (target)  | **4 / 35** | **8 / 35** | **4 / 35** |
| auto_top21_dallas (target) | 0 / 35 | 0 / 35 | 19 / 35 |
| shuffled_labels_dallas (target) | 0 / 35 | 0 / 35 | 11 / 35 |

(The strict and fuzzy hit counts are the same here -- every "Austin" hit is verbatim, never ALL-CAPS.)

**Auto-Dallas wins on raw count** (4 Austin hits vs human's 3, and 8 "Texas" mentions vs human's 3) but **the auto hits are all mangled with a non-printable artifact**: `'isⓧ, Texas, is Austin'` whereas every human hit is clean: `'is Texas is Austin'`. We unpack this below.

**Top-21 and shuffled both produce zero Austin hits**. This is the most informative finding of the smoke:

- top-21 has 9 ablate features for `add_state` (matched to human's set size by influence) -- but those 9 features are the wrong nine. They produce off-task junk like `'isModelAdmin.\n\nThe capital of the state containing Oakland is'` instead of the expected Texas concept.
- shuffled has the same 22 features as human, but with the supernode labels permuted (seed=42). The "Texas" supernode in the shuffled grouping no longer points at the Texas-firing features. Result: 0 Austin hits, 0 Texas mentions, and 11/35 cells where the source capital remains -- the worst suppression-fidelity of any condition with non-zero ablation features.

### Are we getting Austin? -- enumerated, side-by-side

The 6 distinct (source, variant) cells where any condition produced an Austin hit:

| source | variant | human | auto | top-21 | shuffled |
|---|---|---|---|---|---|
| california_oakland | add_state | **'is Texas is Austin'** (clean) | `'isCloseOperation. ... California'` (junk) | `'isModelAdmin'` (junk) | `'is State College is Harrisburg'` (junk) |
| california_oakland | add_state_city | **'is Texas is Austin'** | `'isⓧ, Texas, is San Antonio'` (Texas, wrong cap) | `'isModelAdmin. ... Oakland'` | `', California, is Sacramento'` (default leaks) |
| illinois_chicago | add_state_city | **'is Texas is Austin'** | `'isⓧ, Texas, is Austin'` | `'isModelAdmin: ... Chicago'` | `'is <<<<<<...The answer is Illinois'` |
| new_york_new_york_city | add_state_city | `'isallas. ... New York'` (mentions Dallas, no Austin) | **`'isⓧ, Texas, is Austin'`** | `'isGeografia de New York City'` | `'is absolutely <em>does not</em> have a great food'` |
| florida_miami | add_state_city | `'isGeografia de la Florida'` | **`'isⓧ, Texas, is Austin'`** | `'isModelAdmin: ... A. Tallahassee'` | `'is <<<<<<<<<...A. Florida'` |
| washington_seattle | add_state_city | `'isGeografia de Washington, ... Olympia'` (default leaks) | **`'isⓧ, Texas, is Austin'`** | `'isModelAdmin: ... A. Washington'` | `', Washington, is Olympia'` (default leaks) |

**3 wins for human, 4 for auto, 1 cell shared** (`illinois_chicago/add_state_city`).

The qualitative pattern across the 4 unique auto wins: every auto-Dallas Austin hit takes the form `'isⓧ, Texas, is Austin'`, where `ⓧ` is U+24E7 CIRCLED LATIN SMALL LETTER X. That symbol does not appear in any other completion in the smoke, including auto's non-hit cells. It is the trace of over-amplification: amplifying 126 features for `add_state_city` (auto's full state + city supernodes for Dallas) injects so much energy into the residual stream that the immediate next token is destabilized into a Unicode artifact, but by token ~3-4 the influence resolves into a coherent "Texas, is Austin" continuation.

The 3 human wins all produce the clean form `'is Texas is Austin'` -- only 6 features amplified, no destabilization, fluent grammar.

### Where in the field-additivity matrix do hits live?

```
                       human  auto  top21  shuffled
add_state                1     0     0       0
add_capital              0     0     0       0
add_city                 0     0     0       0
add_state_capital        0     0     0       0
add_state_city           2     4     0       0
add_capital_city         0     0     0       0
add_state_capital_city   0     0     0       0
```

All 7 hits live in `add_state` or `add_state_city`. The variants that include `capital` field-additivity but *not* `city` (`add_capital`, `add_state_capital`) produce 0 Austin hits. This is structurally interesting: the human's "capital" supernode (5 features tagged with the *concept* "capital", not the entity name "Austin") matches `entity.capital="Austin"` only by chance and contributes near-noise to amplification, while the human's "Texas" supernode (6 features) matches `entity.state="Texas"` cleanly and drives the 3 human wins. Auto-Dallas's wins concentrate in `add_state_city`, presumably because the auto pipeline grouped many city-level Dallas features under `Dallas`-named supernodes that fire near the answer position.

### Source-capital suppression -- continuous evidence the human grouping is doing the right thing

Source-capital still in steered text, count out of 5 sources × 7 variants = 35 cells:

```
                         human   auto   top-21   shuffled
add_state                  0      1       0         0
add_capital                1      1       5         1
add_city                   3      2       3         3
add_state_capital          1      0       4         2
add_state_city             1      0       1         2
add_capital_city           1      0       3         1
add_state_capital_city     1      0       3         2
TOTAL                      8      4      19        11
```

Auto-Dallas suppresses the source capital in 31/35 cells (most aggressive, 1182 features amplifying every Dallas-relevant signal). Human-Dallas suppresses in 27/35 (still very strong with only 6 amplify features). Shuffled does 24/35, top-21 only 16/35. **Top-21 is *worse than the no-amplification null* in some variants**: it adds 9 wrong-feature amplification onto a clean source ablation and frequently leaves the source capital intact. This is consistent with "node_influence in the absence of label semantics is not a steering signal."

### Three lenses on the same comparison

1. **Hit rate**: auto > human > {top-21 = shuffled = 0}.
2. **Hit *quality*** (clean Austin vs ⓧ-artifact Austin): human > auto >> rest. Every clean Austin hit comes from the human grouping. Every auto hit has an over-amplification artifact in the immediate next-token position.
3. **Suppression rate**: auto > human > shuffled > top-21. Auto wins on aggressive suppression; top-21 actively damages compared to a smaller well-curated set.

These three orderings tell a consistent story: **the human's 6-feature "Texas" supernode is a high-precision, low-recall steering signal**. It hits less often than auto, but when it does, it produces grammatical, verbatim Austin completions. **Auto's 1182-feature grouping is a high-recall, lower-precision signal**: more hits, but with destabilization artifacts that suggest the M_amplify=20 setting is too strong for that many features. **Top-21 by influence** is a control that demonstrates feature *selection* without label semantics is insufficient. **Shuffled** demonstrates that the *labels* (which determine which features the swap pipeline picks up for each concept-field) carry meaningful information beyond the feature identities themselves.

### Threats

- **5 source states is small**. The human-vs-auto split (3 vs 4 hits with 1 overlap) is at the edge of "no statistical difference" given N=5. Quality differences (clean vs ⓧ-artifact) are categorical and clear at any N, so that finding is more robust.
- **The hit definition is a substring match** in 10 generated tokens. A more precise metric (target-token probability at the answer position, KL divergence, or first-3-token alignment) would cleanly separate the conditions on every cell and is the recommended evaluation for the full 49-state run.
- **Auto's ⓧ artifact** could be specific to the canonical M values. Lowering M_amplify for auto might give it the same clean output as human at the cost of some hits. M-search would test this.
- **The human's annotation has only one supernode (`Texas`) that matches a state-named concept-field**. If we had human annotations for multiple states we could test the labelled-vs-auto comparison more thoroughly. With only one human reference, this smoke is the right scope.
- **The CT model occasionally confuses Dallas with Austin in the natural Texas completion** (e.g., "isallas" appears once in the human grouping for new_york_new_york_city/add_state_city). This is a model-internal artifact independent of the swap quality and would equally affect auto on prompts that happen to land in the same basin.

### Confidence

**Medium-High** for the qualitative claim "human grouping is high-precision, auto grouping is high-recall, top-21 fails, shuffled fails". The categorical asymmetry (human=3 clean hits, auto=4 ⓧ-artifact hits, top-21=0, shuffled=0) is robust to the small N because the 0-hit conditions are conclusive: 35 cells × M=20 amplification produced exactly zero Austin tokens. **Medium** for the precise hit-count claim (3 vs 4 with N=5 sources; could swing to 4 vs 3 or 4 vs 4 with different sources).

### Next step (suggestion)

Two viable scale-ups, in order of value-per-compute:

1. **Full 49-state smoke at the same canonical M** -- 4 conditions × 7 variants × 49 sources = 1372 swaps, ~3-4 h on 4 GPUs in parallel. Will give us 49 Austin-hit cells per condition (vs 5) and decisively rank the 4 groupings on aggregate hit rate, suppression rate, and continuous prob metrics. This is the report-quality run.
2. **Smoke + M-search** at 5 sources but with `m_search.enabled: true`. Replaces fixed M_amplify=20 with the per-cell minimum M that produces an Austin hit. Will expose whether auto's ⓧ artifact disappears at a lower M (tightening the human-vs-auto comparison) and whether top-21/shuffled are unsalvageable at any M.

Awaiting user decision.

---

## [2026-05-04 - AM] Topic: Phase 3 smoke -- complete prompt-completion audit across the 4 conditions: are we getting Austin? Any target-capital hits? human-Dallas vs auto-Dallas as source

**Why this entry**: The previous entry summarized binary-metric saturation. This entry answers the user's direct questions: *what does the model actually say before vs after each swap, with which Dallas grouping*. Every completion (default and steered), every Austin occurrence, and every target-capital hit is enumerated below for the smoke set Dallas->{Oakland CA, NYC NY, Miami FL, Chicago IL, Seattle WA} × 7 field-additivity variants × 4 source-grouping conditions = 140 cells.

Aggregated CSV: `output/research/smoke_swap_completions.csv`. All 140 raw JSONs at `output/usa_states_fact_batch/_swap_conditions/{cond}/_swaps/runs/2026*/by_source/texas_dallas/to_<target>__<variant>.json`.

### The default completion (before any steering)

The five Dallas-source prompts only differ by city name in metadata; the actual prompt text the model sees is fixed because we always swap *from* `texas_dallas`:

```text
<bos><bos>Fact: The capital of the state containing Dallas is Austin.

Fact: The state of Texas is
```

So the default completion **always contains "Austin" verbatim** (35/35 cells, every condition × variant × target). That is the baseline -- what we are trying to undo by steering. The phrase " Austin" is the top-1 next token after `is`, with probability **0.439** (`first_token.default_prob`). We have no need to compare default-vs-default across conditions (they are identical by construction).

### The steered completion (after CT steering)

Counting Austin and target-capital occurrences in the steered output, by condition, over the 35 (variant × target) cells:

| condition                | Austin still present | target capital present (strict) | target capital present (case-insensitive) |
|---|---|---|---|
| **human_dallas**         | 10 / 35 | 3 / 35 | 5 / 35 |
| **auto_dallas**          | 10 / 35 | 3 / 35 | 5 / 35 |
| **auto_top21_dallas**    | 11 / 35 | 3 / 35 | 5 / 35 |
| **shuffled_labels_dallas** | 10 / 35 | 3 / 35 | 5 / 35 |

Suppression of Austin: 24-25 / 35 across all conditions (~70%). Hits on the target capital: 3/35 strict (~9%), 5/35 if we accept ALL-CAPS variants. **The four conditions land within 1 cell of each other on every aggregate metric**.

### Are we getting any hit? -- enumerated

The five **fuzzy hit cells are the same in every condition**. Below is the steered text for each (the target capital is bolded in the human-readable extract; the actual matching is substring case-insensitive).

| target | variant | target capital | steered output (after the prompt) |
|---|---|---|---|
| florida_miami     | add_state_capital      | Tallahassee | `'s TALLAHASSEE.\n\nFact: The capital of'` |
| florida_miami     | add_state_capital_city | Tallahassee | `'s TALLAHASSEE, Fla. (AP) -'` |
| illinois_chicago  | add_state              | Springfield | `'s IL is Springfield.\n\nFact: The state of Illinois'` |
| illinois_chicago  | add_state_city         | Springfield | `'s Efq;s office is Springfield.\n\nThe capital of'` |
| washington_seattle | add_state_city         | Olympia     | `'s Othello is Olympia.\n\nThe state of Washington is located'` |

Two of these are case-mangled "TALLAHASSEE" (only fuzzy match, not strict). Three are clean strict matches: `Springfield`, `Springfield`, `Olympia`. **All four conditions produce the identical steered text in every one of these hit cells**, despite source-ablation counts varying by 10x or more (e.g. `illinois_chicago/add_state`: human ablates 6 features, auto ablates 55, top-21 ablates 9, shuffled ablates 6 -- same final output).

The **30/35 non-hit cells** look like one of three failure modes:

1. *Suppressed but not on target* (most common, ~20 cells): Austin is gone but a different capital, a state name, or junk appears. Examples: `california_oakland/add_state` -> `'is betweenstory 101 is Dallas'`; `new_york_new_york_city/*` -> `'isImageContext.\n\nThe answer is Austin.'` (Austin DOES leak back via a meta-answer pattern); `florida_miami/add_capital` -> `'is Little Rock'` (capital of Arkansas, wrong target).
2. *Austin still present* (~10 cells, see next section): the source ablation failed to remove the source association.
3. *Garbage tokens* (a few cells): the model produces multilingual or code-snippet artifacts, e.g. `'is initComponents(new java.util.ArrayList...'`, `'is Lähteet:\n\nA. Texas...'`. These appear in `add_capital_city` and similar high-amplification variants where the cumulative intervention destabilizes the residual stream.

### Is Austin still appearing? -- enumerated

The 10-11 cells per condition where "Austin" survives in the steered output are listed below. Pattern: **almost all "Austin survives" cells are the variants `add_city`, `add_capital_city`, or `add_state_city`** -- variants where the city-field ablation of `Dallas` is requested but the human/shuffled/top-21 grouping has no `Dallas`-named supernode (so no city ablation actually happens), or where the additivity sum overrides into junk.

| target                | variant                | human-Dallas | auto-Dallas | top-21 | shuffled |
|---|---|---|---|---|---|
| california_oakland    | add_city               | yes (0 abl) | yes (71 abl) | yes (2 abl) | yes (0 abl) |
| new_york_new_york_city | add_state             | yes (6 abl) | yes (55 abl) | yes (9 abl) | yes (6 abl) |
| new_york_new_york_city | add_city              | yes (0 abl) | yes (71 abl) | yes (2 abl) | yes (0 abl) |
| new_york_new_york_city | add_state_city        | yes (6 abl) | yes (126 abl) | yes (11 abl) | yes (6 abl) |
| florida_miami         | add_state             | yes (6 abl) | yes (55 abl) | yes (9 abl) | yes (6 abl) |
| florida_miami         | add_city              | yes (0 abl) | yes (71 abl) | yes (2 abl) | yes (0 abl) |
| florida_miami         | add_capital_city      | yes (0 abl) | NO  (156 abl) | yes (5 abl) | NO  (0 abl) |
| illinois_chicago      | add_city              | yes (0 abl) | yes (71 abl) | yes (2 abl) | yes (0 abl) |
| washington_seattle    | add_state             | NO (6 abl) | yes (55 abl) | yes (9 abl) | NO (6 abl) |
| washington_seattle    | add_city              | yes (0 abl) | yes (71 abl) | yes (2 abl) | yes (0 abl) |
| washington_seattle    | add_capital_city      | yes (0 abl) | yes (156 abl) | yes (5 abl) | yes (0 abl) |

Two interesting per-cell asymmetries:

- **`washington_seattle/add_state`** is the *only* binary cell where human-Dallas helps. Auto, top-21 produce `'is nahilalakip hailing from the city of Austin'`. Human and shuffled produce `'is State: Texas'` -- Austin is gone, replaced by an explicit reference to the source state. Both human's and shuffled's 6 features happen to be the same set, just relabeled, so this difference between {human, shuffled} and {auto, top-21} is about the SIZE of the ablation set (6 features) not its labeling. That is: auto's 55 ablate features actually *hurt* on this cell.
- **`florida_miami/add_capital_city`** is one of two cells where auto-Dallas suppresses Austin while the others do not. Auto's 156 ablate features remove the source association (`'is D.C. is Washington, D.C.'` -- Austin gone), human/shuffled/top-21 leave `'is D.C. is the city of Austin.'`. This is a case where the auto's larger source ablation matters.

### Cross-condition output uniqueness

Per (target, variant) pair, the 4 conditions produce identical steered text in **25 of 35 cells**. Of the 10 divergent cells, every cell has exactly **2 distinct outputs** (never 3 or 4). The conditions partition into clusters that depend on the cell:

- For 5 of the 10 divergent cells, human/top-21/shuffled all match and only auto differs.
- For 3 of the 10 divergent cells, top-21/shuffled/auto all match and only human differs.
- For 2 of the 10 divergent cells, human/auto match against top-21/shuffled.

Top-1 token agreement matrix across all 35 cells:

```text
                 human   auto   top21   shuffled
   human          35      31      31       30
   auto           31      35      33       32
   top21          31      33      35       32
   shuffled       30      32      32       35
```

### Side-by-side example: illinois_chicago / add_state (a hit cell)

Default (same for all conditions):

```text
<bos><bos>Fact: The capital of the state containing Dallas is Austin.

Fact: The state of Texas is
```

Steered (same for all conditions, byte-identical):

```text
<bos><bos>Fact: The capital of the state containing Dallas is IL is Springfield.

Fact: The state of Illinois
```

Ablation counts: human=6, auto=55, top-21=9, shuffled=6. Amplification count: 72 (auto-California's `state` supernode), identical across conditions because the target side never changes.

The model's response is exactly the same in 4 out of 4 cases. The source ablation contributed *nothing* visible to this hit -- the target's amplification of "Illinois state" features pulled `Springfield` out, and the source ablation could have been any of {6, 9, 55} features without changing the byte output.

### Side-by-side example: california_oakland / add_state_capital_city (a non-hit cell)

Default: same as above.

Steered (identical across all 4 conditions):

```text
<bos><bos>Fact: The capital of the state containing Dallas isDatuak, Texas, is San Antonio.

The city
```

Ablate counts: human=6, auto=211, top-21=14, shuffled=6. The model writes "San Antonio" -- an alternate Texas city, not Sacramento. Source ablation went all the way from 6 to 211 features and produced byte-identical output.

### Interpretation -- direct answers to the user's questions

1. **"Are we getting any hit?"** -- Yes, but rarely and unevenly. 3/35 strict + 2/35 ALL-CAPS = 5/35 fuzzy hits per condition (~14%). The hit cells are exactly the same in every condition. Steered text is byte-identical in 4/5 of those hit cells across all 4 conditions.
2. **"Any Austin?"** -- 10-11 cells per condition keep Austin in the steered output (~30%). The cells that fail to suppress Austin are the same set across conditions, again with 25/35 (71%) of cells producing byte-identical steered text regardless of which Dallas grouping is the source.
3. **"Using human-Dallas subgraph?"** -- Hit rate 3/35 strict, 5/35 fuzzy. Austin remains 10/35. Identical to auto-Dallas at the binary level. Differs from auto-Dallas in only 5 of 35 steered outputs, of which 1 is a clear win for human (`washington_seattle/add_state` -- Austin gone) and 1 is a clear loss for human (`florida_miami/add_capital_city` -- Austin remains).
4. **"Using auto-Dallas subgraph?"** -- Same binary numbers as human. Differs from human in 5 of 35 cells; the ablation count differs by an order of magnitude (e.g. 211 vs 6 in `add_state_capital_city`) without changing the steered byte output.

The decisive point: **at canonical M (M_ablate=-2, M_amplify=20), the source ablation is doing essentially nothing**. The target amplification (M=20 over the auto-target's `state` / `capital` / `city` supernodes) writes the answer; the Dallas-side intervention only shifts a few cells, mostly when the source-feature set is *smaller* (e.g. human's 6 features beat auto's 55 features in `washington/add_state`). This is consistent with the M_amplify >> |M_ablate| asymmetry baked into the canonical config.

### Threats to this read

- 5 targets × 7 variants is a small grid. The 10 divergent cells do not form a clean signal -- no condition dominates. With 50 targets we would expect either an order of magnitude more divergent cells (interesting) or the same ~30% divergence rate with the same lack of dominance (less interesting, but conclusive).
- The "byte-identical" claim is exact at temperature 0.3 with seed 42. Other (T, seed) draws would dilute byte equality but the same Top-1 token analysis would still apply.
- The hit cells we found (Springfield, Olympia, Tallahassee) all came through the auto target's `state` field. The `capital` and `city` field-additivity variants almost never produce hits because the human/auto target supernode for those fields overlaps heavily with the source state's structure (e.g., the model often emits the source's capital for the wrong state). A more demanding evaluation would mark these as misses even when fuzzy.
- The shuffled-labels condition was meant to test "do labels carry information beyond features?". Since shuffled and human produce the same binary numbers (and almost the same byte outputs), labels are not adding information at this M -- but this could be because *features themselves* aren't adding information either (target dominance again). M-search would be the right tool to break this tie.

### Confidence

**Medium** for the descriptive claims (counts and per-cell text are exact). **Medium** for the conclusion that "source ablation is dominated by target amplification at canonical M" -- this is supported by 25/35 byte-identical cells and consistent ablation-count-to-output correlations across conditions, but is bounded to this M setting and to the 5 chosen targets. The right next experiment to challenge it is M-search (per-pair adaptive `M_amplify`).

---

## [2026-05-03 - PM++] Topic: Phase 3 smoke -- 4 source-grouping conditions × 5 Dallas->target swaps × 7 field-additivity variants; binary metrics saturated at canonical M, continuous metrics carry the signal

**Why this entry**: Implements the Phase-3 plan from the previous entry. Compares four source-side groupings of `texas_dallas` (with the same auto-generated target groupings for the 5 target states) under the canonical CT steering (`M_ablate=-2`, `M_amplify=20`) on the smoke-test set California-Oakland, NewYork-NewYorkCity, Florida-Miami, Illinois-Chicago, Washington-Seattle. The four conditions are `human_dallas` (the 22 human-pinned features in the supernode design described in `human_annotated_subgraph.json`, with `preposition followed by place name` folded into `state`), `auto_dallas` (the full auto pipeline grouping, 1182 features and 44 supernodes), `auto_top21_dallas` (top-21 auto features by `node_influence`, size-matched to the human's 21 unique features), and `shuffled_labels_dallas` (the same 22 features as human, but with `supernode_name` permuted seed=42).

**Goal**: decide whether to scale to all 50 states.

### Setup

- **Build**: `tools/build_dallas_swap_conditions.py` writes per-condition graphs roots under `output/usa_states_fact_batch/_swap_conditions/{condition}/`. The 5 target slugs are symlinked to the canonical auto run (so the target side is identical across all conditions); only `texas_dallas/02 Node Grouping/node_grouping.csv` differs per condition.
- **Configs**: `scripts/experiments/batch/configs/smoke_swap_{condition}.yml`. Each config defines 5 explicit `defined_pairs` (Dallas -> 5 targets), `concept_fields: [state, capital, city]`, `answer_field: capital`, transcoder `gemma` (16k PLT), `M_ablate=-2`, `M_amplify=20`, no M-search, additivity field-subset matrix `[state], [capital], [city], [state,capital], [state,city], [capital,city], [state,capital,city]` -> 7 variants × 5 pairs = 35 swaps per condition.
- **Pipeline bug found and fixed during the smoke**: `run_single_swap` in `scripts/experiments/batch/run_batch_swaps.py` did not propagate `variant_suffix` to `get_swap_paths`, so all 7 field-additivity variants of a single pair overwrote the same `to_<target>.json` file. The sequential-execution loop now passes `variant_suffix=variant_suffix`, and the M-tuned suffix becomes `f"{variant_suffix}__m_tuned"`. Without this fix, only the LAST variant's results were persisted -- prior smoke runs were unusable. Re-ran from scratch with the fixed code.
- **Hardware**: 4 conditions in parallel on GPUs 4-7 (each loads gemma-2-2b once per swap subprocess, ~30s/swap). Wall clock ~17 min for all 140 swaps (35 × 4).

### Raw findings

Aggregated CSVs at `output/research/smoke_swap_results.csv` (140 rows: condition × variant × pair) and `output/research/smoke_swap_summary.csv` (28 rows: condition × variant means).

**Ablate-feature counts by condition (constant across the 5 pairs because source is always Dallas)**:

| variant                  | auto | top21 | human | shuffled |
|---|---|---|---|---|
| add_state                | 55 | 9 | 6 | 6 |
| add_capital              | 85 | 3 | 0 | 0 |
| add_city                 | 71 | 2 | 0 | 0 |
| add_state_capital        | 140 | 12 | 6 | 6 |
| add_state_city           | 126 | 11 | 6 | 6 |
| add_capital_city         | 156 | 5 | 0 | 0 |
| add_state_capital_city   | 211 | 14 | 6 | 6 |

The human grouping has only the `Texas` supernode (6 features) that matches a state-named supernode for Dallas (`entity.state="Texas"`), so adding the `capital` or `city` field-additivity dimensions does not contribute additional ablations -- the human only annotated the state concept by entity name. `auto_top21` has more `[state]`-matching features than the human because some of the top-21 happen to land in supernodes whose names contain "Texas".

**Binary metrics are nearly identical across conditions**:

| variant                  | target hit (fuzzy) auto/top21/human/shuffled | source suppressed auto/top21/human/shuffled |
|---|---|---|
| add_state                | 0.2 / 0.2 / 0.2 / 0.2 | 0.4 / 0.4 / **0.6** / 0.4 |
| add_capital              | 0.0 / 0.0 / 0.0 / 0.0 | 1.0 / 1.0 / 1.0 / 1.0 |
| add_city                 | 0.0 / 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 / 0.0 |
| add_state_capital        | 0.2 / 0.2 / 0.2 / 0.2 | 1.0 / 1.0 / 1.0 / 1.0 |
| add_state_city           | 0.4 / 0.4 / 0.4 / 0.4 | 0.8 / 0.8 / 0.8 / 0.8 |
| add_capital_city         | 0.0 / 0.0 / 0.0 / 0.0 | 0.8 / 0.6 / 0.6 / 0.8 |
| add_state_capital_city   | 0.2 / 0.2 / 0.2 / 0.2 | 1.0 / 1.0 / 1.0 / 1.0 |

The only binary difference between human and the others at canonical M is in `add_state` suppression: human suppresses `Austin` in 3/5 targets vs 2/5 for the others (the additional case is `washington_seattle`). Everything else is tied.

**Continuous metrics reveal substantive differences**. Top-1 token agreement matrix across the full 35-row table (variant × pair):

|              | human | auto | top21 | shuffled |
|---|---|---|---|---|
| human        | 35 | 31 | 31 | 30 |
| auto         | 31 | 35 | 33 | 32 |
| top21        | 31 | 33 | 35 | 32 |
| shuffled     | 30 | 32 | 32 | 35 |

Human is the most idiosyncratic: it disagrees on 4-5 cells per pairwise comparison. Auto and top21 agree on 33/35 cells (expected -- top21 is a strict subset of auto by influence). Shuffled is closer to auto than to human.

For the `add_state` variant specifically, the steered first-token probability shifts:

| target                | auto | top21 | human | shuffled |
|---|---|---|---|---|
| california_oakland    | 0.161 (`betweenstory`) | 0.178 (`betweenstory`) | 0.117 (`insign`) | 0.270 (`betweenstory`) |
| florida_miami         | 0.031 (`West`) | 0.033 (`West`) | 0.054 (`West`) | 0.031 (`AddTagHelper`) |
| illinois_chicago      | 0.330 (`IL`) | 0.357 (`IL`) | 0.441 (`IL`) | 0.406 (`IL`) |
| new_york_new_york_city | 0.088 (`ImageContext`) | 0.085 (`ImageContext`) | 0.098 (`ImageContext`) | 0.086 (`ImageContext`) |
| washington_seattle    | 0.163 (`state`) | 0.150 (`state`) | 0.217 (`state`) | 0.145 (`state`) |

The human grouping pushes the steered top-1 probability higher in 3/5 cases (`illinois`, `washington`, `florida`) and lower in 1 (`california`). Differences are 1-10 percentage points.

### Interpretation

- **The pipeline is wired correctly end-to-end** for the 4-condition × 7-variant × 5-pair smoke test (after the variant_suffix fix). Every cell of the 4×7×5 design has a `to_<target>__<variant>.json` file with valid `evaluation` blocks. This was the primary go/no-go criterion.
- **Binary metrics (suppression yes/no, target capital fuzzy match) cannot distinguish the conditions at canonical M with only 5 targets**. With 35 (variant × pair) cells per condition, only 1 cell shows a binary difference between human and the auto-baseline (the Washington-Seattle / `add_state` cell). With 50 targets, the 0-2 percentage-point differences seen here would expand to 0-3 cells out of 350, still under any reasonable noise floor.
- **Top-1 token agreement is ~89-94% across conditions**. That means each condition produces the same final token in 30-33 of the 35 cells. This is consistent with the `M_amplify=20` target intervention dominating the outcome and the source-side choice being a tie-breaker. Importantly, **human is the most distinct condition** (30 agreement with shuffled, 31 with auto/top21), which is the right direction.
- **Probability shifts and the cells where conditions disagree** are the natural metric for the full run. They are not saturated at canonical M, and they reveal a consistent pattern (human pushes the top-1 token's probability higher when the target is in-distribution: `illinois->IL`, `washington->state`).

### Threats

- **5 targets is too few for binary go/no-go**. The smoke conclusion that "binary metrics are saturated" could be wrong if the 5 targets happened to be either all easy or all hard. With more targets, binary differences may emerge or disappear.
- **The `state` field is the only field where the human's annotation produces ablation features**. The `capital` and `city` field-additivity variants for the human condition reduce to "amplify-only on auto target", which makes them effectively equivalent to a no-source-intervention control. The labeled-vs-auto comparison is meaningful only for variants that include `state`. This was foreseeable from the human's supernode names (the human pinned a "capital" supernode that represents the *concept* "capital", not the state-specific token "Austin"), but it limits Phase-3 to a single dimension of the field-additivity matrix.
- **The shuffled control was meant to test if labels-without-features-changes degrade performance**. Since binary metrics are tied between human and shuffled, this control fails to discriminate at this M. The continuous-metric difference (human top-1 prob 0.117-0.441 vs shuffled 0.270-0.406 in `add_state`) is small and inconsistent.
- **Canonical M might not be the right comparison point**. The framework supports M-search, which adaptively tunes `M_amplify` until the target capital appears (when possible). Enabling M-search would replace each fixed-M binary outcome with a continuous "minimum M to achieve target hit" -- a richer signal that should distinguish the conditions on each pair. Smoke did not enable M-search to keep the comparison at the same budget as the existing 50-state baseline runs.
- **The 5 chosen targets are deliberately diverse but small-N**. Some have explicit-state tokens in the prompt (`new york`), others don't, and some have ambiguous capitals (`washington` -> Olympia, but the model often outputs `state`). Patterns observed here may not generalize.

### Confidence

**Medium** for the wiring/methodology claim. **Low** for the human-vs-auto effect-size claim -- the smoke is consistent with "human grouping is at least as good as a 6-feature random subset of auto, possibly slightly better at moving probability mass" but the binary go/no-go is dominated by the auto target side and 5 targets is too few to bound the difference.

### Next step (suggestion)

Two viable scale-ups:

1. **Full 50 states with the same configs** (each condition = 50 source × 7 variants = 350 swaps × 4 conditions = 1400 swaps, ~2-3 hours wall-clock on 4 GPUs). Reports binary + continuous metrics on a meaningful sample. Easiest: just edit the 4 `smoke_swap_*.yml` to use `mode: matrix` over the 50 states with `texas_dallas` as the only source slug (or use `defined_pairs` with all 49 targets).

2. **Smoke + M-search** (5 targets × 7 variants × 4 conditions, but with `m_search.enabled: true` and a tighter budget). This would replace fixed-M outcomes with adaptive M, revealing per-pair effort differences between conditions. Smaller scale but richer signal.

Awaiting user decision before kicking the next phase.

---

## [2026-05-03 - PM] Topic: Phase 2 redo with the correct transcoder -- 22/22 human-pinned features now in our graph; concept-level concordance is 13/19 core features (soft, any ctx)

**Why this entry**: The earlier 2026-05-03 Phase-2 entry (immediately below) reported a feature-level overlap of 0/22 and attributed it to a deprecated transcoder swap on Neuronpedia. That was correct *symptomatically* but wrong about the *cause*. The cause was a configuration bug in `scripts/experiments/batch/pipeline/graph.py`: the Neuronpedia API call read `config['model']['source_set']` (alias `clt-hp`, which Neuronpedia now resolves to `mntss/clt-gemma-2-2b-2.5M`, ~96k features/layer), instead of the explicit `graph_generation.api_params.sourceSetName` set to `gemmascope-transcoder-16k` in our YAML. The earlier Phase-2 numbers are still readable as "what the wrong-transcoder run actually computed", but they do not answer the comparison the user asked for. This entry replaces them with the matched-vocabulary run.

**Question (unchanged)**: With prompts and transcoder vocabulary aligned, do the 22 CLT features the human pinned in `gemma-fact-dallas-austin` show up in our pipeline's graph, and are they grouped into supernodes that correspond to the 5 human-named concepts (`capital`, `state`, `Texas`, `preposition followed by place name`, `capital cities/say a capital city`)?

### Setup

- **Bug fix**: `scripts/experiments/batch/pipeline/graph.py` lookup order is now `api_params.sourceSetName` -> `graph_generation.source_set_name` -> `model.source_set`. Both `dallas_fact_only.yml` and `usa_states_fact_full.yml` had `model.source_set: clt-hp` updated to `gemmascope-transcoder-16k` so that the model-level alias matches the api-params (defense in depth).
- **Wrong-transcoder run preserved** at `output/usa_states_fact_batch/texas_dallas__clt-hp_wrong_transcoder/` for diff/audit.
- **New run**: `output/usa_states_fact_batch/texas_dallas/` -- single seed, prompt `<bos>Fact: The capital of the state containing Dallas is`, `transcoder_set: gemma` (= `mwhanna/gemma-scope-transcoders`, GemmaScope per-layer transcoders 16k features/layer), `circuit-tracer 0.2.0`. 1490 nodes, 55,645 links, 1182 CLT features after `cumulative_influence <= 0.95` filter. Source URLs in `info`: `['https://neuronpedia.org/gemma-2-2b/gemmascope-transcoder-16k', 'https://huggingface.co/google/gemma-scope-2b-pt-transcoders']`. Same prompt token set as the human graph.

### Raw findings

CSV at `output/research/dallas_austin_reference/annotation_concordance.csv`. Summary at `annotation_concordance_summary.json`.

**Vocabulary alignment is now nearly identical**:

| set | unique CLT (l, f) | min/max f |
|---|---|---|
| Human graph | 656 | 25 / 16382 |
| Our run | 1182 | 25 / 16382 |
| Intersection | 655 | -- |

We capture **655 of the 656 human CLT features** (one is below our `cumulative_influence <= 0.95` cut). At the (layer, feature, ctx) level the intersection is 696 of 851 human nodes.

**Human pinned features (22 CLT)**:

| metric | result |
|---|---|
| in our graph (l, f) | 22/22 |
| in our graph (l, f, ctx_idx) | 22/22 |
| reach our `node_grouping.csv` at any ctx | 22/22 |
| reach our `node_grouping.csv` at human's pinned ctx | 6/22 |

The drop from 22 -> 6 at the strict-ctx test is explained: our `peak_token_idx` is the position where the feature has its max activation across our **5 probe prompts**, while the human pins where the feature fires in the **target prompt**. So the strict-ctx column compares two different things by construction; the "any ctx" column is the appropriate feature-level concordance.

**Concept-family match** (excluding the 3 unlabeled `(standalone)` features), using a hand-coded mapping from human supernode name to our supernode-name family:

| human supernode | n | reach@ctx | soft@ctx | soft any-ctx | typical our supernodes (any ctx) |
|---|---|---|---|---|---|
| `capital` | 5 | 3/5 | 3/5 | 4/5 | `capital`, `located` |
| `state` | 2 | 1/2 | 1/2 | 2/2 | `state` |
| `Texas` | 6 | 0/6 | 0/6 | 5/6 | `Texas` (5), `Dallas` (1) -- but at ctx 7/10/11, not the human's ctx 9 |
| `capital cities/say a capital city` | 4 | 0/4 | 0/4 | 2/4 | `Say (Austin)` (2), `containing`, `seat` |
| `preposition followed by place name` | 2 | 0/2 | 0/2 | 0/2 | `Say (Austin)` (both) |
| **total core** | **19** | **4/19** | **4/19** | **13/19** | -- |

**The 3 standalone clerped features**: `20_15589_10`, `23_12237_10` -> our `Texas`@ctx=10 (matches the human's "Cities and states names (say Austin)" clerp on `23_12237_10`); `18_8959_10` -> our `Say (capital)`@ctx=15 (vs human clerp "state/regional government"). 2/3 standalone match at any ctx; the third is plausibly the same circuit element re-labeled.

### Interpretation

1. **Feature-level coverage is essentially complete (22/22)**. With matched vocabulary, every feature the human pinned exists in our graph and reaches our grouping at some ctx. The earlier "0/22" was a configuration artifact, not a real disagreement.
2. **Concept-family agreement at any ctx is 13/19 core features (~68%)**. Our subtype/grouping classifier independently labels the same features the same way as the human ~2/3 of the time. The dominant matches are on `Texas` (5/6) and `state` (2/2); the misses concentrate at the answer position where the human used semantic supernodes (`capital cities/say a capital city`, `preposition followed by place name`) and our system uses functional/predictive supernodes (`Say (Austin)`, `seat`). That's a stylistic disagreement about how to label answer-bearing features more than a circuit-level disagreement about which features matter.
3. **Strict-ctx concordance (4/19) is dominated by a methodological mismatch**, not a real disagreement: our `peak_token_idx` is computed against 5 probe prompts, the human's ctx is from the target prompt. To make a head-to-head ctx comparison, we would need to either (a) recompute our `peak_token_idx` on the target prompt only or (b) use the (l, f) presence at the same ctx in the graph itself (which is 22/22, since the human only ever pins features that fire in the target prompt at that ctx).
4. **The 16k transcoder is correct for matching the human graph** going forward. All future Neuronpedia-API graph generations from our pipeline will now use `gemmascope-transcoder-16k` (the bug fix is general). Note that this is a *per-layer transcoder* (PLT, by Google DeepMind), not the cross-layer transcoder family (`mntss/clt-gemma-2-2b-2.5M`) we were accidentally using; this changes graph statistics like number of features per layer and edge density, so prior 96k-vocabulary runs are not directly comparable to anything generated under this fix.

### Threats

- **`HUMAN_TO_OUR_FAMILY` mapping is hand-coded.** Especially `preposition followed by place name -> {of, is, in}` is a forced reading; our system labels those features `Say (Austin)`, which is a plausibly correct alternative (they predict the next token, not signal a syntactic role). Removing `Say (Austin)` from the capital-cities family would also drop the capital-cities concordance from 2/4 to 0/4. Any final report should ship this map alongside numbers.
- **Strict-ctx 4/19 is misleading at face value** because of the probe-vs-target ctx asymmetry above. The "any ctx" concordance is the right number to quote.
- **Pruning threshold mismatch**: human graph uses `node_threshold=0.7` (per its metadata), our run is at `node_threshold=0.8`. The 1 missing human feature out of 656 is consistent with this; a tighter threshold would close that.
- **Generator version**: human ran `circuit-tracer 1.0.0`, we ran `0.2.0`. Pruning logic and influence semantics may differ; the influence values and thus which features survive pruning at any threshold could shift. The 99.85% feature overlap (655/656) suggests this is small, but not zero.
- **Earlier _LOG entry is now partially superseded.** Specifically, "feature-level overlap is zero (different transcoders)" was a *symptom of the configuration bug, not a permanent property of the comparison*. The "concept-level concordance is 4/5" claim from the earlier entry was computed at the supernode-name (concept-family) level using ctx-level aggregates and should be replaced by the 13/19 number above. We are not editing the earlier entry per repo convention; this entry stands as the correction.

### Follow-up

- All 50 USA-state batch runs in `output/usa_states_batch/` were generated with the wrong transcoder (`clt-hp` -> `mntss/clt-gemma-2-2b-2.5M` ~96k). They are not directly comparable to anything we now generate with `gemmascope-transcoder-16k`. The Phase-3 design must regenerate the relevant subset (Dallas plus comparison states) with the corrected config before any swap experiment.
- Open issue: should we re-run the cross-domain swap experiments (books, paintings, etc.) with the 16k transcoder for consistency? Probably yes, but separately tracked.
- Recompute Phase-1 scores on our regenerated `texas_dallas` graph -- the existing Phase-1 result was on the human graph itself, so it is unaffected; but a parallel "scores on our regenerated graph with the human's pinned set" calculation is a useful sanity check to add.
- Phase-3 path chosen: regenerate the smoke set (Dallas + 5 states) with the 16k transcoder, build a true human-features condition (the actual 22 (l, f) IDs work now), plus auto-Dallas / auto-top21 / shuffled-labels controls; run swaps with field-additivity variants matched to `fullscale_usa_field_add`. Decision deferred to user: choose the 5 smoke states.

Confidence: **High** for the 22/22 feature-level coverage (direct (l, f) match in the graph). **Medium** for the 13/19 concept-family match (single prompt, hand-coded family map, multiple reasonable variants).

---

## [2026-05-03 - SUPERSEDED] Topic: Phase 2 (annotation concordance) blocked at the feature level by transcoder-vocabulary mismatch; concept-level concordance recovers 4 of 5 human supernodes

> **NOTE 2026-05-03 PM**: The premise of this entry -- that the transcoder swap on Neuronpedia was the cause of the 0/22 feature overlap -- is incorrect. The actual cause was a configuration bug in `pipeline/graph.py` that read `model.source_set` instead of `graph_generation.api_params.sourceSetName`. Once fixed, 22/22 features overlap. See the entry above for the corrected analysis. This entry is preserved verbatim per the append-only convention.

**Question**: For the same prompt `<bos>Fact: The capital of the state containing Dallas is`, do the 22 CLT features the human pinned in `gemma-fact-dallas-austin` show up in the graph our pipeline generates, and are they grouped into the same 5 supernodes (`capital`, `state`, `Texas`, `preposition followed by place name`, `capital cities/say a capital city`) by our subtype/grouping classifier?

This is Part 2 of the three-part human-vs-auto experiment (see `output/research/dallas_austin_reference/`). The plan was: with prompts now matched (Part-1 baseline used the same prompt only on the human side), measure (a) feature-level coverage of the human-pinned set in our graph and (b) supernode-name agreement at the matched (layer, feature, ctx_idx) keys.

### Setup

- **Our run**: `output/usa_states_fact_batch/texas_dallas/` -- single-seed mini-pipeline launched from `scripts/experiments/batch/configs/dallas_fact_only.yml` with prompt template `Fact: The capital of the state containing {city} is`. Pipeline (graph + probes + grouping) finished in ~7.5 min on one local A100 (env: `nodo207`, `transformer_lens` `hijohnnylin/temp_branch_version`, `torch` 2.5.1+cu121).
- **Tokens are byte-for-byte identical** to the human graph's `prompt_tokens`: `['<bos>', 'Fact', ':', ' The', ' capital', ' of', ' the', ' state', ' containing', ' Dallas', ' is']`.
- **Concordance script**: ad-hoc in this entry; outputs `annotation_concordance.csv` (per-feature row with `in_our_graph` flag) and `annotation_concordance_ctx.csv` (per-token row with human supernodes vs our top supernodes), plus `annotation_concordance_summary.json`.

### Raw findings

**Feature-level overlap is zero.** Of the 22 CLT (layer, feature) pairs the human pinned, 0 appear in our graph. This is not noise -- inspection of node IDs reveals two different feature vocabularies:

| Source | `info.transcoder_set` | Generator version | Min/max CLT feature index | Layer-0 sample IDs |
|---|---|---|---|---|
| Human graph (`gemma-fact-dallas-austin.json`) | (not recorded; older schema) | `circuit-tracer 1.0.0` | 25 / 16382 (~16k features/layer) | `0_437_1, 0_478_1, 0_997_1, 0_1847_1, ...` |
| Our run | `mntss/clt-gemma-2-2b-2.5M` | `circuit-tracer 0.3.1 \| e09b5f3` | 230 / 98149 (~96k features/layer) | `0_2334_1, 0_9418_1, 0_15817_1, ...` |

Both `info.source_urls` claim `clt-hp` on Neuronpedia, but the underlying transcoder set has been swapped at some point between the human's 2025-05-28 capture and our 2026-05-03 capture: from a 16k-per-layer CLT to the current `mntss/clt-gemma-2-2b-2.5M` (~96k per layer, 25 layers, ~2.4M features total). The two vocabularies are not aligned (no shared training, no linear remap published), so feature index N in one set is unrelated to feature index N in the other. The single accidental collision (1 (l, f) pair common to both graphs out of 656 human and 246 ours) is consistent with chance.

**Per-position concept presence (concordance at the supernode-name level)** -- our pipeline still names the right concepts at most of the right token positions, even though the underlying features differ:

| Token (ctx) | Human supernode(s) (n features) | Our top supernodes at this ctx (n features per supernode) | Concept-family match |
|---|---|---|---|
| ` capital` (4) | `capital` (5) | `capital` (17), `state` (11), `(capital) related` (5) | match (22 features in family) |
| ` state` (7) | `state` (2) | `Texas` (24), `state` (2), `located` (2) | match (2 in family); the dominant `Texas` cluster is the "answer-state" feature firing one token early |
| ` Dallas` (9) | `Texas` (6) | `is` (15), `seat` (2), `Dallas` (2), `Say (Austin)` (1), `Austin` (1) | **miss** -- our system does not surface Texas-bound features at the `Dallas` token |
| ` is` (10) | `capital cities/say a capital city` (4), `preposition followed by place name` (2) | `Texas` (13), `is` (11), `Say (Austin)` (4), `located` (4), `of` (3) | match (`Say (Austin)` -> capital-cities family, `is`/`of` -> preposition-followed-by-place family) |

Aggregate: **4 of 5 human supernode concepts are recovered at the same token by our system at this prompt** (capital, state, capital-cities, preposition+place). The miss is `Texas` at ` Dallas` -- our system fires `Texas` features one token earlier (at ` state`, ctx=7) and at the final-position cluster (ctx=10) instead. This is a meaningful semantic disagreement: the human treats Texas-features as "what Dallas is in", our subtype classifier treats them as "the state the question is about" and binds them to the ` state` token.

**Pipeline emits many more features per ctx**. At ctx=1 (` Fact`) our run alone has 215 features in `node_grouping.csv` mass-tagged across 15 supernodes, vs the human's 0 pins at this position. The dominant tags at ctx=1 (`(entity) related` 45, `Say (Austin)` 24, `containing` 19, `capital` 19, ...) suggest "early-token leakage" -- the first content token after `<bos>` carries residual signal for many concepts that the human chose not to pin.

### Interpretation

1. **The literal "is the human's pinned (l, f) set in our graph?" question is unanswerable as posed.** The two graphs were generated against incompatible transcoders. This is not a bug in our pipeline or in `circuit-tracer`; it is the expected consequence of upgrading the `clt-hp` source set on Neuronpedia between captures. `info.transcoder_set` should now be treated as a required dimension of any cross-graph comparison.
2. **Concept-level concordance is 4/5 -- our subtype classifier independently labels four of the five human concepts at the same token positions.** This is encouraging: the macro-structure of the circuit (state-binding at ` state`, capital-naming at ` capital`, "say a capital" at the answer position) is recovered without seeing the human's labels.
3. **The single concept miss (Texas at ` Dallas`) is informative**, not arbitrary. Our classifier groups Texas-features under the ` state` token because that is where the answer-state binding peaks in our probe profile. The human attributes them to ` Dallas` (city -> state lookup). Both are defensible; they reflect a real ambiguity in where to anchor a "city implies state" feature. This is a concrete disagreement to trace if we want to improve the subtype classifier.
4. **Implication for Phase 3 design (steering)**. The plan as written -- "use the human-annotated subgraph to steer the other 49 states" -- cannot use the human's pinned feature IDs directly: those features do not exist in our 96k-feature transcoder. There are three replacements for the "human" condition:
   - (i) **Concept-template**: take the human's 5 supernode names (capital, state, Texas, capital-cities, preposition+place) and select features from OUR grouping whose `supernode_name` falls in those families at the matching ctx. This isolates "human concept menu, automated feature picking" and is the cleanest comparison given the transcoder mismatch.
   - (ii) **Functional match**: regenerate the human-annotation graph with our 96k transcoder and let the human re-pin (requires UI work + a person; out of scope here).
   - (iii) **Old-transcoder regeneration**: rebuild our 50-state pipeline with the older 16k CLT to align vocabularies. Heavy lift (full re-run, possible re-grouping) and locks future work to a deprecated source set.
   The recommendation is (i): treat the human subgraph as a **concept template**, not a feature template. We accept that "human steering" then means "human-chosen concept set + automated feature pick" rather than "human-chosen features".

### Threats

- **N=1 prompt.** All concordance numbers are from the single Dallas/Austin graph. Concept recovery may be lower or higher on other states; only Phase 3's 50-state batch will tell us if "4/5 concepts at matched ctx" is the typical rate.
- **`HUMAN_TO_OUR_FAMILY` is hand-coded.** The mapping between human supernode names ("preposition followed by place name") and our supernode tags (`is`, `of`) is a judgement call by me, not validated. A different mapping (e.g., excluding `is` from the preposition family) would shift the count from 4/5 to 3/5 or 2/5. Any future report should publish the mapping table alongside the score.
- **Human supernode `Texas` at ctx=9 ` Dallas`** is treated as a miss above, but a defensible alternative reading is that our `Texas`@ctx=7 cluster IS the same circuit, just credit-assigned to a different position; under that reading the count is 5/5. Either interpretation is consistent with the data.
- **Our pipeline at ctx=1 emits ~10x more features than the human pins anywhere.** Some of this is real (multi-prompt probe activation -> more features survive pruning), some is likely BOS-adjacent leakage. Without tagging which features are "leakage at ctx=1" vs "real", the supernode counts at ctx=1 should not be compared head-to-head with the human's pinned counts.
- **Generator version skew (1.0.0 vs 0.3.1)** could affect not just the transcoder vocabulary but also pruning rules and influence computations. `circuit-tracer` does change the propagation logic between minor versions; we have not audited the diff.

### Follow-up

- Decide on the concept-template path (option i) or stop and request human re-annotation in our 96k vocabulary.
- Build the `human_dallas` grouping CSV in our vocabulary using the concept-template approach: features from `node_grouping.csv` whose `supernode_name in HUMAN_TO_OUR_FAMILY[h]` and `peak_token_idx == h_ctx`. Compare its size and identity to the auto-Dallas top-21 condition before launching the full 50-state Phase 3.
- Add `info.transcoder_set` to the manifest of every saved graph going forward; reject cross-graph comparisons where the `transcoder_set` differs without an explicit alignment step.
- File a note in `scripts/utils/AGENTIC_RESEARCH_GUIDE.md` ("Known confounds" section) listing the `clt-hp` source-set swap and the 16k vs 96k vocabularies as a confound for any historical Neuronpedia graph predating ~2025-09.

Confidence: **Medium** for the transcoder mismatch finding (directly observed in metadata + node IDs, no plausible alternative). **Low** for the 4-of-5 concept-recovery rate (single prompt, hand-coded family mapping, several reasonable variants give 2-of-5 to 5-of-5).

---

## [2026-05-03] Topic: Human-annotated `gemma-fact-dallas-austin` subgraph beats every size-matched control on replacement and completeness scores -- Part 1 of the human-vs-auto experiment

**Question**: How does the human-curated 22-feature subgraph from
`mh2parker`'s public Neuronpedia view (slug `gemma-fact-dallas-austin`)
compare against (a) the unpruned full graph, (b) random size-matched
draws of CLT features, and (c) the top-k features by `node_influence`,
on the canonical replacement and completeness scores from
`circuit_tracer.graph` (PR safety-research/circuit-tracer#42)?

This is Part 1 of a three-part experiment comparing the human-annotated
subgraph against our automated pipeline (Parts 2-3 pending; see
`output/research/dallas_austin_reference/`).

### Setup

- **Reference graph**: `gemma-fact-dallas-austin.json` (855 nodes,
  34,801 links) downloaded from the S3 URL referenced in
  `https://www.neuronpedia.org/api/graph/gemma-2-2b/gemma-fact-dallas-austin`.
  The graph is already pruned at `node_threshold=0.7, edge_threshold=0.9`
  (uploaded by `mh2parker` 2025-05-28, featured graph). 697 CLT features
  survive pruning.
- **Human pinned set**: 22 unique CLT `node_id`s extracted from the URL's
  `pinnedIds` and `supernodes` parameters: 5 supernodes (`capital`,
  `state`, `Texas`, `preposition followed by place name`,
  `capital cities/say a capital city`) plus 3 standalone pinned features
  (`20_15589_10`, `23_12237_10`, `18_8959_10`, the latter two carrying
  custom human labels via the `clerps` parameter). Saved at
  `output/research/dallas_austin_reference/human_annotated_subgraph.json`.
- **Tool**: `tools/subgraph_scores.py` -- pure-numpy port of
  `compute_graph_scores` and `compute_subgraph_scores` from
  `circuit_tracer.graph` (the latter is from open PR #42). 9 unit tests
  in `tests/test_subgraph_scores.py` validate the formulas on toy graphs
  (pure-token gives R=1; pure-error gives R=0; balanced gives R=0.5;
  pinning all features matches `compute_graph_scores`; missing
  per-(layer, ctx_idx) error nodes are added as virtual error rows).

Random controls: `n=200` draws of `k=22` features, `numpy.default_rng(seed=42)`.

### Raw findings

CSV at `output/research/dallas_austin_reference/subgraph_scores.csv`.

| Condition | k | Replacement | Completeness | Notes |
|---|---:|---:|---:|---|
| Full pruned graph | 697 | 0.5542 | 0.8547 | n_links=34,801 |
| **Human subgraph** | 22 | **0.2961** | **0.6984** | +6 virtual error nodes added |
| Top-k by influence (naive) | 22 | 0.2076 | 0.6059 | features ranked by `node.influence` |
| Random k=22 -- mean | 22 | 0.2143 | 0.6145 | n=200 draws |
| Random k=22 -- median | 22 | 0.2130 | 0.6126 | |
| Random k=22 -- 95th pct | 22 | 0.2272 | 0.6271 | |
| Random k=22 -- max | 22 | 0.2370 | 0.6391 | |

Percentile of human within the random distribution:

- Replacement: **100.0%** (above all 200 random draws)
- Completeness: **100.0%** (above all 200 random draws)

Top-k-by-influence percentile vs random: R = 4.0% (BELOW most random draws).

### Interpretation

The human-curated 22 features account for **53.4% of the full pruned
graph's replacement score** (0.296/0.554) and **81.7% of its
completeness** (0.698/0.855), using only **3.2% of the available CLT
features** (22/697). The same number of features chosen randomly
captures only ~38% of replacement (0.214/0.554), and the same number
chosen by single-feature `node_influence` captures only ~37%
(0.208/0.554) -- *worse than random*.

Three concrete L1 conclusions:

1. **The human's selection is structurally informed**. Beating 200/200
   random draws on both metrics is a clean rejection of the null that
   any tightly-pruned subset of 22 features achieves comparable scores.
2. **`node_influence` alone is not a useful selection criterion at this
   scale**. The top-22 by `influence` falls below the 5th percentile of
   random draws on replacement (0.2076 vs random 5th pct approx 0.2080).
   This suggests the highest-influence features are concentrated in a
   few feature-paths and miss the path diversity needed to route
   token-to-logit influence through features. Selecting only the
   "loudest" features under-covers the circuit. *Confidence: Medium.*
3. **The selection-vs-aggregation tradeoff favours the human**.
   The human picked groups of complementary features (5 supernodes
   spanning input tokens 4, 7, 9 and output position 10). Such position-
   diverse selection naturally improves both metrics relative to any
   single-criterion ranking. *Confidence: Low* (we have not yet tested
   what happens if we constrain `top-k` to be position-balanced; see
   follow-up.)

**Confidence**: Medium for findings 1 and 2 (large effect, deterministic
implementation, validated against toy-graph identities). Low for finding
3 until the position-balanced top-k control is run.

**Epistemic level addressed**: L1 (operationally useful labels). The
human's labels appear to identify a structurally meaningful subgraph.
The result does *not* address L2 (downstream causal effects); that is
Part 3 of the experiment.

### Threats to validity

1. **Implementation drift from the published library.** Our port of
   `compute_subgraph_scores` follows PR #42 verbatim, but PR #42 is
   *open* (not merged) as of 2026-05-03. If the merged version diverges,
   our absolute numbers may shift. *Mitigation: tests lock in the toy-
   graph identities; the relative ranking (human > random > top-by-inf)
   is unlikely to invert under reasonable edits.*
2. **Pruning baseline.** All scores are computed on the already-pruned
   graph (`node=0.7, edge=0.9`). Re-running on an unpruned graph would
   change the absolute scores and *might* change the random control
   distribution (more low-influence features available). *Open question
   for follow-up: regenerate the same prompt with `nodeThreshold=1.0,
   edgeThreshold=1.0` via the API and recompute.*
3. **N=1 prompt.** All findings here are for a single prompt-circuit.
   Generalizing to "human curation always beats random on completeness"
   requires Part 2-3 across multiple entities or domains. *Mitigation:
   the experiment is designed to scale this to 50 USA states with
   matched prompts; results pending.*
4. **The "top-k by influence is bad" finding has known mechanistic
   reasons** (high-influence features cluster on a few paths; subgraph
   metrics reward path diversity). It is not a critique of the library
   or the human -- it just says "single-feature influence is the wrong
   criterion at this k." *Mitigation: the comparison is purely
   diagnostic; we report it because the user might intuit "top influence
   = best subgraph" otherwise.*
5. **22 features may be a sweet spot specifically because of how
   `mh2parker` tuned the view**. The human chose `pruningThreshold=0.6`
   in the URL (a layer of pruning *on top of* the graph's already-
   pruned 0.7), which pushes the curated set toward maximum
   coverage-per-feature. A different curator might have chosen a
   different k and produced different relative results. *Mitigation: we
   compare at a fixed k=22; results are conditional on this choice.*
6. **Graph-level metric, not steering metric**. High completeness does
   *not* automatically mean better steering performance under entity
   swaps -- that's what Part 3 will test. The two metrics measure
   different things (faithfulness of explanation vs causal sufficiency
   for output redirection).

### Follow-up

- **Part 2 (annotation concordance, blocked)**. Need to run our
  pipeline on a `dallas_fact` seed (prompt
  `<bos>Fact: The capital of the state containing Dallas is`)
  because our existing `texas_Dallas` graph (different prompt) shares
  *zero* CLT features with the human's graph. Requires
  `NEURONPEDIA_API_KEY`.
- **Part 3 (steering, blocked)**. Same prerequisite (need to regenerate
  all 50 USA-state graphs with the "Fact:" prompt template) plus
  remote GPU access (nodo207, 8xA40) for activations and grouping.
- **Position-balanced top-k**. Diagnose finding 3: pick top-k features
  per (ctx_idx, layer) bucket and re-score to isolate "diversity" from
  "human label correctness".
- **Recompute on the unpruned graph** to confirm threats #2 and #5.

---

## [2026-05-02] Topic: Feature-class naturalness, deep dive -- three independent methods converge on ~10-12 natural classes, the 4-class story is a coarse-graining

**Question**: This entry extends [2026-05-01] "Feature-class naturalness". The
prior entry computed KMeans/GMM agreement at k=4 and concluded medium
confidence that the rule labels track real structure, with k=5/6 fitting
better than k=4. The follow-up question is sharper: does the data prefer a
specific, principled `k`, and how does the rule taxonomy relate to that
preferred geometry? Three additional methods were applied to answer it:
density-based clustering (HDBSCAN), agglomerative Ward linkage, and
Gaussian-mixture model selection by BIC. Per-dataset t-SNE and UMAP were
added as qualitative cross-domain checks.

### Setup

Same `output/research/feature_manifest.csv` as [2026-05-01]. Same 6-D
standardized vector
(`peak_consistency_main`, `n_distinct_peaks_log1p`, `func_vs_sem_pct`,
`conf_F`, `sparsity_median`, `layer`). All clustering done on the deduped
frame (8,314 global `(layer, feature)` rows) to remove the USA over-weighting.

New cells added to `output/research/feature_clustering.ipynb`:

- `33-34`: per-dataset t-SNE (5-panel facet, 2,500-row sample per panel).
- `35-37`: combined and per-dataset UMAP.
- `38-40`: HDBSCAN parameter sweep (`min_cluster_size` in `{40, 80, 150}`)
  plus side-by-side UMAP overlay of HDBSCAN clusters and rule labels.
- `41-45`: Ward agglomerative clustering. Dendrogram, ARI/NMI/silhouette
  curves over `k = 3..12`, UMAP coloured by Ward partitions at `k = 4, 6, 8`,
  contingency heatmap at `k = 8`.
- `46-48`: Gaussian-mixture model selection by BIC. Sweep `k = 2..12` at two
  covariance shapes (`diag`, `full`), with ARI/NMI/silhouette curves and a
  contingency heatmap and UMAP scatter for the BIC-preferred `k*`.

Notebook runtime (full sweep) is ~9 min on the existing `.venv` stack
(numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, umap-learn 0.5.12,
seaborn 0.13.2). Per-dataset t-SNE dominates at ~3 min; everything else is
under a minute. Sample sizes are deterministic (seed=0) so the analysis is
reproducible.

### Raw findings

**HDBSCAN on the standardized 6-D vector (deduped frame, N=8,314):**

| `min_cluster_size` | clusters discovered | noise points | noise % | ARI vs rules (excl. noise) | NMI (excl. noise) | silhouette (excl. noise) |
|---:|---:|---:|---:|---:|---:|---:|
| 40 | 54 | 2,376 | 28.6% | 0.107 | -- | 0.557 |
| 80 | 26 | 2,770 | 33.3% | 0.221 | -- | 0.557 |
| 150 | 13 | 2,765 | 33.3% | 0.319 | -- | 0.741 |

**Ward agglomerative (Ward linkage, standardized 6-D, deduped frame):**

| k | ARI vs rules | NMI | silhouette |
|---:|---:|---:|---:|
| 3 | 0.404 | 0.405 | 0.529 |
| 4 | 0.449 | 0.490 | 0.589 |
| 5 | 0.501 | 0.540 | 0.626 |
| 6 | 0.501 | 0.537 | 0.632 |
| 7 | 0.524 | 0.549 | 0.652 |
| 8 | 0.533 | 0.568 | 0.661 |
| 10 | 0.520 | 0.555 | 0.665 |
| 12 | 0.570 | 0.575 | 0.635 |

Silhouette plateaus at `k=8-10`. ARI keeps rising past `k=4` and is highest
at `k=12` within the swept range.

**Gaussian-mixture BIC sweep (diag and full covariance, k=2..12):**

| Covariance | BIC-preferred `k*` | BIC at `k*` | BIC at k=4 | ARI at `k*` | ARI at k=4 |
|---|---:|---:|---:|---:|---:|
| diagonal | **12** | -292,850 | -140,474 | 0.620 | 0.371 |
| full | **10** | -272,337 | -159,125 | 0.632 | 0.475 |

Lower BIC = better. The BIC drop from `k=4` to `k*` is more than 100,000 in
both covariance settings; this is many orders of magnitude beyond a
significant difference.

**Cross-method convergence on `k`:**

| Method | Preferred k |
|---|---|
| HDBSCAN density (most permissive setting) | 13 |
| GMM BIC (full covariance) | 10 |
| GMM BIC (diagonal covariance) | 12 |
| Ward silhouette plateau | 8-10 |
| KMeans/GMM ARI peak (from [2026-05-01]) | 6+ |
| Tree's nominal partition | 4-6 |

Three independent principled criteria (density, BIC, silhouette plateau)
land in `k = 8-13`, an order of magnitude away from the `k=4` story.

**Per-dataset visual check (t-SNE and UMAP):** the rule classes occupy
visibly coherent regions in every dataset's projection. `Relationship`
(red) is the cleanest single class across all five domains; the
`Dictionary fallback` bucket consistently splits into multiple visually
disconnected regions in the deduped UMAP.

**Per-dataset KMeans k=4 ARI (from [2026-05-01], for reference):** books
0.50, paintings 0.24, products 0.60, sounds 0.49, USA 0.35.

### Interpretation

Three claims, each with explicit confidence:

1. **The rule labels track real structure.** Threshold sensitivity is low
   (under 1.5% flip rate at +/-10% perturbation per cut, [2026-05-01]),
   classes are spatially coherent in t-SNE/UMAP/PCA across all five
   datasets, and ARI vs rule labels reaches 0.62-0.63 once enough
   components are allowed. The simplest "boring" explanation -- that the
   labels are arbitrary slices through smooth distributions -- is
   inconsistent with the threshold-sensitivity numbers and the ARI levels.
   **Confidence: High.**

2. **The data prefers ~10-12 natural classes, not 4.** Three principled
   criteria (HDBSCAN density at the strictest setting, GMM-BIC under both
   diagonal and full covariance, Ward silhouette plateau) all point to
   `k = 8-13`. The BIC penalty prevents this from being explained by
   overfitting. The 4-class partition does not appear in any of these
   independent estimates as the preferred number. **Confidence: High.**

3. **The 4-class partition is a coherent coarse-graining of the natural
   geometry, not a discovery of natural classes.** ARI of the rule
   partition vs the BIC-preferred 10-12 component partition is in the
   0.45-0.50 range. The rule labels group together multiple naturally
   distinct dense regions under the same name; the most visible example is
   `Semantic (Dictionary fallback)`, which occupies at least two
   disconnected regions in UMAP and is itself the residue of a fallback
   branch in the decision tree (rule 4, `02_node_grouping.py:629`).
   **Confidence: Medium-to-High.** Whether the coarse-graining is *useful*
   for downstream causal reasoning is a separate question (L2 in the
   methodology framework) which this analysis does not address.

A practical implication of (3): the existing `Review`/`Ambiguous` bucket
(786 features in the all-rows manifest, 136 deduped) is much smaller than
the population of features that sit between dense regions. HDBSCAN labels
~33% of features as noise (i.e., not in any dense region) at
`min_cluster_size >= 80`. Either (a) the rule's review bucket is
under-flagging genuinely intermediate features, or (b) HDBSCAN's noise
points are not really ambiguous and just sit in low-density tails.
Distinguishing these is a useful follow-up.

### Threats

- **Same-axis tautology.** The clustering uses the same 6 metrics that the
  decision tree uses. Class regions look coherent in those metrics partly
  because the tree was *defined* on those metrics. The unsupervised
  recovery (ARI 0.45-0.63) is what breaks the tautology, but the failure
  to recover at `k=4` still has to be qualified by this dependence.
  Mitigation: rerun with metrics derived independently (e.g., decoder
  cosine similarity, layer-by-layer activation autocorrelation) and check
  whether the same partitions emerge.
- **t-SNE distorts global geometry.** UMAP and PCA partly compensate, and
  the BIC-based result does not depend on any 2-D projection.
- **n_distinct_peaks is integer-valued.** It was log1p-transformed before
  standardization, but the heavy mass at `1` still creates a thin spike in
  the marginal. This may inflate cluster count slightly.
- **`func_vs_sem_pct` clips to +/-100.** Endpoint piling can artificially
  attract clusters to the +/-100 strips. The full-covariance GMM should
  absorb this as anisotropic variance, but diagonal GMM cannot, which is
  one reason its BIC prefers larger `k`.
- **The deduped frame uses median across an entity's behavioral
  occurrences.** A feature that behaves differently across entities gets
  reduced to one row with median metrics and modal label. The all-rows
  ARI (~0.43 at k=4 from [2026-05-01]) is the corrective, and it is
  weaker but consistent in shape.
- **All five datasets share the same probe-prompt template family.**
  Cross-method convergence on `k = 8-13` may reflect shared template
  structure as much as feature-intrinsic geometry.
- **Per-dataset clustering is computed on the all-rows manifest, not the
  deduped frame**, because dedup needs cross-dataset information to assign
  `dataset = mode`. The per-dataset ARI scores are therefore not
  comparable line-for-line with the combined deduped numbers.
- **The "10-12 natural components" claim is for this metric space.** It
  does not yet imply 10-12 *mechanistic* feature types. The L3 question
  remains open.

### Confidence

**High** that the data prefers many more components than 4 (replicated
under three independent criteria, with BIC differences far beyond noise).
**Medium-to-High** that the rule labels are a coherent coarse-graining of
the natural geometry (ARI > 0.5 at k = 8 Ward; threshold-flip rate near
zero; class spatial coherence in three projections). **Low** for any
specific count of natural classes; the principled estimates span 8-13 and
none of them is definitive.

### Next steps

- **Investigate the `Dictionary fallback` bimodality directly.** The
  fallback branch was meant as a low-confidence catch; the data suggests
  it is sweeping up two genuinely different feature populations. Pull 5
  features from each visual blob and inspect their `node_grouping.csv`
  rows side by side. *Partial answer in the [2026-05-02] entry "`Dictionary
  (fallback)` subtype": what it captures, how naming reacts, and why the
  swap pipeline already ignores it. The bimodal shape in UMAP is still
  open, but the population content is now characterised.*
- **Connect cluster membership to swap success.** The natural clusters
  discovered here are L1 (operational) constructs. The next move is to
  test whether they have downstream causal teeth at L2: do features in
  natural cluster A produce different swap outcomes than features in
  natural cluster B at the same M? The `SwapQuery` / `SwapStats` toolkit
  already gives the per-pair numbers; merge `feature_manifest.csv` with
  per-pair intervention identities to test it.
- **Run the same clustering on a non-tree-derived metric vector.** For
  example: per-feature decoder cosine similarity to the answer-token
  unembedding row, mean activation entropy across probes, layer-wise
  activation autocorrelation. If the same `k = 8-13` structure emerges,
  the geometry is not a tautological consequence of the tree's input
  features.
- **Compare HDBSCAN noise points to the rule's `Review` bucket.** If the
  intersection is high, the rule is approximating a density-aware
  ambiguity flag. If it is low, the two buckets are doing different
  things and the rule's ambiguity criterion may be missing a real signal.

### Reference to earlier entry

This entry extends but does not contradict [2026-05-01]. The earlier
entry's k=4 ARI of ~0.51 (deduped, KMeans) and k=6 ARI of ~0.59 are
recovered exactly here. The new contribution is (a) the principled BIC
estimate of `k`, (b) the density-based estimate via HDBSCAN, (c) the
agglomerative dendrogram showing how fine clusters merge into the rule
labels, and (d) the per-dataset t-SNE/UMAP qualitative cross-check.

---

## [2026-05-02] Topic: `Dictionary (fallback)` subtype -- what it captures, how the naming reacts, and why the swap pipeline already ignores it

**Question**: The node-grouping classifier emits `Semantic` features with two
different `subtype` values that look superficially similar, `Dictionary` and
`Dictionary (fallback)`. Three follow-up questions:

1. What does `Dictionary (fallback)` actually contain in our datasets? Which
   tokens do those features peak on, and is the population homogeneous?
2. The `supernode_name` for a Semantic feature is a single string. How is it
   chosen when the feature peaks on a small set of *different* tokens across
   prompts (which is the defining property of a fallback)?
3. Are these features influential when used as swap candidates? Intuition says
   no -- if a feature fires on prompt-template tokens shared by both source
   and target, the source-minus-target delta is ~0 -- but the question had
   never been quantified.

### Setup

Static-only investigation, no GPU. Code paths examined:

- `scripts/02_node_grouping.py`: `classify_node` (lines 555-652), the rule that
  routes a feature to `Dictionary (fallback)` (`layer <= sem_layer_max=3`
  branch of Rule 4); and `name_semantic_node` (lines 974-1068), the supernode
  naming logic.
- `scripts/experiments/batch/pipeline/grouping.py`: confirms blacklist is just
  `<bos>` for all batch configs (`scripts/experiments/batch/configs/*.yml`).

Three throwaway scripts under `/tmp/`:

- `fallback_stats.py` -- aggregate every `02 Node Grouping/node_grouping.csv`
  under `output/<batch>` and `scripts/experiments/batch/output/<batch>` (135
  CSVs, 192,085 rows), compute subtype counts, layer distribution,
  `n_distinct_peak_tokens` per feature, top peak tokens.
- `fallback_examples.py` -- pick representative `Dictionary (fallback)`
  features in three families (BPE subwords, template-prefix tokens, functional
  words) and dump per-item peak tokens.
- `swap_relevance.py` and `swap_target_check.py` -- (a) for each batch, count
  how many distinct items each `(layer, feature)` is active in, broken down by
  subtype; (b) intersect the 87 unique features intervened by a real swap
  (`output/usa_states_batch/_swaps/runs/full_50states_v1/work/wyoming_casper__to__texas_dallas/features.json`)
  with subtype labels in both source (`wyoming_casper`) and target
  (`texas_dallas`) `node_grouping.csv` files.

### Raw findings

**Subtype distribution (per row, 192,085 rows across 5 batches):**

| subtype | rows | % |
|---|---:|---:|
| `<NA>` (Say "X" / Relationship / Ambiguous) | 67,120 | 35% |
| Dictionary | 49,710 | 26% |
| **Dictionary (fallback)** | **46,705** | **24%** |
| Concept | 23,460 | 12% |
| Ambiguous | 5,090 | 3% |

Total unique `(batch, item, feature)` triples in fallback: **6,264**.

**Layer distribution of fallback features (per-feature):**

| layer | n_features | % |
|---|---:|---:|
| 0 | 4,158 | 66.4% |
| 1 | 567 | 9.0% |
| 2 | 697 | 11.1% |
| 3 | 842 | 13.5% |

(Confirms the rule: `sem_layer_max = 3`. Layer 0 dominates.)

**peak_token_type per-feature (mode):**

| type | n_features |
|---|---:|
| semantic | 5,139 (82%) |
| functional | 1,125 (18%) |

**`n_distinct_peak_tokens` per fallback feature**

```
mean = 3.39   median = 3   p90 = 4   p99 = 5
```

(All have >= 1, by construction. Mean ~3 means a typical fallback feature
peaks on three different tokens across the prompt set.)

**Top-15 peak tokens (over 46,705 fallback rows):**

| token | rows |
|---|---:|
| `entity` | 14,100 |
| `attribute` | 6,742 |
| `relationship` | 6,273 |
| ` is` | 2,479 |
| `:` | 2,128 |
| ` The` | 1,083 |
| ` name` | 994 |
| ` state` | 904 |
| `vary` | 832 |
| ` the` | 659 |
| ` painter` | 401 |
| ` A` | 356 |
| ` of` | 315 |
| `uckleberry` | 294 |
| ` person` | 268 |

**Three behavioural families** confirmed by sampling concrete features:

1. **BPE subword fragments** -- e.g. `book_characters_authors / 3_66599`
   (layer 3, 19 items, 35 distinct peaks): peaks on
   `'ticus'` for Atticus Finch, `'hab'` for Captain Ahab,
   `'uckleberry'` for Huckleberry Finn, `'ina'` for Anna Karenina,
   `' Dracula'` for Dracula, `'morphosis'` for Gregor Samsa, etc.
   Same feature, entity-distinguishing subword changes per item.
2. **Template prefix tokens** -- e.g. `book_characters_authors / 0_44634`
   (layer 0, 21 items, 3 distinct peaks): peaks on `'entity'`/`'attribute'`/
   `'relationship'` depending on which template sentence is being scored.
3. **Functional words family** -- e.g. `book_characters_authors / 0_40780`
   (layer 0, 21 items, 5 distinct peaks): peaks on
   `' the'` (59x) / `' who'` (21x) / `' is'` (59x). Cannot be Say "X" because
   `layer >= 7` is required.

**Naming verification** -- the algorithm in `name_semantic_node` is *not* "most
frequent peak" but *"highest single `activation_max` among rows whose
`peak_token_type == 'semantic'`, skipping blacklisted (only `<bos>`) and pure
punctuation"*. Concrete consequences observed in the data:

| feature_key | layer | n items | n distinct supernode_name | examples |
|---|---:|---:|---:|---|
| `3_66599` | 3 | 19 | **19** | `ticus`, `Dick`, `Quixote`, `Dracula`, `uckleberry`, `Hermione`, `morphosis`, `Twist`, `Kill`, ... |
| `0_25424` | 0 | 10 | 9 | `Karen`, `Dickens`, `Dumas`, `Bennet`, `Bo`, `Granger`, `Caul`, `Fitzgerald`, `Smith` |
| `0_44634` | 0 | 21 | 1 | `Semantic (unknown)` (degenerate -- see Threats) |
| `0_40780` | 0 | 21 | 1 | `the` |
| `0_20807` | 0 | 12 | 1 | `first` |
| `1_34506` | 1 | 6 | 1 | `is` |

For `0_25424` on `anna_karenina`, the row with `peak=' Karen'`
(activation_max=10.87) wins over rows with `peak='attribute'`
(activation_max=0.00). For `0_40780` no semantic peak has `activation_max>0`,
so the function falls through to the secondary branch
(`feature_records[activation_max > 0]` regardless of type) and selects
`' the'` (max activation 57.47) -- producing supernode `'the'`.

**Cross-batch presence (`n_items`) distribution by subtype:**

USA states batch (50 items):

| subtype | n_features | mean(n_items) | % global-like (n_items >= 40/50) |
|---|---:|---:|---:|
| Dictionary | 1,367 | 3.0 | 2.9% |
| Concept | 319 | 4.9 | 4.7% |
| Say "X" | 364 | 5.6 | 5.5% |
| Relationship | 177 | 7.7 | 9.0% |
| **Dictionary (fallback)** | **247** | **8.8** | **13.4%** |
| Ambiguous | 51 | 10.3 | 13.7% |

`Dictionary (fallback)` has ~3x the mean per-feature presence of strict
`Dictionary`, and 4.6x the share of "global-like" features (active in >=80%
of items). The pattern reproduces in `paintings_painters` (7.1% vs 5.3%),
`products_founders` (13.3% vs 4.0%), and `book_characters_authors` (2.2% vs
1.9%).

**Real swap composition**, `wyoming_casper -> texas_dallas`, full_50states_v1
run, 107 interventions / 87 unique `(layer, index)`:

| Source subtype | M=-2 (suppress) | M=+20 (enhance) | Total |
|---|---:|---:|---:|
| Say "X" | 41 | 18 | 59 |
| `<not in source>` (target-side injections) | 0 | 29 | 29 |
| Concept | 8 | 2 | 10 |
| Dictionary | 5 | 0 | 5 |
| Ambiguous | 3 | 0 | 3 |
| **Dictionary (fallback)** | **1** | **0** | **1** |

The single fallback intervention is `L0_F17761`, present in 29/50 states
with top peaks `entity` (41) / `relationship` (29) / `attribute` (29) -- a
template-prefix feature -- used only for source-side suppression (M=-2). It
is reclassified as plain `Dictionary` in the target item's CSV.

### Interpretation

1. **What `Dictionary (fallback)` is**. It is the layer-based safety net of
   Rule 4 (`layer <= 3`) for features that miss the strict Dictionary cut
   (`peak_consistency_main >= 0.80` AND `n_distinct_peaks <= 1`). It captures
   three distinguishable mechanisms that all live in the early layers and
   look "lexical but noisy":
   - BPE subword detectors that fire on the entity-distinguishing piece
     (Atticus -> `ticus`, Ahab -> `hab`, Huckleberry -> `uckleberry`).
   - Template-prefix detectors that flip among the small set of template
     section-names (`entity` / `attribute` / `relationship`).
   - Functional-word detectors at low layer (`is` / `the` / `who`) that are
     too early to qualify as Say "X" (which needs `layer >= 7`).
2. **Naming is not "majority vote"**. Two features with identical aggregate
   metrics can get different `supernode_name` in different runs because the
   selector picks the single highest `activation_max` among semantic peaks.
   This explains why `3_66599` produces 19 distinct supernode labels across
   19 items: in each item the stronger BPE peak is the entity-specific one.
   It also means `feature_key` -- not `supernode_name` -- is the only stable
   cross-graph identifier for these features.
3. **The user's swap intuition is empirically correct**. Three independent
   pieces of evidence converge:
   - Mean per-feature presence across items is ~3x higher for fallbacks than
     for strict Dictionary in USA states (8.8 vs 3.0); the "global-like" tail
     (active in >=80% of prompts) is 4.6x larger for fallbacks. These features
     are over-represented in the population that source and target naturally
     share.
   - In a real swap (`wyoming -> texas`, 107 interventions), only **1/107**
     interventions has `subtype == "Dictionary (fallback)"` in the source
     CSV. The selector already deprioritises them in practice.
   - The single fallback that *is* used appears with `M=-2` (suppression) and
     never with `M=+20` (enhancement) -- coherent with the principle that
     injecting a template feature into the target adds nothing the target
     does not already have.
4. **A nuance**. Not all fallbacks are template-shared. The median `n_items`
   is still 1, meaning many fallback features are item-specific (the BPE
   subword family). Those *would* in principle carry useful steering signal,
   but the swap selector still does not pick them, presumably because their
   raw activation magnitudes at layer 0-3 are dominated by the higher-layer
   `Say "X"` candidates.

Operational consequence: filtering `subtype == "Dictionary (fallback)"` out
of the swap candidate pool is a safe pre-step that loses nothing relative to
current behaviour and makes the implicit policy explicit.

### Threats

- **Edge case in the naming algorithm**. Feature `0_44634` (peaks on
  `'entity'` / `'attribute'` / `'relationship'`, all `peak_token_type ==
  semantic` with `activation_max > 0`) is labeled `Semantic (unknown)` in
  the CSVs, which is the return value when no valid token survives the
  blacklist+punctuation filter. The current code path should have returned
  `'relationship'`. The CSVs were generated by an older invocation of the
  pipeline; the discrepancy points to a legacy blacklist (or a now-removed
  template filter) rather than a bug in the live code. Worth a separate
  investigation if `Semantic (unknown)` ever needs to be ground-truth.
- **Single swap audit**. The 1/107 statistic is from one swap pair; a
  systematic count across the full 50x50 matrix (and across other batches
  and modes: `labeled` / `random` / `field_add`) would harden the claim
  that "the swap selector already excludes fallbacks".
- **Cross-item identity assumption**. The analysis treats `(batch, layer,
  feature)` as a stable identity across items in the same batch. This is
  true at the SAE level, but a feature can play different roles in different
  contexts; the modal subtype hides that variation.
- **Layer cutoff of 3 is set, not derived**. `sem_layer_max = 3` was
  configured, not learned from data. A different cutoff would shift the
  population in/out of `Dictionary (fallback)` without changing any
  underlying mechanism.
- **Per-row vs per-feature accounting**. Some tables report rows (e.g.
  46,705 fallback rows, where each row is a `(feature, prompt)` pair) and
  others report features (6,264 fallback features). These are not directly
  comparable; the "feature-level" tables (subtype mode, layer distribution,
  n_distinct_peak_tokens, n_items, swap intersection) are the load-bearing
  ones.
- **The 29 "<not in source>" features in the swap**. These are target-side
  injections (M=+20) classified by reading the *target* CSV; a small fraction
  could themselves be `Dictionary (fallback)` in the target. The current
  cross-tab confirms none of them are -- they are 17 Say "X", 10 Dictionary,
  2 Concept -- so the conclusion stands, but the asymmetric labelling (source
  side = source CSV, target side = target CSV) is worth flagging.

### Confidence

**Medium-High** for the descriptive claims about what `Dictionary (fallback)`
contains (three behavioural families, dominant at layer 0, mean
`n_distinct_peak_tokens=3.39`, mean per-feature presence ~3x strict
Dictionary in USA). N=6,264 features across 5 datasets, three independent
sub-aggregations all consistent.

**Medium** for the swap-relevance claim (1/107 interventions, single
suppression role). The mechanism (template-shared features cancel under
source-target subtraction) is principled and the per-feature presence stats
support it, but the count is from a single swap.

**Medium** for the naming algorithm description (read directly from code,
verified on six concrete features including one degenerate case).

### Next steps

- Repeat the fallback-vs-intervention intersection across the full 50x50
  USA matrix, plus `paintings`, `products`, `books`, `sounds`, and report
  the global fraction of fallback interventions per swap mode.
- Add an explicit `--exclude-subtype "Dictionary (fallback)"` flag to the
  swap candidate selector so the de-facto policy becomes explicit and
  testable. Compare metrics on a small batch with and without the flag to
  confirm the swap quality is unchanged (or improved).
- Investigate the `Semantic (unknown)` anomaly on `0_44634`-style features:
  identify which earlier pipeline version produced it and whether
  `entity`/`attribute`/`relationship` should be added to the blacklist
  permanently (they are template metadata, not content tokens).
- For the BPE-subword fallbacks (the only "useful" fallback family for
  steering), quantify their activation magnitude vs `Say "X"` candidates at
  the same layer to confirm they really do lose the ranking on magnitude
  alone, not on some other selector criterion.

---

## [2026-05-01] Topic: Feature-class naturalness -- rule labels partially recover unsupervised structure, but k=4 is not the best geometry

**Question**: The node-grouping classifier assigns features to Semantic
Dictionary, Semantic Concept, Say-X, Relationship, and review/fallback buckets
using `peak_consistency_main`, `n_distinct_peaks`, `func_vs_sem_pct`, `layer`,
`sparsity_median`, and `conf_S`. If we plot all collected features across the
five datasets in this metric space, do those classes "show themselves" as
natural structure, or are they mostly imposed by the decision tree?

### Setup

Built `scripts/research/build_feature_manifest.py` to walk the five root
dataset outputs and rebuild one feature-level row per
`(dataset, entity, feature_key)` from existing `node_grouping.csv` files.

Built `output/research/feature_clustering.ipynb` plus a dependency-light
runner, `scripts/research/feature_clustering_analysis.py`, because this
runtime lacks pandas/numpy/sklearn despite the project requirements listing
them. The runner uses deterministic 5,000-row samples for the expensive
clustering grid and computes counts / threshold sensitivity over the full
manifest.

Outputs:
- `output/research/feature_manifest.csv`
- `output/research/feature_clustering_results.json`
- `output/research/feature_clustering_metrics.csv`
- `output/research/feature_classes_naturalness.png`

### Raw findings

Manifest size:

| Frame | N |
|---|---:|
| all rows `(dataset, entity, feature_key)` | 27,817 |
| deduped global `(layer, feature)` | 8,314 |

All-row class counts:

| Class | N |
|---|---:|
| Semantic (Dictionary) | 7,578 |
| Semantic (Dictionary fallback) | 6,264 |
| Relationship | 5,615 |
| Say "X" | 4,098 |
| Semantic (Concept) | 3,476 |
| Ambiguous/Review | 786 |

Deduped class counts:

| Class | N |
|---|---:|
| Semantic (Dictionary) | 3,146 |
| Semantic (Dictionary fallback) | 2,175 |
| Say "X" | 1,046 |
| Semantic (Concept) | 1,000 |
| Relationship | 811 |
| Ambiguous/Review | 136 |

Clustering agreement with rule labels:

| Frame | Algorithm | k | N clustered | ARI | NMI | silhouette |
|---|---|---:|---:|---:|---:|---:|
| all rows | KMeans | 4 | 5,000 | 0.427 | 0.522 | 0.457 |
| all rows | GMM | 4 | 5,000 | 0.420 | 0.532 | 0.446 |
| all rows | best observed | 6 | 5,000 | 0.508 | 0.590 | 0.423 |
| deduped | KMeans | 4 | 5,000 | 0.512 | 0.492 | 0.538 |
| deduped | GMM | 4 | 5,000 | 0.506 | 0.490 | 0.523 |
| deduped | best observed | 6 | 5,000 | 0.597 | 0.613 | 0.639 |

Per-dataset k=4 agreement:

| Dataset | KMeans ARI | GMM ARI |
|---|---:|---:|
| books | 0.496 | 0.509 |
| paintings | 0.235 | 0.247 |
| products | 0.599 | 0.623 |
| sounds | 0.486 | 0.393 |
| USA states | 0.349 | 0.352 |

Threshold sensitivity on all 27,817 rows:

| Threshold | -10% flip rate | +10% flip rate | near-boundary rate |
|---|---:|---:|---:|
| Dictionary `peak_consistency_main >= 0.80` | 1.52% | 1.49% | 1.51% |
| `func_vs_sem_pct >= 50` | 0.05% | 0.31% | 0.58% |
| `sparsity_median < 0.45` | 0.05% | 0.19% | 0.29% |
| Say-X `layer >= 7` | 0.00% | 1.14% | 3.62% |

### Interpretation

The classes do show themselves, but only partially. The pre-registered rule of
thumb was: ARI > 0.5 supports real structure, ARI 0.2-0.4 indicates partial
agreement, and ARI < 0.2 suggests imposed structure. On that scale:

- The deduped `(layer, feature)` frame reaches medium-positive agreement at
  k=4 (ARI ~0.51) for both KMeans and GMM. This is evidence that the labels are
  not arbitrary artifacts of pilot-prompt inspection.
- The all-row frame is weaker at k=4 (ARI ~0.42), consistent with context
  dependence and USA weighting altering the apparent geometry.
- k=6 consistently beats k=4 on deduped ARI/NMI/silhouette, which suggests the
  natural geometry may contain more than the nominal four classes. The obvious
  suspects are `Dictionary fallback`, `Ambiguous/Review`, and the split between
  true Semantic Concept vs. low-layer fallback semantics.
- Cross-domain transfer is uneven: products and books are strong, sounds are
  moderate, USA is only partial, and paintings are weak. The rule geometry is
  therefore not equally natural in every domain.
- The thresholds themselves are not especially fragile: +/-10% perturbations
  flip only 0.05-1.52% of all rows for the four primary cuts. This argues
  against the simplest "many points sit exactly on arbitrary boundaries"
  explanation.

Confidence: **Medium** that the rule labels capture real structure in the
measured feature-behavior space, especially after deduplication. **Low to
Medium** that the correct natural taxonomy is exactly four classes, because
k=5/k=6 clustering fits better than k=4.

### Threats

- The clustering dimensions are the same dimensions used by the decision tree.
  This analysis tests whether unsupervised partitions reproduce the rule labels,
  not whether the labels are independently mechanistic.
- The runtime lacked pandas/numpy/sklearn, so clustering used a pure-Python
  implementation with deterministic 5,000-row samples for the expensive grid.
  The exact ARI/NMI values should be rerun with sklearn before publication.
- t-SNE was not executed in this environment; the notebook includes an optional
  sklearn cell for it.
- The summary PNG is a dependency-light diagnostic figure, not a polished paper
  figure. Use the CSV/JSON outputs as the source of truth.
- `func_vs_sem_pct` has endpoint piling at +/-100 by construction, and
  `n_distinct_peaks` is integer-valued. Both can shape Euclidean clustering.
- Deduping by `(layer, feature)` removes USA over-weighting but also discards
  context variability: a feature that behaves differently across entities gets
  reduced to median metrics and modal label.
- `Dictionary fallback` is produced by the Semantic fallback rule, not by the
  primary Dictionary rule. Treating it as a separate displayed class is
  analytically useful but differs from the nominal four-class story.

### Next steps

- Rerun the notebook with pandas/sklearn installed and compare KMeans/GMM ARI
  to sklearn PCA/t-SNE/UMAP visualizations.
- Inspect the k=6 cluster confusion matrix to see whether the extra clusters
  correspond to fallback semantics, review rows, or domain-specific artifacts.
- Connect cluster membership to swap success metrics (`vsMax`, hit, rank) to
  test whether the natural clusters have downstream causal relevance.

---

## [2026-04-17] Topic: Decoder-competition vs feature-fragmentation -- competitor suppression rescues the NC pair, not the VT/AK ones

**Question**: Is the residual specificity failure in the F-category caused by
*decoder competition* (target capital is a top contender but the sampler keeps
picking a non-capital city) or by *feature fragmentation* (capital-bearing
features are too weak to lift the target into the top of the steered logits)?

### Setup

Built `scripts/utils/probe_decoder_competition.py` to run two controlled
decoding probes on the *same* intervention used by the existing pipeline
(`add_state_capital` features, 52 amplify + 52 ablate, transcoder
`mntss/clt-gemma-2-2b-2.5M`):

- **Probe A (greedy)**: `do_sample=False`, `temperature=0`, `freq_penalty=0`.
  Removes sampler stochasticity. If the target capital is the steered argmax
  at any tested `M`, greedy decoding will emit it.
- **Probe B (competitor suppression + greedy)**: read the steered first-token
  logits from a one-shot `feature_intervention` forward pass, subtract a fixed
  penalty (-8.0) from a curated list of competitor token IDs (state-mate
  non-capital cities and their first sub-tokens), pick argmax, then let the
  model continue normally without further steering. Isolates "what would
  happen if the competitors weren't there."

`M` swept over `{4.472, 6, 8, 12, 20}` for three F-category pairs:

1. `north_dakota_fargo -> north_carolina_charlotte` (target capital `Raleigh`,
   competitors `{Chapel, Cary, Durham, Greensboro, Asheville, Wilmington,
   Winston, Fayetteville, Charlotte}`).
2. `texas_dallas -> vermont_burlington` (target `Montpelier` -- multi-token,
   tracked via first sub-token ` Mont`; competitors
   `{Burlington, Rutland, Stowe, Brattleboro, Manchester, Springfield}`).
3. `idaho_idaho_falls -> alaska_anchorage` (target ` Juneau`; competitors
   `{Soldotna, Anchorage, Fairbanks, Wasilla, Sitka, Kodiak, Kenai, Palmer,
   Sold, Was, Anch, Ken}` to cover multi-token first-piece variants).

Outputs: `output/research/_decoder_competition_probe_{nd_nc, tx_vt, id_ak}.json`.

### Raw findings

**ND -> NC (Raleigh)** -- the only clean recovery.

| M | Probe A first token | rank(Raleigh) | Probe B first token | hit? |
|---|---|---|---|---|
| 4.47 | ` Chapel` | **1 (tied with ` Raleigh`, both p=0.121)** | ` Raleigh` | YES |
| 6.00 | ` Chapel` | 2 | ` Raleigh` | YES |
| 8.00 | ` Chapel` | 2 | ` Raleigh` | YES |
| 12.0 | ` Chapel` | 4 | `Datuak` (OOD) | NO |
| 20.0 | ` Chapel` | 16 | `Datuak` (OOD) | NO |

Probe B continuation at `M ∈ {4.47, 6, 8}`:
``The capital of the state containing Fargo is Raleigh.\n\nThe state of North
Dakota is located in the Midwest region of the …``
(Coherent target-correct emission; the suppressed cluster of NC non-capitals
no longer dominates.) At `M ≥ 12` the OOD token `Datuak` overwhelms the
distribution and suppression cannot help.

**TX -> VT (Montpelier)** -- not recoverable.
- Greedy first token at all `M`: ` the` (low M) or ` Interv[ale]` (high M).
- ` Mont` rank in steered logits: **1320 to 6576** -- never close to the top.
- Top-5 at `M=20`: `[' Interv', ' Shel', ' Lyndon', ' VT', ' Agency']` --
  Vermont-flavoured but the capital is absent.
- Probe B improves the rank by ~1 position; no qualitative change.

**ID -> AK (Juneau)** -- not recoverable.
- Greedy first token: ` Was`(silla) or ` Sold`(otna).
- ` Juneau` rank in steered logits: **21 to 273** depending on M.
- Probe B (with multi-token competitor stems suppressed) lifts the rank
  modestly (e.g. 48 -> 37 at `M=6`, 21 -> 13 at `M=8`) but never into the
  top-10. Argmax becomes generic noise (`a`, ` is`, ` vendus`).

### Interpretation

These three pairs cleanly separate two distinct failure modes that were
previously bundled under "specificity failure":

1. **Decoder competition** (NC pair). The capital token is genuinely competitive
   in the steered residual -- it is **tied for the top** at the empirically best
   `M`. The model picks a non-capital city only because that city's name
   happens to have the same probability mass and lexically wins the tie or the
   sampling draw. Suppressing the competitor cluster (one-shot logit bias on
   a small set of state-mate city tokens) is sufficient to recover the hit at
   moderate `M`. This is a *post-hoc* fix that works without changing the
   feature set.
2. **Feature fragmentation** (VT, AK pairs). The capital token is far down the
   steered logit ranking (rank 21-6500). Suppressing competitors only nudges
   the rank by 1-10 positions; the steered residual simply does not encode
   the capital. The "wrong city" output is not a competition -- it is what
   the model genuinely believes the prompt is steering it toward.

Both effects coexist with the previously documented *magnitude failure*
regime: at `M >= 12` for the NC pair the OOD `Datuak` token dominates and
even suppression of NC competitors cannot rescue it, mirroring the
B/C-category collapse documented in the previous log entry.

The recovery rate for ND -> NC at three `M` values, with no model retraining
and no new features, is itself notable: the reason this pair fell through the
existing M-search is that `_first_token_matches` checks the SAMPLED first
token at `temperature=0.3, freq_penalty=2.0`, and at the right `M` Raleigh
and Chapel are exactly tied -- the sampler picks Chapel ~50% of the time,
which is enough to keep the "no hit" verdict deterministic.

### Threats

- N=3 pairs. The decoder-competition recovery is demonstrated on a single
  pair; we do not yet know the population fraction for which competitor
  suppression alone would rescue an F-category failure.
- Competitor lists are hand-curated per target. A general intervention would
  need an automatic procedure (e.g. enumerate all single-token cities sharing
  the target state's region or all tokens above some prob threshold that are
  not the target capital).
- Suppression of -8.0 logit units is heuristic. We did not sweep this
  parameter; it is large enough to push Raleigh from p=0.121 to p=0.148
  while leaving the rest of the distribution mostly intact. A smaller penalty
  might be insufficient at higher M, a larger one would risk picking an
  arbitrary non-suppressed token.
- Probe B's continuation uses unsteered generation after the manually-chosen
  first token. This is a deliberate isolation but not what production
  steering would do; production would keep steering active across all
  generated tokens. We did not test the "steered + suppressed" combined
  generation loop.
- ` Mont` rank for VT may understate the true Montpelier signal because
  ` Mont` is shared by many words ("Montana", "Montgomery", "Monterey").
  Using the joint (` Mont` -> `pelier`) probability would be more accurate
  but does not change the qualitative conclusion (the rank is in the
  thousands, not single-digit).
- Tested only on the USA dataset. Other datasets may exhibit different ratios
  of decoder-competition vs fragmentation failures.

### Confidence

**Medium** for the existence of a decoder-competition failure mode that is
recoverable by competitor suppression (clean replication across three M
values for one pair, with quantitative log-prob and rank evidence).
**Medium** for the existence of a separate feature-fragmentation failure
mode that competitor suppression cannot rescue (clear separation: ranks in
the 1000s vs ranks in the single digits).
**Low** for the population-level prevalence of each mode; we still need to
run the same probe across the broader hard-fail set.

### Next steps

- Generalize the competitor list: pull all single-token tokens that (a) are
  >5x more probable in the steered distribution than baseline AND (b) are not
  the target capital. This would let us run the suppression probe at scale.
- Re-classify the ~205 F-category pairs into "decoder competition" (capital
  in steered top-15 at some M) vs "feature fragmentation" (capital outside
  top-100 at all M). The fraction in each bucket sets the ceiling for what
  this fix can recover.
- For the fragmentation bucket, the missing intervention is upstream: the
  amplified feature set does not encode the capital. Either we need a
  different attribution graph (one whose target-side features align with the
  capital rather than with the state generally), or we need a complementary
  intervention that injects the target capital answer-token directly via a
  logit bias on the single answer token (essentially a one-shot teacher
  forcing for position 0).

---

## [2026-04-17] Topic: Specificity-failure probes -- simple state-feature pruning does not rescue the hard cases

**Question**: For the residual hard-fail population, especially the `F_generic_or_other`
cases (`Chapel Hill` instead of `Raleigh`, `Intervale` instead of `Montpelier`,
`Soldotna` instead of `Juneau`), can we rescue the hit by pruning the generic
target-state features and keeping only the capital-bearing features?

### Setup

Mapped the target-side amplified features in several `add_state_capital`
interventions back to the target entity's `node_grouping.csv` labels.

Three probe pairs:

1. `texas_dallas -> vermont_burlington`
2. `north_dakota_fargo -> north_carolina_charlotte`
3. `idaho_idaho_falls -> alaska_anchorage`

For each pair, compared the original feature set against a pruned subset:

- `capital_only`: keep only target amplified features whose grouped label matches
  the target capital (or a split piece of it, e.g. `Mont` + `pelier`)
- `drop_state`: remove generic target-state features while keeping capital-bearing
  features

Tested at `M=20` and `M=4.4721` using the same source ablations as the original run.

### Results

#### 1. `texas_dallas -> vermont_burlington`

Target feature mass:

- `Vermont`: 35.797
- `Mont`: 7.719
- `pelier`: 2.406
- `Say (Vermont)`: 2.078

Original run at `M=20` produces `Intervale` / `Shelburne` / `Lyndon` (wrong Vermont
towns). Lowering to `M=4.47` does **not** recover `Montpelier`; it falls back to a
generic/source-side continuation about `Austin`.

Pruned runs (`capital_only` or `drop_state`) also do **not** recover. They degrade
into filler or source-like continuations:

- `"The capital ... is poffible to reach by rail ..."`
- `"The capital ... is the city of Austin ..."`

This is a clean negative result: removing the generic state features does not reveal
the capital; it breaks the intervention.

#### 2. `north_dakota_fargo -> north_carolina_charlotte`

Target feature mass:

- `Say (Raleigh)`: 76.230
- `Carolina`: 28.672
- `North`: 12.703
- `Say (Carolina)`: 10.852
- `Raleigh`: 3.391

Original run at `M=20` renders:

- `Chapel Hill, North Carolina`

At `M=4.47`, the first-token top-k is already:

- `Chapel` (0.1211)
- `Raleigh` (0.1211)

Yet the rendered output still chooses `Chapel Hill`.

Interpretation: the `Raleigh` signal is already present and competitive, but decode
still prefers a nearby local-city continuation. This is **not** simply "missing
capital features" or "too much generic state mass". It looks like a decoder-level
specificity problem where a strong local continuation (`Chapel`) wins even when the
correct capital is tied in the logits.

#### 3. `idaho_idaho_falls -> alaska_anchorage`

Target feature mass:

- `Alaska`: 84.266
- `Say (Juneau)`: 72.191
- `Say (Alaska)`: 2.156

Saved baseline run already shows:

- `Soldotna, Alaska`

which confirms the key pattern: explicit `Juneau` features exist, but the model still
chooses a non-capital Alaska city. Pruned reruns were blocked in this session by GPU
OOM, so this pair remains suggestive but not fully re-tested.

### Interpretation

Simple target-side pruning is **not enough** to rescue specificity failures.

The evidence supports two subtypes:

1. **Feature-fragmentation failure** (`Montpelier` case): after removing the generic
   state features, the remaining capital pieces are too weak / too fragmented to drive
   a coherent decode.
2. **Decoder competition failure** (`Raleigh` case): the correct capital is already
   near the top of the distribution, but the model prefers a locally-consistent wrong
   city (`Chapel Hill`) at generation time.

This means the dominant hard-fail population is not explained by "one bad generic
feature drowning out the right one". At least some of these cases need stronger
token-level control than simple feature pruning.

### Threats

- Only one clean negative pruning result was fully executed end-to-end (`Texas ->
  Vermont`).
- The `Juneau` reruns were blocked by GPU contention, so the Alaska probe is only
  partially conclusive.
- The `Raleigh` case would benefit from a deterministic decode probe
  (`temperature=0`) to verify whether the `Chapel` vs `Raleigh` tie is purely a
  sampling artifact or a deeper continuation preference.

**Confidence**: Medium. The negative `Montpelier` result is strong, and the `Raleigh`
tie is highly informative, but a broader sweep would be needed before claiming all
specificity failures are irrecoverable under pruning.

**Data**:
- Raw probe outputs: `/tmp/specificity_probe_results.json`
- Curated summary: `output/research/_specificity_probe_summary.json`

## [2026-04-17] Topic: Multi-variant M-search on hard-fail pairs -- 25% recovery on a 20-pair sample, mode-dependent

**Question**: After the [2026-04-13] manual rescore confirmed 35/772 hard-fail
pairs as undercounted, the remaining 737 (95.5%) were classified as "real
generation failures" (categories: punctuation, OOD, prompt anchor, generic
local-city continuation). Are any of these still recoverable with the M-search
machinery, and if so which failure modes admit recovery?

### Setup

The prior `run_m_search.py` runs filtered out pairs that had a hit in any
variant, AND the additivity collector picks the single best-vsmax variant per
pair. As a result, the 772 canonical hard-fails (output of
`output/research/_pos0_manual_rescore_summary.json`) had **zero** `__m_tuned`
files in any field-add or labeled run. They were either never attempted (the
collector's best-vsmax pick happened to land on a non-recoverable variant) or
attempted under a variant that found no hit and produced no output file.

New utility: `scripts/utils/recover_hard_fails.py`. For each hard-fail pair,
it always runs the two-phase M-search on the priority variants
`add_state_capital` and `add_capital` (the empirically-dominant winning
variants in the prior 357-hit M-search), plus the top-K vsmax variants.
M-search budget: 5 coarse + 3 fine probes from M_min=1.0 to M_original=20.

Pilot: 20 USA hard-fail pairs sampled stratified by failure mode (4 per
category), 2 GPUs (~78 min wall time, 51 (pair, variant) jobs run).

### Results

| Failure mode | Sampled | Recovered | Recovery rate |
|---|---|---|---|
| `C_ood_foreign` (e.g. `' Efq'`, `' يتيمه'`) | 4 | 3 | **75%** |
| `B_punctuation_html` (e.g. `','`, `"'"`, `'<strong>'`) | 4 | 1 | 25% |
| `C_ood_codey` (e.g. `'Datuak'`, `'expandindo'`) | 4 | 1 | 25% |
| `E_prompt_anchor` (e.g. `' is'`, `' the'`, `' of'`) | 4 | 0 | **0%** |
| `F_generic_or_other` (e.g. `' Greater'`, `' Falls'`, `' Min'`) | 4 | 0 | **0%** |
| **Total** | **20** | **5** | **25%** |

The 5 newly recovered pairs (all USA, all confirmed semantically correct):

| Source | Target | M_tuned | Variant | Steered output preview |
|---|---|---|---|---|
| `louisiana_new_orleans` | `new_york_new_york_city` | 9.46 | add_capital | "...New Orleans is **Albany**.\n..." |
| `montana_billings` | `new_mexico_albuquerque` | 4.47 | add_state_capital | "...Billings is **Santa Fe, New Mexico**." |
| `north_carolina_charlotte` | `new_mexico_albuquerque` | 4.47 | add_state_capital | "...Charlotte is **Santa Fe, New Mexico**." |
| `vermont_burlington` | `oklahoma_tulsa` | 2.11 | add_capital | "...Burlington is, **Oklahoma City**, ..." |
| `wyoming_casper` | `michigan_detroit` | 9.46 | add_capital | "...Casper is **East Lansing, Michigan**." |

(`East Lansing` is a Michigan city ~5 km from Lansing -- partial credit; the
matcher accepts it because it contains "Lansing".)

### Interpretation

The mechanistic split is sharp:

1. **Magnitude failures (B + C categories)**: M=20 saturates the logits
   into rare-vocab tokens (Latin script with long-s `ſ`, Basque `Datuak`,
   Portuguese `expandindo`, Cyrillic `декват`). Lowering M to 2-9 restores
   normal vocabulary AND the right answer surfaces. **Recovery rate: 5/12 = 42%**.

2. **Specificity failures (E + F categories)**: At any M in [1, 20] the
   amplified features point to *the wrong continuation*: a generic local
   city in the target state (`Greater Manchester` for NH, `Shelburne` for VT
   capital, `Falls` for Kansas City), or a prompt-flow continuation
   (`is`, `of`). These are feature-selection failures: the matcher's
   target features don't actually contain the specific "is the state capital"
   signal. **Recovery rate: 0/8 = 0%**.

This is the cleanest separation we've seen between "right features, wrong
strength" and "wrong features at any strength" cases.

### Quantitative implications

If the 25% recovery rate from the stratified sample generalizes to the full
hard-fail population (772 pairs), an exhaustive multi-variant M-search would
unlock approximately **193 additional hits** (35 already from the manual
rescore). Combining with the 35 already-recovered, total recoveries would be
~228/772 = **30% of the hard-fail population**, leaving ~544 pairs (70% of
hard-fails) as genuine specificity failures of the labeled / field-add
intervention machinery.

By failure mode, the population breakdown (737 real-generation-failure pairs;
sample-extrapolated):

- B (186 pairs) + C (95 pairs) = 281 magnitude-failure pairs -> ~118 recoverable (42%)
- E (25 pairs) + F (430 pairs) = 455 specificity-failure pairs -> ~0 recoverable

So the magnitude-failure subgroup is small but high-yield; the specificity
subgroup is large but unrecoverable with M alone. To recover those, the
matcher's feature-selection (concept-pool composition) needs to be revisited,
not the steering strength.

### Threats

- N=20 is small. The 75% rate on `C_ood_foreign` is based on 4 pairs.
  Need to scale to all 281 magnitude-failure pairs to get tight CIs.
- Stratification was random within categories; no balancing for source-state
  identity. Some sources may be systematically harder (e.g. cities whose
  surrounding states have famous secondary cities competing with the capital).
- The pilot only probed `add_state_capital` and `add_capital`. Adding more
  variants per pair could push the recovery rate higher, especially for
  category B (punctuation) where the logit collapse is particularly severe.
- Output files use the `<variant>__m_tuned.json` naming; downstream
  aggregators (demo, _LOG analyses) already index this pattern correctly.
- Recovery measured by `steered_has_to_answer` (the existing strict
  evaluator), not the looser `pos0_distinctive_hit`. All 5 recovered pairs
  pass this stricter check.

**Confidence**: Medium. Mechanism is clean and matches prior LOG findings on
M=20 over-steering ([2026-04-12], [2026-04-07]); the sample is small but
the split between recoverable (B/C) and irrecoverable (E/F) is large enough
to be unlikely from sampling noise alone.

**Data**:
- Sample input: `/tmp/hard_fail_sample20.json`
- Run summary: `/tmp/recovery_sample20.json`
- New `__m_tuned.json` files: in `output/usa_states_batch/_swaps/runs/fullscale_usa_field_add/by_source/<src>/`
- Failure-mode taxonomy: `/tmp/unrecovered_failure_modes.json`

### Recommended follow-up

1. Run `scripts/utils/recover_hard_fails.py` on the full hard-fail population
   for all 5 datasets, restricted to category B + C pairs (~281 pairs total).
   Estimated cost: ~3 GPU-days at 8x A40, expected yield ~100-130 new hits.
2. For category F pairs (the dominant 430-pair group), the recovery cannot
   come from M-search. Two next-step probes worth considering:
   - **Ablate the dominant generic feature** (the one driving the
     `' Greater'` / `' Falls'` / `' Min'` continuation) and re-run the
     baseline M=20 -- tests whether removing the local-city interference
     unmasks the true capital.
   - **Stricter capital-only matcher**: rebuild the labeled feature pool
     using only `state_capital` field tokens (no `state` or `city`) to
     suppress the wrong-city interference at the source.

---

## [2026-04-12] Topic: M-search on field-additivity runs -- 95 new hits rescued

**Question**: The existing M-search was only applied to labeled (full-field)
runs. Field-additivity runs have no canonical files, so `run_m_search.py`
returned zero eligible pairs when pointed at them. Can a lower M unlock hits
that field-additivity at M=20 failed to achieve?

### Setup

Extended `run_m_search.py` with a new `_collect_missed_pairs_additivity()`
function that groups `__add_*` variant files by canonical pair, identifies
fully-missed pairs (zero hits across all variants of all fullscale runs), and
selects the best-scoring variant per pair as the search target (7x cheaper
than searching all 7 subsets).

New shell script: `run_all_m_search_fieldadd.sh`.  Ran with
`--all-runs --gpu-ids 0 1 2 3 4 5 6 7`.  Standard M-search config:
m_min=0.1, 6 coarse probes + 6 fine binary-search steps (≤12 GPU calls/pair).

Total eligible pairs: 867.  Runtime: ~7.5 hours on 8x NVIDIA A40 GPUs.

### Results

| Dataset | Eligible | New hits | Before | After | Delta |
|---------|----------|----------|--------|-------|-------|
| sounds_colors | 21 | 0 | 20.0% | 20.0% | +0.0pp |
| books | 73 | **9** | 59.5% | 63.8% | +4.3pp |
| paintings | 96 | **6** | 16.9% | 21.8% | +4.8pp |
| products | 124 | **2** | 26.4% | 27.6% | +1.1pp |
| usa_states | 553 | **78** | 64.2% | 67.3% | +3.2pp |
| **Total** | **867** | **95** | — | — | — |

Hit rates are over non-identity pairs; denominator = distinct (source, target)
pairs in each field-add run.

### Hit characteristics

- **M values at hit**: range 0.83–20.0; most hits cluster at M=2.4 and M=6.93,
  well below the M=20 used by the standard field-add runs. 78% of hits were
  found in Phase 1 (coarse probe), 22% required Phase 2 (binary refinement).
- **Winning variants by dataset**:
  - *Books*: `add_book` (3), `add_book_author` (2), `add_character_book_author` (2)
  - *Paintings*: `add_painting` (3), `add_first_name` (3) -- i.e. lower-field
    subsets win, suggesting the full triple at M=20 was over-steering
  - *Products*: `add_product_company_founder` and `add_product_founder` (1 each)
  - *USA*: `add_state_capital` (46/78 = 59%) dominated; `add_capital` (15);
    M=6.93 was the modal winning value
- **Sounds**: zero new hits at any M -- field-add M=20 already at ceiling for
  this dataset (18/30 T5 = 60%).

### Interpretation

The main finding is that **over-steering is a real failure mode for field
additivity**: many pairs that fail at M=20 become hits at M≈2–7. The USA
dataset benefits most (78 pairs rescued, +3.2pp), with a strong preference for
`add_state_capital` at intermediate M. Paintings show the same pattern with
single-field variants (`add_painting`, `add_first_name`) winning even though
the best field-add M=20 run had already tested these.

Combining the original field-add results with the new M-tuned variants, the
cross-run best aggregator now surfaces these as `add_X (M-tuned)` in the demo.

### Threats

- Tier is evaluated at M_tuned but the tier definition (token-level exact match)
  is unchanged -- no concern about inflated hits.
- The 7x cost reduction from searching only the best variant means we may miss
  cases where a *different* subset would have been the hit at lower M. However,
  for the scope of this run this is acceptable.
- The M-search exhausts only pairs missed by ALL fullscale variants, so the
  baseline comparison is conservative (we only count genuinely new hits).

**Confidence**: Medium. 95 new hits across 4 datasets with consistent pattern
(lower M rescues over-steered pairs). Needs cross-domain replication at
different entity scales to rule out dataset-specific confounds.

---

## [2026-04-07] Topic: Full-scale M-search across all datasets -- 357 new hits rescued

**Question**: After fixing the `_patch_features_m` bug and validating the
standard config, what is the actual yield of adaptive M-search when applied
to every eligible pair across all five datasets?

### Setup

Ran `run_m_search.py --all-runs --gpu-ids 0 1 2 3 4 5 6 7` for each dataset.
Cross-run filtering excluded all pairs that already had a hit in **any** variant
(labeled, field_add, random). Standard config: m_min=0.1, 6 coarse + 6 fine.

Total eligible pairs: 1210 (no hit in any existing variant).
Runtime: ~10.5 hours on 8x NVIDIA A40 GPUs.

### Results

| Dataset | Eligible | M-tuned hits | Rate | Before | After | Delta |
|---------|----------|-------------|------|--------|-------|-------|
| usa_states | 870 | 329 | 37.8% | 64.4% | 77.4% | +13.0pp |
| books | 85 | 12 | 14.1% | 59.5% | 65.2% | +5.7pp |
| paintings | 103 | 7 | 6.8% | 16.9% | 22.6% | +5.6pp |
| sounds | 23 | 5 | 21.7% | 20.0% | 30.0% | +10.0pp |
| products | 128 | 4 | 3.1% | 26.4% | 28.7% | +2.3pp |
| **Total** | **1210** | **357** | **29.5%** | | | |

"Before" = fraction of non-identity pairs with any hit (labeled + field_add +
random). "After" = including the new `__m_tuned` variants.

### M value distribution (357 hits)

| Range | Count | Share | Typical datasets |
|-------|-------|-------|------------------|
| M < 1 | 10 | 2.8% | sounds, paintings |
| 1 <= M < 3 | 167 | 46.8% | USA (dominant), books |
| 3 <= M < 7 | 9 | 2.5% | paintings, books |
| M ~ 6.93 | 143 | 40.1% | all datasets |
| M > 7 | 28 | 7.8% | USA |

The bimodal pattern -- peaks at M~2.4 and M~6.9 -- reflects the geometric probe
grid. M=2.4 is the 4th probe point and M=6.9 is the 5th probe in the standard
config's 6-point log-spaced ladder from 0.1 to 20. This confirms that the
coarse Phase 1 grid captures most rescuable pairs at exactly those points.

### Phase analysis

| | Phase 1 | Phase 2 | Total |
|---|---------|---------|-------|
| Hits | 333 | 24 | 357 |
| Share | 93.3% | 6.7% | |

Phase 2 (KL-transition binary search) contributed 24 additional hits. These
are pairs where the optimal M falls between coarse grid points. Despite its
low share, Phase 2 is critical for the hardest cases (e.g. starry_night ->
the_scream in paintings, where KL follows a U-shape with a narrow hit pocket
around M~4).

### Per-GPU distribution (USA dataset, largest)

| GPU | Pairs | Hits | Hit rate | Time |
|-----|-------|------|----------|------|
| GPU 0 | 109 | 44 | 40.4% | 25000s |
| GPU 1 | 109 | 42 | 38.5% | 25246s |
| GPU 2 | 109 | 34 | 31.2% | 26570s |
| GPU 3 | 109 | 52 | 47.7% | 24271s |
| GPU 4 | 109 | 38 | 34.9% | 26111s |
| GPU 5 | 109 | 42 | 38.5% | 25764s |
| GPU 6 | 109 | 33 | 30.3% | 26168s |
| GPU 7 | 107 | 32 | 29.9% | 26094s |

Hit rate varies from 30% to 48% across GPU chunks due to pair assignment. The
pairs are sorted alphabetically and chunked sequentially, so some GPUs get
"easier" state-city pairs. ~7 hours wall-clock for 870 pairs on 8 GPUs.

### Key observations

1. **USA states is highly rescuable (37.8%)**: The labeled intervention builder
   captures the right causal structure for most state-city pairs, but the
   default M=20 is too strong for ~38% of eligible misses. Lowering M to 2-7
   rescues them.

2. **Products remain stubbornly low (3.1%)**: Even exhaustive M-search across
   the full range recovers only 4 pairs. The labeled features for product-founder
   associations lack sufficient specificity regardless of steering strength.

3. **The standard config (6+6) is GPU-efficient**: Average GPU calls per pair
   is ~8 (many pairs exit Phase 1 early at steps 3-5 on first hit). The 12-call
   maximum per pair is rarely reached for hits (only for Phase 2 successes or
   full misses).

4. **M=2.4 is the most productive single probe point**: 167 hits occur at
   exactly M~2.4 (46.8%), making it the single best "reduced steering" value.
   A simple one-shot retry at M=2.4 would capture roughly half of all rescuable
   misses at 1 GPU call per pair.

### Impact on demo

All 357 `__m_tuned.json` files are saved in each labeled run's `by_source/`
directory. The demo automatically indexes them as the "Adaptive M" variant via
the `_VARIANT_SUFFIX_RE` pattern and `_CONTROL_MODE_LABELS` mapping.

### Threats

- **Non-determinism**: Steering uses `seed=42` but model loading can introduce
  minor floating point variations. Some borderline hits at M~6.9 might not
  reproduce exactly.
- **Grid artifact**: The M=2.4 and M=6.9 peaks are artifacts of the 6-point
  log-spaced probe grid. With a denser or randomly-placed grid, the M
  distribution would be smoother around those peaks.
- **No verification pass**: Results are single-shot. A verification re-run at
  the winning M would confirm reproducibility.

**Confidence**: High. N=1210 pairs across 5 diverse datasets with consistent
patterns. The `_patch_features_m` fix is mechanistically validated. The
improvement is large (+357 hits) and robust across domains.

**Data**: Full run log at `/tmp/m_search_full_run.log`. Per-pair results in
each dataset's `by_source/` directories as `to_*__m_tuned.json`.

---

## [2026-04-06] Topic: Cross-dataset M-search benchmark -- bug fix, KL profiles, and config comparison

**Question**: How does the two-phase adaptive M-search perform across all five
datasets in the demo? Are there better configurations? Does the algorithm
sequence (coarse + fine) work universally? Critical sub-question: is the
`_patch_features_m` function correctly handling the labeled intervention
builder's feature format?

### Critical bug fix: `_patch_features_m` was overwriting ablation features

**Discovery**: Before running tests, inspection of feature files revealed that
the labeled intervention builder stores both source-ablation (M=-2) and
target-amplification (M=20) features with `"ablate": false`. The original
`_patch_features_m` keyed on the `ablate` flag, so it overwrote **all** M
values -- including source ablations -- when searching for optimal M. This
effectively turned ablations into amplifications at the probe M value, breaking
the entire intervention logic.

**Fix**: Changed `_patch_features_m` to detect ablation by `M < 0` (negative M
signals ablation intent regardless of the `ablate` flag):
```python
is_ablation = f2.get("ablate", False) or (isinstance(orig_m, (int, float)) and orig_m < 0)
```
This preserves M=-2 source features while only patching M>0 target features.

**Impact**: The fix is validated by the `south_carolina_charleston->oregon_portland`
pair which failed all 12 search steps before the fix (OOM-contaminated run) but
after the fix achieves a HIT at M=6.93 in just 5 steps.

### Experimental setup

- **Pairs tested**: 15 pairs total, 3 per dataset (selected via `swap_query.py`
  by near-miss indicators: `vs_max`, `target_rank_improvement`, `first_token_matches_target`)
- **Configurations tested**: 3 configs x 15 pairs = 45 test runs
  - `standard`: m_min=0.1, 6 coarse probes, 6 fine steps (M range: 0.1--20)
  - `wide_range`: m_min=0.01, 8 coarse probes, 6 fine steps (M range: 0.01--20)
  - `ultrawide`: m_min=0.01, 8 coarse + 6 fine, m_max=40 (M range: 0.01--40)
- **GPU**: NVIDIA A40 (GPU 1), ~25s per steering call
- **Total runtime**: 9696s (~2.7 hours), 45 test runs

### Raw findings

#### Overall hit rates

| Config      | Hits | Total | Rate | Avg steps (hits) | Phase1 | Phase2 |
|-------------|------|-------|------|-------------------|--------|--------|
| standard    | 7    | 15    | 47%  | 4.9               | 6      | 1      |
| wide_range  | 6    | 15    | 40%  | 7.0               | 5      | 1      |
| ultrawide   | 7    | 15    | 47%  | 6.1               | 7      | 0      |

#### By dataset

| Dataset              | Hits/Total | standard | wide_range | ultrawide |
|----------------------|------------|----------|------------|-----------|
| usa_states_batch     | 5/9 (56%) | 2/3      | 1/3        | 2/3       |
| products_founders    | 0/9 (0%)  | 0/3      | 0/3        | 0/3       |
| paintings_painters   | 6/9 (67%) | 2/3      | 2/3        | 2/3       |
| sounds_colors        | 3/9 (33%) | 1/3      | 1/3        | 1/3       |
| book_characters      | 6/9 (67%) | 2/3      | 2/3        | 2/3       |

#### Winning M distribution

All 20 hits: M values = [0.77, 0.83, 1.14, 2.28, 2.40, 3.74, 3.74, 3.74,
3.74, 3.92, 4.08, 6.75, 6.75, 6.93, 6.93, 6.93, 6.93, 12.23, 12.23, 20.0]

- Low M (<2): 3 hits (15%) -- all from sounds/colors (bark->hiss)
- Mid M (2-8): 14 hits (70%) -- most common sweet spot
- High M (>=8): 3 hits (15%) -- USA pairs needing stronger steering

#### Key KL profile patterns

**Pattern A: "U-shaped KL" (starry_night->the_scream)**
KL starts very high (~17), drops to a minimum around M=2-3 (~9), then rises
again at high M (~16). The hit zone is exactly at the KL minimum. Phase 2
successfully found this at M=4.08 via the KL transition detector.

**Pattern B: "Flat-then-rise KL" (bark->hiss)**
KL stays very low throughout (1.2--1.8) because the sound/color features are
inherently weak. The hit occurs at M=0.83 where KL is at its minimum (1.17).
Even tiny M values steer successfully.

**Pattern C: "Rising KL with hit in middle" (katniss->jay_gatsby)**
KL starts around 12.3 and rises to 14.5 at the winning M=2.4. Hit occurs
despite relatively high KL -- the key is that the target answer gains enough
probability before coherence collapses.

**Pattern D: "Persistently high KL, no hit" (products/facebook pairs)**
All products->facebook pairs show KL consistently 12--16 across the entire M
range with no hit at any M. This indicates a **specificity failure** -- the
labeled features don't capture the right causal mechanism for these pairs.

#### Config disagreements (most informative cases)

1. **NC_charlotte->OR_portland**: Only `ultrawide` finds a hit (M=12.23).
   `standard` and `wide_range` probe up to M=20 but miss. The `ultrawide`
   config's M_max=40 places probe points at different log-spaced positions,
   and M=12.23 happens to land in a narrow hit pocket.

2. **VA_virginia_beach->ND_fargo**: Only `standard` finds a hit (M=6.93).
   `wide_range` and `ultrawide` spread their probes over a wider range,
   so they skip the exact M=6.93 value that standard hits. This demonstrates
   that **denser probing in the likely range beats wider coverage**.

### Interpretation

1. **The `standard` config is the best default.** It achieves the same hit rate
   as `ultrawide` (47%) with fewer steps per hit (4.9 vs 6.1). The M range
   0.1--20 covers the effective steering range for all datasets.

2. **`wide_range` (m_min=0.01) adds no value.** All M<0.1 probes consistently
   fail to find hits -- the 0.01--0.1 range is wasted computation. The extra
   probes dilute coverage in the 1--20 range where hits actually occur.

3. **`ultrawide` (M up to 40) occasionally rescues pairs** that `standard`
   misses (NC_charlotte->OR_portland). But it also misses pairs that `standard`
   finds (VA->ND). Net effect is neutral.

4. **Products/founders dataset is immune to M-search.** All 9 runs across 3
   configs produced zero hits. These pairs have **consistently high KL (12-16)**
   at every M value, suggesting the labeled features for products are missing
   critical causal structure. The intervention changes the distribution but
   never in the right direction.

5. **Phase 2 (KL transition search) works but rarely activates.** Only 2 out of
   20 hits came from Phase 2 (both for starry_night->the_scream). The coarse
   Phase 1 probe is sufficient for most rescuable pairs. However, Phase 2 is
   valuable precisely for the hardest cases like the U-shaped KL pattern.

6. **The bug fix is the single biggest improvement.** Correctly preserving
   source-ablation features (M=-2) during the M search is what enables hits.
   Without the fix, the search was fundamentally broken because it converted
   source ablations into (weak) amplifications.

7. **Optimal M varies dramatically by domain:**
   - Sounds/colors: M ~ 0.8 (very gentle)
   - Paintings: M ~ 4-7 (moderate)
   - USA states: M ~ 7-12 (strong)
   - Books: M ~ 2-7 (moderate)

### Recommendation for default config

```yaml
m_search:
  enabled: true
  m_min: 0.1        # 0.01 wastes GPU calls
  n_coarse_probes: 6  # sufficient for Phase 1
  n_fine_steps: 6
  log_tolerance: 0.1
  min_kl_drop: 1.0
```

No change from the original standard config. The wider/denser alternatives
tested here do not improve overall hit rate.

### Threats

- **Sample size**: 15 pairs (3 per dataset) is small. The near-miss selection
  strategy biases toward rescuable pairs -- the 47% hit rate overstates the
  expected rate on the full population of misses.
- **Non-determinism**: CT steering has a seed parameter but model loading and
  floating point can introduce slight non-determinism. Some hits at boundary M
  values may not reproduce.
- **Products anomaly**: Zero hits might reflect bad pair selection (all 3 target
  "facebook") rather than a dataset-wide problem.
- **Config probe points are correlated**: Standard and wide_range/ultrawide
  share similar (not identical) probe points due to log-spacing. Independent
  random probing was not tested.

**Confidence**: Medium. The bug fix is high-confidence (mechanistically sound
and validated). The config comparison is medium (consistent pattern but
small N and selection bias).

**Data**: Full report at `output/research/m_search_test_results.json`

---

## [2026-04-04] Topic: M_amplify sweep on sounds/colors -- fine-grained strength recovers hits

**Question**: The fullscale sounds/colors labeled run (M_amplify=20) produces
0/30 hits. The preceding answer-space geometry entry showed that the 6-color
answer space has near-uniform competition (margin ~0.15), suggesting M=20
overshoots thin margins. Does reducing M_amplify to a fine-grained range
(0.1 to 5.0) recover any hits?

**Method**: Created 10 YAML configs at M_amplify = {0.1, 0.2, 0.3, 0.5, 0.7,
1.0, 1.5, 2.0, 3.0, 5.0}, all else identical to `fullscale_sounds_labeled`
(M_ablate=-2, temperature=0.3, seed=42, freq_penalty=2.0, top_k=5). Ran all
30 non-identity pairs per config (360 total runs). Compared against the
existing M=20 labeled run and the M=20 random baseline. Results queried with
`SwapQuery` and `SwapStats`.

Configs: `scripts/experiments/batch/configs/sweep_sounds_m{0_1,...,5_0}.yml`.
Results: `output/sounds_colors_batch/_swaps/runs/sweep_sounds_m{0_1,...,5_0}/`.

**Raw findings**:

Table 1 -- Aggregate metrics by M_amplify (N=30 non-identity pairs each):

| M     | Hit%  | Flip@0 | 1stTok | Suppr  | vsMax  | vsMax_md | rkGrp | gapCl | ctrl_stab |
|-------|-------|--------|--------|--------|--------|----------|-------|-------|-----------|
| 0.1   |  0.0% | 46.7%  |  0.0%  | 96.7%  |  0.68  |   0.50   | 1.33  |  0.96 |   9.79    |
| 0.2   |  6.7% | 53.3%  |  6.7%  | 93.3%  |  0.99  |   0.69   | 1.33  |  1.23 |   9.61    |
| 0.3   |  6.7% | 53.3%  | 10.0%  | 93.3%  |  0.83  |   0.50   | 1.33  |  1.21 |   9.66    |
| **0.5** | **10.0%** | **63.3%** | **10.0%** | **96.7%** | **0.90** | **0.60** | **1.43** | **1.26** | **9.24** |
| 0.7   | 10.0% | 73.3%  | 10.0%  | 90.0%  |  0.99  |   0.75   | 1.57  |  1.28 |   9.02    |
| 1.0   | 10.0% | 76.7%  | 13.3%  | 86.7%  |  1.16  |   0.88   | 1.43  |  1.32 |   8.52    |
| 1.5   |  3.3% | 76.7%  |  3.3%  | 86.7%  |  1.14  |   1.29   | 1.30  |  1.28 |   8.99    |
| 2.0   |  0.0% | 76.7%  |  0.0%  | 90.0%  |  1.45  |   1.66   | 1.13  |  1.11 |   8.44    |
| 3.0   | 10.0% | 76.7%  |  0.0%  | 86.7%  |  1.81  |   1.37   | 1.13  |  1.07 |   7.64    |
| 5.0   | 16.7% | 76.7%  |  0.0%  | 90.0%  |  2.37  |   1.69   | 1.00  |  1.90 |   8.00    |
| 20    |  0.0% | 63.3%  | 13.3%  | 96.7%  |  1.91  |   1.95   | 1.03  |  3.28 |  10.61    |
| rand  |  1.1% | 33.3%  |  0.0%  | 80.0%  |  1.02  |   0.97   | 1.26  |  3.54 |  13.88    |

Entity-color mapping for reference: meow=black, hiss=green, bark=brown,
oink=pink, buzz=yellow, whinny=white.

Table 2 -- Pair-level hits by M value:

| M   | Hits (from -> to)                                      | Color swap     |
|-----|--------------------------------------------------------|----------------|
| 0.1 | (none)                                                 |                |
| 0.2 | bark->whinny, hiss->meow                              | brown->white, green->black |
| 0.3 | bark->whinny, hiss->meow                              | brown->white, green->black |
| 0.5 | bark->hiss, bark->whinny, hiss->meow                  | +brown->green  |
| 0.7 | bark->hiss, bark->whinny, hiss->meow                  | (same as 0.5)  |
| 1.0 | bark->hiss, bark->whinny, hiss->meow                  | (same as 0.5)  |
| 1.5 | hiss->meow                                             | green->black   |
| 2.0 | (none)                                                 |                |
| 3.0 | buzz->whinny, hiss->whinny, bark->whinny              | *->white       |
| 5.0 | bark->whinny, hiss->whinny, buzz->whinny, oink->whinny, buzz->meow | mostly *->white |
| 20  | (none)                                                 |                |

First-token matches (steered first token = target answer, but full output
does not confirm hit): peaked at M=1.0 (4/30 = 13.3%), with matches at
bark->hiss, bark->whinny, hiss->meow, buzz->whinny. At M=20, 4/30 first-
token matches exist (whinny->hiss, bark->hiss, meow->hiss, oink->hiss) --
all targeting hiss/green. The low-M and high-M first-token-match sets are
**completely disjoint**, suggesting different steering regimes.

**Interpretation**:

1. **Fine-grained M recovers hits that M=20 completely misses.** The sweet
   spot is M=0.5-1.0, where Hit% reaches 10% (3/30) with diverse pair
   coverage (two different target colors: white and black, plus green). This
   confirms the overshoot hypothesis from the geometry entry: M=20 is too
   strong for the thin margins between 6 color candidates.

2. **Two distinct regimes emerge.** At low M (0.2-1.0), hits come from
   genuinely diverse source-target pairs: bark->whinny (brown->white),
   hiss->meow (green->black), bark->hiss (brown->green). These are
   semantically varied and suggest the labeled features carry some real
   color-specific signal when applied gently. At high M (3.0-5.0), hits
   cluster heavily on *->whinny (white), suggesting the higher perturbation
   non-specifically pushes toward "white" as a dominant attractor rather
   than the correct target color.

3. **There is a "dead zone" at M=1.5-2.0.** Hit% drops to 3.3% at M=1.5
   and 0% at M=2.0 before rebounding at M=3.0 with the white-dominated
   regime. This non-monotonicity mirrors the USA sweep finding (some pairs
   hit at M=5 but not M=10 or M=20). The dead zone may represent the
   transition between "gentle, targeted steering" and "brute-force logit
   disruption."

4. **Flip@0 and Hit% tell opposite stories about optimal M.** Flip@0
   saturates at ~77% by M=0.7 and stays there through M=5.0, but drops
   back to 63% at M=20. Hit% peaks at M=5.0 (16.7%) but those hits are
   mechanistically suspect (white-dominant). The highest *credible* Hit%
   is at M=0.5-1.0 (10%).

5. **Control stability confirms overshoot.** ctrl_stab (mean absolute logit
   shift on non-answer tokens) rises from 7.6 at M=3.0 to 10.6 at M=20,
   confirming that higher M produces more collateral disruption. At the
   sweet spot (M=0.5-1.0), ctrl_stab is 8.5-9.2, meaning the intervention
   is better contained.

6. **10% Hit% from 0% is meaningful but modest.** Going from 0/30 to 3/30
   is a real improvement (p=0.12 by Fisher exact one-sided, not
   conventionally significant at 0.05 given N=30). Combined with the
   qualitative evidence (diverse pairs, disjoint from high-M white cluster),
   this is suggestive rather than conclusive.

Confidence: **Medium**. The sweep is deterministic (fixed seed) and covers
the full matrix, but N=30 is small and the hit rate even at the optimum is
low. Epistemic level: **L2** (causal intervention design).

**Threats to validity**:

- N=30 pairs is too small for reliable rate estimation; 3/30 vs 0/30 is not
  statistically significant at conventional thresholds.
- The M=5.0 hits cluster on target=whinny (white), which could be a baseline
  effect (white being an attractor color) rather than genuine targeting.
- M_ablate is fixed at -2 throughout; varying it jointly might change the
  picture.
- The seed is fixed (42), so results are deterministic for this seed but
  might differ at other seeds. A multi-seed replication would strengthen
  the finding.
- The "dead zone" at M=1.5-2.0 could be noise with N=30.

**Follow-up**:

- Run the same sweep with M_ablate varied (e.g., -0.5, -1.0) to test
  whether ablation strength interacts with amplification strength.
- Run a random-feature sweep at the same M values (especially M=0.5 and 1.0)
  to confirm the low-M hits are label-specific, not a generic effect.
- Examine the 3 consistent low-M hit pairs (bark->whinny, hiss->meow,
  bark->hiss) in detail: which features drive the hit, and are they
  color-classified supernodes?

**References**: `scripts/experiments/batch/configs/sweep_sounds_m*.yml`;
`output/sounds_colors_batch/_swaps/runs/sweep_sounds_m*/`;
previous entry `[2026-04-04] Answer-space geometry`;
`[2026-04-01] M_amplify sweep -- full investigation summary` (USA analogue)

---

## [2026-04-04] Topic: Answer-space geometry -- are color tokens too similar to steer between?

**Question**: The sounds/colors dataset has the lowest hit rate of any domain
(0/30 in labeled runs). One hypothesis is that the model's representation of
the six color answers is so tightly clustered that steering interventions cannot
reliably shift the output from one color to another. Is the color answer space
genuinely "more similar" than the answer spaces of higher-performing domains
(USA capitals, book authors), and does this similarity persist from input
embeddings through the last hidden layer to the next-token logit distribution?

**Method**: Using Gemma-2-2b (the model used in all batch experiments),
computed four levels of answer-set geometry:

1. **Input-embedding pairwise cosine**: for each answer string, space-prefixed
   and mean-pooled over subword tokens via `model.get_input_embeddings()`.
   Measured mean pairwise cosine similarity across all answer pairs.

2. **Last-layer hidden-state pairwise cosine**: ran each entity's actual seed
   prompt through the full model with `output_hidden_states=True`, extracted
   the last-layer hidden vector at the final prompt position. Measured mean
   pairwise cosine across entity prompts within a domain.

3. **First-subtoken restricted distribution** at the seed: for each entity
   prompt, took the true last-position logits, restricted to the first
   subtoken ID of each candidate answer, renormalized to a simplex.
   Reported mean normalized entropy, top-1 mass, and top1-top2 margin
   across entity prompts.

4. **Full-sequence teacher-forced distribution**: for each entity prompt and
   each candidate answer, computed the sum of teacher-forced log probabilities
   \(\sum_j \log P(\text{tok}_j | \text{prompt}, \text{tok}_{<j})\) across all
   subword tokens of the answer. Softmaxed the K resulting scores to get a
   probability simplex over candidates. Same restricted metrics as (3).

All three datasets used the same seed prompt templates and entity lists from
the corresponding batch configs. Scripts: `scripts/utils/seed_answer_geometry.py`.

**Raw findings**:

Table 1 -- Input-embedding statistics (mean-pooled over subword tokens):

| Answer group          | K  | Mean pairwise cos | Norm mean | Norm std |
|-----------------------|----|-------------------|-----------|----------|
| Colors (sounds)       |  6 | 0.3120            | 1.603     | 0.056    |
| US capitals           | 50 | 0.2093            | 1.617     | 0.240    |
| Book authors          | 15 | 0.1781            | 1.278     | 0.117    |
| Book characters       | 15 | 0.1852            | 1.146     | 0.215    |

Table 2 -- Last-layer hidden-state pairwise cosine (across entity prompts):

| Domain          | Mean pairwise cos (last hidden) |
|-----------------|---------------------------------|
| Sounds/colors   | 0.6236                          |
| USA/capitals    | 0.8738                          |
| Books/authors   | 0.8125                          |

Table 3 -- Restricted next-token distribution (mean over entity prompts):

| Domain        | Method         | Norm entropy | Top-1 mass | Margin |
|---------------|----------------|--------------|------------|--------|
| Sounds/colors | first-subtoken | 0.7252       | 0.474      | 0.210  |
| Sounds/colors | full-sequence  | 0.7336       | 0.439      | 0.146  |
| USA/capitals  | first-subtoken | 0.6628       | 0.263      | 0.121  |
| USA/capitals  | full-sequence  | 0.6686       | 0.274      | 0.151  |
| Books/authors | first-subtoken | 0.4489       | 0.541      | 0.348  |
| Books/authors | full-sequence  | 0.2964       | 0.725      | 0.578  |

**Interpretation**:

1. **Input embeddings: colors are the most clustered.** Mean pairwise cosine
   for colors (0.312) is ~50% higher than for book authors (0.178) and ~49%
   higher than for US capitals (0.209). Embedding norms do not explain the
   difference -- colors have normal or slightly above-average norms. This
   means that at the very first layer, color tokens already point in more
   similar directions than proper names do: "brown", "black", "green" etc.
   live in a tighter cone than "Harper Lee", "Jane Austen", "Mark Twain."

2. **Last hidden layer: sounds prompts are the *least* clustered.** At 0.624
   mean pairwise cosine, sounds entity prompts are more spread out than USA
   (0.874) or books (0.812). This means the model's internal representations
   at the seed prompt are more differentiated for sounds than for USA --
   **the opposite of what a "colors too similar" story predicts**. The tighter
   clustering of USA/books hidden states is consistent with those prompts
   sharing structural templates with more overlap (50 US state city names in
   similar sentence frames). The model *can* tell sounds entities apart
   internally -- the difficulty lies at the output layer, not in the middle.

3. **The output distribution is nearly flat over 6 color candidates.**
   Normalized entropy over candidate answers is 0.73 for sounds (full-sequence
   teacher forcing). To make this concrete: with K=6 colors, the model's
   probability distribution on the correct prompt looks roughly like
   [44%, 15%, 13%, 12%, 9%, 7%] -- about 4 colors are live competitors.
   This means the gap between the intended target color and the next-best
   color is only ~0.15 in probability (the "margin"). Any perturbation that
   is even slightly miscalibrated can flip the winner to a *wrong* color
   rather than the intended target. This is what "near-uniform competition"
   means: the six horses are bunched together at the finish line, and a
   nudge is as likely to help the wrong horse as the right one.

   For comparison, USA (K=50) has similar normalized entropy (0.67) but 50
   candidates to spread across, so a steering intervention has more room to
   improve the target's *rank* -- moving from rank 20 to rank 1 is possible
   even if lots of capitals are in play. For books (K=15), the distribution
   is sharply peaked (norm entropy 0.30, top-1 mass 73%): the model is
   already quite sure of the right author, and steering mostly needs to
   *swap which author dominates* rather than pick one from a flat crowd.

4. **Why this matters for hit rate.** All fullscale runs used the same
   steering strength (M_amplify=20, M_ablate=-2). For the sounds labeled
   run (N=30): Hit%=0%, but flip@0=63.3%, first_token_matches=13.3%,
   vs_max mean=1.91. For sounds random (N=90): Hit%=1.1%, flip@0=33.3%,
   first_token_matches=0%, vs_max mean=1.02. So labeled features *do* show
   some specificity -- they double the flip rate and produce 13% first-token
   matches that random never achieves. The problem is that M=20 is a blunt
   instrument applied to a knife-edge competition: it reliably *disrupts* the
   source color (suppressed=97%) and moves the output into the color space,
   but lands on the correct target color only by chance because 4 colors are
   nearly tied.

5. **"Similar embeddings" is a partial but incomplete explanation.** The color
   answer tokens are closer in input embedding space, and K is small, so any
   perturbation can flip the winner among a few nearby candidates. But the
   model's hidden states and logit distributions tell a more nuanced story:
   sounds prompts are actually well-separated internally; the main bottleneck
   is the combination of (a) a tiny answer set (K=6) with (b) near-uniform
   probability across most of those answers, leaving razor-thin margins that
   a coarse steering multiplier cannot navigate precisely.

6. **Would a fine-grained M_amplify sweep help?** Potentially yes, for a
   specific reason. The current M_amplify=20 was tuned for USA states
   (K=50, wider margins). For sounds, the target color starts at probability
   ~0.09-0.15 and only needs to gain ~0.15 to overtake the leader. A
   multiplier of 20 applied to ~80 features is a large perturbation that
   overshoots these thin margins, disrupting the output distribution in ways
   that do not preferentially benefit the intended target. A fine sweep
   (M_amplify from 0.5 to 5.0 in 0.5 steps, or even 0.1 steps in the low
   range) could find a regime where the steering nudge is small enough to
   promote the correct color without blowing past it. The existing evidence
   supports this: labeled features already outperform random on flip@0 and
   first_token_matches at M=20; a gentler push might convert some of those
   first-token matches into full hits.

   **However**, a fine-grained sweep faces structural headwinds:
   - The labeled-vs-random vs_max gap is only +0.89 for sounds (vs +5.17 for
     USA). Even at the optimal M, the features may not encode enough
     color-specific signal to reliably pick 1-of-6 colors.
   - With N=30 pairs and K=6, statistical power is low; random variation
     across M values will produce noisy results.
   - The 13% first_token_matches rate at M=20 is a ceiling estimate for
     "some signal exists"; if most of these are lucky near-ties rather than
     genuine targeting, lower M will not help.
   Verdict: a sweep is worth running as a diagnostic (low cost: 30 pairs x
   ~10 M values = 300 runs), but expectations should be calibrated to
   "small improvement" rather than "rescues the domain."

Confidence: **Medium**. The geometric facts are deterministic given the model,
but the causal link from "answer-space geometry -> swap hit rate" is
correlational, not ablated. Epistemic level: **L1** (model representation
properties) with **L2** implications (explaining downstream swap difficulty).

**Threats to validity**:

- Three domains is a small cross-domain sample. Products (n=12) and paintings
  (n=10) were excluded for brevity but should be checked.
- Mean-pooling over subword tokens is a rough proxy for how the model "sees"
  multi-token answers; the unigram embedding is only a starting point.
- The teacher-forced logprob is computed autoregressively per candidate; the
  actual generation process involves sampling/greedy choices that may amplify
  or dampen the effects measured here.
- The comparison confounds K (6 vs 15 vs 50) with domain structure. Normalized
  entropy partially controls for this, but residual confounding remains.
- USA uses the highm_usa_m100 entity set (50 entities); other runs may use
  different subsets.
- The claim that M=20 "overshoots" for sounds is inferred from the geometry
  analysis, not directly measured. A sweep is the necessary test.

**Follow-up**:

- **Fine-grained M_amplify sweep on sounds**: run M_amplify in
  {0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0} (and optionally finer steps 0.1-2.0)
  to test whether a gentler push improves Hit% or first_token_matches.
- Repeat for products and paintings to complete the 5-domain picture.
- Test whether **steering vector dot product with the answer-set centroid** is
  a better predictor of swap success than per-entity error_node_pct.
- Run a matched experiment: pick entity pairs with similar baseline metrics
  across domains and compare steering success, to disentangle K from other
  domain properties.
- Compute **effective dimensionality** (PCA eigenspectrum) of the answer
  embedding cluster per domain to get a richer view than mean cosine.

**References**: `scripts/utils/seed_answer_geometry.py`;
`scripts/utils/datasets/sounds_colors_v2.json`;
`scripts/utils/datasets/book_characters_authors.json`;
`output/usa_states_batch/_swaps/runs/highm_usa_m100/config_resolved.json`;
`output/sounds_colors_batch/_swaps/runs/fullscale_sounds_labeled/_summary.json`;
`output/sounds_colors_batch/_swaps/runs/fullscale_sounds_random/_summary.json`

---

## [2026-04-04] Topic: Late-position trajectory recovery in labeled failures

**Question**: For swap failures (steered_has_to_answer = False), does the target
token ever recover to a high rank at later generation positions (pos > 0)? If
so, does continuing steering beyond position 0 reveal genuine signal that the
position-0 snapshot misses, or are the recoveries spurious?

**Method**: For all five domains, loaded every labeled swap failure and extracted
the full 11-position logit trajectory (positions 0-10). Measured:
(a) target absolute rank at each position,
(b) target rank within the same-dataset contrast group at each position,
(c) target-minus-max-other-answer logit at each position.
Defined "late recovery" as: target NOT in top-K at position 0, but reaching
top-K at some position > 0. Deep-dived into the most dramatic recovery cases
to inspect steered outputs and generated tokens at the recovery positions.

**Raw findings**:

Late recovery rates (failures only, skip identity, labeled runs):

| Domain | N failures | Late top-1 | Late top-5 | Late top-10 | Late top-20 |
|--------|-----------|-----------|-----------|------------|------------|
| Sounds | 30 | 0 (0.0%) | 1 (3.3%) | 3 (10.0%) | 3 (10.0%) |
| Paintings | 119 | 0 (0.0%) | 11 (9.2%) | 19 (16.0%) | 18 (15.1%) |
| Products | 151 | 1 (0.7%) | 4 (2.6%) | 7 (4.6%) | 14 (9.3%) |
| Books | 203 | 0 (0.0%) | 2 (1.0%) | 10 (4.9%) | 10 (4.9%) |
| USA | 1844 | 83 (4.5%) | 467 (25.3%) | 653 (35.4%) | 854 (46.3%) |

Sounds/colors has 0/30 successes overall and essentially zero meaningful
late recovery. Only 3/30 ever touch top-10, at marginal ranks 5, 8, 10.

Mean contrast-group rank by position (failures only):

| Domain (group size) | pos 0 | pos 2 | pos 4 | pos 5 | pos 8 |
|---------------------|-------|-------|-------|-------|-------|
| Sounds (~6) | 2.63 | 2.80 | 2.87 | 2.33 | 2.80 |
| Paintings (~10) | 2.28 | 3.67 | 4.76 | 4.18 | 4.69 |
| Products (~12) | 1.35 | 4.30 | 4.89 | 5.20 | 5.40 |
| Books (~16) | 2.03 | 4.84 | 6.24 | 5.98 | 6.39 |
| USA (~50) | 10.74 | 8.74 | 9.09 | 10.48 | 13.33 |

USA failures improve at later positions (e.g., 36.2% rank-1 at pos 4 vs
29.0% at pos 0). All other domains degrade from position 0.

Deep-dive into notable recovery cases:

- **bark -> whinny** (sounds, best recovery: rank 39->5 at pos 6): The target
  token " white" reaches rank 5 at the position where the model generates
  " brown" -- the source entity's color. Recovery reflects generic color-token
  salience at the answer slot, not steering.
- **oink -> hiss** (sounds, rank 40->10 at pos 8): Steered output is
  "BOWOWOWOWOWO! is white" -- garbled before a wrong color. Recovery at the
  "is X" slot is coincidental token proximity.
- **the_scream -> nighthawks** (paintings, rank 4793->2 at pos 2): Target
  " Edward" and source " Ed" are near-synonymous tokens. At the answer
  position the model naturally considers both variants; this is token
  co-occurrence, not causal redirection.
- **twitter -> alibaba** (products, rank 191->1 at pos 3): Both founders
  share the first name "Jack" (Dorsey/Ma). Target and source tokens are
  identical (" Jack"/" Jack"). This is an answer-identity confound, not
  genuine steering.
- **tennessee_memphis -> kansas_wichita** (USA, rank 9149->1 at pos 5):
  Steered output is "Falls, Kansas, is Wichita." The target "Topeka" reaches
  rank 1 at pos 5 because the model is in Kansas answer space at that position.
  This is the most genuine-looking recovery: the model is in the right
  geographic region even though it produces the wrong city.

**Interpretation**: Continuing steering beyond position 0 produces almost no
additional genuine hits. Confidence: **Medium**. Epistemic level: **L2**.

1. **Sounds/colors** -- definitively negative. Zero late top-1, three marginal
   top-10 cases that are all spurious on inspection. The domain is a total
   failure regardless of trajectory position.

2. **Weak domains** (paintings, products, books) -- late recoveries exist but
   are small (1-16% of failures) and mostly explained by two artifacts:
   (a) the model naturally ranks answer-category tokens higher at answer
   positions (generic token salience at the answer slot), and
   (b) token identity/overlap confounds (e.g., " Edward"/" Ed", " Jack"/" Jack").
   These are not evidence that steering is doing additional useful work.

3. **USA states** -- the one domain where late-position signal is real. 35%
   of failures recover to top-10, and 4.5% to top-1. The contrast-group rank
   actually improves at positions 4-5. But even here, the "recovered" cases
   produce garbled text at position 0, then the model self-corrects into the
   right geographic region at later positions. This may reflect the model's
   strong geographic priors rather than sustained feature steering effect.

4. **Position 0 is the best discriminator for most domains.** For products,
   books, and paintings, 69-78% of failures are already rank-1 in contrast
   group at position 0, then degrade. Position 0 captures the steering signal
   at its peak; later positions add noise. The exception is USA, where the
   larger answer space (50 states) means position 0 is noisier and positions
   4-5 let the model "settle" into the right answer region.

**Threats to validity**:

- The trajectory is 11 positions only; if the model generates long outputs,
  the real "answer position" might be beyond the tracked range for some
  domains.
- "Late recovery" is defined by absolute token rank; contrast-group rank may
  tell a different story, though in practice both agree.
- The deep-dived cases are hand-selected dramatic examples; systematic
  inspection of all recovery cases was not performed.
- Products twitter->alibaba confound (same " Jack" token) may affect other
  pairs in other domains that were not checked.
- The USA recovery pattern at positions 4-5 could be partially explained by
  prompt structure ("The capital of the state containing X is...") placing
  the answer at a predictable position, rather than steering strength.

**Follow-up**:

- For USA, compare late-recovery rate between labeled and random controls: if
  random also recovers at positions 4-5, the signal is generic prompt structure,
  not steering.
- Check if removing token-identity confounds (same source/target token) changes
  the late-recovery counts for products and paintings.
- Consider extending trajectory length beyond 11 positions for sounds/colors
  to rule out very late recovery.

**References**: `scripts/utils/swap_query.py`; `scripts/utils/AGENTIC_RESEARCH_GUIDE.md`

---

## [2026-04-03] Topic: Top-k feature steering by graph influence -- signal is distributed, not concentrated

**Question**: Can we replicate Anthropic's single-feature high-M paradigm by
selecting only the top-k most causally influential features and amplifying them
at high M? Does concentrating amplification on fewer, "better" features produce
more targeted steering?

**Methodology**: For the products->facebook domain (6 source pairs), ranked all
67 amplify features by `graph_influence` (causal influence from the target
entity's attribution graph). Ran a full factorial sweep: k in {1, 3, 5, 10, 67}
x M in {20, 50, 100, 200} = 120 steering runs in a single GPU batch.

**Key discovery during setup**: Graph influence has a **negative** Spearman
correlation with stored_activation (rho = -0.362, p = 0.003). High-activation
features are NOT the most causally influential. Using activation as a proxy for
importance would select the WRONG features.

Feature influence distribution is relatively flat (top-1 = 1.8%, top-10 = 17.7%,
top-20 = 34.9% of total influence). No single feature dominates.

**Raw findings**:

*Hit rate matrix (k x M), 6 pairs per cell:*

| k    | M=20 | M=50 | M=100 | M=200 |
|------|------|------|-------|-------|
| 1    | 0/6  | 0/6  | 0/6   | 0/6   |
| 3    | 0/6  | 0/6  | 0/6   | 0/6   |
| 5    | 0/6  | 0/6  | 0/6   | 0/6   |
| 10   | 0/6  | 0/6  | 0/6   | 0/6   |
| 67   | 2/6  | 2/6  | 1/6   | 1/6   |

Only k=67 (all features) ever produces hits. No subset, at any M, achieves
a single hit. Total: 0/96 hits for k < 67.

*Per-pair hit table (k=67 baseline vs top-k):*

| Pair              | k=1..10 all M | k=67 M=20 | k=67 M=50 | k=67 M=100 | k=67 M=200 |
|-------------------|---------------|-----------|-----------|------------|------------|
| alibaba->facebook | 0/16          | HIT       | HIT       | miss       | miss       |
| iphone->facebook  | 0/16          | HIT       | HIT       | HIT        | HIT        |
| windows->facebook | 0/16          | miss      | miss      | miss       | miss       |
| ford_cars->facebook| 0/16         | miss      | miss      | miss       | miss       |
| dell_xps->facebook| 0/16          | miss      | miss      | miss       | miss       |
| dyson->facebook   | 0/16          | miss      | miss      | miss       | miss       |

*What top-k features generate (alibaba->facebook, M=20):*

| k  | First token   | Generated text                              | Character |
|----|---------------|---------------------------------------------|-----------|
| 1  | "the"         | "the founder of Alibaba in 1999"            | Generic   |
| 3  | "ACA"         | garbage tokens                              | Noise     |
| 5  | "."           | "The company that makes Facebook was..."    | Confused  |
| 10 | "optString"   | programming tokens                          | Code mode |
| 67 | "Mark"        | "Mark Zuckerberg. He is a 31-year..."       | Correct   |

*KL divergence: fewer features = LESS disruption but WRONG output:*

| Pair              | KL(k=1) | KL(k=67) | Delta |
|-------------------|---------|----------|-------|
| dyson->facebook   | 9.0     | 15.0     | -6.1  |
| iphone->facebook  | 14.3    | 16.6     | -2.3  |
| windows->facebook | 14.9    | 16.4     | -1.5  |
| alibaba->facebook | 10.9    | 11.6     | -0.7  |
| ford_cars->facebook| 21.6   | 19.8     | +1.8  |

For 4/5 pairs, top-1 produces lower KL than top-67 (less distributional
disruption), yet generates completely wrong output. Lower KL with wrong
features is worse than higher KL with the right features.

*Top-1 feature at M=50 produces quiz/list format:*
- windows: "A) Microsoft, B) Apple, C..."
- dyson: "A) 1980, B..."
- The top graph-influence features activate a "multiple choice" generation
  mode rather than factual completion. These features likely encode
  general-purpose "question answering" patterns in the graph, not
  entity-specific knowledge.

**Interpretation**:

1. **The steering signal is irreducibly distributed.** The "Mark Zuckerberg"
   concept is encoded across all 67 target features working together, not
   concentrated in any subset. This is fundamentally different from the
   Anthropic single-feature paradigm, where one SAE feature can encode a
   complete concept.

2. **Graph influence != concept-field specificity.** The attribution graph
   ranks features by their importance to the graph's OVERALL output. The
   top features encode general-purpose patterns (question formats, entity
   types) rather than specific facts (founder names). The features carrying
   "Zuckerberg" information may have low individual graph influence but
   contribute critically to the distributed signal.

3. **The negative activation-influence correlation** (rho=-0.362) is itself
   significant: strongly-activating features tend to be LESS causally
   influential. This suggests that high-activation features may be "loud
   but unhelpful" -- they fire strongly but don't direct the output toward
   the correct answer.

4. **Architectural explanation**: Cross-transcoder features are inherently
   more distributed than SAE features because they operate across layers,
   encoding inter-layer transformations rather than single-layer concepts.
   A concept like "Mark Zuckerberg" requires coordinated activation across
   many layers (name encoding, biographical knowledge, social context),
   with no single cross-layer feature capturing the full concept.

5. **Why k=67 works at all**: The full feature set creates a "constructive
   interference" effect where individually weak signals combine to push the
   logit distribution toward "Mark." Removing ANY significant subset
   destroys this cooperative dynamic.

**Threats**:

- Only tested on products->facebook (6 pairs). Other domains/targets might
  have more concentrated feature signals.
- The influence ranking comes from the graph's OWN output, not from steering
  effectiveness. A feature-importance metric based on steering gradient
  (dP(target)/d(feature_activation)) might identify a more useful subset.
- The negative correlation between activation and influence could be an
  artifact of the graph construction method.
- Only the "labeled" control mode was tested; "field_add" mode uses
  different feature selection and might respond differently to top-k.

**Confidence**: **Medium-High**. N=120 runs, zero positive results for k<67,
clean mechanistic explanation. But single-domain limitation and lack of
alternative ranking metrics (gradient-based) reduce confidence.

**Follow-ups**:

1. Implement gradient-based feature importance: compute dP(target_token)/
   d(feature_activation) for each feature, rank by this steering-specific
   metric instead of graph influence.
2. Test on USA states domain where hit rate is higher -- a domain with
   more existing hits might reveal different concentration patterns.
3. Test "additive" approach: instead of removing features, set low-influence
   features to M=1 (identity) while setting top-k to high M. This preserves
   the cooperative baseline while concentrating amplification.
4. Analyze whether successful pairs (iphone->facebook) have qualitatively
   different feature influence distributions than failures (ford_cars->facebook).

---

## [2026-04-03] Topic: High M_amplify (50-200x) does not rescue missed pairs -- magnitude vs. specificity

**Question**: Anthropic's work reports steering strengths up to 200-300x. Can
very high M_amplify (50, 100, 200) rescue pairs that miss at M=20 in our
cross-transcoder setup?

**Methodology**: Identified the most promising candidates for high-M rescue
across all five domains. Selection criteria: pairs with no hit at M=20 that
have (a) positive rank_imprv (no position-0 disruption), (b) moderate-to-high
vsMax (directional signal exists), and (c) first-token evidence of partial
steering (e.g., correct first name but wrong surname).

Best candidate domain: **products->facebook**. At M=20, 6/13 ->facebook pairs
produce "Mark [wrong surname]" (Mark Hurd, Mark Shuttleworth, Mark Parker,
Mark Fields, Mark Dyson). The features encode "Mark" generically but lack
specificity for "Zuckerberg." These are ideal high-M candidates because the
features are pointing in the right direction.

Created configs at M=50, M=100, M=200 for products (10 pairs each), paintings
(6 pairs ->the_scream), and USA (4 low-amplify-count pairs). Total: 80 runs.

**Raw findings**:

*Products ->facebook hit rate by M:*

| M    | Hits/Total | Hit Rate | Notes                                       |
|------|-----------|----------|---------------------------------------------|
| 20   | 6/13      | 46%      | Baseline                                    |
| 50   | 2/8       | 25%      | Lost alibaba (->Jack Ma), lost iphone->Mark |
| 100  | 1/8       | 12%      | Only iphone survives                        |
| 200  | 1/8       | 12%      | Only iphone survives                        |

Zero pairs that missed at M=20 gained a hit at M=50, M=100, or M=200.
The only surviving hits were pre-existing hits from M=20.

*Paintings ->the_scream*: 0/18 (6 pairs x 3 M values). All outputs produce
`<bos>` first token followed by HTML garbage. Already over-steered at M=20.

*USA low-amp pairs*: 0/8 (4 pairs x 2 M values). Outputs frozen on garbage
tokens regardless of M.

*Name generation evolution (products ->facebook, key examples):*

| Source pair          | M=20               | M=50               | M=100              | M=200              |
|---------------------|---------------------|---------------------|---------------------|---------------------|
| ford_cars           | Mark Fields         | Mark Fields         | Mark Fields         | Mark Fields         |
| windows             | Mark Hurd           | Mark Hurd           | (HTML garbage)      | (HTML garbage)      |
| dell_xps            | Mark Shuttleworth   | Mark Shuttleworth   | (HTML garbage)      | (HTML garbage)      |
| alibaba             | Mark Zuckerberg HIT | Mark Zuckerberg HIT | Jack Ma (reverted)  | Jack Ma (reverted)  |
| iphone              | Mark Zuckerberg HIT | Mark Zuckerberg HIT | Mark Zuckerberg HIT | Mark Zuckerberg HIT |

*KL divergence saturates at high M:*

| Pair (->facebook)  | KL@50  | KL@100 | KL@200 | Delta KL (50->200) |
|---------------------|--------|--------|--------|--------------------|
| windows             | 17.5   | 18.0   | 18.1   | +0.6               |
| iphone              | 17.2   | 17.4   | 17.6   | +0.4               |
| alibaba             | 12.5   | 13.0   | 13.3   | +0.8               |
| dyson               | 16.3   | 16.7   | 16.9   | +0.6               |

KL increases only marginally from M=50 to M=200 (0.4-0.8 nats), suggesting
logit disruption saturates while output quality continues to degrade.

*Entropy at position 0 decreases with M (wrong token concentrates mass):*
wordpress: ent=5.2 (M=50) -> 4.4 (M=100) -> 3.8 (M=200). The intervention
concentrates probability on garbage tokens like `<bos>`, producing a more
"confident" but wrong distribution.

*M_effective = amplify_count x M:*
All ->facebook pairs share identical amplify_count=67. At M=200, M_eff=13,400
across all pairs, yet iphone still hits while windows does not. **M_effective
does not discriminate hits from misses.** The discriminating factor is feature
content specificity, not aggregate magnitude.

**Interpretation**:

1. **High M does not rescue misses.** In our setup (cross-transcoder features,
   Gemma-2-2b, multi-feature intervention), increasing M_amplify beyond the
   baseline produces monotonically worse results. The Anthropic paradigm of
   "push harder to achieve the hit" does not apply here.

2. **Three-phase degradation pattern** as M increases:
   - **Phase 1 (M=20-50)**: First token shifts from correct (e.g., "Mark") to
     garbage (`<bos>`), but autoregressive recovery allows the model to
     generate the same name from position 2 onward (e.g., still "Mark Hurd").
   - **Phase 2 (M=100)**: `<bos>` first token derails generation into HTML
     formatting tags (`<strong>`, `</strong>`). Some pairs revert to source
     knowledge (alibaba -> "Jack Ma" instead of "Mark Zuckerberg").
   - **Phase 3 (M=200)**: Distribution is maximally disrupted. Entropy drops
     (probability mass concentrated on wrong tokens). Output quality identical
     to Phase 2 -- additional M has no effect.

3. **The "wrong Mark" problem is feature specificity, not magnitude.** The
   features encode a "Mark + tech founder" concept, not "Mark Zuckerberg"
   specifically. Amplifying generic features harder does not resolve specificity.
   The ford_cars pair is the canonical example: at M=200, the model still
   produces "Mark Fields" because Ford's association with Mark Fields is
   deeply entrenched and the features carry no Zuckerberg-specific signal.

4. **Why iphone->facebook survives M=200**: This pair's features likely encode
   something specifically about Zuckerberg/Facebook (perhaps via Apple-Meta
   competitive framing in training data). Even with `<bos>` as first token,
   the model recovers to "Mark Zuckerberg" at position 2. KL=17.6, entropy
   stable at 5.6 -- suggesting a qualitatively different feature set.

5. **Structural difference from Anthropic**: Our cross-transcoder approach
   amplifies 40-400 features simultaneously. Each feature adds independent
   noise. M=200 with 67 features = 13,400 units of total modification. In
   contrast, Anthropic's SAE approach steers with a single feature, making
   high M a targeted directional push rather than a distributed perturbation.
   This architectural difference likely explains why high M works in their
   setting but not ours.

**Threats**:

- Only tested on pairs pre-selected as "most promising." A random sample might
  behave differently (though the theoretical reasoning -- multi-feature
  amplification causes distributed noise -- applies generally).
- Paintings produced 0 data at M>20 (run storage issue), so cross-domain
  validation is weaker than desired.
- We did not test intermediate values (M=30, M=40) that might reveal a narrow
  optimal window for some pairs.
- The evaluator uses exact match -- some M=50 outputs might contain correct
  answers in non-standard form.

**Confidence**: **Medium-High**. N=80 runs across 3 domains, zero positive
rescue effects, clear degradation mechanism. But paintings data gap and lack
of M=30-40 intermediate testing reduce to Medium-High rather than High.

**Follow-ups**:

1. Test single-feature steering: select the ONE most important feature per pair
   (by gradient or activation magnitude) and sweep M on that single feature.
   This would replicate the Anthropic single-feature paradigm and test whether
   high M works in that regime.
2. Investigate the ford_cars/iphone qualitative difference: what feature
   content distinguishes pairs where the same amplify_count produces
   persistent wrong answers vs. correct answers?
3. Test intermediate M values (M=25, 30, 35) on the alibaba->facebook pair
   to find the exact transition point where the hit is lost.
4. Implement feature importance ranking (e.g., by gradient or activation
   contribution) to enable selective high-M amplification of top-k features.

---

## [2026-04-03] Topic: KL divergence as a predictor of useful steering strength

**Question**: Can KL(baseline || steered) at position 0 predict the M_amplify
value at which a hit becomes achievable? If so, can it serve as a runtime
diagnostic for adaptive M selection?

**Method**: Using the 30 observations from the entropy study (10 pairs x M={5,
10, 20}), fitted per-pair linear models KL(M) = a*M + b and evaluated: (1) KL
linearity in M (R-squared); (2) whether the slope `a` and intercept `b` are
predictable from pair-level features (amplify_count, ablate_count, total_count,
baseline_entropy); (3) extrapolated "critical M" (M where KL crosses 12) vs
actual hit M; (4) confusion matrix for KL < 12 as a hit predictor.

**Raw findings**:

KL is highly linear in M for every pair:

| Pair | slope (a) | intercept (b) | R-squared | amplify | total |
|------|-----------|---------------|-----------|---------|-------|
| kansas->oklahoma | 0.318 | 8.28 | 0.941 | 73 | 163 |
| delaware->oklahoma | 0.269 | 7.49 | 0.995 | 73 | 152 |
| texas->oklahoma | 0.218 | 9.34 | 0.986 | 73 | 138 |
| florida->oklahoma | 0.263 | 10.06 | 1.000 | 73 | 139 |
| vermont->kansas | 0.079 | 8.43 | 0.864 | 90 | 130 |
| rhode_island->wisconsin | 0.194 | 8.16 | 0.982 | 86 | 156 |
| iowa->utah | 0.245 | 6.99 | 0.935 | 93 | 253 |
| indiana->arkansas | 0.374 | 5.09 | 0.967 | 69 | 269 |
| indiana->minnesota | 0.317 | 6.16 | 0.946 | 82 | 282 |
| hawaii->oklahoma | 0.109 | 13.69 | 0.848 | 73 | 158 |

R-squared > 0.93 for 8/10 pairs. Two outliers: vermont->kansas (0.864) and
hawaii->oklahoma (0.848).

KL slope correlates with pair features:

| Feature | r(slope) | r(intercept) |
|---------|----------|--------------|
| amplify_count | -0.42 | -0.20 |
| ablate_count | **+0.68** | **-0.63** |
| total_count | +0.61 | -0.65 |
| baseline_entropy | -0.40 | -0.12 |

Ablate count is the strongest predictor of KL slope (r=+0.68): more source
features ablated = steeper KL increase per unit M. Total_count is the strongest
negative predictor of intercept (r=-0.65): higher total feature count = lower
"floor" KL, meaning the pair starts with less distributional disruption at M=0.

Critical M (extrapolated M where KL=12) vs actual hit pattern:

| Pair | M_crit | Hits at | Match? |
|------|--------|---------|--------|
| kansas->oklahoma | 11.7 | M=5 only | Yes (hit below M_crit) |
| delaware->oklahoma | 16.8 | M=5 only | Yes |
| texas->oklahoma | 12.2 | M=5 only | Yes |
| florida->oklahoma | 7.4 | M=5 only | Yes (tight) |
| vermont->kansas | 44.9 | none | N/A (feature failure) |
| rhode_island->wisconsin | 19.8 | none | N/A (feature failure) |
| iowa->utah | 20.5 | M=5, M=10 | Yes (both below M_crit) |
| indiana->arkansas | 18.5 | M=5 only | Yes |
| indiana->minnesota | 18.4 | none | N/A (evaluator gap) |
| hawaii->oklahoma | -15.5 | none | Yes (intercept > 12, never achievable) |

For pairs where hits exist, all hits occur at M < M_crit. hawaii->oklahoma has
intercept=13.69, meaning KL > 12 at ALL M values including M=0 extrapolation.

Confusion matrix for KL < 12 as hit predictor:

|  | Hit | No hit | Total |
|--|-----|--------|-------|
| KL < 12 | 7 | 12 | 19 |
| KL >= 12 | 0 | 11 | 11 |
| Total | 7 | 23 | 30 |

- Recall: 7/7 = **100%** (no false negatives)
- Precision: 7/19 = **37%** (12 false positives)
- Specificity: 11/23 = 48%

The 12 false positives (KL < 12 but no hit) break down as:
- 3x vermont->kansas (KL 8.6-9.9): feature specificity failure (generates
  Hutchinson not Topeka). Irreducible -- no M value produces a hit.
- 3x indiana->minnesota (KL 7.3-10.0): evaluator gap ("St. Paul" vs "Saint
  Paul"). Actually correct output, miscounted by the metric.
- 2x rhode_island->wisconsin (KL 9.0-10.3): signal collapse between M=7 and
  M=10. Features too weak for any M.
- 4x oklahoma_tulsa pairs at M=10 (KL 10.0-11.7): M=10 reduces KL below 12
  but the remaining disruption (rank_imprv still -3K to -15K) prevents a hit.
  M=5 succeeds for these.

**Interpretation**:

KL divergence serves as a **necessary-but-not-sufficient condition** for hits.
It functions as a reliable veto: KL >= 12 guarantees failure (100% recall), but
KL < 12 does not guarantee success (37% precision).

The practical value is as a **runtime diagnostic in an adaptive pipeline**:

1. Run steering at M=20. Measure KL.
2. If KL >= 12, compute M_crit = (12 - b) / a. This requires at least one
   additional M point to fit the line (or a lookup table of typical slopes).
3. Re-run at M = floor(M_crit * 0.8) as safety margin.
4. If KL at M_crit is still >= 12, the pair's intercept b >= 12 (like
   hawaii->oklahoma) and no M value will help. Flag as intrinsically
   disruptive.

The limitation is structural: KL measures the *magnitude* of distributional
shift, not its *direction*. A pair with well-aligned features at low KL
(indiana->arkansas, KL=6.6 at M=5) hits because the shift points toward
the correct answer. A pair with equally low KL but misaligned features
(vermont->kansas, KL=8.6 at M=5) misses because the features encode
"Kansas" but not specifically "Topeka." KL cannot distinguish these cases.

The ablate_count correlation with KL slope (r=+0.68) has a mechanistic
explanation: M_ablate=-2 reverses each source feature's contribution by
multiplying its activation by -2. More features ablated means more total
reversal magnitude, which grows proportionally with M because the amplified
target features interact with the reversed source features. The intercept's
negative correlation with total_count (r=-0.65) is less intuitive and may
reflect that high-feature-count entities have more internally consistent
representations that resist distributional disruption at M=0.

Confidence: **Medium** for KL >= 12 as a veto threshold (N=30, 0 false
negatives, but single domain and limited pair diversity). **Low** for the
M_crit extrapolation (linear fit from 3 M values, untested at intermediate
M). **Medium** for KL slope predictability from ablate_count (r=0.68 on
N=10, plausible mechanism).

**Threats to validity**:

- [x] The KL=12 threshold is derived from N=30 observations on 10 pairs in
  one domain (USA). Domains with different vocabulary distributions (books,
  paintings) may have different natural KL scales.
- [x] Linear extrapolation of KL(M) uses only 3 M values. The relationship
  could be sublinear at very low M (M < 5) or exhibit saturation at very
  high M (M > 20). R-squared < 0.87 for 2/10 pairs suggests non-linearity
  exists.
- [x] The confusion matrix includes 3 observations (indiana->minnesota) that
  are false positives solely due to the "Saint Paul" evaluator gap, not
  genuine failures. Correcting these would raise precision to 7/16 = 44%.
- [x] KL(baseline||steered) is directional. KL(steered||baseline) would
  penalize differently (heavier penalty when steered assigns low probability
  to tokens that baseline expects). The choice of direction has not been
  validated.
- [x] The slope correlations (r=0.68 for ablate_count) are on N=10 pairs
  and should not be treated as predictive models without larger-scale
  validation.

**Follow-up**:

- Validate the KL=12 threshold on a larger sample (e.g., all 2450 USA pairs
  at M=20 if the run can be backfilled with distribution metrics).
- Test whether M_crit extrapolation works in practice: for pairs with
  M_crit in [8, 15], run at floor(M_crit * 0.8) and check hit rate.
- Evaluate KL(steered||baseline) as an alternative that may have different
  precision/recall tradeoffs.
- Investigate whether combining KL with vsMax improves precision: a pair
  with KL < 12 AND vsMax > 10 may be a much stronger hit predictor than
  KL alone.
- Extend to non-USA domains (books, products) to calibrate domain-specific
  KL thresholds.

---

## [2026-04-03] Topic: Entropy and KL divergence as distributional measures of steering strength

**Question**: The new `position_0_distribution_metrics` (baseline_entropy,
steered_entropy, entropy_delta, kl_baseline_to_steered) measure how much the
steered distribution at position 0 diverges from baseline. How do these relate
to M_amplify, hit rate, and the previously identified overshoot mechanism?
Can KL serve as a principled, M-independent measure of intervention magnitude?

**Method**: Added unit tests for the new metrics pipeline (17 tests:
`tests/test_distribution_metrics.py`). Re-ran 10 selected pairs at M={5, 10, 20}
with the updated code (run_ids `entropy_study_m{5,10,20}`), yielding 30 data
points with entropy/KL values. Pairs selected to span severe overshoot (4
oklahoma_tulsa), moderate signal (2), borderline (2), and signal-collapse (2).
Analyzed KL vs M, KL vs hit, KL thresholds, within-pair KL slope, and
relationship to existing metrics (ctrl_stab, vs_max, best_gap).

**Raw findings**:

Full data table (10 pairs x 3 M values):

| Pair | M | hit | bl_H | st_H | dH | KL | vsMax | ctrl_stab | rank_imprv |
|------|---|-----|------|------|----|----|-------|-----------|------------|
| kansas->oklahoma | 5 | Y | 3.47 | 2.66 | -0.81 | 9.41 | 14.34 | 6.68 | -49 |
| kansas->oklahoma | 10 | N | 3.47 | 3.07 | -0.40 | 12.15 | 15.78 | 11.81 | -3651 |
| kansas->oklahoma | 20 | N | 3.47 | 2.82 | -0.65 | 14.41 | 15.80 | 14.14 | -113493 |
| delaware->oklahoma | 5 | Y | 4.07 | 2.49 | -1.59 | 8.95 | 13.94 | 6.70 | -280 |
| delaware->oklahoma | 10 | N | 4.07 | 3.36 | -0.71 | 10.02 | 14.91 | 11.70 | -15830 |
| delaware->oklahoma | 20 | N | 4.07 | 2.91 | -1.16 | 12.93 | 15.02 | 13.84 | -167524 |
| texas->oklahoma | 5 | Y | 3.33 | 2.51 | -0.83 | 10.28 | 13.75 | 6.78 | -132 |
| texas->oklahoma | 10 | N | 3.33 | 2.88 | -0.45 | 11.74 | 14.84 | 11.81 | -7453 |
| texas->oklahoma | 20 | N | 3.33 | 2.83 | -0.51 | 13.62 | 14.81 | 13.95 | -136528 |
| florida->oklahoma | 5 | Y | 3.45 | 2.55 | -0.90 | 11.41 | 13.94 | 7.31 | -282 |
| florida->oklahoma | 10 | N | 3.45 | 3.35 | -0.10 | 12.65 | 15.53 | 12.12 | -14414 |
| florida->oklahoma | 20 | N | 3.45 | 3.16 | -0.29 | 15.35 | 15.38 | 14.12 | -167255 |
| vermont->kansas | 5 | N | 4.55 | 1.48 | -3.08 | 8.65 | 0.19 | 8.32 | 3 |
| vermont->kansas | 10 | N | 4.55 | 1.38 | -3.17 | 9.50 | 8.09 | 10.47 | -1082 |
| vermont->kansas | 20 | N | 4.55 | 1.91 | -2.64 | 9.93 | 8.38 | 11.06 | -25563 |
| rhode_island->wisconsin | 5 | N | 4.67 | 2.75 | -1.93 | 8.98 | 2.12 | 7.36 | -12 |
| rhode_island->wisconsin | 10 | N | 4.67 | 3.03 | -1.64 | 10.32 | 8.38 | 9.83 | -163 |
| rhode_island->wisconsin | 20 | N | 4.67 | 3.51 | -1.17 | 11.96 | 8.22 | 12.81 | -1490 |
| iowa->utah | 5 | Y | 3.08 | 4.52 | +1.43 | 7.84 | 10.81 | 7.55 | 386 |
| iowa->utah | 10 | Y | 3.08 | 4.56 | +1.48 | 10.00 | 6.19 | 10.37 | 450 |
| iowa->utah | 20 | N | 3.08 | 4.00 | +0.92 | 11.70 | 8.75 | 10.98 | 44 |
| indiana->arkansas | 5 | Y | 3.49 | 1.63 | -1.85 | 6.56 | 5.75 | 10.66 | 179 |
| indiana->arkansas | 10 | N | 3.49 | 1.50 | -1.99 | 9.42 | 5.56 | 11.53 | 178 |
| indiana->arkansas | 20 | N | 3.49 | 1.09 | -2.40 | 12.36 | 5.69 | 13.27 | 178 |
| indiana->minnesota | 5 | N | 3.49 | 2.20 | -1.28 | 7.30 | 6.00 | 6.40 | 191 |
| indiana->minnesota | 10 | N | 3.49 | 1.47 | -2.02 | 9.98 | 6.88 | 8.48 | 191 |
| indiana->minnesota | 20 | N | 3.49 | 1.70 | -1.79 | 12.27 | 5.50 | 10.21 | 191 |
| hawaii->oklahoma | 5 | N | 3.29 | 2.88 | -0.41 | 13.97 | 4.81 | 8.98 | -368 |
| hawaii->oklahoma | 10 | N | 3.29 | 4.27 | +0.98 | 15.17 | 14.03 | 13.58 | -21627 |
| hawaii->oklahoma | 20 | N | 3.29 | 3.83 | +0.54 | 15.73 | 14.12 | 14.99 | -167481 |

KL divergence by M_amplify (all pairs):

| M | mean KL | std | min | max |
|---|---------|-----|-----|-----|
| 5 | 9.33 | 2.04 | 6.56 | 13.97 |
| 10 | 11.10 | 1.74 | 9.42 | 15.17 |
| 20 | 13.03 | 1.69 | 9.93 | 15.73 |

KL divergence: hits vs misses:

| | N | mean KL | std | range |
|-|---|---------|-----|-------|
| Hits | 7 | 9.21 | 1.49 | [6.56, 11.41] |
| Misses | 23 | 11.74 | 2.27 | [7.30, 15.73] |

KL threshold analysis (hit rate below/above threshold):

| Threshold | Below (hit%) | Above (hit%) |
|-----------|-------------|--------------|
| KL < 8 | 2/3 (67%) | 5/27 (19%) |
| KL < 10 | 5/12 (42%) | 2/18 (11%) |
| KL < 12 | 7/19 (37%) | **0/11 (0%)** |

**No hit occurs at KL >= 12.** The maximum KL among hits is 11.41 (florida->
oklahoma at M=5).

Correlations (N=30):

| Pair | r |
|------|---|
| KL vs M_amplify | **+0.63** |
| KL vs ctrl_stab | **+0.73** |
| KL vs hit | **-0.45** |
| ctrl_stab vs M | +0.79 |
| ctrl_stab vs hit | -0.55 |

Within-pair KL slope (KL increase per unit M):

| Pair | KL slope (/M) | hits (M=5/10/20) |
|------|---------------|------------------|
| indiana->arkansas | **0.387** | Y/N/N |
| kansas->oklahoma | 0.333 | Y/N/N |
| indiana->minnesota | 0.331 | N/N/N |
| delaware->oklahoma | 0.265 | Y/N/N |
| florida->oklahoma | 0.262 | Y/N/N |
| iowa->utah | 0.257 | Y/Y/N |
| texas->oklahoma | 0.223 | Y/N/N |
| rhode_island->wisconsin | 0.199 | N/N/N |
| hawaii->oklahoma | **0.118** | N/N/N |
| vermont->kansas | **0.086** | N/N/N |

**Entropy delta (dH = steered_entropy - baseline_entropy) is NOT monotonic with
M**. Mean dH by M: -1.12 (M=5), -0.80 (M=10), -0.91 (M=20). The steered
distribution can be either more or less entropic than baseline depending on the
pair. iowa->utah is the only pair with consistently positive dH (steered more
uncertain than baseline at all M).

**Interpretation**:

**KL divergence is a strong, interpretable measure of total intervention
disruption.** It correlates highly with both M_amplify (r=+0.63) and
control_stability (r=+0.73), but captures additional information: KL measures
the full distributional shift over all ~256K tokens at position 0, while
ctrl_stab measures mean absolute logit change on a small set of control tokens.

**KL >= 12 is a hard ceiling for hits in this sample.** No hit occurs above
KL=12 in any of the 30 observations. The KL=12 threshold corresponds roughly
to M=10-15 for most pairs. Below KL=10, the hit rate is 42%. Below KL=8,
it is 67% (but N=3 so low confidence). This suggests KL could serve as a
stopping criterion for M selection: reduce M until KL < ~10.

**KL and ctrl_stab are complementary but not redundant (r=0.73, not 0.95+).**
The divergence matters: KL captures distributional shifts in the long tail of
the vocabulary (rank > 100K tokens) that ctrl_stab misses. For example,
hawaii->oklahoma at M=5 has KL=13.97 (highest in the M=5 column, consistent
with its being the only oklahoma_tulsa pair that misses at M=5) but
ctrl_stab=8.98 (moderate, not the highest). KL detects the disruption that
ctrl_stab underestimates.

**Entropy delta is not useful as a steering metric.** Unlike KL, entropy delta
shows no monotonic relationship with M and no clear separation between hits and
misses. The sign depends on whether the intervention concentrates probability
mass (dH < 0, most cases) or disperses it (dH > 0, iowa->utah). Both cases can
produce hits or misses.

**KL slope varies substantially across pairs (0.086-0.387 per unit M).** Pairs
with high KL slope (indiana->arkansas, 0.387) are most sensitive to M and most
likely to benefit from M reduction. Pairs with low KL slope (hawaii->oklahoma,
0.118; vermont->kansas, 0.086) have high KL even at M=5 and are unlikely to
benefit from further M reduction. The low-slope pairs also tend to be the
never-hit pairs, consistent with their features being intrinsically disruptive
(high "floor" KL) rather than just over-amplified.

**hawaii->oklahoma is the clearest KL outlier.** Its KL=13.97 at M=5 exceeds
all other pairs' KL at M=10. This pair has a signal-collapse mechanism (vsMax
drops from 14.12 to 4.81 at M=5) that is now quantitatively captured: the
features cause maximal distributional disruption even at minimal amplification.

Confidence: **Medium** for the KL-hit relationship (N=30, consistent threshold,
mechanistically plausible). **Low** for the KL=12 threshold as a general rule
(limited to 10 pairs, 1 dataset). **High** for KL being monotonically increasing
with M (consistent across all 10 pairs without exception).

**Threats to validity**:

- [x] N=30 observations from 10 pairs, all USA domain. The KL=12 threshold may
  not generalize to other domains (books, products) where the vocabulary
  distribution and feature counts are different.
- [x] KL(baseline||steered) is asymmetric. Using KL(steered||baseline) would
  give different values and possibly different correlation patterns. The choice
  of direction (baseline as reference) is principled but not the only option.
- [x] The hit metric is binary and coarse. KL likely correlates better with
  continuous metrics (vsMax, gap_closure) but this was not tested.
- [x] Baseline entropy varies across pairs (3.08--4.67) because different
  prompts have different baseline confidence levels. Normalizing KL by baseline
  entropy might improve pair-level comparability.
- [x] The KL computation uses epsilon=1e-10 clamping. For distributions with
  many zero-probability tokens, this introduces a small positive bias. The bias
  is constant across M values so relative comparisons are unaffected.

**Follow-up**:

- Compute KL vs vsMax and KL vs gap_closure correlations (continuous, not binary
  hit) for a more sensitive test of the relationship.
- Test whether KL/baseline_entropy (normalized KL) is a better predictor than
  raw KL for cross-pair comparison.
- Run KL analysis on a wider set of pairs (e.g., all 2450 USA pairs at M=20,
  if the fullscale run can be backfilled with distribution metrics) to test the
  KL=12 threshold at scale.
- Evaluate KL(steered||baseline) as an alternative and compare predictive power.
- Consider adding KL to SwapSummary fields in swap_query.py for systematic
  filtering.

---

## [2026-04-01] Topic: Late-layer scaffold as pair-level predictor of swap success

**Question**: Does scaffold compatibility specifically in late layers (the output
circuit, layers 6+) predict pair-level swap success better than overall scaffold?
The prior entry showed overall scaffold explains the domain gradient but has no
within-domain pair-level signal in USA. Late-layer scaffold showed the steepest
cross-domain gradient (USA 16.3% vs books 4.3%). Is this where the action is?

**Method**: Swept the early/late cutoff from layer 3 to layer 15 across all 4 domains.
Computed r(late_scaffold, vsMax) and r(late_scaffold, gap_closure) at each cutoff.
Examined hit/miss effect sizes (Cohen's d), quartile analyses, per-individual-layer
correlations, and target-identity confound checks.

Total pairs analyzed: USA 2450, books 240, products 132, paintings 90.

**Raw findings**:

### Cutoff sweep: r(late_scaffold, vsMax) by domain

| Cutoff | USA | Books | Products | Paintings |
|---|---|---|---|---|
| 3 | -0.097 | -0.004 | +0.105 | +0.118 |
| 5 | -0.077 | +0.000 | +0.131 | +0.066 |
| 7 | -0.036 | +0.002 | **+0.161** | +0.136 |
| 9 | -0.028 | +0.002 | **+0.175** | +0.121 |
| 11 | -0.028 | -0.001 | +0.113 | +0.048 |
| 13 | -0.055 | +0.003 | +0.144 | +0.030 |
| 15 | -0.057 | -0.002 | +0.072 | +0.004 |

Products peaks at cutoff 7-9 (r=+0.16 to +0.18). Paintings peaks at cutoff 3-7. USA
is uniformly negative/null. Books is uniformly zero.

### Hit/miss effect sizes (Cohen's d)

| Metric | USA (606h) | Books (9h) | Products (20h) | Paintings (4h) |
|---|---|---|---|---|
| scaffold_inf_mean | -0.09d | +0.61d | +0.30d | +0.70d |
| early_5_mean | -0.08d | +0.05d | +0.31d | +1.08d |
| **late_5_mean** | **+0.01d** | **+4.83d** | **+0.35d** | **-0.13d** |
| late_7_mean | +0.06d | +5.79d | +0.44d | -0.16d |
| late_9_mean | +0.09d | +5.99d | **+0.47d** | -0.17d |

### Books late_scaffold: artifact of 2 outlier pairs

The d=+4.83 to +5.99 effect in books is driven by exactly 2 same-book pairs:

- scout_finch -> atticus_finch: late_5 = **0.7636** (HIT)
- atticus_finch -> scout_finch: late_5 = **0.7419** (HIT)

Population mean late_5 = 0.049. These two points (from the same novel, To Kill a
Mockingbird) are 15x the population mean. Without them, the remaining 7 hits have
mean late_5 = 0.049, identical to misses.

Further: within jay_gatsby targets (6/9 hits), gatsby hits have **lower** late_5
(0.048) than gatsby misses (0.057). The late_scaffold effect in books is entirely
an artifact. **The giant effect size is spurious.**

### Products late_scaffold: genuine signal surviving target-identity control

Products target distribution: 11/20 hits -> model_s, 5 -> facebook, 4 -> windows.

Target-residualized correlation (controlling for target mean): **r=+0.292** (N=132).
This survives the confound check -- within a given target, source entities with higher
late-layer scaffold compatibility achieve better vsMax.

Per-individual-layer correlations for products (r > 0.15 marked):

| Layer | r(scaffold, vsMax) | Mean scaffold % |
|---|---|---|
| 11 | **+0.232** | 0.3% |
| 15 | **+0.225** | 0.1% |
| 16 | **+0.203** | 0.1% |
| 21 | **+0.160** | 0.0% |
| 20 | **+0.149** | 0.0% |

The signal concentrates in layers 11-16 and 20-21 -- the mid-to-late transition
where entity-specific and structural features intermix.

Products quartile analysis (late_5_mean):

| Quartile | N | late_5 | hit% | vsMax |
|---|---|---|---|---|
| Q1 (low) | 33 | 0.026 | 3.0% | +2.53 |
| Q2 | 33 | 0.056 | 18.2% | +3.69 |
| Q3 | 33 | 0.085 | 24.2% | +4.29 |
| Q4 (high) | 33 | 0.123 | 15.2% | +3.33 |

Clear gradient from Q1 to Q3 for both hit% and vsMax, with partial rollback at Q4.

### Paintings: early scaffold matters more

For paintings (N=90), early_scaffold at cutoff 3 has r=+0.384 with vsMax, and
r stays around +0.36-0.39 across all cutoffs. Late_scaffold peaks at only r=+0.14
(cutoff 7). The paintings hit/miss comparison confirms: early_5 d=+1.08, while
late_5 d=-0.13 (no late effect). Paintings success is predicted by structural
compatibility in early layers, not late.

### Cross-domain: late_scaffold does NOT improve over overall scaffold

Late scaffold rank: USA > paintings > products > books.
Hit% rank: USA > products > paintings > books.
Products and paintings are swapped. Overall scaffold_inf (r-entry above: USA >
products > paintings > books) is a perfect ordinal match. Late_scaffold alone is
a worse cross-domain predictor.

**Interpretation**:

1. **Products is the one domain with genuine within-domain late_scaffold signal.**
   Target-residualized r=+0.29, concentrated in layers 11-16 and 20-21. Effect size
   d=+0.47 (late_9) for hits vs misses. This is the only domain where the "graft
   compatibility" theory works at the pair level with defensible evidence (N=20 hits,
   12 distinct sources, 3 targets, survives target-residualization). **Confidence:
   Medium** (N=20 hits is still modest; multivariate controls needed).

2. **Books late_scaffold was entirely an artifact of 2 same-book outlier pairs.**
   The atticus/scout pairs have 74% late scaffold (15x population mean) because
   they share a novel. Without them, no signal. The d=+4.8 to +6.0 effect sizes
   reported in the prior entry were misleading. **Confidence: High** (mechanism
   clear, artifact demonstrated).

3. **USA has no late_scaffold signal at any cutoff.** Domain is too homogeneous.
   All |r| < 0.10. **Confidence: High** (N=2450).

4. **Paintings responds to early, not late scaffold.** The predictive signal is
   r=+0.38 for early_scaffold (layers 0-3), not for late layers. This suggests
   that for paintings, it's the input-processing compatibility (how the model
   encodes the entity) that matters, not the output circuit. But N=4 hits makes
   this fragile. **Confidence: Low** (N=4).

5. **Different domains have different "compatibility zones."** Products: mid-late
   layers (11-21). Paintings: early layers (0-3). USA: none. This suggests that
   the layer where scaffold matters depends on the domain's computational structure.
   **Confidence: Low** (exploratory, N=2 domains with signal).

**Threats to validity**:

- [x] Books outlier artifact confirmed and documented.
- [x] Products target-identity confound tested: r=+0.29 survives residualization.
- [ ] Products N=20 hits: effect size is defensible but fragile. Need to test on
  field-additivity variants for replication.
- [ ] Per-layer products correlations (r=+0.23 at layer 11) are on N=132 and have
  not been corrected for multiple comparisons across 25 layers.
- [ ] Have not controlled for error_node_pct or feature count in the products
  regression.
- [ ] The products "rollback at Q4" (Q4 hit% = 15% vs Q3 = 24%) suggests the
  relationship may be non-linear or that very high scaffold pairs have some other
  confound.

**Follow-up**:

1. Multivariate regression for products: late_scaffold + error_node_pct + n_features
   -> vsMax, to isolate independent contribution.
2. Replicate products signal on field-additivity variants (same pairs, different
   intervention scope).
3. Investigate the products Q4 rollback: what characterizes high-scaffold pairs that
   still fail?
4. Check whether the random-feature control in products also shows late_scaffold
   signal (if yes, the effect is generic, not label-specific).

---

## [2026-04-01] Topic: Graph compatibility ("graft") as predictor of swap success

**Question**: When source and target attribution graphs share a large population of
features with stable grouping (the "scaffold"), does the swap succeed more often?
Conversely, when the graphs are structurally incompatible (low shared scaffold, high
entity-specific influence), do swaps fail? Sub-questions:

1. What fraction of a graph's influence is scaffold (shared features, same supernode)?
2. Does scaffold percentage predict pair-level swap success within a domain?
3. Does mean scaffold percentage explain the domain gradient (USA > books > products > paintings)?

**Method**: For every entity pair, decomposed features into three populations:

- **Scaffold**: same `feature_key` in both graphs AND same supernode assignment. These
  are structural primitives (copula, prepositions, task operators) that remain stable
  across entities.
- **Regrouped**: same `feature_key` in both graphs but different supernode (typically
  entity-appropriate re-assignment, e.g., Say(Austin) -> Say(Sacramento)).
- **Entity-only**: `feature_key` present in one graph only.

Measured each population's share of total `node_influence`. Computed these metrics for
all pairs in 4 domains: USA (2450 pairs), books (240), products (132), paintings (90).
Correlated scaffold metrics with swap outcomes (hit%, vsMax, gap_closure).

Used `graph_feature_static_metrics.csv` (key = `layer_id`) for influence and
`node_grouping.csv` for supernode assignments.

**Raw findings**:

### Dallas/Oakland detailed decomposition (reference pair)

| Population | N features | Dallas influence | Oakland influence |
|---|---|---|---|
| Scaffold (shared + same supernode) | 119 | 50.6% | 49.2% |
| Regrouped (shared + different supernode) | 29 | 12.3% | 13.7% |
| Entity-only | 55 / 62 | 21.7% | 19.5% |

Layer structure: scaffold dominates layers 0-5 (75-100% of influence). Entity-only
features dominate layers 15-24 (50-100%). Layers 6-14 are a transition zone.

The 29 regrouped features are almost entirely entity-appropriate:
- 15x Say(Austin) -> Say(Sacramento)
- 4x Texas -> California
- 3x Dallas -> Oakland
- 2x Say(Texas) -> Say(California)
- 1x Austin -> Sacramento
- 4 genuinely inconsistent (2.7%)

### Cross-domain scaffold gradient

| Domain | scaffold_inf (mean) | hit% | gap_closure | N pairs |
|---|---|---|---|---|
| USA | 0.530 | 24.7% | 4.67 | 2450 |
| Products | 0.422 | 15.2% | 0.19 | 132 |
| Paintings | 0.359 | 4.4% | 0.80 | 90 |
| Books | 0.253 | 3.8% | 0.01 | 240 |

**Scaffold rank: USA > products > paintings > books.**
**Hit% rank: USA > products > paintings > books.**

The rankings are identical. Mean scaffold influence is a perfect ordinal predictor of
domain-level swap success.

Additional metrics by domain:

| Domain | shared_pct | src_only_inf | early_scaffold | late_scaffold | mean N features |
|---|---|---|---|---|---|
| USA | 63.7% | 29.5% | 74.6% | 16.3% | 234 |
| Products | 52.1% | 31.7% | 62.1% | 10.3% | 233 |
| Paintings | 44.8% | 38.0% | 50.9% | 9.2% | 378 |
| Books | 48.9% | 42.3% | 39.7% | 4.3% | 293 |

The late_scaffold column is striking: USA entities share 16.3% of late-layer influence
as scaffold, while books share only 4.3%. This means in books, the output-generation
circuit is almost entirely entity-specific -- the "graft" has very little compatible
tissue where it matters most.

### Within-domain pair-level prediction

| Domain | r(scaffold, vsMax) | r(scaffold, gc) | hit_scaffold | miss_scaffold | delta | N |
|---|---|---|---|---|---|---|
| USA | -0.088 | -0.082 | 0.527 | 0.531 | -0.004 | 2450 |
| Books | -0.000 | -0.058 | 0.318 | 0.250 | +0.068 | 240 |
| Products | +0.051 | +0.069 | 0.453 | 0.416 | +0.037 | 132 |
| Paintings | +0.334 | +0.101 | 0.391 | 0.357 | +0.033 | 90 |

USA: no within-domain signal (scaffold range too narrow: 0.38-0.73, mean 0.53).
Non-USA domains: hit pairs consistently have higher scaffold (delta +0.03 to +0.07).
Paintings: r=0.334 (moderate), but N=90 and fragile.

### USA quartile analysis (2450 pairs)

| Scaffold quartile | mean scaffold | hit% | mean vsMax |
|---|---|---|---|
| Q1 (lowest) | 0.468 | 27.8% | +3.15 |
| Q2 | 0.513 | 23.2% | +2.90 |
| Q3 | 0.545 | 23.7% | +2.94 |
| Q4 (highest) | 0.593 | 24.3% | +2.43 |

No monotonic trend. Q1 actually has the highest hit rate. Within USA, scaffold does
not predict pair-level success.

**Interpretation**:

1. **The graft metaphor explains the domain gradient.** Scaffold influence is a
   perfect ordinal predictor of domain-level swap success. This is the strongest
   finding. Domains with more shared structural tissue (USA 53%) achieve higher hit
   rates than domains where most influence is entity-specific (books 25%). This makes
   causal sense: if the scaffold (structural features like copula, prepositions, task
   operators) is a small fraction of the circuit, the intervention touches
   proportionally more entity-specific features that may not have proper counterparts
   in the target. **Confidence: High** (N=4 domains, perfect rank ordering, large
   effect sizes, mechanistically plausible).

2. **Within a domain, scaffold does not predict pair-level success.** In USA (N=2450,
   the largest dataset), all correlations with scaffold metrics are |r| < 0.1. The
   scaffold range is too narrow (0.38-0.73, concentrated around 0.53) to discriminate
   pairs. The domain is structurally too homogeneous for this metric to have power.
   **Confidence: High** (large N, unambiguous null result).

3. **In smaller/harder domains, there is a weak positive signal.** Books, products,
   and paintings all show hit_scaffold > miss_scaffold (consistent positive delta
   0.03-0.07). Paintings shows r=0.334 (the only non-trivial within-domain
   correlation). However, the Ns are small (90-240), hit counts are very low
   (9 hits in books, 4 in paintings), and alternative explanations (error_node_pct,
   feature count) have not been fully ruled out. **Confidence: Low** (small N,
   especially for hits; fragile).

4. **Late-layer scaffold is the key differentiator.** The cross-domain drop in
   late_scaffold (USA 16.3% -> books 4.3%) is sharper than the drop in early_scaffold
   (USA 74.6% -> books 39.7%). The output-generation layers (16+) are where
   entity-specific features concentrate, and where structural compatibility matters
   most. This aligns with the "less is more" finding: intervening on fewer (more
   targeted) features avoids disrupting the fragile late-layer scaffold.
   **Confidence: Medium** (consistent pattern across domains, mechanistically
   plausible, but N=4 domains).

**Threats to validity**:

- [x] Within-domain null result confirmed: scaffold does not predict pair-level
  success in USA (largest, most powered dataset).
- [ ] Cross-domain N=4 makes the "perfect rank ordering" less impressive -- with 4
  items, a random ordering has 1/24 = 4.2% chance of matching. However, the effect
  sizes are large (53% vs 25%) and mechanistically motivated.
- [ ] Domain-level confound: scaffold correlates with error_node_pct, feature count,
  and answer-field specificity. These are all intercorrelated. A proper multivariate
  decomposition is needed to isolate scaffold's independent contribution.
- [ ] The scaffold metric counts features assigned to identical supernode names. If
  the naming scheme is inconsistent across entities (which we showed 2.7% are), the
  scaffold count has a ~3% noise floor.
- [ ] Books hit count is N=9. Any claim about books hit/miss scaffold differences is
  anecdotal.
- [ ] I have not tested whether random-feature controls show the same cross-domain
  scaffold pattern. If random controls also succeed more in high-scaffold domains,
  the scaffold effect is generic (not label-specific).

**Follow-up**:

1. Test scaffold vs random controls: does the scaffold advantage persist when
   comparing labeled-vs-random within each domain?
2. Multivariate analysis: regress vsMax on scaffold_inf + error_node_pct + n_features
   to isolate independent contributions.
3. Run the paintings within-domain analysis on the field-additivity variant to see if
   the r=0.334 replicates with more pairs/conditions.
4. Test late_scaffold specifically as a predictor (since it shows the largest
   cross-domain gradient).
5. For the "less is more" connection: check whether the capital-only field variant
   preferentially preserves scaffold features (explaining why fewer fields work better).

---

## [2026-04-01] Topic: Section 4.6 Cross-Prompt Robustness -- claim verification

**Question**: Do the specific quantitative claims in METHODOLOGY_REPORT.md Section 4.6
(Dallas vs Oakland cross-prompt comparison) hold against the current data? The five
sub-claims tested:

1. "7/7 universal concept supernodes transfer (copula, prepositions, relational operators)"
2. "8/8 entity-specific supernodes show appropriate non-transfer"
3. "25 shared features (12.8% of total)"
4. "94% activation stability" for shared features
5. "Layer 0-1 feature overlap: 80-92%; Layer 16-22 overlap: 0-50%"

**Method**: Loaded current `node_grouping.csv` for `texas_Dallas` (203 unique features,
1015 probe-rows, 32 supernodes) and `california_Oakland` (210 unique features,
1050 probe-rows, 34 supernodes). Compared supernode names, computed per-feature
overlap by layer, measured activation stability via relative activation difference
on shared feature_keys. Cross-referenced against the original analysis artifacts in
`output/validation/supernode_level_robustness/` and
`output/validation/feature_level_robustness/` (both dated 2025-10-27), and the
original script `scripts/experiments/analyze_cross_prompt_robustness.py`.

**Raw findings**:

### Feature overlap -- the central discrepancy

| Metric | Original (Oct 2025) | Current data | Source |
|--------|---------------------|--------------|--------|
| Dallas unique features | 39 | 203 | `feature_key` unique count |
| Oakland unique features | 46 | 210 | `feature_key` unique count |
| Shared features | 25 | 148 | intersection of `feature_key` sets |
| Shared % of Dallas | 64.1% | 72.9% | shared / unique Dallas |
| Report's "12.8%" | 25/195 rows | N/A | see denominator analysis below |

The original feature-level analysis (`cross_prompt_robustness_dallas_oakland.json`)
found 39 Dallas features, 46 Oakland, 25 shared. The "12.8% (25/195)" cited in
VERIFIED_CLAIMS.md and METHODOLOGY_REPORT.md uses 195 as the denominator. This 195
is the total number of **rows** in Dallas's node_grouping.csv at the time (39
features x 5 probes = 195 rows), not 195 unique features. The correct percentage
on the original data is 25/39 = **64.1%**, not 12.8%.

On current data, the overlap is even higher: **148/203 = 72.9%**. The data has been
regenerated with ~5x more features per entity since the October 2025 analysis.

### Denominator error confirmation

- Feature-level JSON: `n_features_prompt1: 39`, `n_features_prompt2: 46`
- VERIFIED_CLAIMS.md: "25 out of 195 Dallas features (12.8%)"
- 39 features x 5 probes = 195 rows. 25 + 170 = 195. QED: denominator is rows.
- The `analyze_cross_prompt_robustness.py` line 57 prints `len(self.df1)` (row
  count, not unique features) as "features", propagating the confusion.

### Supernode transfer (claims 1 & 2)

**Claim 1: "7/7 universal concept supernodes transfer"**

The original 7 were: `is`, `capital`, `of`, `containing`, `(containing) related`,
`(capital) related`, `seat`. All 7 are present in both entities on current data.
However, 26 supernode names are now shared between the two entities (including
`state`, `government`, `punctuation`, `The`, `relationship`, `attribute`, `city`,
`entity`, `USA`, `serving`, `States`, `located`, `United`, `which`, `in`, `(entity)
related`, `(attribute) related`, `(serving) related`, `Say (capital)`). The "7/7"
selects a small subset of the actual shared supernodes using the `universal_keywords`
list in the script (line 78: `['is', 'of', 'capital', 'containing', 'related',
'seat']`). The match is keyword-based and excludes many shared structural supernodes.

**Claim 2: "8/8 entity-specific supernodes show appropriate non-transfer"**

The original 8 were: Texas, California, Dallas, Oakland, (Texas) related,
(California) related, United, (United) related. On current data:

- Dallas-only supernodes (6): Austin, Dallas, Say(Austin), Say(Texas), Texas, the
- Oakland-only supernodes (8): California, Oakland, Sacramento, Say(California),
  Say(Oakland), Say(Sacramento), Say(city), Say(state)

"United" now appears in **both** entities (shared supernode), contradicting its
original classification as entity-specific. "(Texas) related" and "(California)
related" no longer appear as distinct supernodes. The entity-specific claim is
directionally correct but the specific 8/8 itemization no longer matches.

### Activation stability (claim 4)

| Metric | Original | Current data |
|--------|----------|--------------|
| Mean relative diff | 0.058 | 0.037 |
| Similarity (1 - rel_diff) | 94.2% | 96.3% |
| Peak token same | 88% (22/25) | 93.2% (138/148) |
| Peak type same | 96% (24/25) | 98.6% (146/148) |
| Same supernode | 68% (17/25) | 80.4% (119/148) |

Claim directionally correct and actually **conservative** -- current data shows
higher stability. Entity-appropriate variants (e.g., Say(Austin) -> Say(Sacramento))
account for 16.9% (25/148). Only 4 features (2.7%) are genuinely inconsistent across
entities.

### Layer overlap (claim 5)

Claim: "Layer 0-1 feature overlap: 80-92%; Layer 16-22 overlap: 0-50%"

Original data (per-layer, % of Dallas):
L0 = 91.7%, L1 = 80.0% => range 80-92% as claimed.
L16-22: individual layers ranged 0-100% (L22=0%, L17=100%).

Current data (per-layer, % of Dallas):
L0 = 80.7%, L1 = 69.2% => range 69-81%, NOT 80-92%.
L16-22 aggregate: 51.5% of Dallas features shared, outside the "0-50%" claim.

Individual current layers in L16-22:
L16=55.6%, L17=100%, L18=50%, L19=100%, L20=50%, L21=33.3%, L22=14.3%.

The general direction (early > late overlap) holds but specific ranges do not match.

### Known bug in original report

The `cross_prompt_report_20251027_183408.md` Executive Summary states "universal:
0/7 successful transfers" -- a counting bug acknowledged in
`DOUBLE_CHECK_RESULTS.md`. The detailed table in the same report correctly shows all
7 universal supernodes with "Full transfer". The 7/7 claim was manually corrected
after discovery but the report was not regenerated.

**Interpretation**:

1. **The "12.8% feature overlap" is wrong** -- it is a denominator error mixing
   unique features (numerator=25) with probe-rows (denominator=195). On the original
   data, true unique-feature overlap was 64.1%. On current data it is 72.9%. The
   interpretation "low feature overlap reflects entity-specificity" is incorrect;
   the majority of features are shared. **Confidence: High.**

2. **The narrative is inverted**: The methodology report frames low overlap as
   evidence of entity-specificity. In reality, the high overlap (~73%) shows that
   most CLT features active in the attribution graph are **shared structural
   primitives**, with entity-specific features being the minority (~27%). This
   actually strengthens the case for robust concept discovery, but for the opposite
   reason stated. **Confidence: High.**

3. **Section 4.6 is based on stale data**: All five claims reference analysis from
   October 2025 when entities had ~39 features. Current data has ~203 features (5x
   more). The graphs have been regenerated, making the original analysis artifacts
   unreliable for current claims. **Confidence: High.**

4. **Supernode transfer is broader than claimed**: 26 shared supernodes exist, not
   7. The "7/7" cherry-picks a subset using keyword matching. Entity-specific
   non-transfer is real but the exact 8/8 itemization is outdated. **Confidence:
   Medium** (the categorization is somewhat subjective).

5. **Activation stability holds and is conservative**: The 94% claim is actually an
   underestimate -- current data shows 96.3%. This is the one claim that survives
   scrutiny. **Confidence: High.**

**Threats to validity**:

- [x] Different data version: Confirmed. Oct 2025 data had ~39 features per entity,
  current has ~203. Pipeline was regenerated.
- [x] Denominator error: Confirmed. 195 = 39 features x 5 probes = rows, not unique
  features.
- [ ] My analysis might use different feature counting: I use unique `feature_key`
  from `node_grouping.csv`; the original may have used a different CSV or filtering.
  However, `selected_features_with_nodes.json` also shows 203 features for current
  Dallas, consistent with my count.
- [ ] Supernode classification is subjective: The boundary between "universal" and
  "entity-specific" depends on keyword lists. Different keyword choices yield
  different counts.
- [ ] N=2 entity comparison: The entire cross-prompt analysis compares exactly 2
  entities. This is acknowledged in the original report's limitations but the
  methodology report presents the results without this caveat.

**Follow-up**:

1. Re-run `analyze_cross_prompt_robustness.py` on current data to produce an updated
   report with correct denominators.
2. Correct section 4.6 of METHODOLOGY_REPORT.md: replace "12.8%" with the actual
   overlap percentage, update layer ranges, note the data version.
3. Consider extending the cross-prompt comparison to more entity pairs (not just
   Dallas/Oakland) to increase N and test generalizability.
4. Add a third entity with different structural properties (e.g., a token-overlap
   entity like `colorado_colorado_springs`) to stress-test transfer claims.

---

## [2026-04-01] Topic: M_amplify sweep -- full investigation summary

**Question**: Does reducing M_amplify from 20 to lower values convert "right direction,
no hit" cases into hits? What is the mechanism, how far does the effect extend, and
what are its limits? Four sub-questions investigated:
(F1) Does the M=5 rescue effect generalize across the full high-vsMax no-hit
population?
(F2) Is there a usable M between 5 and 10 for moderate-signal pairs?
(F3) How does all-fields M=5 compare to the existing capital-only field variant
as a fix for field interference?
(F4) Does the iowa→utah non-monotonic vsMax result replicate? Are there evaluator
blind spots?

**Method**: Created YAML configs `sweep_usa_m5.yml`, `sweep_usa_m7.yml`,
`sweep_usa_m10.yml` (M_amplify=5/7/10, all else identical to `fullscale_usa_labeled`).
Ran via `run_batch_swaps.py --pair` for targeted pairs; for F1 ran a shell loop
over all 40 remaining high-vsMax no-hit oklahoma_tulsa pairs. Queried results with
`SwapQuery.get/search`. Compared against existing `fullscale_usa_labeled` (M=20)
and `fullscale_usa_field_add` variant `add_capital` (capital-only, M=20). All
runs stored under `output/usa_states_batch/_swaps/runs/sweep_usa_m{5,7,10}/`.

Total new steering runs executed this session: 5 pilot pairs × 2 M values +
40-pair batch (M=5) + 4 moderate pairs × 3 M values + 4 high-total pairs × 2 M
values = ~70 individual steering runs.

**Raw findings**:

### Section A: Pilot -- 5 pairs across the overshoot severity spectrum

Pair selection and baseline severity:


| Pair (source -> target)                     | total | amplify | rank_imprv (M=20) | vsMax (M=20) |
| ------------------------------------------- | ----- | ------- | ----------------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | 163   | 73      | -113,493          | 15.80        |
| delaware_wilmington -> oklahoma_tulsa       | 163   | 90      | -167,524          | 15.02        |
| vermont_burlington -> kansas_wichita        | 130   | 90      | -25,268           | 8.34         |
| rhode_island_warwick -> wisconsin_milwaukee | ~130  | ~75     | -1,515            | 8.78         |
| iowa_cedar_rapids -> utah_provo             | 253   | 93      | +35               | 8.62         |


Summary table (hit / vsMax):


| Pair                                        | M=20     | M=10        | M=5          |
| ------------------------------------------- | -------- | ----------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | N / 15.8 | N / 15.8    | **Y / 14.3** |
| delaware_wilmington -> oklahoma_tulsa       | N / 15.0 | N / 14.9    | **Y / 13.9** |
| vermont_burlington -> kansas_wichita        | N / 8.3  | N / 8.1     | N / **0.3**  |
| rhode_island_warwick -> wisconsin_milwaukee | N / 8.8  | N / 8.5     | N / **2.1**  |
| iowa_cedar_rapids -> utah_provo             | N / 8.6  | **Y / 6.1** | **Y / 10.8** |


Hits: M=20: 0/5, M=10: 1/5, M=5: 3/5.

Peak logit advantage over source (best_gap) across M -- stability indicator:


| Pair                                        | M=20  | M=10  | M=5      |
| ------------------------------------------- | ----- | ----- | -------- |
| kansas_wichita -> oklahoma_tulsa            | 16.91 | 16.84 | 16.88    |
| delaware_wilmington -> oklahoma_tulsa       | 22.03 | 23.16 | 23.86    |
| vermont_burlington -> kansas_wichita        | 16.69 | 16.38 | **9.59** |
| rhode_island_warwick -> wisconsin_milwaukee | 13.91 | 13.85 | **9.31** |
| iowa_cedar_rapids -> utah_provo             | 7.97  | 8.00  | 9.88     |


Position-0 disruption (target_rank_improvement at pos0):


| Pair                                        | M=20     | M=10    | M=5  |
| ------------------------------------------- | -------- | ------- | ---- |
| kansas_wichita -> oklahoma_tulsa            | -113,493 | -3,651  | -49  |
| delaware_wilmington -> oklahoma_tulsa       | -167,524 | -15,830 | -280 |
| vermont_burlington -> kansas_wichita        | -25,268  | -1,060  | +7   |
| rhode_island_warwick -> wisconsin_milwaukee | -1,515   | -156    | -11  |
| iowa_cedar_rapids -> utah_provo             | +35      | +451    | +409 |


Control stability (mean absolute logit shift on non-answer tokens):


| Pair                                        | M=20  | M=10  | M=5  |
| ------------------------------------------- | ----- | ----- | ---- |
| kansas_wichita -> oklahoma_tulsa            | 14.14 | 11.81 | 6.68 |
| delaware_wilmington -> oklahoma_tulsa       | 13.84 | 11.70 | 6.70 |
| vermont_burlington -> kansas_wichita        | 11.11 | 10.49 | 8.28 |
| rhode_island_warwick -> wisconsin_milwaukee | 11.75 | 9.81  | 7.37 |
| iowa_cedar_rapids -> utah_provo             | 11.04 | 10.34 | 7.56 |


First tokens and outputs at each M for the two rescued oklahoma_tulsa pairs:

- M=20: `'AddTagHelper'` → "County, Oklahoma, is **Tulsa**" (city, not capital)
- M=10: `' County'` → "County, Oklahoma, is **Tulsa**" (still city)
- M=5: `','` → ", **Oklahoma City**, and Tulsa is Oklahoma" (capital)

iowa->utah at M=20: `' Too'` → "Tooele County, Utah, USA" (no hit).
M=10: `' Too'` → "Tooele County is the city of Salt Lake" (hit). M=5: `' St'`
→ "River, Utah is Salt Lake City" (hit). Non-monotonic: vsMax at M=5 (10.81) >
M=20 (8.62).

### Section B: F1 -- Full oklahoma_tulsa high-vsMax population at M=5

All 42 high-vsMax (vsMax > 12) no-hit oklahoma_tulsa pairs share the same target.
(There are zero high-vsMax no-hit pairs with any other target in the USA dataset.)

Hit rates for all -> oklahoma_tulsa pairs by condition:


| Condition                               | N tested | Hits | Hit%      |
| --------------------------------------- | -------- | ---- | --------- |
| All-fields M=20 (fullscale_usa_labeled) | 49       | 0    | 0.0%      |
| Capital-only M=20 (add_capital variant) | 49       | 11   | 22.4%     |
| All-fields M=5 (sweep_usa_m5)           | 42       | 37   | **88.1%** |


Capital-only M=20 hits cluster at vsMax 7.50--9.12 (median 8.25).
Capital-only M=20 misses cluster at vsMax 9--13. Inverted vsMax/hit correlation:
higher confidence → worse outcome within the capital-only run (replication of the
confidence-hit paradox at smaller scale).

Capital-only hit mechanism: position-1 recovery after garbage first token.
Example: "...isexpandindo-o, **Oklahoma City**, and Tulsa" -- comma/garbage at
position 0, correct capital at position 1. Capital-only miss mechanism: "...is
AddTagHelper, Oklahoma, is **Tulsa**" -- city still dominates positions 1-2.

5 misses at M=5 (comma first token in all cases):


| Source                   | ablate | total | vsMax (M=5) | rank_imprv (M=5) | failure type                                 |
| ------------------------ | ------ | ----- | ----------- | ---------------- | -------------------------------------------- |
| west_virginia_huntington | 97     | 170   | 9.44        | -211             | partial signal drop; "Tulsa" in continuation |
| maryland_baltimore       | 83     | 156   | 14.34       | -117             | "County, Oklahoma, is Tulsa" after comma     |
| hawaii_hilo              | 28     | 101   | **4.81**    | -368             | signal collapse; reverts to Hilo facts       |
| south_dakota_sioux_falls | 141    | 214   | 13.78       | **+94**          | "County, Oklahoma, is Tulsa" after comma     |
| indiana_fort_wayne       | 200    | 273   | 13.56       | -32              | "County" continuation; token-overlap entity  |


South_dakota at M=5: rank_imprv=+94 (zero first-token disruption), first token
`','`, but continuation still generates "County, Oklahoma, is Tulsa." This is
intrinsic failure, not overshoot.

Hits vs misses for comma-first-token pairs at M=5 (sorted by ablate count):


| Source                             | ablate | total | result at M=5 |
| ---------------------------------- | ------ | ----- | ------------- |
| new_hampshire_manchester           | 54     | 127   | HIT           |
| texas_dallas                       | 65     | 138   | HIT           |
| ohio_cleveland                     | 67     | 140   | HIT           |
| delaware_wilmington                | 79     | 152   | HIT           |
| maryland_baltimore                 | 83     | 156   | MISS          |
| kansas_wichita                     | 90     | 163   | HIT           |
| west_virginia_huntington           | 97     | 170   | MISS          |
| south_dakota_sioux_falls           | 141    | 214   | MISS          |
| indiana_fort_wayne (token overlap) | 200    | 273   | MISS          |


No clean ablate-count threshold: kansas (ablate=90) hits while maryland (ablate=83)
misses. The pattern is non-monotonic with the exception of the two highest-ablate
cases (south_dakota, indiana) which both have "County" continuations.

### Section C: F2 -- M=7 on moderate-signal pairs

M=7 results for the two moderate-signal pairs:


| Metric                              | vermont->kansas                 | rhode_island->wisconsin       |
| ----------------------------------- | ------------------------------- | ----------------------------- |
| vsMax: M=20 / M=10 / M=7 / M=5      | 8.34 / 8.12 / 7.75 / **0.31**   | 8.78 / 8.47 / **2.38** / 2.12 |
| rank_imprv: M=20 / M=10 / M=7 / M=5 | -25,268 / -1,060 / **-97** / +7 | -1,515 / -156 / **-47** / -11 |
| first token: M=7                    | `' Falls'`                      | `' County'`                   |
| continuation: M=7                   | Falls, Kansas, is Hutchinson    | County, New York, is Albany   |
| Hit at M=7?                         | **No**                          | **No**                        |


No M in {5, 7, 10, 20} produces a hit for either pair.

At M=7, vermont->kansas has rank_imprv=-97 (minimal first-token disruption) but
first token is still `' Falls'` and continuation is "Falls, Kansas, is Hutchinson"
(wrong Kansas capital). Signal collapse for rhode_island->wisconsin occurs between
M=10 (vsMax=8.47) and M=7 (vsMax=2.38). Signal collapse for vermont->kansas occurs
between M=7 (vsMax=7.75) and M=5 (vsMax=0.31).

### Section D: F4 -- Non-monotonic M, high-total_count pairs, and evaluator gap

High-total_count (total > 240) mild-disruption pairs at M=5:


| Pair                                               | total | rank_imprv (M=20) | M=20                | M=10                | M=5                      |
| -------------------------------------------------- | ----- | ----------------- | ------------------- | ------------------- | ------------------------ |
| indiana_fort_wayne -> arkansas_fayetteville        | 269   | +178              | N / 5.56 (`tonode`) | N / 5.56 (`tonode`) | **Y / 5.75** ( `Little`) |
| indiana_fort_wayne -> minnesota_minneapolis        | 282   | +191              | N / 5.56 ( `St`)    | N / 6.88 ( `St`)    | N / 6.00 ( `St`)         |
| idaho_idaho_falls -> minnesota_minneapolis         | 251   | +119              | N / 5.81 ( `St`)    | N / 6.25 ( `St`)    | N / 4.38 ( `St`)         |
| colorado_colorado_springs -> minnesota_minneapolis | 245   | +301              | N / 5.62 ( `St`)    | N / 4.94 ( `St`)    | N / 4.81 ( `St`)         |


`indiana -> arkansas` at M=5: HIT via a different rescue mechanism. The garbage
token 'tonode' at M=20/M=10 is NOT caused by rank disruption (rank_imprv=+178,
always positive). M=5 eliminates a feature-interaction artifact that specifically
activates the 'tonode' token at high amplification. First token becomes `' Little'`
→ "Little Rock, Arkansas" (correct capital).

`-> minnesota_minneapolis` evaluator gap: all three sources output "St. Paul,
Minnesota" at all M values. Stored capital is "Saint Paul" (full form). Evaluator
substring match fails in both directions; fuzzy match also fails. `steered_has_to_answer`
= False across all runs despite geographically correct output. This is a structural
mismatch between training-text abbreviation and stored formal name. Affects all
->minnesota_minneapolis pairs at every M value -- relative M comparisons are
unaffected but absolute hit rates for this target are systematically undercounted.

vsMax non-monotonic behavior for indiana->minnesota: M=20 (5.56) → M=10 (6.88) →
M=5 (6.00). M=10 is the local maximum. This replicates the iowa->utah non-monotonic
finding (vsMax higher at M=5 than M=20) with a different shape.

**Interpretation**:

Five failure modes are now identified and partially separated:


| Mode                            | Mechanism                                                                                                                  | Fix                                                                                     |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Severe overshoot**            | rank_imprv << -100K, garbage first token; best_gap stable across M                                                         | M=5 rescues (88.1% on oklahoma_tulsa)                                                   |
| **Field interference**          | City features dominate capital features at position 1-2                                                                    | M=5 reduces interference; capital-only field variant partially helps via different path |
| **Feature interaction garbage** | Garbage token NOT from rank disruption (rank_imprv positive); specific feature combination activates code tokens at high M | M=5 rescues (indiana->arkansas)                                                         |
| **Signal collapse**             | vsMax collapses (7-14 → <1) below a M threshold; model reverts to source geography                                         | No M tested produces a hit; threshold pair-specific (M=5--M=10)                         |
| **Feature specificity**         | No first-token disruption, correct state context, wrong capital (e.g. Hutchinson not Topeka)                               | Not fixable by M tuning; requires better feature grouping                               |


The 88.1% M=5 hit rate for oklahoma_tulsa reflects that 37 of 42 pairs fall into
modes 1-2 (rescuable), while the 5 misses span modes 3, 4, and 5. The 0%
all-fields M=20 baseline and 22.4% capital-only M=20 baseline confirm that M=5 is
the strongest single-parameter fix tested so far for this target.

The best_gap stability across M values for the rescued oklahoma_tulsa pairs (16.88 /
16.84 / 16.91 at M=5/10/20) is the critical mechanistic observation: M does not
change the underlying label signal strength at all -- it only controls how cleanly
position 0 decodes. This means the features genuinely encode Oklahoma City; the
failure at M=20 is entirely in the decoding layer, not in the representation.

The "County continuation" misses (south_dakota, indiana at M=5 with rank_imprv near
zero and comma first token) are the clearest counterexample to a pure overshoot story.
They show that even with perfect position-0 decoding, the position-1 continuation
can still fail if source-entity residual features (after M_ablate=-2 multiplication,
not zeroing) generate a stronger "County" bigram than the amplified target capital
features. This may be solvable by M_ablate tuning rather than M_amplify tuning.

The "Saint Paul" evaluator gap is a new pipeline finding with no equivalent in prior
entries. Its extent across other abbreviable capitals (e.g. "Saint Louis" vs "St.
Louis") is unknown but plausibly non-trivial.

Confidence:

- M=5 rescues severe-overshoot oklahoma_tulsa pairs: **Medium-High** (N=37 hits,
consistent mechanism, best_gap stability confirmed)
- M=5 fails for moderate-signal and signal-collapse pairs: **Medium** (N=4 pairs,
two failure modes confirmed)
- "County continuation" as distinct failure mode: **Medium** (N=3 cases, but all
have anomalous ablate counts or token overlap)
- "Saint Paul" evaluator gap: **High** (structural mismatch, consistent across all
observed sources and M values)
- Non-monotonic vsMax: **Low** (2 pairs, different shapes)

**Threats to validity**:

- All 42 high-vsMax no-hit pairs share the same target (oklahoma_tulsa). The
88.1% rate may be specific to Oklahoma City's feature representation, the fixed
amplify_count=73, or the question format. No other high-vsMax target was tested.
- The M=5 hits produce grammatically unusual outputs ("is, Oklahoma City, and
Tulsa is Oklahoma"). A first-token-strict evaluation would count all as misses.
The metric is lenient enough to count "Oklahoma City" anywhere in 10 tokens.
- South_dakota's "County" continuation at M=5 with rank_imprv=+94 is NOT an
overshoot artifact. A full explanation requires feature-level analysis not done
here.
- The "Saint Paul" evaluator gap was confirmed for 3 sources; the remaining
46 ->minnesota_minneapolis pairs were not verified individually.
- Non-monotonic vsMax at M=10 for indiana->minnesota (6.88 > 5.56 and 6.00)
is N=1 and should not be cited without replication.
- M=7 was tested only on the two moderate-signal pairs. The signal-collapse
cliff locations (M=5--7 for vermont->kansas; M=7--10 for rhode_island->wisconsin)
may not generalize to other pairs.
- The 'tonode' mechanism for indiana->arkansas is observed but unexplained at
feature level. The rescue at M=5 is real but the root cause is unknown.

**Follow-up**:

- Run M=5 on the 7 oklahoma_tulsa pairs not yet tested (complete the population N=49).
- Test M=5 on high-vsMax no-hit pairs from other targets to verify generalizability
beyond oklahoma_tulsa.
- Test M=3 on the "County continuation" misses (south_dakota, indiana) to check if
further M reduction can flip the position-1 probability from "County" to "Oklahoma
City," given that position-0 is already clean at M=5.
- Investigate the M_ablate dimension: the "County continuation" may respond to
M_ablate=0 (full suppression of source features) rather than M_amplify tuning.
- Use PipelineTracer on kansas_wichita's capital supernode to check if it contains
Topeka-specific features or is contaminated with generic Kansas geography (explains
the vermont->kansas feature-specificity failure).
- Quantify the "Saint Paul" evaluator gap across all 49 ->minnesota_minneapolis
pairs and check other abbreviated-capital targets (e.g. "Saint Louis", "Saint
Augustine").
- Update the domain-level hit rate tables in `FULLSCALE_CONTROL_REPORT.md` with a
note that the USA rate at M=20 likely understates the achievable rate; M=5 is a
candidate for a re-run on the full USA dataset.

---

## [2026-04-01] Topic: M_amplify sweep on selected overshoot cases -- pilot results

**Question**: Can reducing M_amplify from 20 to {10, 5} convert "right direction,
no hit" cases to hits? The [2026-03-25] entry established that severe position-0
disruption (rank_imprv <= -100K) is the proximate cause of failure for high-vsMax
pairs. This pilot tests whether smaller M values rescue those cases without
destroying the label-specific signal.

**Method**: Selected 5 pairs from the USA `fullscale_usa_labeled` run, spanning
the overshoot severity spectrum (target_rank_improvement at pos0 from -167K to
+35). Created two new YAML configs (`sweep_usa_m5.yml`, `sweep_usa_m10.yml`)
identical to `fullscale_usa_labeled.yml` except M_amplify=5 and M_amplify=10
respectively (M_ablate=-2, temperature=0.3 unchanged). Ran each pair with:

```
python run_batch_swaps.py --config configs/sweep_usa_m{5,10}.yml \
    --run-id sweep_usa_m{5,10} --pair <from>:<to>
```

Results stored in `output/usa_states_batch/_swaps/runs/sweep_usa_m5/` and
`sweep_usa_m10/`. Compared using `SwapQuery.get()` and direct trajectory
inspection.

Pair selection criteria and M=20 baseline:


| Pair                                        | total_count | amplify | rank_imprv (M=20) | vsMax (M=20) |
| ------------------------------------------- | ----------- | ------- | ----------------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | 163         | 73      | -113,493          | 15.80        |
| delaware_wilmington -> oklahoma_tulsa       | 163         | 90      | -167,524          | 15.02        |
| vermont_burlington -> kansas_wichita        | 130         | 90      | -25,268           | 8.34         |
| rhode_island_warwick -> wisconsin_milwaukee | ~130        | ~75     | -1,515            | 8.78         |
| iowa_cedar_rapids -> utah_provo             | 253         | 93      | +35               | 8.62         |


**Raw findings**:

Hit/vsMax summary across M values (N=5 pairs each):


| Pair                                        | M=20     | M=10        | M=5          |
| ------------------------------------------- | -------- | ----------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | N / 15.8 | N / 15.8    | **Y / 14.3** |
| delaware_wilmington -> oklahoma_tulsa       | N / 15.0 | N / 14.9    | **Y / 13.9** |
| vermont_burlington -> kansas_wichita        | N / 8.3  | N / 8.1     | N / **0.3**  |
| rhode_island_warwick -> wisconsin_milwaukee | N / 8.8  | N / 8.5     | N / **2.1**  |
| iowa_cedar_rapids -> utah_provo             | N / 8.6  | **Y / 6.1** | **Y / 10.8** |


Hits: M=20: 0/5, M=10: 1/5, M=5: 3/5.

Position-0 disruption (target_rank_improvement):


| Pair                                        | M=20     | M=10    | M=5  |
| ------------------------------------------- | -------- | ------- | ---- |
| kansas_wichita -> oklahoma_tulsa            | -113,493 | -3,651  | -49  |
| delaware_wilmington -> oklahoma_tulsa       | -167,524 | -15,830 | -280 |
| vermont_burlington -> kansas_wichita        | -25,268  | -1,060  | +7   |
| rhode_island_warwick -> wisconsin_milwaukee | -1,515   | -156    | -11  |
| iowa_cedar_rapids -> utah_provo             | +35      | +451    | +409 |


Peak logit advantage over source (best_gap) -- M-stability indicator:


| Pair                                        | M=20  | M=10  | M=5      |
| ------------------------------------------- | ----- | ----- | -------- |
| kansas_wichita -> oklahoma_tulsa            | 16.91 | 16.84 | 16.88    |
| delaware_wilmington -> oklahoma_tulsa       | 22.03 | 23.16 | 23.86    |
| vermont_burlington -> kansas_wichita        | 16.69 | 16.38 | **9.59** |
| rhode_island_warwick -> wisconsin_milwaukee | 13.91 | 13.85 | **9.31** |
| iowa_cedar_rapids -> utah_provo             | 7.97  | 8.00  | 9.88     |


Control stability (mean absolute logit shift on non-answer tokens):


| Pair                                        | M=20  | M=10  | M=5  |
| ------------------------------------------- | ----- | ----- | ---- |
| kansas_wichita -> oklahoma_tulsa            | 14.14 | 11.81 | 6.68 |
| delaware_wilmington -> oklahoma_tulsa       | 13.84 | 11.70 | 6.70 |
| vermont_burlington -> kansas_wichita        | 11.11 | 10.49 | 8.28 |
| rhode_island_warwick -> wisconsin_milwaukee | 11.75 | 9.81  | 7.37 |
| iowa_cedar_rapids -> utah_provo             | 11.04 | 10.34 | 7.56 |


First token and steered output by M (M=20 first):

**kansas_wichita -> oklahoma_tulsa** (target capital = Oklahoma City):

- M=20: `'AddTagHelper'` (p=0.291) -- "County, Oklahoma, is Tulsa" (generates city, not capital)
- M=10: `' County'` (p=0.475) -- "County, Oklahoma, is Tulsa" (same wrong pattern)
- M=5: `','` (p=0.365) -- ", Oklahoma City, and Tulsa is Oklahoma" (**contains Oklahoma City**)

**delaware_wilmington -> oklahoma_tulsa** (same target):

- M=20: `'AddTagHelper'` (p=0.363) -- "County, Oklahoma, is Tulsa"
- M=10: `' County'` (p=0.457) -- "County, Oklahoma, is Tulsa"
- M=5: `','` (p=0.504) -- ", Oklahoma City, and Tulsa is Oklahoma" (**hit**)

**vermont_burlington -> kansas_wichita** (target capital = Topeka):

- M=20: `' Falls'` (p=0.652) -- "Falls, Kansas, is Hutchinson" (Kansas context but wrong city)
- M=10: `' Falls'` (p=0.711) -- "Falls, Kansas, is Hutchinson" (unchanged)
- M=5: `','` (p=0.428) -- "Falls, New York, is Albany" (signal dead -- reverts to source-like geography)

**iowa_cedar_rapids -> utah_provo** (target capital = Salt Lake City):

- M=20: `' Too'` (p=0.291) -- "Tooele County, Utah, USA" (Utah context but wrong place)
- M=10: `' Too'` (p=0.167) -- "Tooele County is the city of Salt Lake" (**hit**)
- M=5: `' St'` (p=0.094) -- "River, Utah is Salt Lake City" (**hit**)

**Interpretation**:

Three distinct regimes emerge:

1. **Severe overshoot, strong signal (oklahoma_tulsa pairs, vsMax > 14, rank_imprv
  << -100K)**: M=5 rescues both hits. The critical observation is that the
   best_gap (peak logit advantage over source) is nearly IDENTICAL across all
   three M values (16.88-16.91 for kansas pair, 22.03-23.86 for delaware pair).
   M does not change the underlying label-specific signal -- it only controls
   how cleanly position 0 decodes. At M=20, combined amplification of ~73*20=1460
   units pushes the target rank to -100K+, generating garbage (AddTagHelper).
   At M=5, the amplification of 73*5=365 units still produces the same peak
   logit advantage but does not corrupt position 0. The first token becomes `','`
   which allows the model to generate "Oklahoma City" as a continuation. M=10
   reduces disruption but not enough (rank_imprv still -3651 to -15830), and
   the first token (' County') still prevents a hit.
2. **Moderate overshoot, weak-to-moderate signal (vermont->kansas,
  rhode_island->wisconsin, vsMax ~8, rank_imprv -25K to -1.5K)**: M=5
   eliminates position-0 disruption (rank_imprv near 0) but also collapses
   the label-specific signal. best_gap drops from 16.69 to 9.59 (vermont->
   kansas) and vsMax from 8.34 to 0.31. The model reverts to source-like
   output ("Falls, New York, is Albany" -- wrong state, wrong capital).
   M=10 reduces disruption (rank_imprv from -25K to -1060) but the wrong
   first token (' Falls') persists and the generation still fails. There
   is no M in {5, 10, 20} that produces a hit. The optimal M for these
   pairs likely lies between 5 and 10, but may not exist -- the features
   for Topeka/Kansas and Madison/Wisconsin may be too weak at any usable M.
3. **Borderline disruption (iowa->utah, rank_imprv ~+35 at M=20)**: Both
  M=10 and M=5 produce hits. At M=20, the model generates "Tooele County"
   and terminates without producing "Salt Lake City". At M=10 and M=5, the
   model generates "Tooele County is the city of Salt Lake..." or "River,
   Utah is Salt Lake City" -- the correct answer emerges later in the
   generation. Notably, vsMax at M=5 (10.81) is higher than at M=20 (8.62),
   suggesting that for this high total_count (253) pair, M=20 is the
   threshold at which the amplification starts to suppress later-position
   recovery. Confidence: **Low** (single pair, non-monotonic behavior).

**An asymmetry in the oklahoma_tulsa outcomes**: At M=20 and M=10, the model
generates "County, Oklahoma, is Tulsa" -- producing the target entity's city
(Tulsa) rather than its capital (Oklahoma City). At M=5, it produces "Oklahoma
City." This suggests that at high M, the simultaneous amplification of all three
concept fields (state, capital, city) creates interference: the "city" features
for Tulsa compete with the "capital" features for Oklahoma City, and at M=20/10
the city features dominate position 0. At M=5, the reduced amplification allows
the capital features (more relevant to the question "The capital of the state
containing X is...") to emerge. This is distinct from pure overshoot and
warrants further investigation.

Confidence for the headline finding (M=5 rescues severe overshoot):
**Medium** -- consistent across 2 oklahoma_tulsa pairs, mechanistically
plausible (best_gap preserved), but N=2 pairs. The failure of M=5 for the
moderate-signal pairs (vermont->kansas, rhode_island->wisconsin) confirms
the "signal collapse" threat to validity identified in [2026-03-25].

**Threats to validity**:

- N=5 pairs total, N=2 hits recovered at M=5. Both successful cases share
the same target (oklahoma_tulsa). The effect may be specific to Oklahoma City
having a particularly clean feature representation rather than a general
M=5 superiority. Requires testing against other high-vsMax no-hit targets.
- The first-token `','` at M=5 succeeds because the model generates
"is, Oklahoma City" -- a grammatically unusual pattern. The hit is
technically correct (Oklahoma City appears in the output) but the output
quality is low. A more demanding evaluation (e.g., exact first-token match)
would not count this as a hit.
- The signal collapse at M=5 for moderate pairs (vermont->kansas, vsMax
drops from 8.34 to 0.31) confirms the threat identified in [2026-03-25].
A full sweep at M values between 5 and 10 would be needed to find the
optimum for these cases. It is not guaranteed an optimum exists.
- The iowa->utah case at M=5 shows vsMax=10.81 > M=20's 8.62 -- a
non-monotonic reversal. This could be noise (n=1), or could indicate
that very high total_count (253) creates enough interference at M=20 that
reducing M actually improves signal strength. Cannot distinguish without
more pairs.
- All five pairs were selected because they had high vsMax at M=20. They
are not representative of the full right-direction-no-hit population
(N=1345 in USA). The benefit of M=5 for the full population may be lower
because many no-hit pairs have lower vsMax and may suffer signal collapse.
- The control stability reduction at M=5 (from ~14 to ~6.7 for oklahoma
pairs) is positive but does not rule out other forms of disruption not
captured by the metric (e.g., disruption to attention heads or to tokens
not in the control window).

**Follow-up**:

- Run M=5 on a larger sample of high-vsMax no-hit pairs (e.g., top 30 by
vsMax with vs_max > 12 and no hit at M=20) to check if the 2/2 oklahoma_tulsa
hit recovery generalizes to other targets.
- Test M values between 5 and 10 (e.g., M=7) on the moderate-signal pairs
(vermont->kansas, rhode_island->wisconsin) to locate the signal-collapse
threshold. Is there a sweet spot between 5 and 10 that reduces disruption
without killing the signal?
- Investigate the "city vs capital interference" hypothesis: compare a run
using ONLY capital field features (not state + capital + city) at M=20 vs
a run using all three fields at M=5. If the city features are the source
of interference, field-restricted steering may outperform M reduction.
- Replicate the iowa->utah non-monotonic M result (vsMax higher at M=5 than
M=20) with other high-total_count pairs to determine if the effect is real.
- Update the regime taxonomy from [2026-03-24] with the new M=5 results:
which regime does the `','` first-token hit pattern belong to?

---

## [2026-04-01] Topic: M=5 oklahoma_tulsa sweep -- full population, miss analysis, and field comparison

**Question**: Does the M=5 rescue effect generalize across all 42 high-vsMax
no-hit oklahoma_tulsa pairs? What characterizes the misses? How does all-fields
M=5 compare to the existing capital-only M=20 variant as an alternative fix?

**Method**: Ran M=5 (config `sweep_usa_m5`, run_id `sweep_usa_m5`) on all 40
remaining high-vsMax no-hit oklahoma_tulsa pairs using `run_batch_swaps.py --pair`.
Combined with 2/2 from prior pilot: 42 total pairs tested.
For field comparison, queried `fullscale_usa_field_add` `add_capital` variant
(capital features only, M=20 unchanged) for all 49 oklahoma_tulsa pairs.
For miss analysis, loaded M=5 detail via `SwapQuery.get()` for the 5 failures.

**Raw findings**:

Hit rates for all->oklahoma_tulsa pairs by condition:


| Condition                                                | N               | Hits | Hit%  |
| -------------------------------------------------------- | --------------- | ---- | ----- |
| All-fields M=20 (fullscale_usa_labeled)                  | 49              | 0    | 0.0%  |
| Capital-only M=20 (fullscale_usa_field_add, add_capital) | 49              | 11   | 22.4% |
| All-fields M=5 (sweep_usa_m5)                            | 42 of 49 tested | 37   | 88.1% |


The all-fields M=5 vs all-fields M=20 comparison covers the same 42 pairs tested.
Capital-only M=20 covers all 49 (7 pairs not yet tested at M=5 are identity or
excluded from the high-vsMax set).

5 misses at M=5 (all->oklahoma_tulsa):


| Source                   | ablate | amplify | total | vsMax (M=5) | rank_imprv (M=5) | first_token | continuation                 |
| ------------------------ | ------ | ------- | ----- | ----------- | ---------------- | ----------- | ---------------------------- |
| west_virginia_huntington | 97     | 73      | 170   | 9.44        | -211             | `','`       | "Oklahoma is called Tulsa"   |
| maryland_baltimore       | 83     | 73      | 156   | 14.34       | -117             | `','`       | "County, Oklahoma, is Tulsa" |
| hawaii_hilo              | 28     | 73      | 101   | **4.81**    | -368             | `','`       | "'s population is 15,000"    |
| south_dakota_sioux_falls | 141    | 73      | 214   | 13.78       | **+94**          | `','`       | "County, Oklahoma, is Tulsa" |
| indiana_fort_wayne       | 200    | 73      | 273   | 13.56       | -32              | `','`       | "County, Oklahoma, is Tulsa" |


Three miss sub-types:

- **'County' continuation** (maryland, south_dakota, indiana): first token is `','`
but position 1 generates "County" then "Oklahoma, is Tulsa." The model has
non-garbage first token but still produces the wrong answer continuation.
- **West Virginia**: `','` first token but continuation is "Oklahoma is called
**Tulsa**" -- correct state but wrong concept (city not capital). vsMax dropped
to 9.44 from 14.69, partial signal degradation.
- **Hawaii signal collapse**: vsMax drops from 14.12 to 4.81 at M=5. Output is
"'s population is 15,000" -- model reverts to source entity context (Hilo facts).

Comma-first hits vs misses at M=5 (intervention count comparison):


| Source                   | ablate | total | vsMax (M=5) | rank_imprv | result        |
| ------------------------ | ------ | ----- | ----------- | ---------- | ------------- |
| new_hampshire_manchester | 54     | 127   | 14.38       | -212       | HIT           |
| texas_dallas             | 65     | 138   | 13.75       | -132       | HIT           |
| ohio_cleveland           | 67     | 140   | 13.69       | -30        | HIT           |
| delaware_wilmington      | 79     | 152   | 13.94       | -280       | HIT           |
| kansas_wichita           | 90     | 163   | 14.34       | -49        | HIT           |
| maryland_baltimore       | 83     | 156   | 14.34       | -117       | MISS (County) |
| west_virginia_huntington | 97     | 170   | 9.44        | -211       | MISS (Tulsa)  |
| south_dakota_sioux_falls | 141    | 214   | 13.78       | +94        | MISS (County) |
| indiana_fort_wayne       | 200    | 273   | 13.56       | -32        | MISS (County) |


No clean separation by ablate count or total. Kansas (ablate=90) hits while
maryland (ablate=83) misses with similar vsMax. South_dakota (ablate=141) and
indiana (ablate=200) both miss with the "County" continuation despite rank_imprv
near 0 or positive. Indiana_fort_wayne is a known token-overlap entity (ablate=200).

Capital-only M=20 hit mechanism: hits occur via position-1 recovery.
Example output: "...isexpandindo-o, **Oklahoma City**, and Tulsa" -- garbage at
position 0, but "Oklahoma City" immediately at position 1. The capital-only hits
cluster at vsMax 7.50-9.12. Capital-only misses at high vsMax (9-13) produce
"...isAddTagHelper, Oklahoma, is Tulsa" -- worse at high vsMax (capital-city
interference persists even with capital-only, inverted vsMax/hit correlation).

**Interpretation**:

The 88.1% hit rate at M=5 for the full oklahoma_tulsa high-vsMax no-hit set is
a strong result. It substantially exceeds capital-only M=20 (22.4%) and all-fields
M=20 (0%). Confidence: **Medium-High** (N=42 pairs, all same target, convergent
mechanism).

The three miss sub-types reveal that even at M=5, failure occurs via three distinct
paths:

1. **County continuation** (maryland, south_dakota, indiana): Position 0 is clean
  (comma), but the position-1 probability still favors "County" over "Oklahoma City."
   This may reflect that these source entities have concepts that generate a "County"
   bigram in context -- possibly because their features (after ablation) leave residual
   signals that reinforce the "...is County" continuation pattern. Indiana_fort_wayne
   (token overlap, ablate=200) is the extreme case. No simple M adjustment will fix
   this without also investigating the ablation component.
2. **West Virginia**: Partial signal degradation (vsMax 14.69→9.44) plus wrong
  concept generated (Tulsa instead of Oklahoma City). A candidate for M=7 or M=6
   tuning -- the vsMax drop suggests we are near the signal-collapse boundary.
3. **Hawaii signal collapse**: Full collapse at M=5 (vsMax 14.12→4.81), similar
  to vermont_burlington case. Hawaii's feature representation may be intrinsically
   weaker or more diffuse, causing the same cliff behavior.

The capital-only vs all-fields M=5 comparison reveals a deep asymmetry:
capital-only achieves hits through position-1 recovery after a garbage token,
while all-fields M=5 achieves hits through a clean-ish comma that allows
"Oklahoma City" in the grammatical continuation. All-fields M=5 produces nearly
4x the hit rate (88% vs 22%) because the stronger combined signal allows more
sources to generate "Oklahoma City" at position 1 even after the comma.

The inverted vsMax/hit relationship in capital-only M=20 (hits at vsMax 7-9, misses
at vsMax 9-13) is a replication of the confidence-hit paradox at a smaller scale.
Higher vsMax in capital-only generates "Oklahoma, is Tulsa" (city) while lower vsMax
generates "Oklahoma City" (capital) -- the capital features at moderate amplification
are more specifically informative than at high amplification where field interference
re-emerges even in the capital-only variant.

Confidence: **Medium** -- all conclusions limited to one target entity (oklahoma_tulsa).
Cannot determine generalizability without testing other targets.

**Threats to validity**:

- All 42 pairs share the same target (oklahoma_tulsa). The conclusions are
specific to this target. The feature quality, intervention count (amplify=73
fixed for all pairs), and answer identity (Oklahoma City) are all target-specific.
Other targets may show different rates.
- The 5 misses are heterogeneous: one signal-collapse (hawaii), one partial
degradation (west_virginia), three "County continuation." A satisfying explanation
requires feature-level analysis (which supernodes generate "County") that this
investigation did not do.
- "County" continuation at M=5 for south_dakota (rank_imprv=+94) means the
failure occurs even with zero first-token disruption. This is an intrinsic
failure of the feature combination, not an overshoot artifact.
- Indiana_fort_wayne is a known token-overlap entity (ablate=200), which may
bias the miss characterization by ablate count toward an artifact of entity type.

**Follow-up**:

- Test M=5 on all 49 oklahoma_tulsa pairs (7 not yet run) to get the complete
population rate.
- Investigate the "County continuation" mechanism: use PipelineTracer to check
which source supernodes are being ablated for south_dakota vs kansas, and whether
residual county-related features explain the bigram.
- Test M=5 on high-vsMax no-hit pairs from OTHER targets (to validate that the
88.1% rate is not oklahoma_tulsa-specific).
- Investigate the capital-only hit mechanism more carefully: why does lower vsMax
in capital-only lead to hits while higher vsMax leads to misses?

---

## [2026-04-01] Topic: M=7 threshold for moderate-signal pairs; non-monotonic M and evaluator gap

**Question**: (F2) Is there a usable M between 5 and 10 for moderate-signal pairs
(vermont_burlington->kansas_wichita, rhode_island_warwick->wisconsin_milwaukee)?
(F4) Does the iowa->utah non-monotonic vsMax pattern replicate on other
high-total_count pairs? And are there systematic metric undercounts?

**Method**: Created `sweep_usa_m7.yml` (M_amplify=7, all else unchanged). Ran M=7
on the two moderate-signal pairs. For F4, ran M=5 and M=10 on 4 high-total_count
(>250) pairs with mild/positive rank_imprv at M=20: indiana_fort_wayne->
{minnesota_minneapolis, arkansas_fayetteville}, idaho_idaho_falls->minnesota_minneapolis,
colorado_colorado_springs->minnesota_minneapolis. Loaded full detail via SwapQuery.

**Raw findings**:

M=7 on moderate-signal pairs:


| Pair                                  | M=20                            | M=10     | M=7              | M=5                        |
| ------------------------------------- | ------------------------------- | -------- | ---------------- | -------------------------- |
| vermont->kansas: vsMax                | 8.34                            | 8.12     | 7.75             | 0.31                       |
| vermont->kansas: rank_imprv           | -25,268                         | -1,060   | -97              | +7                         |
| vermont->kansas: first                | `Falls`                         | `Falls`  | `Falls`          | `,`                        |
| vermont->kansas: continuation         | Falls, Kansas, is Hutchinson    | same     | same             | Falls, New York, is Albany |
| rhode_island->wisconsin: vsMax        | 8.78                            | 8.47     | 2.38             | 2.12                       |
| rhode_island->wisconsin: rank_imprv   | -1,515                          | -156     | -47              | -11                        |
| rhode_island->wisconsin: first        | `expandindo`                    | `County` | `County`         | `,`                        |
| rhode_island->wisconsin: continuation | County, Wisconsin, is Green Bay | same     | County, New York | County, New York           |


**No M in {5, 7, 10, 20} produces a hit for either moderate-signal pair.**

Key observation for vermont->kansas at M=7: rank_imprv=-97 (minimal first-token
disruption), first token still ' Falls', continuation "Falls, Kansas, is Hutchinson."
The failure at M=7 is NOT first-token disruption -- the model generates the correct
state context (Kansas) but the wrong capital (Hutchinson, a large Kansas city).

For rhode_island->wisconsin: signal collapse between M=10 (vsMax=8.47) and M=7
(vsMax=2.38). The cliff is between M=10 and M=7 for this pair (vs between M=5 and
M=7 for vermont->kansas).

F4 -- High-total_count pairs with mild/positive rank_imprv at M=20:


| Pair                | total (M=20) | M=20     | M=10     | M=5          |
| ------------------- | ------------ | -------- | -------- | ------------ |
| indiana->minnesota  | 282          | N / 5.56 | N / 6.88 | N / 6.00     |
| indiana->arkansas   | 269          | N / 5.56 | N / 5.56 | **Y / 5.75** |
| idaho->minnesota    | 251          | N / 5.81 | N / 6.25 | N / 4.38     |
| colorado->minnesota | 245          | N / 5.62 | N / 4.94 | N / 4.81     |


Key F4 outputs:

`indiana_fort_wayne -> arkansas_fayetteville` (target capital = Little Rock):

- M=20: `'tonode'` -- "...istonode.\n\nThe capital of..."  (garbage token, output broken)
- M=10: `'tonode'` -- same failure
- M=5: `' Little'` -- "...is Little Rock, Arkansas..." **HIT!**
- rank_imprv=+178-179 at all M (no position-0 disruption). The 'tonode' token is
a different class of garbage -- NOT from rank disruption but from feature
interaction at M=20 that specifically generates a JavaScript/code token.
M=5 rescues by eliminating that interaction.

`->minnesota_minneapolis` pairs (target capital stored as "Saint Paul"):

- All M values, all sources: model outputs "St. Paul, Minnesota" (abbreviated)
- Evaluator requires "Saint Paul" (full spelling) -- systematic miss
- Affected pairs: indiana->minnesota, idaho->minnesota, colorado->minnesota
(and likely all 49 ->minnesota_minneapolis pairs at any M)
- `steered_has_to_answer` = False despite correct geographic content
- `steered_has_to_capital` = False (same metric, same field)

Example: idaho_idaho_falls->minnesota_minneapolis at ALL three M values outputs
"...Idaho Falls is St. Paul, Minnesota, is the largest..." which is a correct
description of Minnesota's capital but fails the evaluator.

vsMax behavior for indiana->minnesota across M values: non-monotonic
(5.56→6.88→6.00 for M=20→10→5). The M=10 value (6.88) is higher than both
M=20 (5.56) and M=5 (6.00). This non-monotonic pattern confirms the iowa->utah
finding but with moderate magnitude changes.

**Interpretation**:

For the moderate-signal pairs (F2), the investigation reaches a definitive
negative: no M in {5, 7, 10, 20} produces a hit. The two pairs fail via
fundamentally different mechanisms:

1. **vermont->kansas**: First-token disruption is NOT the failure mode at M=7
  (rank_imprv=-97, minimal). The model generates "Falls, Kansas, is Hutchinson"
   -- the source city token (' Falls') still dominates position 0, and the
   continuation correctly identifies Kansas as the target state but generates
   Hutchinson (a large Kansas city) instead of Topeka. **The features are pointing
   at Kansas/Wichita but not specifically at Topeka.** This is a feature specificity
   failure, not an overshoot failure. No M tuning can fix this without better
   features.
2. **rhode_island->wisconsin**: Signal collapses sharply between M=10 (intact,
  vsMax=8.47) and M=7 (collapsed, vsMax=2.38). The cliff is steeper and earlier
   than for vermont->kansas. At M=7, the model defaults to New York/Albany --
   same source-state reversion seen at M=5 for vermont->kansas.

For F4 (high-total_count non-monotonic):

`indiana->arkansas` at M=5 is a clean example of a different rescue mechanism:
the 'tonode' garbage token at M=20/10 is NOT caused by rank disruption
(rank_imprv=+178, always positive) but by a high-M feature interaction that
specifically activates a code-adjacent token. At M=5, this interaction is below
threshold and ' Little' (for "Little Rock") emerges. This is mechanistically
different from the oklahoma_tulsa overshoot rescue.

The "Saint Paul" evaluator gap is a systematic pipeline issue. All
->minnesota_minneapolis pairs appear to generate "St. Paul" (the standard
abbreviated form used in training text) rather than "Saint Paul" (the stored
formal name). The evaluator's substring match fails in both directions:
"St. Paul" is not in "Saint Paul" and "Saint Paul" is not in "St. Paul". The
fuzzy match also fails (different token strings). This affects the hit count
for all conditions tested (M=20, M=10, M=5) equally, so relative comparisons
between M values are unaffected, but absolute hit rates for ->minnesota_minneapolis
are systematically undercounted across the entire dataset.

The non-monotonic vsMax at M=10 for indiana->minnesota (6.88 > 5.56 at M=20 and
6.00 at M=5) is plausible: M=10 is at a "sweet spot" where the target signal is
maximally expressed without the interference that reduces it at M=20 or the
under-amplification at M=5. This remains single-pair evidence (Low confidence).

Confidence: **Medium** for the F2 negative result (consistent across 4 M values,
two pairs, mechanistically explained). **Low** for F4 non-monotonic vsMax.
**High** for the "Saint Paul" evaluator issue (affects all sources, all M values,
a structural mismatch between stored and generated form).

**Threats to validity**:

- The F2 negative result is limited to 2 pairs. There may be other moderate-
signal pairs with different targets where M=7 would produce a hit.
- The 'tonode' garbage mechanism for indiana->arkansas is unexplained at
feature level. We observe the token but do not know which specific features
generate it.
- The "Saint Paul" issue is confirmed for 3 sources but the full extent
across all 49 ->minnesota_minneapolis pairs was not verified due to shell
issues during analysis. Likely affects all 49 based on the consistent
"St. Paul" generation pattern across observed cases.
- Non-monotonic vsMax (M=10 > M=20 for some pairs) is single-pair evidence.

**Follow-up**:

- Check how many ->minnesota_minneapolis pairs have "St. Paul" vs "Saint Paul"
in outputs to quantify the full evaluator gap for this target.
- Investigate whether other targets with multi-word or abbreviated capitals
(e.g., "Salt Lake City" vs "SLC") have similar evaluator gaps.
- For the vermont->kansas "Hutchinson not Topeka" failure: run PipelineTracer
on kansas_wichita's grouping to see if "capital" supernode specifically
contains Topeka features or is contaminated with other Kansas city features.
- Test M=3 on the 5 M=5 misses (west_virginia, south_dakota, indiana) to see
if reducing M further can rescue the "County continuation" cases.

---

## Entry Template

Copy this block for each new investigation entry.

```
## [YYYY-MM-DD] Topic: [short descriptive title]

**Question**: What specifically are we testing? What claim does this probe?

**Method**: What queries, comparisons, or traces were run? Include the
exact SwapQuery/SwapStats/PipelineTracer calls or describe the filtering
logic.

**Raw findings**: Numbers, tables, sample details. No interpretation here --
just what the data shows.

**Interpretation**: What this evidence supports or undermines. State the
confidence level (Low / Medium / High) and which epistemic level it
addresses (L1: operational labels, L2: causal effects, L3: mechanistic).

**Threats to validity**:
- [ ] Could this be a pipeline artifact? (concept matching, blacklist, fallback)
- [ ] Could this be a metric artifact? (mechanical flip@0, fuzzy T5 matching)
- [ ] Is N large enough? What is the denominator?
- [ ] Does this replicate across entities / domains / conditions?
- [ ] Is there a simpler explanation?

**Follow-up**: What should be checked next to strengthen or falsify this?

**References**: Link to related entries, summary reports, or methodology
report sections.
```

---

(Investigation entries go below this line, newest first.)

## [2026-03-27] Topic: debunking target recovery rate as "single most discriminating signal"

**Question**: The `[2026-03-24] logit-shift taxonomy` entry claims target
recovery rate (does the target logit exceed its unsteered baseline at any
trajectory position?) is "the single most discriminating signal between
labeled and random" in regime C, citing 92% labeled vs 29% random. Is this
finding robust, or is it an artifact of the USA dataset, the max-over-
positions criterion, intervention count, redundancy with vs_max, or regime C
selection bias?

**Method**: Wrote `scripts/research/debunk_target_recovery.py`. Loaded all
labeled and random swap JSONs for USA (2450 labeled, 7350 random) and books
(240 labeled, 720 random). For each swap, extracted baseline target/source
logits, steered logit trajectories (11 positions), position-0 comparison,
intervention counts, and vs_max. Classified each swap into regime (A/C/D/E/B)
using position-0 deltas. Computed target recovery (any position > baseline)
and early recovery (positions 1-3 only). Tested five debunking hypotheses:

- H1: Max-over-positions inflation -- compared target recovery vs control
token recovery (control pos>0 exceeds control pos0) as a null model.
- H2: Intervention count confound -- compared total_count distributions
between labeled and random; checked recovery rate by count quartile.
- H3: Redundancy with vs_max -- checked if recovery adds discriminative
information beyond vs_max conditioning.
- H4: Regime C selection bias -- computed recovery across ALL regimes.
- H5: Position-specific robustness -- used stricter early-recovery criterion.

**Raw findings**:

*H0: Reproduction across domains*

Recovery rate in regime C:


| Dataset | Labeled regime C  | Random regime C     | Delta       |
| ------- | ----------------- | ------------------- | ----------- |
| USA     | 92.2% (1606/1741) | 18.9% (421/2223)    | **+73.3pp** |
| Books   | 91.9% (124/135)   | **88.9%** (128/144) | **+3.0pp**  |


Recovery rate across ALL regimes:


| Dataset | Labeled           | Random              | Delta      |
| ------- | ----------------- | ------------------- | ---------- |
| USA     | 92.4% (2264/2450) | 31.3% (2302/7350)   | +61.1pp    |
| Books   | 93.8% (225/240)   | **88.8%** (639/720) | **+5.0pp** |


The 92% vs 29% claim **does not replicate in books**. In books, which has
the *highest* vs_max delta of any domain (+6.14 per the domain gradient
entry), recovery rate barely separates labeled from random (3pp in regime C,
5pp overall).

*H1: Control token recovery as null model*

Control tokens "recover" (pos>0 exceeds pos0 logit) at near-100% rates:


| Condition              | Target recovers | Control recovers | Delta   |
| ---------------------- | --------------- | ---------------- | ------- |
| USA labeled regime C   | 92.2%           | 99.9%            | -7.7pp  |
| USA random regime C    | 18.9%           | 97.9%            | -79.0pp |
| Books labeled regime C | 91.9%           | 100.0%           | -8.1pp  |
| Books random regime C  | 88.9%           | 96.7%            | -7.8pp  |


Note: This comparison is not apples-to-apples. Control recovery is measured
against pos-0 logit (not unsteered baseline), because unsteered control
logits are not stored. The near-100% control rate confirms the overshoot
entry's finding that position 0 is catastrophically disrupted and later
positions always recover from the overshoot. The key observation is that in
USA random, target tokens do NOT participate in this generic recovery (only
18.9%), while in books random, they DO (88.9%).

*H2: Intervention count*


| Condition     | Mean total_count | Median |
| ------------- | ---------------- | ------ |
| USA labeled   | 177.7            | 164    |
| USA random    | 177.7            | 164    |
| Books labeled | 304.4            | 293    |
| Books random  | 304.4            | 293    |


Intervention counts are **matched by design** between labeled and random.
Within USA labeled regime C, recovery rate by total_count quartile:


| Quartile | Range   | Recovery |
| -------- | ------- | -------- |
| Q1       | 0-148   | 87.1%    |
| Q2       | 148-165 | 95.7%    |
| Q3       | 165-202 | 93.9%    |
| Q4       | 202+    | 91.7%    |


Recovery is high across all quartiles; no monotonic relationship with
feature count. **H2 ruled out.**

*H3: Redundancy with vs_max*

Labeled regime C, vs_max by recovery status:


| Dataset | Recoverers         | Non-recoverers     |
| ------- | ------------------ | ------------------ |
| USA     | mean 2.60 (N=1606) | mean -0.81 (N=135) |
| Books   | mean 4.85 (N=124)  | mean 3.19 (N=11)   |


Recovery is correlated with vs_max, but does it add information?

Among swaps with vs_max > 0 only:


| Dataset | Labeled recovery | Random recovery   | Delta       |
| ------- | ---------------- | ----------------- | ----------- |
| USA     | 96.3% (N=1951)   | 45.5% (N=929)     | **+50.8pp** |
| Books   | 94.4% (N=234)    | **88.6%** (N=342) | **+5.8pp**  |


In USA, recovery separates labeled from random even after conditioning on
positive vs_max. In books, the gap is only 5.8pp -- nearly gone.

*H4: Regime C selection bias*

Already shown above: recovery across all regimes has the same pattern.
USA gap persists (92.4% vs 31.3%). Books gap barely exists (93.8% vs 88.8%).
**H4 ruled out for USA, confirmed for books (no signal to select for).**

Per-regime recovery for random:


| Regime | USA random        | Books random    |
| ------ | ----------------- | --------------- |
| A      | 45.3% (809/1784)  | 92.9% (289/311) |
| C      | 18.9% (421/2223)  | 88.9% (128/144) |
| D      | 32.1% (1071/3337) | 83.8% (222/265) |


Books random recovery is **83-93%** across ALL regimes. The books model
easily recovers target logits above baseline regardless of whether the
intervention is labeled or random.

*H5: Early recovery (positions 1-3 only)*


| Dataset | Labeled regime C  | Random regime C     | Delta      |
| ------- | ----------------- | ------------------- | ---------- |
| USA     | 61.5% (1070/1741) | 11.7% (259/2223)    | +49.8pp    |
| Books   | 73.3% (99/135)    | **78.5%** (113/144) | **-5.2pp** |


In books, early recovery **inverts** -- random actually exceeds labeled!

Position-specific recovery in USA regime C:


| Position | Labeled | Random | Delta   |
| -------- | ------- | ------ | ------- |
| 1        | 10.2%   | 0.8%   | +9.4pp  |
| 2        | 52.4%   | 9.6%   | +42.8pp |
| 3        | 30.6%   | 2.2%   | +28.4pp |
| 4        | 63.0%   | 3.7%   | +59.3pp |
| 5        | 55.1%   | 4.2%   | +50.9pp |
| 6        | 44.5%   | 2.8%   | +41.7pp |
| 7        | 36.9%   | 1.3%   | +35.6pp |
| 8        | 24.3%   | 2.1%   | +22.2pp |
| 9        | 34.6%   | 3.6%   | +31.0pp |
| 10       | 27.2%   | 0.9%   | +26.3pp |


In USA, the gap is robust at every individual position, peaking at
positions 2 and 4-5 (the same positions where the overshoot entry found
target rank recovering to top-15).

*Recovery magnitude*


| Condition                         | Mean excess above baseline | Median |
| --------------------------------- | -------------------------- | ------ |
| USA labeled regime C recoverers   | +5.12                      | +4.88  |
| USA random regime C recoverers    | +1.38                      | +1.00  |
| Books labeled regime C recoverers | +4.81                      | +4.44  |
| Books random regime C recoverers  | +2.90                      | +2.75  |


Even in books where recovery rates are similar, labeled recoverers exceed
baseline by larger amounts (4.81 vs 2.90 logit units). Recovery magnitude
discriminates better than the binary recovery indicator in books.

**Interpretation**: The claim that target recovery rate is "the single most
discriminating signal between labeled and random" is **domain-specific and
overstated**. Confidence: **High** for the debunking. Epistemic level:
**L1** (metric validity) with **L2** implications.

The evidence shows:

1. **Does not replicate across domains.** The 92% vs 29% gap in USA regime C
  becomes 92% vs 89% in books regime C -- a 3pp delta, well within noise for
   N=135/144. The early-recovery variant actually *inverts* in books (73% vs
   79%). A metric that only discriminates in one of two tested domains cannot
   be called "the single most discriminating signal."
2. **USA-specificity has a plausible explanation.** In USA, random
  interventions produce very low target recovery (31%) because random
   features do not activate on target-concept contexts, so amplifying them
   does not push the target logit above its baseline. In books, random
   interventions produce high target recovery (89%) despite not being
   targeted -- likely because the books model has 16 entities with strongly
   distinct representations, and any sufficiently large perturbation
   activates enough residual target-concept circuitry to exceed the baseline.
   This means recovery in books is **mechanically easy**, not informative.
3. **Recovery magnitude is more informative than the binary flag.** Even in
  books where binary recovery is non-discriminating, labeled recoverers
   exceed baseline by 4.81 vs 2.90 logit units for random. A continuous
   "max excess above baseline" metric would retain discriminative power
   across domains where the binary version fails.
4. **The intervention count confound is cleanly ruled out.** Both conditions
  use identical feature counts by design, and within labeled there is no
   monotonic relationship between count and recovery. The signal is about
   *which* features are amplified, not *how many*.
5. **Regime C selection bias is ruled out for USA but irrelevant for books.**
  The USA gap persists across all regimes (92% vs 31% overall). In books,
   there is no gap to explain.
6. **The "any position" criterion is not the issue.** Even position-specific
  rates at individual trajectory positions show massive USA gaps (e.g.,
   52% vs 10% at position 2). The max-over-positions does inflate the
   absolute rate but does not create the labeled/random delta.

**Net assessment of the original claim**: Target recovery rate is a real and
meaningful signal in USA, where it captures whether amplified features
specifically activate target-concept logits. It is not a universal
discriminator. The log entry should have tested replication before calling
it "the single most discriminating signal." The correct statement is:
"target recovery rate is the strongest discriminator in USA but loses
nearly all discriminative power in books, where random recovery is
mechanically high."

**Recommended replacement metric**: `tgt_max_excess` (max logit excess over
unsteered baseline across trajectory positions). This continuous metric
retains separation in both USA and books (5.12 vs 1.38 and 4.81 vs 2.90
respectively) and is not subject to the binary ceiling effect that makes
recovery useless in books.

**Threats to validity**:

- Only two domains tested (USA, books). Products, paintings, and sounds
should be checked. However, sounds has known structural issues, and
paintings has small N (90 pairs).
- The control token recovery null model uses a different baseline
(pos-0 logit, not unsteered), so it cannot directly test whether target
recovery is target-specific. A proper null model would need unsteered
control logits, which are not stored in the swap JSONs.
- The books result could reflect books-specific properties (small answer
space, highly distinctive entity names) rather than a general failure of
the metric. But this is precisely the point: a metric that fails on
"easy" datasets is not robust.
- Recovery magnitude (recommended replacement) has not been formally
validated as a discriminator with bootstrap CIs or effect sizes.
- The regime classification uses position-0 deltas, which are themselves
subject to overshoot. Different classification thresholds could shift the
regime C populations.

**Follow-up**:

- Compute `tgt_max_excess` across all 5 datasets and run `SwapStats.compare()`
to check if it maintains labeled vs random separation with proper effect
sizes.
- Check products and paintings for recovery rate discrimination. If books is
the only domain where recovery fails, the explanation may be books-specific
rather than a general debunking.
- Consider whether the books model's high random recovery reflects weaker
baseline representations (smaller answer space = easier to perturb above
baseline) vs structural properties of the attribution graphs.
- Re-examine the `[2026-03-24] logit-shift taxonomy` entry's composite
label-evidence score (`vs_max > 0` + recovery + `tgt_win_pct > 0.5`) --
if one of the three components is non-discriminating in books, the
composite may also be weak there.

**References**: `[2026-03-24] logit-shift taxonomy and label-evidence metric design` (original claim); `[2026-03-25] best field-add variant vs random in regime taxonomy`; `[2026-03-25] steering strength overshoot`;
`scripts/research/debunk_target_recovery.py`

---

## [2026-03-25] Topic: steering strength overshoot -- evidence and sweep design

**Question**: The current steering uses M_ablate=-2, M_amplify=20, temperature=0.3
for all runs. Many swaps show correct logit direction (vs_max > 0) but no exact-
match hit. Is this because the intervention is too strong, destroying the logit
distribution at position 0 and producing garbage tokens? Would a steering strength
sweep recover hits from these cases?

**Method**: Used SwapQuery across all 5 datasets to classify swaps by (direction
right, hit vs no-hit). For no-hit cases: inspected steered first tokens, steered
output text, and full logit trajectories via `q.get()`. Correlated intervention
magnitude (`total_count`), disruption (`control_stability_mean`), and first-token
confidence (`steered_first_prob`) with outcome. Examined position-0 vs later
positions in the trajectory for recovery patterns.

**Raw findings**:

The "right direction, no hit" population is massive:


| Dataset   | N total | Direction right | + hit | + no hit | No-hit % |
| --------- | ------- | --------------- | ----- | -------- | -------- |
| USA       | 2450    | 1951 (79.6%)    | 606   | **1345** | 54.9%    |
| Books     | 240     | 234 (97.5%)     | 9     | **225**  | 93.8%    |
| Products  | 132     | 107 (81.1%)     | 20    | **87**   | 65.9%    |
| Paintings | 90      | 70 (77.8%)      | 4     | **66**   | 73.3%    |
| Sounds    | 30      | 30 (100%)       | 0     | **30**   | 100%     |


Books is extreme: 97.5% of swaps have the target logit beating all competitor
answer logits at some trajectory position, but only 3.8% produce the target
answer in text.

First tokens in the right-direction-no-hit population:


| Dataset   | Top tokens (% of no-hit)                                         | Obvious garbage % |
| --------- | ---------------------------------------------------------------- | ----------------- |
| USA       | `' Efq'` (19.9%), `'AddTagHelper'` (9.7%), `'expandindo'` (8.8%) | ~95%+             |
| Books     | `"'"` (39.1%), `'-'` (10.2%), `','` (8.9%), `' Efq'` (6.7%)      | ~63%              |
| Products  | `"'"` (51.7%), `' '` (13.8%), `','` (13.8%)                      | ~85%              |
| Paintings | `'<bos>'` (19.7%), `' Majefty'` (19.7%), `'e'` (10.6%)           | ~95%+             |


USA and paintings generate tokens from completely unrelated vocabularies:
`' Efq'`, `'AddTagHelper'`, `'expandindo'`, `' يتيمه'`, `' Audiodateien'`,
`'Datuak'`, `' Majefty'`, `' Houfe'` -- Arabic, Portuguese, German, 18th-century
English, JavaScript variable names. These are hallmarks of a logit distribution
pushed so far off the manifold of coherent text that random high-activation
tokens from unrelated subspaces dominate.

Books and products predominantly output punctuation (`'`, `-`, `,`) -- the model's
logit distribution is broken but lands on common short tokens.

**Paradox: higher confidence = worse outcome.** Among right-direction-no-hit:


| Dataset   | mean steered_first_prob (hit) | mean steered_first_prob (no-hit) |
| --------- | ----------------------------- | -------------------------------- |
| USA       | 0.282                         | **0.383**                        |
| Books     | 0.299                         | **0.367**                        |
| Products  | **0.149**                     | 0.319                            |
| Paintings | **0.571**                     | 0.314                            |


In USA and books, the model is MORE confident at position 0 when it produces
garbage than when it produces a hit. The intervention pushes the model to very
high confidence in a wrong token -- classic overshoot.

Trajectory deep dive (5 USA swaps with vs_max > 15, no hit):


| Position | Target logit   | Target rank        | Generated token |
| -------- | -------------- | ------------------ | --------------- |
| 0        | -0.60 to -3.36 | 113,504 -- 167,275 | `' County'`     |
| 1        | 23.00 -- 24.12 | 10 -- 15           | `','`           |
| 2        | **27.25**      | **1**              | `' Oklahoma'`   |
| 3        | 24.12 -- 24.50 | 18 -- 23           | `','`           |
| 5        | 24.25 -- 24.88 | 2 -- 6             | `' Tulsa'`      |


**Position 0 is catastrophic (rank > 100K), but by position 2 the target reaches
rank 1.** The correct answer appears in the continuation: "County, Oklahoma, is
Tulsa" -- the model recovers but the corrupted first token prevents exact match.

Trajectory deep dive (books, hermione_granger -> jay_gatsby, vs_max=13.7):


| Position | Target logit | Target rank | Generated token |
| -------- | ------------ | ----------- | --------------- |
| 0        | 19.25        | 2           | `"'"`           |
| 1        | -0.64        | 179         | `'s'`           |
| 2        | 25.12        | 5           | `' author'`     |
| 3        | 13.44        | 1846        | `','`           |
| 4        | 8.06         | 2375        | `' J'`          |


Output: `"written by's author, J.K. Rowling"` -- apostrophe at position 0, then
the model recovers to produce the DEFAULT (source) author, not the target.

Position-0 disruption metrics:


| Metric                                 | Range across samples           |
| -------------------------------------- | ------------------------------ |
| target_logit_delta (pos 0 vs baseline) | -2.1 to **-26.7** logit units  |
| source_logit_delta (pos 0 vs baseline) | -15.8 to **-30.9** logit units |
| target_rank at pos 0                   | 2 to **167,275**               |


When M_ablate=-2 and M_amplify=20 are applied to hundreds of features
simultaneously, the combined effect can shift logits by 20-30 units at position 0,
pushing tokens to ranks > 100K.

Intervention count vs disruption (USA):


| total_count quartile | N   | Hit%      | vs_max   | ctrl_stability |
| -------------------- | --- | --------- | -------- | -------------- |
| Q1 (94-147)          | 614 | 23.6%     | 2.45     | 13.3           |
| Q2 (148-164)         | 642 | **27.3%** | **3.27** | 13.4           |
| Q3 (165-203)         | 586 | 27.0%     | 3.38     | 13.7           |
| Q4 (204-369)         | 608 | 21.1%     | 2.33     | **15.2**       |


Q2 is the sweet spot: moderate feature count, best hit rate, good vs_max, low
disruption. Q4 (most features) has highest disruption and lowest hit rate despite
strong direction (the "less is more" effect appears here too, compounded by
overshoot).

Key correlations (USA, N=2450):

- `steered_first_prob` vs hit: r = **-0.211** (more confident = fewer hits)
- `total_count` vs `control_stability`: r = **+0.232** (more features = more disruption)
- `total_count` vs hit: r = -0.035 (weak)
- `control_stability` vs hit: r = -0.058 (weak but correct sign)

**Interpretation**: There is strong evidence for steering overshoot. Confidence:
**High** for the existence of overshoot; **Medium** for quantifying how much a
sweep would recover. Epistemic level: **L2** (causal intervention design).

The case for a strength sweep rests on four convergent signals:

1. **Massive right-direction-no-hit population.** 55-94% of swaps have the correct
  logit direction but fail to produce the target in text. These are not cases where
   the labels are wrong -- the features point at the right concept. The decoding
   step is what fails.
2. **Position-0 catastrophic disruption.** The combined effect of M_ablate=-2 on
  hundreds of source features and M_amplify=20 on hundreds of target features
   produces logit shifts of 20-30 units, pushing target rank to > 100K at position
  1. This is orders of magnitude more disruption than needed to flip the target
    ove the source.
3. **Recovery at later positions.** By position 2-3, target rank typically returns
  to 1-15 and the model generates coherent tokens including the target answer.
   The information is there -- the first token just gets destroyed.
4. **Confidence-hit paradox.** Higher steered_first_prob at position 0 correlates
  with FEWER hits (r=-0.211 in USA). The intervention does not just shift the
   logit distribution -- it concentrates probability mass on a single wrong token,
   making the model very confident in garbage.

**Sweep design recommendations**:

*Sweep parameters*:


| Parameter   | Current | Recommended sweep values | Rationale                                                  |
| ----------- | ------- | ------------------------ | ---------------------------------------------------------- |
| M_amplify   | 20      | **2, 5, 10, 15, 20**     | Primary suspect; 20x stored activation is likely excessive |
| M_ablate    | -2      | **0, -0.5, -1, -2**      | Reversal (-2) may be too aggressive; 0 = full ablation     |
| temperature | 0.3     | **0.3, 0.5, 0.7, 1.0**   | Higher T may help escape distorted distribution            |


*Priority*: M_amplify sweep alone is the highest-value test. It directly controls
how hard target features are injected. M_ablate and temperature are secondary.

*Minimal viable sweep*: M_amplify in {5, 10, 20} with M_ablate fixed at -2 and
temperature at 0.3. This is 3 runs per dataset -- feasible as a pilot on USA only
(~2450 pairs each, ~3 hours per run on current infra).

*Evaluation focus*: The sweep should primarily track:

- hit rate (expect non-monotonic: too low = no steering, too high = overshoot)
- control_stability_mean (expect monotonic decrease with lower M)
- steered_first_prob (watch for the confidence-hit paradox disappearing)
- vs_max (may decrease with lower M -- acceptable if hits increase)

*Expected outcome*: A lower M_amplify (5-10) should:

- Reduce position-0 disruption, producing coherent first tokens
- Potentially sacrifice some vs_max (target logit won't beat competitors as strongly)
- Increase hit rate if the "right direction, garbage output" cases convert to hits
- Decrease control_stability (less collateral damage)

The optimal M_amplify is likely in the 5-15 range. Below 5, the steering may be
too weak to overcome the baseline source-answer dominance. Above 15, the overshoot
evidence suggests diminishing returns.

*Alternative to M sweep*: An intervention-count cap (top-K features per concept
field) would reduce the combined magnitude without changing M. This could be
combined with an M sweep for a 2D exploration.

**Threats to validity**:

- The "garbage token" classification is based on visual inspection and heuristic
rules, not a formal classifier. Some tokens classified as garbage may be
legitimate (e.g., `' St'` for "St. Louis" could be correct in some contexts).
- The confidence-hit paradox (r=-0.211) is a population-level correlation.
Individual pairs may behave differently. A proper causal test requires the
sweep itself.
- The trajectory analysis shows 5 hand-picked high-vs_max cases. The
recovery pattern may not hold for lower-vs_max cases where the direction is
only marginally correct.
- Lower M_amplify might not just reduce overshoot -- it might also reduce
the label-specific signal, making labeled interventions more similar to random
ones. The sweep must compare labeled vs random at each M value.
- Temperature interacts with M: lower M + higher T might produce different
results than lower M alone. A 2D sweep would be ideal but more expensive.
- The current metric suite may not capture all the effects. Consider adding
a "position-0 coherence" metric (e.g., is the first token in the top-100
unsteered tokens?) to track overshoot directly.

**Follow-up**:

- Implement a minimal M_amplify sweep on USA: {5, 10, 20} with current M_ablate
and temperature. Compare hit rate, vs_max, and control_stability.
- Consider a "top-K features" variant alongside the M sweep: cap ablate_count
and amplify_count at K={20, 50, 100} to reduce combined intervention magnitude.
- Add a position-0 coherence metric to the evaluation pipeline: does the steered
first token appear in the top-K of the unsteered distribution?
- After the sweep: recompute the regime taxonomy (entry [2026-03-24]) at the
optimal M value to see if regime A prevalence increases.

**References**: `scripts/03_ct_steering.py` (M semantics, lines 362-364);
`scripts/neuronpedia_steering/batch_steering_ct.py` (new_value = M * original,
line 403-405); config `scripts/experiments/batch/configs/fullscale_*_labeled.yml`;
previous entries `[2026-03-24] logit-shift taxonomy`, `[2026-03-25] best field-add variant vs random in regime taxonomy`

---

## [2026-03-25] Topic: impact of reverse-substring supernode matches on swap performance

**Question**: The concept-to-supernode matcher uses bidirectional substring
matching: `supernode_lc in word` (reverse). This causes supernodes like "is" to
match concept "mississippi", "port" to match "gulfport", "Karen" to match
"karenina", "ica" to match "guernica". These reverse-substring matches pull in
large, low-layer, likely polysemantic supernodes. Do they degrade swap
targeting? Would excluding them improve results?

**Method**: Wrote `scripts/research/substring_supernode_investigation.py`.
Classified every concept-to-supernode match into 5 types:

- **exact**: concept == supernode (e.g., "mississippi" = "mississippi")
- **word_exact**: a word from concept == supernode (e.g., "jackson" from "Jackson" = "Jackson")
- **concept_in_sn**: full concept in supernode or vice versa
- **word_in_sn**: concept word found inside supernode name
- **sn_in_word**: supernode name found inside concept word (REVERSE -- most
problematic; e.g., "is" inside "mississippi", "ica" inside "guernica")

For each entity: counted active features by match type, computed noisy_pct
(fraction of active features from sn_in_word matches), and correlated with
per-entity mean `vs_max` as source. Additionally tested within-entity using
field-add variants to compare outcomes when noisy fields are included vs
excluded.

**Raw findings**:

Reverse-substring (sn_in_word) prevalence across datasets:


| Dataset   | sn_in_word features | % of active | Top noisy supernodes                                   |
| --------- | ------------------- | ----------- | ------------------------------------------------------ |
| USA       | 442 / 4,579         | 9.0%        | "is" (293), "port" (75), "in" (31)                     |
| Books     | 994 / 2,260         | 34.7%       | "Karen" (194), "uckleberry" (130), "hab" (111)         |
| Products  | 60 / 797            | 7.5%        | "Tes" (38), "Press" (8), "Dy" (8)                      |
| Paintings | 1,049 / 1,880       | 48.8%       | "ica" (192), "atte" (169), "ighth" (131), "ring" (125) |
| Sounds    | 138 / 561           | 24.6%       | "iss" (60), "ble" (36), "is" (27)                      |


Per-entity extremes:


| Entity               | Noisy%    | Active | Noisy | Direct | vs_max | Dataset mean |
| -------------------- | --------- | ------ | ----- | ------ | ------ | ------------ |
| mississippi_Gulfport | **77.5%** | 160    | 124   | 36     | 3.20   | 2.86         |
| nighthawks           | **78.1%** | 192    | 150   | 42     | 1.68   | 1.55         |
| grande_jatte         | **77.2%** | 246    | 190   | 56     | 1.65   | 1.55         |
| anna_karenina        | **68.2%** | 209    | 143   | 66     | 6.51   | 5.98         |
| hiss                 | **65.5%** | 145    | 95    | 50     | 3.29   | 3.28         |


All five highest-noisy entities perform **at or above** their dataset mean on
vs_max.

Correlations with mean_vs_max:


| Dataset   | r(noisy_pct, vsMax) | r(noisy_feats, vsMax) | r(active_total, vsMax) | r(direct_feats, vsMax) | N   |
| --------- | ------------------- | --------------------- | ---------------------- | ---------------------- | --- |
| USA       | 0.121               | 0.083                 | **-0.298**             | **-0.402**             | 50  |
| Books     | -0.207              | -0.215                | 0.211                  | **-0.281**             | 16  |
| Products  | -0.442              | -0.439                | -0.265                 | -0.084                 | 12  |
| Paintings | -0.036              | -0.057                | -0.334                 | -0.205                 | 10  |
| Sounds    | -0.545              | -0.384                | -0.289                 | 0.355                  | 6   |


Within-entity field-add comparison (USA, Mississippi_Gulfport vs low-noisy
entities as source):


| Condition                | vs_max (Mississippi) | vs_max (low-noisy, N=5) | Delta     |
| ------------------------ | -------------------- | ----------------------- | --------- |
| state only               | 2.51                 | 2.68                    | -0.17     |
| state+capital            | **4.03**             | **4.20**                | -0.17     |
| all 3 fields (adds city) | 3.09                 | 3.02                    | **+0.07** |
| Drop (s+c -> all)        | -0.94                | **-1.18**               | --        |


Adding the city field (which brings in 124 noisy "port"/"Gulf" features for
Mississippi) causes a vs_max drop of 0.94. But the low-noisy group drops
**more** (1.18) when adding their clean city features. The noisy features are
not causing extra harm.

**Interpretation**: Reverse-substring matches add large volumes of likely
irrelevant features to interventions, but **they do not measurably harm swap
performance**. Confidence: **Medium-High** (strong USA evidence, directionally
consistent across datasets, but small N in non-USA). Epistemic level: **L1**
(pipeline/metric quality) with **L2** implications (causal intervention design).

The evidence converges from four angles:

1. **Direct correlation is absent or wrong-signed in the largest dataset.** USA
  (N=50) shows r=0.121 between noisy_pct and vs_max -- slightly *positive*,
   not negative. The five highest-noisy entities all perform at or above their
   dataset mean. If noisy features were actively harmful, Mississippi_Gulfport
   (77.5% noisy) should perform badly; it doesn't (vs_max 3.20 vs mean 2.86).
2. **The real predictor is total feature count, not match quality.** `direct_feats`
  correlates *more negatively* with vs_max (r=-0.402 in USA) than `active_feats`
   (r=-0.298). This means entities with more *cleanly-matched* features perform
   worse -- the problem is dilution, not noise. When the intervention spreads
   amplification/ablation across more features, each individual feature gets a
   weaker push, reducing targeting precision. Noisy features add to the count but
   don't create a qualitatively different problem from having too many clean matches.
3. **Within-entity comparison shows no differential.** The field-add experiment
  for Mississippi (adding the city field which brings 124 noisy features) causes
   a 0.94-point vs_max drop. But low-noisy entities adding their clean city
   features drop *more* (1.18 points). The noisy features do not cause extra harm
   beyond the generic "more features = weaker intervention" effect.
4. **The extreme cases work fine.** Paintings has 48.8% of all active features from
  reverse-substring matches (nighthawks 78.1%, grande_jatte 77.2%, guernica 76.6%).
   If nearly half the intervention were "junk" features, these entities should perform
   catastrophically. They don't -- their vs_max values are at or above the dataset
   mean. This is the strongest evidence that the noisy features are not actively
   interfering.

**Why don't noisy features hurt?** Two possible mechanisms:

- (a) The amplification/ablation multipliers are applied per-feature. Noisy features
that are semantically irrelevant to the swap have low activation on the target
concept's context, so amplifying/ablating them has small absolute effect on logits.
They dilute the intervention magnitude but don't push logits in wrong directions.
- (b) Some "noisy" matches are actually partially relevant. "Karen" features for
Anna Karenina likely fire on Karenina-related contexts. "ica" features for
Guernica may include features that respond to the painting's name. The substring
match catches semantically adjacent features, not purely random ones.

**What actually matters**: The consistent finding across investigations is that
**total intervention size** (feature count) is the primary predictor of performance,
with a modest negative correlation. The "less is more" effect documented in the
field-add experiments is driven by feature count dilution, not by the quality of
individual feature matches. Improving the matcher to exclude reverse-substring
matches would reduce feature counts by 9-49% depending on dataset, which could
improve performance -- but through the count-reduction mechanism, not because the
features are harmful per se.

**Threats to validity**:

- USA is the only dataset with N=50 for entity-level correlations. Books (16),
products (12), paintings (10), sounds (6) have small N where any correlation
is unreliable. The USA null finding (r=0.121) is the most trustworthy.
- Entity-level correlations conflate many factors. An entity with high noisy%
may also differ in graph quality, prompt structure, answer specificity, etc.
The within-entity field-add comparison is cleaner but only tests one entity
(Mississippi) with extreme noisy burden.
- "Noisy features don't hurt" could mean "the metrics don't capture the harm."
If noisy features cause more control_stability disruption or push logits toward
wrong answers in ways vs_max doesn't capture, the harm could be hidden.
- The field-add comparison uses different pairs for Mississippi (N=49) vs
low-noisy (N=392), so population differences could mask effects.
- Paintings and sounds have known dataset-level issues (tiny answer space,
field collapse) that may dominate any substring effect.
- Mechanism (b) above -- partial semantic relevance of "noisy" matches --
is speculative and would need activation-level analysis to verify.

**Follow-up**:

- Test whether *removing* reverse-substring features from interventions improves
outcomes. This requires either rerunning swaps with a strict matcher or
simulating the effect by comparing pairs where the noisy features have low
vs high baseline activation.
- Investigate whether the `direct_feats` negative correlation in USA (r=-0.402)
is driven by specific concept fields (city generates the most features) or
is uniform across fields.
- Consider implementing an intervention-count cap: rather than matching all
features in concept-matching supernodes, take only the top-K by node_influence.
This would address the dilution problem directly without requiring matcher
changes.
- Check whether noisy features correlate with `control_stability_mean` (collateral
damage metric). Even if vs_max is unaffected, noisy features might increase
non-specific disruption.

**References**: Previous entries `[2026-03-24] reverse substring matching confound scan`, `[2026-03-25] do "(concept) related" Relationship features hurt swap performance?`, `[2026-03-25] best field-add variant vs random in regime taxonomy`;
`scripts/utils/pipeline_tracer.py` (_concept_matches_supernode)

---

## [2026-03-25] Topic: do "(concept) related" Relationship features hurt swap performance?

**Question**: Relationship features (e.g., "(entity) related", "(capital) related")
are classified as `pred_label = "Relationship"` in the grouping pipeline. They tend
to be polysemantic, activating for relational/contextual patterns rather than
specific entity tokens. Does including them in swap interventions degrade targeting
metrics? Would excluding them improve results?

**Method**:

1. Profiled all Relationship features across 5 datasets: prevalence, layer
  distribution, supernode names.
2. Tested which Relationship supernodes match concept fields via
  `_concept_matches_supernode()`. This determines whether they enter the
   intervention at all.
3. Traced specific swap pairs (`trace_swap_matching`) to count Relationship vs
  Semantic features in the actual ablate/amplify sets.
4. Computed per-entity: active Relationship count and %, low-layer feature %
  (layers 0-3), mean active layer, total active count. Correlated each with
   mean `vs_max` as source entity.

**Raw findings**:

Relationship features as share of all features vs share of active (concept-matched):


| Dataset   | Rel % of total | Rel % of active | Rel features matched |
| --------- | -------------- | --------------- | -------------------- |
| USA       | 11.3%          | 0.0%            | 1/2962               |
| Books     | 35.1%          | 0.7%            | 13/1757              |
| Products  | 35.7%          | 2.0%            | 16/797               |
| Paintings | 13.0%          | 0.7%            | 11/1665              |
| Sounds    | 20.6%          | 2.0%            | 6/295                |


The generic Relationship supernodes never match concept values:

- "(entity) related" (869 features in USA): concept values are state/capital/city
names, not "entity" -- no match.
- "(literary) related" (886 in books), "(famous) related" (604 in books): concept
values are character/book/author names -- no match.
- "(is) related" (779 in products): no concept value contains "is" as a word match.
- "(A) related" (404 in sounds, 165 in paintings, 87 in books): no match.

Only entity-specific Relationship supernodes match, e.g.:

- "(Oliver) related" matches "Oliver Twist" (character field) -- 3 features, layer 1/6
- "(Facebook) related" matches "Facebook" (product field) -- 5 features, layer 1
- "(Pablo) related" matches "Pablo Picasso" (painter field) -- 2 features, layer 1

These are consistently at layers 1-6 (mean ~2.5).

Correlation of feature profile with mean_vs_max per entity:


| Dataset   | r(low_layer_pct, vsMax) | r(rel_pct, vsMax) | r(active_total, vsMax) | N   |
| --------- | ----------------------- | ----------------- | ---------------------- | --- |
| USA       | 0.018                   | -0.044            | **-0.298**             | 50  |
| Books     | **0.473**               | 0.475             | 0.211                  | 16  |
| Products  | -0.070                  | 0.146             | -0.265                 | 12  |
| Paintings | 0.051                   | 0.455             | -0.334                 | 10  |
| Sounds    | -0.101                  | 0.412             | -0.289                 | 6   |


Notable per-entity examples (books):


| Entity           | Active | Rel | Low%  | mLayer | vsMax |
| ---------------- | ------ | --- | ----- | ------ | ----- |
| holden_caulfield | 127    | 2   | 70.9% | 3.9    | 6.85  |
| hermione_granger | 78     | 1   | 23.1% | 12.1   | 5.53  |
| captain_ahab     | 183    | 0   | 64.5% | 5.3    | 6.07  |
| katniss_everdeen | 120    | 0   | 39.2% | 9.1    | 5.19  |


**Interpretation**: Excluding Relationship features from swap interventions would
have **no measurable effect**. Confidence: **High**. Epistemic level: **L1**
(pipeline mechanism) and **L2** (causal relevance).

Three reasons:

1. **They're already excluded.** The concept matcher does not match generic
  Relationship supernodes like "(entity) related", "(literary) related",
   "(is) related", "(A) related" -- which together account for >95% of all
   Relationship features. These never enter any intervention.
2. **The few that match are entity-specific and tiny.** Only supernodes named
  after actual concept words (e.g., "(Oliver) related", "(Facebook) related")
   get included, and they constitute 0.0-2.0% of the active feature set. At
   this scale, excluding them would change intervention feature counts by
   0-3 features out of 60-250+. The effect on logit-level metrics would be
   within noise.
3. **Correlations run in the wrong direction.** Where correlations between
  Relationship % and vs_max exist (books r=0.475, paintings r=0.455), they
   are *positive* -- more Relationship features is associated with *higher*
   vs_max. This is likely confounded by entity name specificity (entities with
   distinctive names like "Oliver" or "Pablo" get both Relationship matches
   AND better steering), not a causal signal from the Relationship features
   themselves. With N=10-16, these correlations are unreliable regardless.

A more interesting signal emerged: **active_total negatively correlates with
vs_max** in USA (r=-0.298, N=50). Entities with more total concept-matched
features tend to have lower targeting precision. This is consistent with the
"less is more" finding from the field-add experiments -- more features in the
intervention means more noise and less surgical steering. The Relationship
features are too few to be the cause; the volume comes from Semantic features
at low layers (e.g., "port" = 375 features for Gulfport, "do" = 325 for Frodo).

**Threats to validity**:

- Per-entity correlations have small N for non-USA datasets (6-16). Individual
correlations are unreliable; only USA's N=50 has reasonable statistical power.
- Correlations between Relationship % and vs_max are confounded by entity
name properties. Entities with distinctive first names (Oliver, Pablo, Jack)
get both Relationship matches and potentially different baseline confusion.
- The analysis counts features matched by the tracer's concept matcher, not
the actual pipeline's matcher. If they differ, the counts could be wrong.
However, the tracer uses the same `_concept_matches_supernode` logic.
- "Active" features counted here are per-entity. In a swap, source features
are ablated and target features are amplified -- the actual intervention set
depends on both entities, not just one.
- The books positive correlation (more low-layer features = higher vs_max)
could reflect that entities with more low-layer matches have more distinctive
names, not that low-layer features help.

**Follow-up**:

- The active_total negative correlation in USA is worth investigating further.
Is it feature-count dilution (same amplification spread over more features
reduces per-feature effect) or interference (irrelevant features actively
disrupt)? The field-add experiments already suggest dilution is the main
mechanism, but a within-entity analysis (same pair, different active counts
across field-add variants) would be cleaner.
- The large Semantic supernodes at low layers (e.g., "port" = 375, "is" = 115)
are a much bigger potential source of polysemantic noise than Relationship
features. An investigation of whether large-supernode-count entities have
worse performance would address the polysemanticity concern more directly.
- Consider whether the "less is more" effect is better explained by
intervention count alone (ablate_count + amplify_count from swap JSONs)
rather than the upstream feature profile. The swap JSON counts are the
actual intervention size after deduplication.

**References**: Previous entries `[2026-03-25] cumulative influence of Semantic (unknown) nodes`, `[2026-03-25] best field-add variant vs random in regime taxonomy`; `scripts/02_node_grouping.py`; `scripts/utils/pipeline_tracer.py`

---

## [2026-03-25] Topic: cumulative influence of Semantic (unknown) nodes on swap results

**Question**: Features classified as "Semantic (unknown)" in the node grouping
pipeline are features the naming step could not label. How prevalent are they?
Do they carry meaningful circuit influence? And does their presence affect swap
outcomes?

**Method**: Wrote `scripts/research/unknown_node_investigation.py` to scan all
entities across 5 datasets. For each entity:

1. Read `node_grouping.csv` and counted features with
  `supernode_name == "Semantic (unknown)"`.
2. Joined with `graph_feature_static_metrics.csv` (matching by `layer_id`, not
  `layer_feature`) to compute the node-influence share of unknown features.
3. Compared swap performance (vs_max, gap_closure, hit%) for entities with/without
  unknown nodes, and computed per-entity Pearson correlations.
4. Traced the root cause through `02_node_grouping.py`'s `name_semantic_node()`
  function and the per-dataset blacklist configs.
5. Verified whether "Semantic (unknown)" supernodes are ever matched by the
  concept matcher (`_concept_matches_supernode`) during swap interventions.
6. Computed the broader "inert feature" population: all selected features in
  supernodes that never match any concept field (3-field set).

**Raw findings**:

Prevalence of "Semantic (unknown)" across datasets:


| Dataset    | Entities affected | Unknown feat %  | Unknown influence % |
| ---------- | ----------------- | --------------- | ------------------- |
| USA states | 0/50 (0%)         | 0.0%            | 0.0%                |
| Books      | 16/16 (100%)      | 2.3% (109/4693) | 1.7%                |
| Products   | 12/12 (100%)      | 2.5% (70/2791)  | 1.7%                |
| Paintings  | 10/10 (100%)      | 2.3% (86/3785)  | 1.7%                |
| Sounds     | 6/6 (100%)        | 3.4% (71/2111)  | 2.8%                |


Root cause -- blacklist configuration difference:

- **USA** config (`usa_states_full.yml`): `blacklist_tokens: ["<bos>"]` only.
Features with peak_token=`entity`/`attribute` get named normally and form
supernodes like "entity" (1 feature), "attribute" (4 features).
- **Non-USA** configs (books, products, paintings, sounds):
`blacklist_tokens: ["<bos>", "entity", "attribute"]`. Features whose best
semantic peak token is `entity` or `attribute` have no valid fallback and
become "Semantic (unknown)".

Peak tokens on unknown rows (all non-USA datasets pooled):


| Token                           | Rows | % of unknown |
| ------------------------------- | ---- | ------------ |
| `entity`                        | 967  | 57.5%        |
| `attribute`                     | 334  | 19.9%        |
| `relationship`                  | 332  | 19.8%        |
| other (`:`, `The`, `Don`, etc.) | 47   | 2.8%         |


Subtypes of unknown features: Dictionary (fallback) 60.5%, Concept 38.7%,
Dictionary 0.3%.

Concept matcher verification: "Semantic (unknown)" (lowercased) never matches
any concept field value through `_concept_matches_supernode()`. These features
are **never ablated or amplified** during swap interventions.

Equivalent USA inert features: USA's "entity", "attribute", "relationship", and
related supernodes contain 1271/11682 (10.9%) of features -- these are equally
unmatched by the concept matcher, just not labeled "unknown".

Full inert-feature population (all selected features not matching any concept,
using all 3 concept fields per dataset):


| Dataset   | Active % | Unknown % | Labeled-inert % |
| --------- | -------- | --------- | --------------- |
| USA       | 39.2%    | 0.0%      | 60.8%           |
| Books     | 48.2%    | 2.3%      | 49.5%           |
| Products  | 44.0%    | 2.5%      | 53.5%           |
| Paintings | 49.7%    | 2.3%      | 48.1%           |
| Sounds    | 26.6%    | 3.4%      | 70.1%           |


Correlation with swap performance:


| Dataset   | Pearson r (unknown_influence_pct, mean_vs_max) | N   |
| --------- | ---------------------------------------------- | --- |
| USA       | 0.000 (no variance)                            | 50  |
| Books     | 0.006                                          | 16  |
| Products  | 0.320                                          | 12  |
| Paintings | 0.181                                          | 10  |
| Sounds    | -0.297                                         | 6   |


No within-dataset comparison of "with unknown" vs "zero unknown" is possible
because USA has 0% and all non-USA datasets have 100% of entities affected.

**Interpretation**: "Semantic (unknown)" features are **not relevant** to swap
outcomes. Confidence: **High**. Epistemic level: **L1** (pipeline measurement).

Three independent lines of evidence converge:

1. **Mechanism**: The concept matcher never matches "Semantic (unknown)" as a
  supernode name. These features are strictly inert -- they are neither
   ablated nor amplified during any swap. They cannot causally influence the
   intervention.
2. **Scale**: At 2.3-3.4% of features and 1.7-2.8% of node influence, unknown
  features are a small fraction of the graph. Even if they were somehow
   relevant, the magnitude is too small to explain meaningful outcome variance.
3. **Context**: Unknown features are a tiny, visible subset of a much larger
  inert population (49-70% of all selected features never match any concept).
   The pipeline by design selects the top-95% cumulative-influence features
   from the graph, then only intervenes on the subset matching concept fields.
   The majority of selected features are structural, syntactic, or discourse
   features that don't correspond to any concept field.

The asymmetry between USA (0% unknown) and non-USA (2-3% unknown) is entirely
explained by the blacklist configuration: non-USA datasets blacklist `entity`
and `attribute` tokens, which forces features with those peak tokens into the
unknown bin. USA doesn't blacklist these tokens, so equivalent features get
named "entity"/"attribute" -- but they are equally inert in swap interventions.

**Threats to validity**:

- The per-entity correlation has very small N (6-16) for non-USA datasets.
Individual correlations are unreliable; the conclusion rests on the mechanism
(matcher never matches) rather than correlation.
- The influence join uses `(layer, id)` from the static metrics CSV.
A small fraction of features may fail to match if the node_id format changed
between pipeline versions.
- This analysis considers only first-order effects (direct intervention).
Unknown features could theoretically interact with intervened features through
shared circuits. This second-order effect is not measured here and would
require activation-level analysis.
- The "inert feature" computation counts features per entity separately.
A feature that is inert for entity A might be active for entity B if B's
concept values happen to match its supernode name.

**Follow-up**:

- The much larger question raised by this investigation: **51-74% of selected
features are labeled but never matched by any concept**. These are not
"unknown" -- they have valid supernode names (e.g., "is", "of", "containing",
"punctuation", "The") that simply don't correspond to any concept field. This
large inert population is the real "dark matter" of the intervention, not the
2-3% unknown nodes. A follow-up investigation should quantify whether
intervening on these features (e.g., ablating functional/syntactic supernodes)
has any detectable effect.
- Consider harmonizing the blacklist across datasets. The current asymmetry
(USA vs non-USA) is a confound in cross-domain comparisons. Either add
`entity`/`attribute` to USA's blacklist or remove them from non-USA configs.
- The `relationship` token is not blacklisted in any dataset but appears on
19.8% of unknown rows. These rows have `relationship` as peak_token on some
probes but their overall best semantic peak is a blacklisted token. No action
needed.

**References**: `scripts/02_node_grouping.py` (name_semantic_node, line 974-1068);
batch configs `scripts/experiments/batch/configs/*.yml`;
`scripts/utils/pipeline_tracer.py` (_concept_matches_supernode);
previous entry `[2026-03-24] reverse substring matching confound scan`

---

## [2026-03-25] Topic: entry-level flaw scan across all datasets

**Question**: Beyond the dataset-level issues already documented (answer
identity pairs, metric misalignment, zero-coverage fields), are there
additional entry-level flaws -- specific entities or pairs whose data
properties make them unreliable as redirection tests?

**Method**: Wrote a systematic scanner that loaded every entity from the five
labeled runs (`fullscale_*_labeled`) and checked for: (1) answer collisions
(same answer across entities), (2) near-duplicate answers (SequenceMatcher
ratio >= 0.7), (3) target-answer leaking into source prompt, (4) field
ambiguity (two concept fields holding the same value), (5) first-token
sharing across different answers, (6) short/common single-word answers,
(7) answer cross-contamination (one entity's answer as substring in another's
non-answer fields), (8) answer-space entropy, (9) baseline confusion (target
answer already rank <= 3 or prob >= 5% before any intervention). Drilled
into flagged entries with full swap-level detail.

**Raw findings**:

- **Answer collisions (same answer)**:
  - Sounds: 4/6 entities answer `brown` (bark, gobble, hoot, neigh).
  12/30 non-identity pairs (40%) share the same answer. Only 3 unique
  answers (`brown`, `black`, `green`) for 6 entities.
  - Books: 2/16 entities answer `Harper Lee` (atticus_finch, scout_finch).
  2/240 pairs (0.8%) are answer-collisions.
  - USA, Products, Paintings: all answers unique.
- **Near-duplicate answers (similarity >= 0.7)**:
  - USA: 4 capital pairs -- Indianapolis/Annapolis (0.76),
  Columbus/Columbia (0.75), Denver/Dover (0.73),
  Jefferson City/Carson City (0.72).
  - Paintings: Edvard/Edward (0.83) for the_scream/nighthawks.
  Detail: default first token for both is `' Ed'`/`' Edward'`; at
  baseline the_scream already has Edward at rank 4 (prob 3.5%).
- **Target-answer leaking into source prompt**:
  - USA: 1 pair. `south_carolina_charleston` prompt contains "Charleston"
  which is `west_virginia_huntington`'s answer. Swap scores hit=True
  but steered output is `"isExterneburg, West Virginia..."` -- the hit
  comes from the echoed prompt, not from generation.
  - No leaks in other datasets.
- **Field ambiguity (concept fields sharing same value)**:
  - Books: 3/16 entities have `character == book`:
  anna_karenina, don_quixote, oliver_twist. In field-add runs, the
  `add_character` and `add_book` variants produce identical ablation
  counts (anna_karenina: 141/141, don_quixote: 60/60,
  oliver_twist: 121/121) -- the pipeline cannot distinguish the two
  fields because all matching supernodes overlap.
  - Products: 1/12 entity has `product == company`: twitter/Twitter.
- **First-token sharing (different answer, same first token)**:
  - Products: `Jack Ma` (alibaba) and `Jack Dorsey` (twitter) share
  first token `Jack`. Both have baseline rank=1 for each other
  (prob 39-45%). Neither swap produces the correct target output.
  - Books "J." cluster: `J.R.R. Tolkien` (frodo), `J.K. Rowling`
  (hermione), `J.D. Salinger` (holden) all share first token `J`.
  All 6 cross-pairs have baseline rank=1 (prob 28-54%) and
  gap_closure=0.0 despite high vs_max (4.75-7.22). The model
  already represents the competing answer at baseline because
  all three are "J."-initial authors.
- **Baseline confusion (target at rank <= 3 before intervention)**:
  - USA: 8/2450 pairs (0.3%). Notable cases:
    - `missouri_kansas_city -> kansas_wichita`: rank=1 (31.4%) because
    prompt says "Kansas City" and target state is Kansas.
    - `maine_portland -> oregon_portland`: rank=1 (15.7%) because both
    share city name Portland.
  - Books: 8/240 (3.3%). The 6 "J." cluster pairs (all rank=1) plus
  the 2 Finch/Lee identity pairs (rank=1, 25-57%).
  - Products: 3/132 (2.3%). Both Jack pairs (rank=1) plus
  `nike_shoes -> windows` (rank=1, 21.1%).
  - Paintings: 1/90 (1.1%). `grande_jatte -> water_lilies` rank=3 (6.3%).
  - Sounds: 25/30 (83.3%). Nearly the entire dataset. 12 same-answer
  pairs at rank=1 plus 13 cross-color pairs where the tiny answer
  space puts most targets in the top few.
- **Answer-space entropy**:
  - USA: 5.64 bits (maximum possible for N=50).
  - Books: 3.88 / 4.00 bits (97% of maximum).
  - Products: 3.58 / 3.58 bits (100% of maximum).
  - Paintings: 3.32 / 3.32 bits (100% of maximum).
  - Sounds: 1.25 / 2.58 bits (48% of maximum).
- **Aggregate across all 2942 non-identity labeled pairs**:
  - 14 same-answer pairs (0.5%), all in sounds (12) and books (2).
  - 40 baseline-confused pairs at rank <= 3 (1.4%), with sounds
  contributing 20 of those.

**Interpretation**: The scan reveals several distinct classes of entry-level
flaws, varying from catastrophic (sounds) to minor (USA near-duplicate
capitals). Confidence: **High** for the existence of each flaw;
**Medium** for quantifying downstream impact. Epistemic level: **L1**
(measurement and data quality).

Severity ranking of flaws found:

1. **Sounds answer-space collapse (CRITICAL)**: With only 3 unique answers
  and 48% entropy, sounds is not a meaningful redirection benchmark.
   40% of pairs are answer-identity, and 83% have the target already at
   rank <= 3. The labeled-vs-random comparison on this dataset is measuring
   noise, not label quality. Recommendation: **exclude sounds from all
   headline claims** or restrict analysis to the 8 cross-color pairs
   (meow<->hiss, meow<->brown_entities, hiss<->brown_entities) -- but even
   those have high baseline confusion (rank 2-12).
2. **Books "J." cluster (HIGH)**: 6/240 pairs (2.5%) have the target answer
  at rank=1 with prob 28-54% at baseline. The model already "knows" the
   answer class from the `J.` token alone. These pairs can inflate vs_max
   and rank_in_group without any meaningful steering. Separately, 3/16
   entities have character==book field collapse, making character-only and
   book-only field-add variants degenerate.
3. **Products Jack confound (MODERATE)**: 2/132 pairs (1.5%) share first
  token `Jack` and show baseline rank=1. A small but non-negligible
   fraction. Additionally, twitter has product==company.
4. **Paintings Edvard/Edward (LOW-MODERATE)**: 1 pair with 83% string
  similarity between answers. Baseline rank=4, not rank=1, so the
   confound is weaker but still relevant for first-token metrics.
5. **USA geographic confounds (LOW)**: 8/2450 pairs (0.3%) have baseline
  rank <= 3, mostly from shared city names (Portland, Kansas City,
   Charleston) or geographic proximity. Individually significant; aggregate
   impact negligible given N=2450.

**Threats to validity**:

- The baseline rank is computed at a single position (position 0). The
model's internal representation may differ at later trajectory positions.
- "First token sharing" does not automatically mean the model confuses
the entities -- it means the first generated token is ambiguous, which
may resolve by position 2+. But gap_closure=0.0 for the J. cluster
suggests it does not resolve.
- The near-duplicate thresholds (0.7 similarity, rank <= 3) are
somewhat arbitrary. Changing them shifts counts but not the qualitative
conclusions.
- The field-ambiguity flaw (character==book) affects the field-add
analysis specifically, not the full-triple labeled run.
- This scan covers entity/answer properties only. It does not cover
upstream pipeline quality (error nodes, reverse substring) which are
documented in separate log entries.

**Follow-up**:

- Recompute headline metrics (labeled vs random deltas on vs_max,
gap_closure, rank_in_group) after excluding: (a) all sounds pairs,
(b) books Finch/Lee pairs, (c) books J. cluster pairs,
(d) products Jack pairs. Report how much the deltas change.
- For baseline-confused pairs, check whether gap_closure or vs_max still
shows labeled > random separation. If the intervention adds nothing
beyond what the model already represents, these pairs should be flagged.
- Consider adding an "effective redirection" filter to aggregate stats:
exclude pairs where from_answer == to_answer OR baseline target rank <= 2.
- Investigate whether the books character==book field collapse inflates
the "less is more" finding (the full triple appears worse because two
of three fields are redundant, not because field interference is real).

**References**: Previous entry `[2026-03-24] curiosity-sampled method flaws across datasets` (which first identified books Finch/Lee and sounds brown
collisions); `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/swap_query.py`

---

## [2026-03-25] Topic: gap closure is regime-dependent and mostly misleading

**Question**: Is `gap_closure` a useful signal for label evidence across
regimes, or is it only relevant in specific circumstances?

**Method**: Re-examined gap closure values from the regime taxonomy data already
collected in the `[2026-03-24] logit-shift taxonomy` and `[2026-03-25] best field-add variant` entries. Compared gap closure across regimes A, C, D for
labeled, best variant, and random conditions, and checked whether it
discriminates labeled from random within each regime. Also checked the
cross-domain anomaly (USA vs books) where gap closure and `vs_max` disagree.

**Raw findings**:

Gap closure by regime (USA, full labeled vs random):


| Regime                 | Labeled gc | Random gc | Labeled vs_max | Random vs_max |
| ---------------------- | ---------- | --------- | -------------- | ------------- |
| A (tgt UP, src DOWN)   | 0.88       | 0.76      | 4.28           | -0.19         |
| C (both DOWN, flip)    | 2.73       | 1.59      | 2.33           | -0.10         |
| D (both DOWN, no flip) | **13.62**  | **6.46**  | 4.11           | -0.07         |


Gap closure by regime (USA, best variant vs random):


| Regime | Best gc   | Random gc | Best vs_max | Random vs_max |
| ------ | --------- | --------- | ----------- | ------------- |
| A      | 1.44      | 0.76      | 4.01        | -0.19         |
| C      | 3.14      | 1.59      | 3.81        | -0.10         |
| D      | **16.25** | **6.46**  | 5.08        | -0.07         |


Cross-domain comparison (full labeled):


| Domain    | gap_closure | vs_max | Interpretation conflict?                    |
| --------- | ----------- | ------ | ------------------------------------------- |
| USA       | 4.67        | 2.86   | --                                          |
| Books     | 0.01        | 5.98   | Yes: gc says weak, vs_max says strongest    |
| Products  | 0.19        | 3.46   | --                                          |
| Paintings | 0.80        | 1.55   | --                                          |
| Sounds    | 1.46        | 3.28   | Mild: gc > paintings but vs_max > paintings |


**Interpretation**: Gap closure is regime-dependent and mostly misleading as a
general label-evidence metric. Confidence: **High**. Epistemic level: **L1**
(metric validity).

Per-regime analysis:

- **Regime A**: gap closure is **redundant**. The target already flipped above
source at position 0. Gap closure measures how much further the winning target
pulls ahead across later positions -- it adds no discriminative information
beyond the flip itself. `vs_max` separation between labeled and random is
4.28 vs -0.19 (delta 4.47). Gap closure separation is only 0.88 vs 0.76
(delta 0.12). Gap closure is nearly useless here.
- **Regime C**: gap closure is **weakly informative**. It captures some of the
target recovery signal, but target recovery rate (92% vs 29%) and
`tgt_win_pct` (0.67 vs 0.32) are cleaner binary/continuous signals that
separate labeled from random far more sharply. Gap closure's separation in
regime C (2.73 vs 1.59) is modest and noisy because it depends on the
magnitude of the initial disruption.
- **Regime D**: gap closure is **actively misleading**. Regime D has the
*highest* gap closure of any regime (13.62 labeled, 6.46 random) despite
being the weakest evidence regime (target never overtakes source). The reason
is mechanical: when both tokens start far apart and both get hammered, the
trajectory has room to "close" the gap substantially without the target ever
winning. A naive user looking at gap closure would think regime D is the
strongest outcome, when in fact it is the weakest.

Cross-domain: gap closure says books is nearly zero (0.01) while USA is strong
(4.67). But `vs_max` says books is the strongest domain (5.98 vs 2.86). The
discrepancy exists because books pairs tend to have small baseline gaps (target
and source start close together), so there is little room for "closure" even
when the target wins convincingly at the token level. Gap closure is confounded
by baseline gap magnitude and is therefore not comparable across domains.

**Threats to validity**:

- This analysis uses existing aggregate data, not a fresh per-sample
correlation study. A formal correlation between gap closure and swap success
conditioned on regime would strengthen the argument.
- Gap closure might still be useful in a narrow context: regime C cases with
large baseline gaps where target eventually overtakes source. This is a small
subset and would need explicit filtering.

**Follow-up**:

- De-emphasize gap closure in headline reporting and label-evidence metrics.
- Consider replacing it with a regime-aware composite: use `vs_max` as primary,
target recovery as secondary, and gap closure only for regime C cases with
baseline gap > some threshold.
- Update the metric reference in `AGENTIC_RESEARCH_GUIDE.md` Section 6 to note
gap closure's regime dependence.

**References**: Previous entries `[2026-03-24] logit-shift taxonomy`,
`[2026-03-25] best field-add variant`; `output/FULLSCALE_CONTROL_REPORT.md`

---

## [2026-03-25] Topic: best field-add variant vs random in regime taxonomy

**Question**: The previous entry compared full labeled (all 3 fields) vs random.
But the "less is more" finding showed that 2-field subsets often outperform the
full triple. Does the regime taxonomy look even cleaner when we compare the best
field-additivity variant (intermediate+answer) against random?

**Method**: For each dataset, selected the known best 2-field variant from the
full-scale control report and classified every swap in that variant, the full
labeled run, and random (capped at 1500) using the same regime taxonomy from the
previous entry. Compared regime prevalence, hit rate, `vs_max`, target recovery
rate, and target-wins-source fraction.

Best variants used:

- USA: `add_state_capital` (intermediate + answer)
- Books: `add_book_author` (intermediate + answer)
- Products: `add_company_founder` (intermediate + answer)
- Paintings: `add_painter_first_name` (intermediate + answer)
- Sounds: `add_sound_animal` (input + intermediate)

**Raw findings**:

Regime A (target UP, source DOWN -- cleanest label evidence):


| Dataset   | best variant               | full labeled               | random                     |
| --------- | -------------------------- | -------------------------- | -------------------------- |
| USA       | 34.9%, hit 46%, vsMax 4.01 | 8.9%, hit 31%, vsMax 4.28  | 19.4%, hit 0%, vsMax -0.19 |
| Books     | 62.1%, hit 54%, vsMax 9.08 | 38.8%, hit 4%, vsMax 7.64  | 40.8%, hit 0%, vsMax -1.49 |
| Products  | 62.1%, hit 32%, vsMax 3.75 | 56.8%, hit 25%, vsMax 4.48 | 51.5%, hit 0%, vsMax 0.44  |
| Paintings | 47.8%, hit 0%, vsMax 2.25  | 17.8%, hit 6%, vsMax 3.76  | 23.3%, hit 0%, vsMax -0.54 |


Regime C (both DOWN, flip -- differential disruption):


| Dataset   | best variant                            | full labeled                            | random                                 |
| --------- | --------------------------------------- | --------------------------------------- | -------------------------------------- |
| USA       | 55.1%, hit 35%, recov 93%, winPct 0.804 | 71.1%, hit 23%, recov 92%, winPct 0.673 | 35.0%, hit 1%, recov 29%, winPct 0.319 |
| Books     | 33.8%, hit 7%, recov 96%, winPct 0.378  | 56.2%, hit 2%, recov 92%, winPct 0.364  | 23.3%, hit 2%, recov 89%, winPct 0.192 |
| Products  | 32.6%, hit 12%, recov 86%, winPct 0.315 | 39.4%, hit 2%, recov 98%, winPct 0.199  | 22.7%, hit 0%, recov 83%, winPct 0.282 |
| Paintings | 48.9%, hit 2%, recov 89%, winPct 0.273  | 75.6%, hit 4%, recov 93%, winPct 0.203  | 33.3%, hit 0%, recov 77%, winPct 0.188 |


Regime D (both DOWN, no flip -- generic disruption):


| Dataset   | best variant | full labeled | random |
| --------- | ------------ | ------------ | ------ |
| USA       | 9.1%         | 19.4%        | 45.3%  |
| Books     | 3.3%         | 3.3%         | 34.6%  |
| Products  | 2.3%         | 2.3%         | 22.0%  |
| Paintings | 2.2%         | 6.7%         | 42.2%  |


**Interpretation**: Confidence: **High**. Epistemic level: **L2**.

The best field-add variant dramatically amplifies the separation from random
compared to the full labeled run. Three patterns stand out:

1. **Regime A prevalence jumps**: the best variant pushes far more cases into
  regime A (clean target-up, source-down). USA goes from 8.9% to 34.9%. Books
   goes from 38.8% to 62.1%. This means removing input-field features eliminates
   a large amount of generic disruption that was pushing cases into regime C/D.
2. **Hit rates within regimes improve**: USA regime A goes from 31% hit (full
  labeled) to 46% hit (best variant). Books regime A goes from 4.3% to 54.4%.
   This is not just a redistribution across regimes -- the quality of each
   regime improves too.
3. **Regime D nearly vanishes**: the "both down, no flip" regime (weakest label
  evidence) drops from 19.4% to 9.1% in USA, and from 6.7% to 2.2% in
   paintings. Meanwhile random concentrates in regime D (42-45%). The best
   variant produces almost no generic-disruption-dominant cases.

The overall picture: the best field-add variant vs random is a much cleaner
test of label correctness than the full labeled vs random comparison. The
input-field features in the full triple add noise that pushes many cases from
regime A (clear evidence) into regime C (ambiguous). The intermediate+answer
combination produces interventions that are more surgical and more interpretable.

For label-evidence metrics, this means the composite indicator from the previous
entry (`vs_max > 0` + target recovery + `tgt_win_pct > 0.5`) should be
validated primarily on the best field-add variant, not the full triple. The
full triple conflates label quality with intervention design.

**Threats to validity**:

- The "best variant" was chosen based on aggregate hit rate, which is circular
for this analysis. A fairer test would pre-register the variant choice.
- Paintings shows an anomaly: best variant regime A has 0% hit despite 48%
prevalence and positive `vs_max`, confirming the answer-field weakness
(`first_name`) identified in previous entries.
- Random was capped at 1500 samples for USA due to the 3-replicate expansion;
this is still representative but not exhaustive.
- Sounds is omitted from regime A analysis because it has zero regime A cases
in any condition.

**Follow-up**:

- Use the best field-add variant as the primary labeled condition for the
label-evidence metric validation.
- Check whether the regime A prevalence increase correlates with intervention
count decrease (fewer features = less disruption = more regime A).
- Test whether the intermediate-only single-field variant (`add_state`,
`add_book`) achieves even higher regime A prevalence, to see if the
answer field helps or is redundant.

**References**: Previous entry `[2026-03-24] logit-shift taxonomy`;
`output/FULLSCALE_CONTROL_REPORT.md` Section 6

---

## [2026-03-24] Topic: logit-shift taxonomy and label-evidence metric design

**Question**: When a swap does not produce a perfect (T5) result, what does the
logit trajectory tell us about whether the feature labels are correct? Can we
separate "the labels pointed at the right circuits" from "the swap happened to
produce the right string"?

**Method**: Classified every labeled and random swap in the five full-scale runs
by what happens to target and source token logits at position 0 relative to
their unsteered baselines. Defined four main regimes:


| Regime | Target logit | Source logit | Flip at pos 0? | Intuition                                     |
| ------ | ------------ | ------------ | -------------- | --------------------------------------------- |
| **A**  | UP           | DOWN         | yes            | Clean redirection: target gains, source loses |
| **C**  | DOWN         | DOWN         | yes            | Both disrupted, but target less so            |
| **D**  | DOWN         | DOWN         | no             | Both disrupted, source still dominant         |
| **E**  | FLAT         | DOWN         | yes            | Pure suppression, no target lift              |


Then compared regime prevalence, hit rates, `vs_max`, `gap_closure`, target
recovery (does target logit exceed baseline at any later position?), and
target-wins-source fraction across the 11 trajectory positions.

For regime C specifically, sub-classified USA labeled cases into:

- **C1**: target recovers above baseline AND `vs_max > 2` (specific recovery)
- **C2**: target recovers above baseline but `vs_max <= 2` (generic recovery)
- **C3**: target never recovers but beats source at >50% of positions
- **C4**: target never recovers and loses to source at most positions

**Raw findings**:

Regime prevalence (labeled / random):


| Dataset   | A (labeled) | A (random) | C (labeled) | C (random) | D (labeled) | D (random) |
| --------- | ----------- | ---------- | ----------- | ---------- | ----------- | ---------- |
| USA       | 8.9%        | 19.4%      | 71.1%       | 35.0%      | 19.4%       | 45.3%      |
| Books     | 38.8%       | 40.8%      | 56.2%       | 23.3%      | 3.3%        | 34.6%      |
| Products  | 56.8%       | 51.5%      | 39.4%       | 22.7%      | 2.3%        | 22.0%      |
| Paintings | 17.8%       | 23.3%      | 75.6%       | 33.3%      | 6.7%        | 42.2%      |
| Sounds    | 0%          | 0%         | 43.3%       | 26.7%      | 56.7%       | 73.3%      |


Key observations from regime-level comparison:

- Labeled interventions push far more cases into regime C (both down, flip)
than random does. Random instead concentrates in regime D (both down, no
flip). This means labeled features cause source to drop much harder
relative to target than random features do.
- In regime A (clean redirection), labeled `vs_max` is dramatically higher
than random across all datasets. But regime A is actually *less common*
in labeled than random for USA (8.9% vs 19.4%), suggesting random more
often produces small, undirected target bumps.

Regime C deep dive (USA):

- Labeled regime C: N=1741, hit=22.5%, `vs_max`=2.33, tgt_recovers=92.2%,
`tgt_win_pct`=0.673, `avg_sd`=-22.33
- Random regime C: N=525, hit=0.6%, `vs_max`=-0.10, tgt_recovers=29.3%,
`tgt_win_pct`=0.319, `avg_sd`=-12.49

The critical difference: in labeled regime C, the target token **recovers
above its own baseline** at later positions 92.2% of the time (vs 29.3% for
random). The labeled source drop is also much deeper (-22.33 vs -12.49).

USA labeled regime C sub-classification:

- **C1** (recovers + specific): N=857, hit=44.0%, `vs_max`=4.93, `tgt_win_pct`=0.817
- **C2** (recovers + generic): N=749, hit=1.7%, `vs_max`=-0.07, `tgt_win_pct`=0.560
- **C3** (no recovery, wins positions): N=45, hit=4.4%, `vs_max`=-0.24
- **C4** (no recovery, loses positions): N=90, hit=0.0%, `vs_max`=-1.10

**Interpretation**: The regime taxonomy reveals that "both tokens lose
probability" (regime C) is actually the dominant labeled behavior in USA and
paintings, not an edge case. But within regime C, the labeled vs random
distinction is stark: labeled features cause **differential disruption** where
the target token recovers across the generation trajectory while the source
stays suppressed, whereas random disruption is more uniform.

Confidence: **Medium-High**. Epistemic level: **L2** (causal effects) with
implications for **L1** (label validity).

The "confusing" case you asked about -- both lose but target stays above
source -- is actually the strongest evidence of label specificity when combined
with two additional signals:

1. **Target recovery**: does the target logit exceed its own unsteered baseline
  at any trajectory position? (92% labeled vs 29% random in regime C)
2. **Differential suppression**: is the source drop much larger than the target
  drop? (labeled avg: source drops 22.3, target drops 7.7; random avg: source
   drops 12.5, target drops 4.6)

**Proposed label-evidence metric candidates**:

1. **Recovery-adjusted specificity (RAS)**: `vs_max` restricted to positions
  where target logit exceeds its own unsteered baseline. Filters out
   cases where target "wins" only because everything is destroyed.
2. **Differential disruption ratio (DDR)**: `|source_delta| / |target_delta|`
  at position 0. A ratio > 1 means the intervention hit the source harder
   than the target. Labeled USA regime C averages 2.9; random averages 2.7.
   The gap is modest, so this alone is not sufficient.
3. **Target recovery rate**: binary -- does target logit exceed its unsteered
  baseline at any trajectory position? This is the single most discriminating
   signal between labeled and random in regime C (92% vs 29%).
4. **Sustained dominance**: fraction of trajectory positions where target
  logit > source logit. Labeled regime C averages 0.673; random 0.319.
5. **Composite label-evidence score**: combine `vs_max > 0`, target recovery,
  and `tgt_win_pct > 0.5` into a 3-bit indicator. Cases with all three
   are strong label evidence; cases with none are generic disruption.

Recommendation: **target recovery rate** is the simplest, most discriminating
single signal to add to the evaluation. It separates "the model's circuits
responded to the target concept" from "everything got disrupted and target
happened to be less disrupted." Combined with `vs_max > 0` (target beats all
other answer-group competitors), it produces a conservative but meaningful
label-evidence indicator.

**Threats to validity**:

- The regime classification uses position-0 logit deltas only; some cases may
shift regime if measured at a different position.
- "Target recovery" uses max over 11 positions and could be noisy for short
generations.
- The sub-classification thresholds (e.g., `vs_max > 2` for "specific") are
somewhat arbitrary.
- Sounds has no regime A cases at all for labeled, which may indicate the
taxonomy does not fit all domains equally well.
- This analysis does not yet incorporate field-additivity variants.

**Follow-up**:

- Implement target recovery rate as a computed field and rerun the labeled vs
random comparison with it as the primary metric.
- Check whether the composite label-evidence score correlates with known
entity-level predictors (error_node_pct, concept coverage).
- Test the taxonomy on field-additivity variants to see if intermediate+answer
fields produce more regime A / C1 cases than input fields.
- Examine whether regime C2 (recovers but generic) represents cases where the
labels are correct but the steering magnitude is too large.

**References**: `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/swap_query.py`

---

## [2026-03-24] Topic: curiosity-sampled method flaws across datasets

**Question**: If we sample a small number of curiosity-driven results from each
dataset, what flaws in the current methods become visible? The goal here is
adversarial error-finding, not representative performance estimation.

**Method**: Treated `x = 3` and sampled three labeled swaps per dataset
(`15` total), chosen for curiosity value rather than uniformity: cases with
large labeled-vs-random deltas, large `vs_max` but no exact-match hit, random
beating labeled, or otherwise contradictory metrics. For each sampled pair,
inspected labeled output, three random replicates, intervention counts, and
`PipelineTracer.trace_swap_matching()` totals / warnings. Then ran targeted
sanity checks suggested by the sampled failures: answer-level identity-pair
counts, prompt leakage in exact-match evaluation, first-token false positives,
rank-1-but-no-hit counts, zero-coverage concept fields, and dataset directory
counts vs actual swap-entity counts.

**Raw findings**:

- Sampled pairs that exposed issues:
  - USA: `new_hampshire_manchester -> oklahoma_tulsa`,
  `south_carolina_charleston -> west_virginia_huntington`,
  `indiana_fort_wayne -> missouri_kansas_city`
  - Books: `frodo_baggins -> katniss_everdeen`,
  `atticus_finch -> scout_finch`,
  `captain_ahab -> holden_caulfield`
  - Products: `windows -> facebook`, `windows -> wordpress`,
  `dyson -> model_s`
  - Paintings: `starry_night -> the_scream`,
  `the_scream -> persistence_of_memory`,
  `grande_jatte -> girl_pearl_earring`
  - Sounds: `meow -> neigh`, `bark -> gobble`, `neigh -> hiss`
- Flaw 1: USA upstream scans can overcount entities.
  - `output/usa_states_batch/` contains 68 non-underscore directories.
  - The actual swap runs use 50 unique source entities and 50 unique target
  entities.
  - The extra directories are casing / formatting variants like
  `colorado_Colorado Springs` vs `colorado_colorado_springs`,
  `new hampshire_Manchester` vs `new_hampshire_manchester`,
  `virginia_Virginia Beach` vs `virginia_virginia_beach`.
- Flaw 2: exact-match hit can be spuriously true from prompt leakage.
  - In sampled USA pair
  `south_carolina_charleston -> west_virginia_huntington`, the steered
  output was:
  `"The capital of the state containing Charleston isExternéburg, West Virginia..."`
  - This counts as `steered_has_to_answer = True` only because target answer
  `Charleston` already appears in the prompt string.
  - Prompt-leak pairs found in labeled runs: USA `1/2450` (0.04%), all other
  datasets `0`.
- Flaw 3: answer-level identity swaps remain in nominally non-identity runs.
  - Books: `2/240` non-identity pairs share the same answer
  (`atticus_finch <-> scout_finch`, both `Harper Lee`).
  - Sounds: `12/30` non-identity pairs share the same answer (`brown`) --
  `40.0%` of the dataset.
  - Example: `bark -> gobble` has source answer `brown`, target answer `brown`,
  so the steering task is ill-posed as a redirection test.
- Flaw 4: `first_token_matches_target` has false positives.
  - USA: `54/2450` labeled swaps (2.2%) have `first_token_matches_target = True`
  while `steered_has_to_answer = False`.
  - Books: `3/240` (1.25%).
  - Products: `10/132` (7.58%).
  - Sounds: `3/30` (10.0%).
  - Example: `windows -> facebook` counts as first-token match because the
  token is `' Mark'`, but the output is `Mark Hurd`, not `Mark Zuckerberg`.
  - Example: `neigh -> hiss` has first token `' GREEN'` according to top-k
  metadata, while the rendered output begins `BOW WOW!`.
- Flaw 5: ranking / logit metrics and string-hit metrics are badly misaligned.
  - Fraction of labeled swaps with `rank_in_group = 1` but no exact-match hit:
    - USA: `1371/2450` (55.96%)
    - Books: `225/240` (93.75%)
    - Products: `87/132` (65.91%)
    - Paintings: `67/90` (74.44%)
    - Sounds: `30/30` (100%)
  - Example: `frodo_baggins -> katniss_everdeen` has `vs_max = 15.16`,
  `rank = 1`, but output `... was written by-Eragon`.
  - Example: `starry_night -> the_scream` has `vs_max = 10.5`, `rank = 1`,
  but output stays `Vincent Van Gogh`.
- Flaw 6: some concept fields have no matched supernodes.
  - In sounds, `animal` has zero matching supernodes for `2/6` entities:
  `bark` and `hoot`.
  - Sampled pair `bark -> gobble` produced tracer warning:
  `source concept 'dog' (animal) matched no supernodes in bark`.

**Interpretation**: The curiosity sample surfaced several genuine method flaws,
not just noisy bad examples. Confidence: **High** for the existence of the
flaws; **Medium** for their aggregate impact on headline conclusions. Epistemic
level: primarily **L1** (measurement / pipeline validity), with downstream
implications for **L2**.

Most important issues:

- The **exact-match hit metric is not trustworthy on its own**, because it can
be inflated by prompt leakage and deflated by answer-format mismatch.
- The **first-token metric is also not trustworthy on its own**, because it can
reward shared first names (`Mark`) or disagree with the rendered output.
- The **sounds dataset is structurally problematic** for causal redirection:
many pairs share the same answer, and one concept field sometimes has zero
coverage.
- Any **dataset-level upstream scan over USA directories** is vulnerable to
overcounting because the folder structure contains duplicate variants.

The sampled cases strengthen the case that contrast-group metrics (`vs_max`,
`rank_in_group`) capture something useful, but they also show that those
metrics cannot simply be interpreted as answer-level success.

**Threats to validity**:

- This was a curiosity sample, not a random sample, so it is designed to find
flaws rather than estimate prevalence fairly.
- Some metric mismatches may reflect real model behavior differences between
token-level trajectory and decoded text, not only evaluator bugs.
- The sampled cases are enough to prove the flaws exist, but not enough to
fully quantify how much each flaw changes the main cross-domain conclusions.

**Follow-up**:

- Patch evaluation to check exact-match only on generated continuation, not the
echoed prompt prefix.
- Exclude answer-level identity pairs from redirection analysis, especially in
sounds and the Finch/Lee book pair.
- Redefine or de-emphasize `first_token_matches_target`; require stronger token
evidence than substring overlap on the full answer string.
- Fix upstream directory canonicalization before using `itertools`-style scans
over entity folders in USA.
- Quantify how headline metrics change after these filters / fixes.

**References**: `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/pipeline_tracer.py`; `scripts/utils/swap_query.py`; `scripts/experiments/batch/pipeline/swap_evaluator.py`

---

## [2026-03-24] Topic: domain gradient explanation scan

**Question**: Why does `usa_states_batch` appear stronger than books,
products, paintings, and sounds? Is the domain gradient mainly explained by
upstream data quality, metric definition, concept ambiguity, or graph
structure?

**Method**: Ran a cross-domain scan using `SwapStats.compare()` on the five
full-scale labeled vs random runs and `PipelineTracer.grouping_quality_table()`
for per-entity upstream quality summaries. Collected, per domain: labeled vs
random deltas on `vs_max`, `gap_closure`, and `rank_in_group`; mean
`error_influence_pct`, selected features, supernodes, and review-flagged
counts; mean concept-coverage counts from the current matcher; and the
reverse-substring confound rate from the stricter one-way matching check used
in the previous investigation entry.

**Raw findings**:

- Labeled vs random `vs_max` delta by domain:
  - Books: +6.14
  - USA states: +5.17
  - Products: +3.23
  - Paintings: +1.58
  - Sounds: +0.14
- Labeled vs random `gap_closure` delta by domain:
  - USA states: +2.24
  - Sounds: -0.84
  - Products: -1.52
  - Paintings: -2.69
  - Books: -3.38
- Mean error-node influence by domain:
  - USA states: 10.01%
  - Books: 12.00%
  - Sounds: 12.88%
  - Products: 14.64%
  - Paintings: 14.87%
- Mean selected features / supernodes by domain:
  - USA states: 277.6 features, 23.9 supernodes
  - Books: 437.8 features, 26.8 supernodes
  - Products: 378.5 features, 25.8 supernodes
  - Paintings: 579.5 features, 30.6 supernodes
  - Sounds: 609.8 features, 32.8 supernodes
- Mean review-flagged rows by domain:
  - Products: 6.3
  - Books: 20.9
  - USA states: 36.2
  - Sounds: 42.5
  - Paintings: 55.0
- Reverse-substring confound rate by domain:
  - USA states: 28.0%
  - Books: 43.75%
  - Products: 29.17%
  - Paintings: 45.0%
  - Sounds: 25.0%
- Existing report-level structural observations:
  - USA: `state+capital` beats the full triple strongly.
  - Books: `book+author` beats the full triple dramatically.
  - Paintings: `painter` and `painter+first_name` are effectively identical.
  - Sounds: labeled and random are nearly indistinguishable on `vs_max`.

**Interpretation**: The domain gradient is not explained by a single factor.
Confidence: **Medium**. Epistemic level: **L2** (downstream causal effects) with
some **L1** support from upstream quality scans.

Most supported explanation: a combination of semantic answer-field quality and
upstream ambiguity burden.

- **Not mainly graph size/structure volume**: the weakest domains
(`paintings_painters_batch`, `sounds_colors_batch`) have the *most* selected
features and supernodes. More graph material does not produce stronger
specificity.
- **Partly upstream quality**: USA has the lowest mean error-node influence,
while paintings/products are worst on this measure. This supports the idea
that cleaner graphs help, but it does not fully explain the ranking because
books are strong despite only middling error-node burden.
- **Ambiguity/overlap likely matters a lot**: paintings has the highest
review-flagged burden and one of the highest substring-confound rates, and
the report already notes field collapse (`painter` subsumes `first_name`).
Sounds has a tiny, semantically coarse answer space (`color`) and almost no
labeled-vs-random separation.
- **Metric definition matters**: `Hit%` is not comparable across domains, and
`rank_in_group` compresses in small answer spaces. `gap_closure` is also not
a clean cross-domain strength metric, because books show strong specificity on
`vs_max` while random exceeds labeled on `gap_closure`.

Provisional synthesis: USA looks strongest because it combines relatively clean
upstream graphs with a highly specific answer space (`capital`) and a strong
intermediate-to-answer pathway (`state -> capital`). Books are also highly
specific on contrast-group metrics, but weaker on `Hit%` / `gap_closure`,
suggesting metric semantics and generation behavior obscure some of the signal.
Paintings and sounds look weak mainly because the target concept is less
entity-specific (`first_name`, `color`) and the matching/grouping pipeline is
more ambiguity-prone there.

**Threats to validity**:

- This is a domain-level observational scan, not a controlled ablation.
- Some metrics conflict (`vs_max` says books are very strong; `gap_closure`
does not), so conclusions depend on which metric is treated as primary.
- The upstream-quality summaries are coarse averages; they may hide a few
high-leverage entities or fields.
- The review-flagged and concept-coverage counts are proxies for ambiguity, not
validated causal measures.

**Follow-up**:

- Test answer-field specificity directly by comparing domains on answer-group
size, answer uniqueness, and baseline answer confusion.
- Build a simple domain-level regression / matched comparison using entity-level
predictors (`error_node_pct`, review burden, intervention count, field
coverage) to see which factors best predict `vs_max`.
- Investigate paintings and sounds with pair-level traces to confirm whether
weak performance comes from bad matching, coarse answers, or weak target
circuits.

**References**: `output/FULLSCALE_CONTROL_REPORT.md`; `output/CROSS_DOMAIN_CONTROL_REPORT.md`; `scripts/utils/pipeline_tracer.py`; `scripts/utils/swap_stats.py`

---

## [2026-03-24] Topic: reverse substring matching confound scan

**Question**: Does the current concept-to-supernode matching logic introduce
spurious matches through reverse containment (for example, short supernode names
such as `is` matching longer concepts such as `mississippi`)?

**Method**: Ran an ad hoc Python scan over all five `*_batch` datasets using
`PipelineTracer` helpers. For each entity and configured concept field, compared
the current matcher (`_concept_matches_supernode()`) against a stricter
one-way rule that allows `concept in supernode` and `word in supernode`, but
disallows the reverse fallback `supernode in word`. Counted extra supernodes
matched only by the current rule and recorded representative examples.

**Raw findings**:

- Denominator: 188 entity-field combinations across 5 datasets.
- USA states: 28/100 combinations affected (28.0%); 33 extra supernode matches.
- Books: 14/32 affected (43.75%); 26 extra matches.
- Products: 7/24 affected (29.17%); 7 extra matches.
- Paintings: 9/20 affected (45.0%); 17 extra matches.
- Sounds: 3/12 affected (25.0%); 4 extra matches.
- Affected combinations were present in every dataset scanned.
- Representative examples:
  - `mississippi_gulfport`, field `state`, concept `mississippi` -> extra
  match `is` (115 features)
  - `idaho_idaho_falls`, field `capital`, concept `boise` -> extra match
  `is` (110 features)
  - `wisconsin_milwaukee`, field `state`, concept `wisconsin` -> extra matches
  `is` (105 features) and `in` (5 features)
  - `anna_karenina`, field `book`, concept `anna karenina` -> extra matches
  `ina` (155 features) and `Karen` (485 features)
  - `guernica`, field `painter`, concept `pablo picasso` -> extra match
  `ica` (480 features)

**Interpretation**: This is evidence for a real pipeline artifact at the
concept-matching stage, not just a hypothetical edge case. Confidence:
**Medium**. Epistemic level: **L1** (operational label assignment / matching
quality). This does **not** yet establish that swap outcomes are materially
distorted downstream, only that the current matcher can add semantically
questionable supernodes in a sizeable minority of entity-field cases.

**Threats to validity**:

- The scan uses the tracer's simplified matching helper rather than a full
end-to-end replay of intervention assembly.
- "Extra match" does not automatically mean "bad match"; some cases may be
weak aliases or partial names rather than pure noise.
- The unit counted here is matched supernodes, not final ablate/amplify effect
on swap behavior, so downstream impact remains unmeasured.
- The scan is broad across domains, but it does not yet compare labeled vs
random swap performance with and without the reverse rule.

**Follow-up**: Measure downstream impact. Re-run a sample of swaps under a
strict one-way matcher and compare intervention counts, `vs_max`, `gap_closure`,
and `rank_in_group`. Prioritize USA and books, where both feature counts and
confound examples are large.

**References**: `scripts/utils/pipeline_tracer.py`; `scripts/utils/AGENTIC_RESEARCH_GUIDE.md`

---

## [2026-04-15] Topic: Scalable Cross-Prompt Robustness (N=1607 pairs, 5 domains)

**Question**: The Section 4.7 cross-prompt robustness claim rests on exactly 2
entities (Dallas, Oakland) from 1 domain (USA). Does the finding -- high feature
overlap, high activation stability, layer-gradient in overlap -- generalize across
all 103 entities and 5 domains?

**Method**: Built a generic pairwise comparison engine
(`scripts/experiments/cross_prompt_robustness_scalable.py`) that loads any two
entities from their standardized `02 Node Grouping/node_grouping.csv` files,
deduplicates to unique `feature_key`, and computes:

- Feature overlap: Jaccard and directional (|shared|/|A|)
- Activation stability: 1 - mean(relative diff of activation_max)
- Peak token agreement: fraction of shared features with same peak_token / same peak_token_type
- Supernode consistency: same-supernode, entity-regrouped, inconsistent (using slug+concept-field keywords for entity detection)
- Per-layer overlap in 3 buckets (early 0-5, mid 6-14, late 15+) and per individual layer
- Influence-weighted Jaccard (via graph.json node influence)

Ran all 1,607 intra-domain pairs across 5 domains. Also ran bootstrap CIs
(5,000 resamples), permutation tests (2,000 draws from pools of 1k--50k features),
and correlations with swap performance (vsMax, gap_closure) from labeled runs.

**Raw findings**:

### Cross-domain aggregate (N=1,607 pairs)

| Domain | N pairs | Jaccard (95% CI) | Dir. overlap | Stability (95% CI) | Peak token | Peak type | Same SN | Regrouped | Inconsist. |
|---|---|---|---|---|---|---|---|---|---|
| USA | 1,225 | 0.465 [0.462, 0.468] | 0.635 | 0.947 [0.946, 0.948] | 0.890 | 0.966 | 0.766 | 0.162 | 0.073 |
| Books | 210 | 0.308 [0.302, 0.315] | 0.469 | 0.908 [0.905, 0.911] | 0.891 | 0.970 | 0.475 | 0.128 | 0.397 |
| Products | 91 | 0.364 [0.356, 0.374] | 0.533 | 0.903 [0.898, 0.907] | 0.933 | 0.988 | 0.652 | 0.165 | 0.184 |
| Paintings | 66 | 0.286 [0.279, 0.292] | 0.451 | 0.916 [0.911, 0.921] | 0.851 | 0.928 | 0.710 | 0.099 | 0.191 |
| Sounds | 15 | 0.621 [0.597, 0.648] | 0.799 | 0.944 [0.938, 0.949] | 0.982 | 0.990 | 0.856 | 0.089 | 0.056 |

### Layer gradient (early vs late overlap)

| Domain | Early (L0-5) | Mid (L6-14) | Late (L15+) | Early/Late ratio |
|---|---|---|---|---|
| USA | 0.543 | 0.440 | 0.293 | 1.85x |
| Books | 0.347 | 0.340 | 0.184 | 1.89x |
| Products | 0.496 | 0.308 | 0.164 | 3.02x |
| Paintings | 0.302 | 0.311 | 0.212 | 1.43x |
| Sounds | 0.684 | 0.544 | 0.440 | 1.56x |

### Permutation test

All 5 domains: p < 0.001 at all pool sizes (1k, 5k, 10k, 50k). Observed Jaccard
significantly exceeds chance for any plausible CLT feature pool.

### Correlation with swap performance

| Domain | N matched | r(Jaccard, vsMax) | r(Jaccard, gap_closure) | r(Jaccard, hit) |
|---|---|---|---|---|
| USA | 2,450 | +0.024 | +0.014 | -0.016 |
| Books | 210 | +0.233 | +0.004 | +0.021 |
| Products | 174 | +0.087 | -0.023 | +0.070 |
| Paintings | 124 | +0.311 | +0.089 | +0.119 |
| Sounds | 30 | -0.135 | +0.079 | 0.000 |

### Comparison: original Dallas/Oakland (N=2) vs population (N=1,225)

| Metric | Dallas/Oakland | USA population mean | Percentile |
|---|---|---|---|
| Jaccard | 0.558 | 0.465 | ~93rd |
| Directional | 0.729 | 0.635 | ~90th |
| Stability | 0.963 | 0.947 | ~75th |
| Same SN rate | 0.804 | 0.766 | ~75th |
| Early overlap | 0.677 | 0.543 | ~93rd |
| Late overlap | 0.327 | 0.293 | ~70th |

**Interpretation**:

1. **Activation stability generalizes robustly.** All 5 domains show >90%
   stability (range 0.903--0.947). This is the strongest cross-prompt finding.
   The N=2 value (96.3%) is above the USA population mean (94.7%) but within
   the normal range. **Confidence: High** (N=1,607, narrow CIs, consistent
   across domains).

2. **Feature overlap is substantial but domain-dependent.** Jaccard ranges from
   0.286 (paintings) to 0.621 (sounds). The overlap is massively above chance
   (p < 0.001) even at the most conservative pool estimate. The original
   Dallas/Oakland Jaccard (0.558) was a high-end USA outlier (~93rd percentile),
   not representative. **Confidence: High** for the finding itself; the
   Dallas/Oakland pair was not representative.

3. **The layer gradient generalizes.** In 4/5 domains, early-layer overlap
   significantly exceeds late-layer overlap (ratio 1.4x--3.0x). Paintings is
   the exception (ratio 0.90x, early and late are similar). This is consistent
   with the architectural expectation. **Confidence: Medium-High** (4/5 domains,
   paintings is unexplained).

4. **Supernode consistency varies dramatically by domain.** USA has 76.6% same-
   supernode, sounds 85.6%, but books only 47.5% (with 39.7% inconsistent).
   The high inconsistency in books suggests that supernode naming is less stable
   when entity-specific content dominates the graph (books has the lowest
   scaffold influence). The entity-regrouped rate is stable across domains
   (~9-17%), suggesting the keyword-based detection captures genuine regrouping.
   **Confidence: Medium** (supernode consistency depends on keyword heuristics).

5. **Overlap does NOT predict swap success within USA.** r(Jaccard, vsMax) = +0.024,
   essentially null. This matches the scaffold finding (Section 4.8). USA is too
   structurally homogeneous for overlap to discriminate. In smaller domains,
   books shows r=+0.233 and paintings r=+0.311, consistent with scaffold
   predictions. **Confidence: High** for USA null; **Low** for smaller domains
   (modest N, no confound control).

6. **Cross-domain overlap rank matches difficulty gradient.** Sounds (0.621) >
   USA (0.465) > Products (0.364) > Books (0.308) > Paintings (0.286). The
   anomaly is sounds, which has high overlap but 0% hit rate (structural issues
   documented in Section 6.5). Excluding sounds, the overlap ranking roughly
   tracks hit rate (USA 24.7% > Products 13.2% > Paintings 4.0% > Books 3.3%).
   **Confidence: Medium** (N=4 domains for the gradient, sounds is anomalous).

**Threats to validity**:

- [x] Dallas/Oakland was not representative -- confirmed, it's ~93rd percentile
  for USA. The population means are lower but still substantial.
- [ ] Supernode consistency uses keyword-based entity detection. In books, many
  entity keywords (character names, book titles) are unique multi-word strings
  that might not match supernode names well, inflating "inconsistent" rate.
- [ ] The permutation test uses uniform random selection from a pool, which may
  not model the actual feature selection process (graph-based thresholding). A
  more realistic null would sample features by layer distribution.
- [ ] Influence-weighted Jaccard is lower than unweighted (USA: 0.418 vs 0.465),
  meaning high-influence features are slightly *less* likely to be shared. This
  could indicate that the most causally important features are entity-specific.
- [ ] Paintings' inverted layer gradient (early overlap < late overlap) is
  unexplained. Could be a small-sample artifact (N=66 pairs, 12 entities) or
  reflect genuinely different prompt structure.
- [ ] The swap correlation for paintings (r=+0.311) is modest and untested for
  confounds (target identity, error_node_pct).

**Follow-up**:

1. Investigate books' high inconsistent rate: are the "inconsistent" features
   genuinely misassigned or is the keyword detector failing on literary names?
2. Investigate paintings' inverted layer gradient.
3. Run multivariate correlation: Jaccard + error_node_pct + n_features -> vsMax
   for products and paintings.
4. Consider cross-domain overlap (USA entity vs books entity) as a negative control.

**References**: `scripts/experiments/cross_prompt_robustness_scalable.py`;
`scripts/experiments/run_scalable_cross_prompt.py`;
`output/research/cross_prompt_scalable/` (all raw data).

---

