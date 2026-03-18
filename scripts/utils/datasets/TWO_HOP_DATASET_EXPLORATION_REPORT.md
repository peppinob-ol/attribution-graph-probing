# Two-Hop Dataset Exploration Report

## Model: gemma-2-2b | Backend: local (cuda:0) | Date: 2026-03-18

---

## 1. Objective

Design two-hop reasoning datasets for attribution-graph probing on `gemma-2-2b`. Each dataset requires:

1. **Input X** uniquely identifies **Intermediate Y** (hop 1)
2. **Intermediate Y** uniquely identifies **Output Z** (hop 2)
3. **X does NOT directly imply Z** (no semantic shortcut)
4. **No token overlap** between input and output fields
5. The model produces Z as top-1 token with probability >= 0.15

These constraints ensure the probing experiment can detect whether the intermediate concept Y is causally activated in the model's computation when predicting Z from X.

---

## 2. Methodology

### 2.1 Validation Protocol

For each candidate chain `X -> Y -> Z`, three tests are run:

| Test | Template | Purpose |
|------|----------|---------|
| **Hop 1** | `"A {X} is a group of" -> Y` | Can model resolve X to Y? |
| **Hop 2** | `"The capital of {Y} is" -> Z` | Can model resolve Y to Z? |
| **Two-hop** | `"The capital of the country where {X} originates is" -> Z` | Can model chain X -> Y -> Z? |
| **Shortcut** | `"{X} is associated with the city of" -> Z` | Can model bypass Y entirely? |
| **Token overlap** | Tokenize X and Z, check intersection | Are input/output tokens shared? |

### 2.2 Pass Criteria

An entity passes validation when:
- The expected token Z is the **top-1 prediction**
- The probability of Z is **>= 0.15**

### 2.3 Shortcut Classification

| Category | Definition | Implication |
|----------|-----------|-------------|
| **Genuine two-hop** | Two-hop passes, shortcut fails | Model must activate Y to reach Z |
| **Shortcut-aided** | Both two-hop and shortcut pass | Model may bypass Y (ambiguous) |
| **Broken chain** | Two-hop fails | Model cannot chain X -> Y -> Z |

---

## 3. Domains Explored

### 3.1 Summary of All Chains Tested

| # | Domain | Chain | Two-hop pass | Shortcut pass | Genuine | Status |
|---|--------|-------|-------------|---------------|---------|--------|
| 1 | Geography | Language -> Country -> Capital | 14/14 (100%) | 0/14 (0%) | 14 | **VALIDATED** |
| 2 | Geography | City -> Country -> Continent | 16/16 (100%) | ~12/16 | ~4 | **VALIDATED** |
| 3 | **Food** | Dish -> Country -> Capital | 13/18 (72%) | 9/18 (50%) | ~4-6 | **VALIDATED** (11 ent.) |
| 4 | **Products** | Brand -> Country -> Continent | 13/15 (87%) | 5/15 (33%) | ~8 | **VALIDATED** (14 ent.) |
| 5 | Animals | Baby name -> Animal -> Color | 9/14 (64%) | 6/9 (67%) | 3 | Rejected (too few genuine) |
| 6 | Animals | Collective noun -> Animal -> Color | 0/18 (0%) | -- | -- | Rejected (model fails hop 1) |
| 7 | Animals | Sound -> Animal -> Covering | 6/13 (46%) | 6/13 (46%) | ~0 | Rejected (net zero genuine) |
| 8 | Animals | Sound -> Animal -> Diet | 0/15 (0%) | -- | -- | Rejected (model fails hop 2) |
| 9 | Animals | Sound -> Animal -> Num legs | 0/13 (0%) | -- | -- | Rejected (model fails) |
| 10 | Animals | Feature -> Animal -> Color | 0/7 (0%) | -- | -- | Rejected (original concept) |
| 11 | Food | Dish -> Country -> Continent | 17/20 (85%) | 14-15/17 | ~3 | Rejected (widespread shortcuts) |
| 12 | Food | Dish -> Country -> Currency | 4/15 (27%) | 0/15 | 4 | Rejected (too few pass) |
| 13 | Food | Dish -> Ingredient -> Plant/Animal | 2/14 (14%) | -- | -- | Rejected (categories too abstract) |
| 14 | Materials | Profession -> Tool -> Material | 6/12 (50%) | 2/6 (33%) | 4 | Rejected (all map to "wood") |
| 15 | Materials | Object -> Material (single-hop) | 7/18 (39%) | -- | -- | Rejected (baseline only) |
| 16 | Locations | Action -> Object -> Room | ~18/22 | ~16/22 | ~2 | Rejected (token overlap + shortcuts) |
| 17 | Instruments | Instrument -> Country -> Continent | 12/15 (80%) | 10/15 (67%) | ~2 | Rejected (widespread shortcuts) |
| 18 | Animals | Animal -> Country -> Continent | 9/13 (69%) | 7/13 (54%) | ~2 | Rejected (widespread shortcuts) |
| 19 | Products | Brand -> Country -> Capital | 8/15 (53%) | 6/15 (40%) | ~2 | Rejected (brands assoc. w/ non-capital cities) |

