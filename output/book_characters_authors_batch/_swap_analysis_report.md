# Book Characters Authors - Swap Experiment Analysis

**Run:** `20260316_072435_book_characters_authors_swap_mab-2_mam20_seed42_cfg-738101ec91`
**Date:** 2026-03-16
**Model:** google/gemma-2-2b + mntss/clt-gemma-2-2b-2.5M
**Config:** M_ablate=-2, M_amplify=20, matrix mode, 16x16 = 256 pairs

## 1. Overall Results

| Metric                       | Value         |
|------------------------------|---------------|
| Total pairs                  | 256 (16 identity + 240 swap) |
| Target author exact match    | 94/256 (36.7%) |
| Source author suppressed     | 203/256 (79.3%) |

Suppression works well (ablating source author features effectively removes
the original answer). Amplification is weaker: the steered output contains
the target author in only ~37% of cases.


## 2. Per-Target Hit Rate (amplification effectiveness)

Sorted from worst to best. This measures "when we amplify target author
features from entity X's graph, does the steered output contain that author?"

| Target Entity       | Author                | Amp Features | Hit Rate |
|---------------------|-----------------------|:------------:|:--------:|
| oliver_twist        | Charles Dickens       | 167          | 0%       |
| winston_smith       | George Orwell         | 33           | 0%       |
| holden_caulfield    | J.D. Salinger         | 9            | 0%       |
| raskolnikov         | Fyodor Dostoevsky     | 26           | 0%       |
| don_quixote         | Miguel de Cervantes   | 96           | 0%       |
| dracula             | Bram Stoker           | 104          | 0%       |
| jay_gatsby          | F. Scott Fitzgerald   | 121          | 0%       |
| hermione_granger    | J.K. Rowling          | 53           | 7%       |
| anna_karenina       | Leo Tolstoy           | 81           | 27%      |
| frodo_baggins       | J.R.R. Tolkien        | 74           | 33%      |
| scout_finch         | Harper Lee            | 48           | 33%      |
| elizabeth_bennet    | Jane Austen           | 51           | 80%      |
| atticus_finch       | Harper Lee            | 49           | 87%      |
| captain_ahab        | Herman Melville       | 58           | 100%     |
| huckleberry_finn    | Mark Twain            | 111          | 100%     |
| katniss_everdeen    | Suzanne Collins       | 63           | 100%     |

Key observation: **high feature count does not guarantee success**.
oliver_twist (167 features) and jay_gatsby (121 features) both have 0% hit
rate, while captain_ahab (58 features) achieves 100%.


## 3. Per-Source Suppression Rate (ablation effectiveness)

| Source Entity       | Author                | Ablate Features | Suppression |
|---------------------|-----------------------|:---------------:|:-----------:|
| anna_karenina       | Leo Tolstoy           | 81              | 69%         |
| dracula             | Bram Stoker           | 81*             | 69%         |
| elizabeth_bennet    | Jane Austen           | 51*             | 69%         |
| hermione_granger    | J.K. Rowling          | 53*             | 75%         |
| atticus_finch       | Harper Lee            | 49              | 75%         |
| don_quixote         | Miguel de Cervantes   | 96*             | 75%         |
| holden_caulfield    | J.D. Salinger         | 9*              | 75%         |
| katniss_everdeen    | Suzanne Collins       | 63*             | 75%         |
| frodo_baggins       | J.R.R. Tolkien        | 74*             | 81%         |
| jay_gatsby          | F. Scott Fitzgerald   | 121*            | 81%         |
| scout_finch         | Harper Lee            | 48*             | 81%         |
| captain_ahab        | Herman Melville       | 58              | 88%         |
| huckleberry_finn    | Mark Twain            | 111*            | 88%         |
| oliver_twist        | Charles Dickens       | 167*            | 88%         |
| raskolnikov         | Fyodor Dostoevsky     | 26*             | 88%         |
| winston_smith       | George Orwell         | 33              | 94%         |

Ablation is broadly effective (69-94%) across all sources.


## 4. Supernode Coverage Analysis

### 4.1 Full-title supernodes are rare, but book concepts are still used

Only `dracula` has a supernode matching the full book title exactly
("Dracula"). However, the earlier conclusion that the `book` concept field
adds no steering signal for 15/16 seeds was incorrect.

The actual matcher in `03_ct_steering.py` first tries a full-string match and
then falls back to **per-word matching** for multi-word concepts. That means:

- `"Harry Potter"` matches `Harry`, `Potter`, `Say (Potter)`, `(Harry) related`
- `"The Great Gatsby"` matches `Great`, `Gatsby`
- `"Pride and Prejudice"` matches `Pride`, `Prejudice`, `Say (Pride)`
- `"Crime and Punishment"` matches `Crime`, `Punishment`, `(Crime) related`

