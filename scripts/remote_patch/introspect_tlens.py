from transformer_lens import HookedTransformer
import inspect

print("has_generate", hasattr(HookedTransformer, "generate"))
print("has_generate_stream", hasattr(HookedTransformer, "generate_stream"))
if hasattr(HookedTransformer, "generate"):
    print("generate_sig", inspect.signature(HookedTransformer.generate))
    print("generate_doc:")
    print(HookedTransformer.generate.__doc__)