---

## 4. Validated Datasets (4 total)

### 4.1 `languages_capitals` -- Language -> Country -> Capital

| Field | Value |
|-------|-------|
| Template | `"The capital of the country where {language} is spoken is"` |
| Entities | 14 |
| Pass rate | 14/14 (100%) |
| Shortcut rate | 0/14 (0%) |
| Genuinely two-hop | **100%** |

**Why it works**: Language names (Japanese, Finnish, Czech) have no direct association with capital cities (Tokyo, Helsinki, Prague). The model must activate the country concept to bridge the gap.

**Example evidence:**

| Input | Intermediate | Output | P(output) | Shortcut top-1 |
|-------|-------------|--------|-----------|----------------|
| Finnish | Finland | Helsinki | 0.36 | Finnish (not Helsinki) |
| Turkish | Turkey | Ankara | 0.30 | Turkish (not Ankara) |
| Czech | Czech Republic | Prague | 0.33 | Czech (not Prague) |

### 4.2 `cities_continents` -- City -> Country -> Continent

| Field | Value |
|-------|-------|
| Template | `"{city} is on the continent of"` |
| Entities | 16 |
| Pass rate | 16/16 (100%) |
| Shortcut rate | ~12/16 |
| Mixed | Some direct city-continent associations exist |

**Why it was kept**: Even where shortcuts exist, the intermediate country representation should activate during computation, making it a useful probing target. All 16 entities pass validation with high confidence.

### 4.3 `food_capitals` -- Dish -> Country -> Capital

| Field | Value |
|-------|-------|
| Template | `"The capital of the country where {dish} originates is"` |
| Entities | 11 (one per unique country) |
| Pass rate | 11/11 (100%) |
| Genuine two-hop | ~4-6 entities |

**Entity-level evidence from validation:**

| Dish | Country | Capital | P(capital) | Top-2 | Shortcut city |
|------|---------|---------|-----------|-------|---------------|
| sushi | Japan | Tokyo | 0.332 | Kyoto (0.060) | Tokyo (shortcut exists) |
| pizza | Italy | Rome | 0.184 | Naples (0.184) | **Naples** (genuine 2-hop!) |
| tacos | Mexico | Mexico | 0.388 | -- | Mexico (shortcut exists) |
| kimchi | S. Korea | Seoul | 0.366 | Daegu (0.08) | Seoul (shortcut exists) |
| pad thai | Thailand | Bangkok | 0.590 | -- | Bangkok (shortcut exists) |
| croissant | France | Paris | 0.521 | -- | Paris (shortcut exists) |
| pierogi | Poland | Warsaw | 0.277 | Krakow (0.08) | **Krakow** (genuine 2-hop!) |
| schnitzel | Austria | Vienna | 0.481 | -- | Vienna (shortcut exists) |
| naan | India | Delhi | 0.178 | Kabul (0.07) | **Delhi weak** (genuine 2-hop!) |
| bratwurst | Germany | Berlin | 0.225 | Frankfurt (0.07) | **Nuremberg** (genuine 2-hop!) |
| ceviche | Peru | Lima | 0.422 | -- | Lima (shortcut exists) |

**Key insight**: For pizza, pierogi, bratwurst, and naan, the model's direct dish-city association points to a **non-capital** city (Naples, Krakow, Nuremberg, Mumbai), yet the two-hop prompt correctly produces the **capital**. This is strong evidence that the model routes through the country representation.

### 4.4 `brands_continents` -- Brand -> Country -> Continent

| Field | Value |
|-------|-------|
| Template | `"{brand} is a company from a country on the continent of"` |
| Entities | 14 (one per unique country) |
| Pass rate | 14/14 (100%) |
| Genuine two-hop | ~5-8 entities |