Under the matcher actually used by the swap runner, the `book` field
contributes non-zero features for **15/16 seeds**. The only seed with zero
book-derived features is `winston_smith`, whose book `"1984"` does not surface
as a matching supernode.

Across the full run, deduplicated intervention features are split almost
evenly between book and author concepts:

- book-derived features: 567
- author-derived features: 577

So the correct conclusion is the opposite of the original one: `book` is not
dead weight in this experiment; it provides about half of all intervention
features.

### 4.2 Author supernodes per seed

| Slug               | Author                | Supernodes found                                       | Issues |
|---------------------|-----------------------|--------------------------------------------------------|--------|
| anna_karenina       | Leo Tolstoy           | leo, tolstoy, Say (tolstoy)                            | OK     |
| atticus_finch       | Harper Lee            | harper, Say (harper)                                   | No "lee" (too short, filtered) |
| captain_ahab        | Herman Melville       | herman, Say (herman), melville                         | OK     |
| don_quixote         | Miguel de Cervantes   | Say (miguel), miguel, cervantes, Say (cervantes)       | OK, "de" skipped |
| dracula             | Bram Stoker           | bram, Say (bram)                                       | **No "stoker"** |
| elizabeth_bennet    | Jane Austen           | jane, Say (jane), austen                               | OK     |
| frodo_baggins       | J.R.R. Tolkien        | tolkien, Say (tolkien)                                 | Only surname |
| hermione_granger    | J.K. Rowling          | rowling, Say (rowling)                                 | Only surname |
| holden_caulfield    | J.D. Salinger         | J, D                                                   | **No "salinger"!** |
| huckleberry_finn    | Mark Twain            | mark, Say (mark), twain                                | OK     |
| jay_gatsby          | F. Scott Fitzgerald   | Say (scott), scott, fitzgerald, F                      | OK     |
| katniss_everdeen    | Suzanne Collins       | Say (suzanne), suzanne, collins                        | OK     |
| oliver_twist        | Charles Dickens       | charles, Say (charles), dickens                        | OK     |
| raskolnikov         | Fyodor Dostoevsky     | Dosto, odor, Say (odor)                                | **No "dostoevsky"** (fragmented) |
| scout_finch         | Harper Lee            | harper, Say (harper)                                   | No "lee" |
| winston_smith       | George Orwell         | george, Say (george), orwell                           | OK     |

### 4.3 Critical supernode gaps

Three seeds have severely degraded author representation:

1. **holden_caulfield**: "J.D. Salinger" only yielded `J` (20 feats) and
   `D` (10 feats) -- just initials. The grouping never produced a
   "Salinger" or "Say (Salinger)" cluster. This explains 0% hit rate as
   target: 9 amplification features from two single-letter initials cannot
   steer the model toward "J.D. Salinger".

2. **raskolnikov**: "Fyodor Dostoevsky" is fragmented into `Dosto` (20),
   `odor` (30), `Say (odor)` (140). The tokenizer splits "Dostoevsky" into
   subword pieces, and the grouping algorithm assigned them different
   supernode names. The concept matcher searches for "dostoevsky" as a
   substring but finds no exact match. This explains 0% hit rate as target.

3. **dracula**: "Bram Stoker" only has `bram` and `Say (bram)` -- missing
   "stoker" entirely. Despite 104 amplification features, they all relate
   to the first name "Bram" which is ambiguous.

### 4.4 Reassessment across results, code, and groupings

#### Results

The weak targets are not failing because book features are absent. In several
0%-hit cases, book-derived features are actually the majority of the matched
intervention set:

- `oliver_twist`: 121 book + 46 author = 167 total
- `jay_gatsby`: 75 book + 46 author = 121 total
- `don_quixote`: 60 book + 36 author = 96 total
- `dracula`: 66 book + 38 author = 104 total

This means "high feature count but 0% hit rate" is often a **feature quality**
problem, not a **feature availability** problem. The matched book words are
present, but many are too generic (`Oliver`, `Don`, `Anna`, `Games`, `Kill`)
or too weakly tied to the desired author string to reliably force the correct
completion.

#### Code

There are two relevant code paths, and they do different things:

1. `run_batch_swaps.py` uses **all** configured `concept_fields` when building
   interventions, so `concept_fields: [book, author]` really does use both
   fields during steering.
2. `swap_loader.py` stores only the **first** concept field as
   `pair.from_concept` / `pair.to_concept`, and `swap_evaluator.py` serializes
   that single value into the JSON result as `source.concept` / `target.concept`.

That serialization choice can make the run artifacts look as if there is one
primary concept ("harry potter", "the great gatsby", etc.), even though the
actual intervention builder later adds both book and author features. This is
likely what made the earlier manual analysis misleading.

