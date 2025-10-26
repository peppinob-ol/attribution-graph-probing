# Token Blacklist Feature for Node Naming

## Overview

The Token Blacklist feature allows you to exclude specific tokens from being selected as labels for supernodes. When a token is blacklisted, the system automatically falls back to the second (or next available) token with the highest activation.

## Why Use This Feature?

Some tokens might be semantically uninformative or too generic to serve as good labels. For example:
- Common function words: "the", "a", "is"
- Punctuation that appears frequently
- Special tokens: "<bos>", "<eos>", "<pad>"
- Generic terms that don't add semantic value

By blacklisting these tokens, you ensure that your supernodes get more meaningful, interpretable labels.

## How It Works

### Fallback Mechanism

The system implements a **smart fallback** mechanism:

1. **Semantic Nodes**: 
   - Sorts all candidate tokens by `activation_max` (descending)
   - Iterates through candidates and selects the first token NOT in the blacklist
   - Falls back to "Semantic (unknown)" if all tokens are blacklisted

2. **Relationship Nodes**:
   - Collects all token activations from probe prompts
   - Sorts by activation (descending)
   - Selects first semantic token NOT in the blacklist
   - Multiple fallback levels ensure robust naming

3. **Say X Nodes**:
   - Iterates through records sorted by `activation_max` (descending)
   - For each record, checks target_tokens
   - Selects first target token NOT in the blacklist
   - Falls back to "Say (?)" if all targets are blacklisted

## Usage

### Via Streamlit UI

1. Navigate to **Node Grouping** page (02_Node_Grouping.py)
2. In the sidebar, find **"Token Blacklist"** section
3. Enter tokens to blacklist, **one per line** (case-insensitive)
4. Run Step 3 (Naming) - blacklisted tokens will be automatically skipped

Example input:
```
the
a
is
was
<bos>
<eos>
```

### Via Command Line

Use the `--blacklist` argument with comma-separated tokens:

```bash
python scripts/02_node_grouping.py \
    --input output/export.csv \
    --output output/export_GROUPED.csv \
    --json output/activations_dump.json \
    --graph output/graph_data/example.json \
    --blacklist "the,a,is,was,<bos>,<eos>" \
    --verbose
```

### Via Python API

```python
from scripts.node_grouping import name_nodes

# Define blacklist
blacklist_tokens = {'the', 'a', 'is', 'was', '<bos>', '<eos>'}

# Call name_nodes with blacklist
df_named = name_nodes(
    df_classified,
    activations_json_path="output/activations_dump.json",
    graph_json_path="output/graph_data/example.json",
    blacklist_tokens=blacklist_tokens,
    verbose=True
)
```

## Configuration

### Global Default Blacklist

You can set a global default blacklist in `scripts/02_node_grouping.py`:

```python
# Token blacklist: tokens che non dovrebbero essere usati come label
TOKEN_BLACKLIST = {
    'the', 'a', 'is', '<bos>', '<eos>'  # Add your defaults here
}
```

### Per-Run Blacklist

Pass custom blacklist via function parameters or CLI arguments to override the global default.

## Examples

### Example 1: Excluding Generic Articles

**Without blacklist:**
- Feature `1_12345` → Label: "the"
- Feature `2_67890` → Label: "a"

**With blacklist `{'the', 'a'}`:**
- Feature `1_12345` → Label: "capital" (second highest activation)
- Feature `2_67890` → Label: "city" (second highest activation)

### Example 2: Excluding Special Tokens

**Without blacklist:**
- Feature `5_11111` → Label: "<bos>"

**With blacklist `{'<bos>', '<eos>'}`:**
- Feature `5_11111` → Label: "Texas" (first non-blacklisted token)

## Technical Details

### Implementation

- **Case-insensitive matching**: All tokens are normalized to lowercase before checking
- **Order preservation**: Falls back in order of activation strength (highest to lowest)
- **Multiple fallback levels**: Each naming function has multiple fallback strategies
- **No mutation**: Original data is never modified; blacklist only affects label selection

### Performance

- **Minimal overhead**: Blacklist checking is O(1) using set lookups
- **No extra API calls**: Fallback uses existing activation data
- **Memory efficient**: Blacklist stored as a small set

## Best Practices

1. **Start conservative**: Begin with a small blacklist (common function words)
2. **Iterate**: Add tokens to blacklist as you identify uninformative labels
3. **Document**: Keep track of which tokens you've blacklisted and why
4. **Review results**: Check naming quality after adding tokens to blacklist
5. **Domain-specific**: Customize blacklist based on your specific use case

## Troubleshooting

### All tokens are blacklisted

If you see labels like "Semantic (unknown)" or "Say (?)", you might have blacklisted too many tokens.

**Solution**: Reduce your blacklist or check if it's too broad.

### Fallback not working

Ensure you're passing the blacklist parameter correctly:
- CLI: Use `--blacklist "token1,token2"`
- Python: Use `blacklist_tokens=set(['token1', 'token2'])`
- Streamlit: Enter tokens one per line in the text area

### Case sensitivity issues

All blacklist matching is case-insensitive. "The", "THE", and "the" are all treated identically.

## Future Enhancements

Potential improvements for future versions:
- Pattern-based blacklisting (e.g., regex)
- Token category blacklisting (e.g., "all punctuation")
- Whitelist mode (only allow specific tokens)
- Context-aware blacklisting (different blacklists for different node types)

## Summary

The Token Blacklist feature is a simple but powerful tool for improving the quality of supernode labels. By excluding uninformative tokens and falling back to more meaningful alternatives, you can create cleaner, more interpretable attribution graphs.

**Key Points:**
- ✅ Easy to use (UI, CLI, or Python API)
- ✅ Smart fallback mechanism
- ✅ No performance overhead
- ✅ Flexible and customizable
- ✅ Works with all node types (Semantic, Relationship, Say X)