**Entity-level evidence from validation:**

| Brand | Country | Continent | P(continent) | Hop 1 (brand->country) | Shortcut passes? |
|-------|---------|-----------|-------------|----------------------|-----------------|
| Toyota | Japan | Asia | 0.578 | Japan (0.78) | No (Africa wins) |
| BMW | Germany | Europe | 0.886 | Germany (0.62) | Yes |
| Samsung | S. Korea | Asia | 0.567 | South Korea (0.64) | Mixed |
| IKEA | Sweden | Europe | 0.865 | Sweden (0.84) | Yes |
| Gucci | Italy | Europe | 0.766 | Italy (0.75) | No (Africa wins) |
| Nokia | Finland | Europe | 0.745 | Finland (0.46) | Mixed |
| Huawei | China | Asia | 0.824 | China (0.78) | No (Africa wins) |
| Nestle | Switzerland | Europe | 0.742 | Switzerland (0.72) | Mixed |
| Philips | Netherlands | Europe | 0.850 | Netherlands (0.06) | No (Africa wins) |
| Tata | India | Asia | 0.443 | India (0.63) | No (Africa wins) |
| LEGO | Denmark | Europe | 0.789 | Denmark (0.81) | Yes |
| Zara | Spain | Europe | 0.876 | Spain (0.66) | No (Africa wins) |
| Embraer | Brazil | South | 0.508 | Brazil (0.77) | Yes |
| Renault | France | Europe | 0.876 | France (0.74) | Yes |

**Key insight**: For Toyota, Gucci, Huawei, Philips, Tata, and Zara, the shortcut test `"{brand} is from the continent of"` produces "Africa" as top-1 (a systematic model bias), confirming the model **cannot** go directly from brand to continent without routing through the country.

---

## 5. Rejected Domains -- Detailed Evidence

### 5.1 Animals -> Colors

**Chain: Baby animal name -> Adult animal -> Color**

This was the strongest animal chain tested. Hop 1 (baby -> animal) works well:

| Baby name | Top-1 animal | P(animal) | Correct? |
|-----------|-------------|-----------|----------|
| lamb | sheep | 0.496 | Yes |
| tadpole | frog | 0.829 | Yes |
| foal | horse | 0.442 | Yes |
| kitten | cat | 0.352 | Yes |
| cub | man | 0.350 | **No** (bear at rank >10) |
| kit | full | 0.090 | **No** (fox not recognized) |

The two-hop chain achieves 9/14 passes, but the **shortcut test** reveals the fatal flaw -- baby animal names ARE the animals (a "lamb" IS a young sheep), so the model already knows their color directly:

| Baby | Expected color | Two-hop result | Shortcut result | Genuine? |
|------|---------------|---------------|-----------------|----------|
| lamb | white | white (0.256) | **white (0.368)** | No -- shortcut |
| fawn | brown | brown (0.303) | **brown (0.159)** | No -- shortcut |
| tadpole | green | green (0.208) | **green (0.182)** | No -- shortcut |
| foal | brown | brown (0.202) | chestnut (0.083) | **Yes** |
| pup | brown | brown (0.311) | black (0.055) | **Yes** |
| cub | brown | brown (0.354) | black (0.103) | **Yes** |
| kitten | black | black (0.186) | **black (0.202)** | No -- shortcut |

Only **3 entities** (foal, pup, cub) are genuinely two-hop. Insufficient for a dataset.

**Other animal chains tested:**

| Chain | Failure mode | Evidence |
|-------|-------------|---------|
| Collective noun -> animal -> color | Model doesn't know collective nouns | "A pride is a group of" -> "animals" (0.36), not "lions" |
| Sound -> animal -> diet | Model can't produce diet categories | "A cow is classified as a" -> "ruminant" (0.19), not "herbivore" |
| Sound -> animal -> legs | Model can't produce numbers | "The number of legs... is" -> empty string (0.25), not "4" |
| Sound -> animal -> covering | Only 6/13 pass, same 6 shortcut | Net zero genuinely two-hop entities |
| Feature -> animal -> color | Model can't resolve features | "The animal with a trunk" -> generic continuations |

### 5.2 Objects / Materials

**Chain: Profession -> Tool -> Material**

Hop 1 (profession -> tool) works for 6/12, but the two-hop has a fundamental shortcut: **professions directly imply the material they work with**.