#### Groupings

The grouping stage usually does **not** produce whole-title supernodes for
multi-word book names. Instead it surfaces salient component words. That is
enough for the matcher to recover many book-related features, but it also
creates a specificity problem:

- useful cases: `Potter`, `Gatsby`, `Prejudice`, `Punishment`
- weak/generic cases: `Kill`, `Games`, `Anna`, `Don`, `Oliver`
- fully missing case: `1984`

So the grouping issue is not "book titles are unused"; it is "book titles are
often represented only by partial lexical fragments, and some fragments are too
generic to steer the answer field well."


## 5. Why High Feature Count Can Mean 0% Hit Rate

Seven targets have 0% hit rate despite having 9-167 amplification features.
The failure modes differ:

### 5.1 Polysemous first names (oliver_twist, don_quixote, dracula)

Features for "Charles" (oliver_twist) activate for any Charles -- not
specifically Charles Dickens. Amplifying 167 "Charles" features creates a
noisy signal that doesn't reliably produce "Charles Dickens". Similarly,
"Miguel" and "Bram" are common names. Steered outputs are often garbled:

```
steered: "...was written by, and the movie was dir"  (oliver_twist target)
steered: "...was written by's first novel. It was"   (don_quixote target)
```

### 5.2 Fragmented/missing author supernodes (raskolnikov, holden_caulfield)

When the tokenizer splits an author name into unusual subwords and the
grouping doesn't reassemble them, the **author-side** concept matcher fails to
find enough specific features. These targets may still receive book-derived
features (`Crime`, `Punishment`, `Catcher`), but those do not reliably produce
the desired author string. Amplifying "Dosto" fragments or single-letter
initials produces gibberish or weak, non-specific steering.

### 5.3 "Say" supernodes dominate but lack semantic specificity (winston_smith, jay_gatsby)

winston_smith has `Say (George)` (145 feats) and `George` (15 feats).
jay_gatsby has `Say (Scott)` (200 feats) and `Scott` (10 feats).
These "Say (X)" groups capture features that predict the next token "X" --
they are output-layer features. But "George" and "Scott" are common tokens
not specific to Orwell or Fitzgerald. Amplifying them may increase the
probability of those tokens without creating a coherent "George Orwell"
or "F. Scott Fitzgerald" completion.


## 6. Successful Swap Examples

### captain_ahab -> katniss_everdeen (100% success)
```
default: "...Captain Ahab was written by Herman Melville. The novel..."
steered: "...Captain Ahab was written by Suzanne Collins. The book..."
```
58 ablation features (herman, melville, Say(herman)) cleanly suppress
Melville; 63 amplification features (suzanne, collins, Say(suzanne))
cleanly inject Collins.

### don_quixote -> atticus_finch (success)
```
default: "...Don Quixote was written by Miguel de Cervantes..."
steered: "...Don Quixote was written by Harper Lee..."
```
96 ablation features suppress Cervantes; 49 amplification features
inject Harper Lee.


## 7. Near-miss patterns

Several failures are "near-misses" where the model shifts toward the
correct answer but doesn't produce the exact target string:

- anna_karenina -> raskolnikov: steered output says "Dostoyevsky" (English
  transliteration variant) but exact match expects "Fyodor Dostoevsky"
- anna_karenina -> frodo_baggins: steered output says "J.D. Salinger"
  (wrong author, but an author with initials -- partial concept transfer)


## 8. Recommendations

1. **Relax exact match**: Use fuzzy/semantic matching for evaluation.
   "Dostoyevsky" vs "Fyodor Dostoevsky" should count as a hit.

2. **Improve grouping for subword-fragmented names**: When the tokenizer
   splits names like "Dostoevsky" into "Dosto" + "evsky", the grouping
   should attempt to merge adjacent subword supernodes into a single
   cluster.

3. **Do not drop the `book` concept field based on this run**: Book-derived
   matches exist for 15/16 seeds and account for 567/1144 total intervention
   features (~49.6%). If anything, the next step is to separate and inspect
   book-vs-author contributions explicitly rather than assuming `book` is
   unused.

4. **Log matched supernode names per concept in the swap artifacts**: Storing
   the exact matched supernode names and per-concept feature counts would make
   it much easier to audit whether a swap was driven by book words, author
   words, or both.

5. **Consider "Say (X)" supernode quality**: Features that simply predict
   a common first name (George, Charles, Scott) are not specific enough
   for reliable amplification. A threshold on supernode specificity or
   name-uniqueness could filter these out.

6. **Investigate why some author supernodes are missing**: "Stoker" (from
   dracula), "Salinger" (from holden_caulfield) are absent from their
   graphs. This may be a graph generation or grouping threshold issue
   rather than a fundamental limitation.