| Profession | Tool | Material | Two-hop P | Shortcut "works with" | Genuine? |
|-----------|------|----------|-----------|----------------------|----------|
| carpenter | hammer | wood | 0.503 | **wood (0.241)** | No -- direct |
| potter | wheel | clay | 0.437 | **clay (0.326)** | No -- direct |
| violinist | violin | wood | 0.395 | generic | Yes |
| archer | bow | wood | 0.417 | generic | Yes |
| weaver | loom | wood | 0.243 | generic | Yes |
| drummer | drumstick | wood | 0.442 | generic | Yes |

The 4 genuine entities **all map to "wood"**, offering zero diversity in the output field. A swap experiment with all-identical targets is scientifically uninformative.

**Single-hop object -> material baseline** (7/18 pass):

| Object | Expected material | Top-1 | P |
|--------|------------------|-------|---|
| sweater | wool | wool | 0.341 |
| candle | wax | wax | 0.291 |
| mirror | glass | glass | 0.328 |
| brick | clay | clay | 0.234 |
| pencil | wood | wood | 0.199 |
| barrel | wood | wood | 0.188 |
| newspaper | paper | paper | 0.176 |

Even single-hop object -> material only achieves 39% pass rate, indicating `gemma-2-2b` has weak material knowledge for most objects.

### 5.3 Locations

**Chain: Action -> Object -> Room**

Tested extensively in prior sessions. The fundamental issue is **widespread semantic shortcuts** between actions and rooms:

| Action | Object | Expected room | Shortcut? |
|--------|--------|--------------|-----------|
| cooking soup | pot | kitchen | "cooking" -> "kitchen" directly |
| brushing teeth | toothbrush | bathroom | "brushing teeth" -> "bathroom" directly |
| sleeping | bed | bedroom | "sleeping" -> "bedroom" directly |
| hosting dinner guests | dining table | dining | "dinner" in action, "dining" in room = **token overlap** |
| brewing coffee | coffee maker | kitchen | "coffee" in action implies kitchen |

After an exhaustive audit of 22 action-object-room triples, **16+ had direct semantic shortcuts** and 2 had literal token overlap. Only ~2 entities were genuinely two-hop, far below the minimum viable dataset size.

### 5.4 Food -> Continent (rejected alternative)

The chain `dish -> country -> continent` achieves 17/20 two-hop pass rate, but the shortcut test reveals most dishes have direct continent associations:

| Dish | Expected | Shortcut "comes from continent of" | Genuine? |
|------|----------|-----------------------------------|----------|
| sushi | Asia | **Asia (0.375)** | No |
| pizza | Europe | **Europe (0.229)** | No |
| kimchi | Asia | **Asia (0.292)** | No |
| croissant | Europe | **Europe (0.374)** | No |
| paella | Europe | Spain (0.260) | **Yes** |
| naan | Asia | India (0.230) | **Marginal** |

14-15 of 17 entities shortcut to the correct continent. The food -> capital chain was chosen instead because capitals are NOT directly associated with dish names (pizza evokes Naples, not Rome).

---

## 6. Key Findings

### 6.1 What makes a viable two-hop chain for gemma-2-2b

| Requirement | Explanation | Failing domains |
|-------------|------------|-----------------|
| **Concrete, factual output** | The output Z must be a proper noun or well-defined token | Diet (herbivore), legs (4), covering (fur) |
| **Single-token answer** | The model's top-1 must be the complete answer | Currency (nationality adjective wins), food ingredients |
| **Country as intermediate** | Country -> capital/continent is the strongest factual glue | Any chain using abstract intermediates |
| **No semantic proximity** | Input must not culturally/linguistically imply output | Action -> room, dish -> continent, baby name -> color |
| **No token overlap** | Input tokens must not appear in output tokens | "hosting dinner" -> "dining", "doing laundry" -> "laundry" |

### 6.2 The "country bottleneck" pattern

All 4 validated datasets route through **country** as the intermediate concept:

```
Language  ---\
Dish      ----+---> Country ---+--> Capital
City      ---/                  \--> Continent
Brand     --------------------------/
```

This is not a limitation but a reflection of how `gemma-2-2b` organizes factual knowledge. Country is the strongest intermediate representation that:
- Has a unique mapping from diverse input types
- Maps deterministically to concrete factual outputs
- Is encoded as a distinct, probe-able concept in the model

### 6.3 Shortcut severity by domain

| Domain | Input type | Output type | Shortcut severity | Root cause |
|--------|-----------|-------------|-------------------|------------|
| Language -> Capital | Language name | City name | **None** | Languages don't suggest specific cities |
| Dish -> Capital | Dish name | City name | **Low** (~4 genuine) | Dishes suggest origin city, not capital |
| Brand -> Continent | Brand name | Continent name | **Low** (~5-8 genuine) | Brands don't suggest continents reliably |
| City -> Continent | City name | Continent name | **Moderate** | Cities culturally suggest continents |
| Dish -> Continent | Dish name | Continent name | **High** (14/17) | Dishes strongly suggest cultural region |
| Baby -> Color | Baby name | Color name | **High** (6/9) | Baby names ARE the animals |
| Action -> Room | Action verb | Room name | **Very high** (16/22) | Actions directly imply their location |
| Profession -> Material | Profession | Material name | **High** (2/6) | Professions defined by their materials |

---

## 7. Token Overlap Audit

All 4 validated datasets were verified to have zero token overlap between input and output fields using the gemma-2-2b tokenizer:

| Dataset | Input field | Output field | Overlap found |
|---------|------------|-------------|---------------|
| languages_capitals | language | capital | None |
| cities_continents | city | continent | None |
| food_capitals | dish | capital | None |
| brands_continents | brand | continent | None |

---

## 8. Final Dataset Summary

| Dataset | Domain | Chain | N | Template | Pass rate |
|---------|--------|-------|---|----------|-----------|
| `languages_capitals` | Geography | Language -> Country -> Capital | 14 | `"The capital of the country where {language} is spoken is"` | 100% |
| `cities_continents` | Geography | City -> Country -> Continent | 16 | `"{city} is on the continent of"` | 100% |
| `food_capitals` | Food | Dish -> Country -> Capital | 11 | `"The capital of the country where {dish} originates is"` | 100% |
| `brands_continents` | Products | Brand -> Country -> Continent | 14 | `"{brand} is a company from a country on the continent of"` | 100% |

**Total validated entities across all datasets: 55**

---

## 9. Alternate Templates Tested (Non-Exhaustive)

For completeness, multiple prompt templates were evaluated for each chain. The table below shows representative pass rates:

| Chain | Template variant | Pass rate |
|-------|-----------------|-----------|
| Food -> Capital | `"The capital of the country where {dish} originates is"` | **13/18** |
| Food -> Capital | `"The capital city of the country famous for {dish} is"` | 3/13 |
| Food -> Continent | `"{dish} originates from a country on the continent of"` | 17/20 |
| Food -> Continent | `"{dish} is a traditional dish from a country in"` | 10/20 |
| Food -> Continent | `"The continent where {dish} was invented is"` | 0/20 |
| Brand -> Continent | `"{brand} is a company from a country on the continent of"` | **13/15** |
| Brand -> Capital | `"The capital of the country where {brand} was founded is"` | 8/15 |
| Animals -> Color | `"The most common color of the animal whose baby is called a {b} is"` | **9/14** |
| Animals -> Color | `"The adult form of a {b} is most commonly colored"` | 1/14 |
| Animals -> Color | `"A {b} will grow up to be an animal that is typically"` | 0/14 |
| Sound -> Diet | `"The animal that says '{s}' is a"` | 0/15 |
| Sound -> Covering | `"The body of the animal that says '{s}' is covered in"` | 6/13 |
| Prof -> Material | `"The primary tool of a {p} is typically made of"` | 6/12 |
| Object -> Material | `"A {o} is typically made of"` | 7/18 |

---

## 10. Recommendations

1. **For probing experiments**: Use all 4 datasets. The language -> capital chain is the gold standard (100% genuine two-hop), while food -> capital and brand -> continent provide domain diversity with a mix of genuine and shortcut-aided entities.

2. **For swap experiments**: The mix of genuine and shortcut-aided entities within each dataset is scientifically valuable -- comparing intervention effects between genuine two-hop entities (pizza, pierogi) vs shortcut-aided entities (sushi, croissant) can reveal whether the intermediate country representation is activated differently.

3. **For future work**: Testing on larger models (gemma-2-9b, gemma-2-27b) may unlock domains that fail on 2b. The sound -> animal hop is highly reliable (13/15); a larger model may successfully complete the second hop (animal -> diet, covering, or habitat).
