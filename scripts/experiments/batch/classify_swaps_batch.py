#!/usr/bin/env python3
"""
Batch classification of swap results using OpenAI Batch API.

This is much faster and 50% cheaper than sequential API calls.

Usage:
    # Submit batch job
    python classify_swaps_batch.py submit --output-dir _analysis_batch

    # Check status
    python classify_swaps_batch.py status --batch-id batch_xxx

    # Download results when complete
    python classify_swaps_batch.py download --batch-id batch_xxx --output-dir _analysis_batch
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent paths for imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline.swap_classifier import SwapTier


def load_all_swap_results(swaps_dir: Path) -> List[Dict[str, Any]]:
    """Load all swap result JSON files."""
    results = []
    by_source = swaps_dir / "by_source"
    
    if not by_source.exists():
        print(f"ERROR: {by_source} not found")
        return results
    
    for source_dir in sorted(by_source.iterdir()):
        if not source_dir.is_dir():
            continue
        for result_file in sorted(source_dir.glob("to_*.json")):
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_file"] = str(result_file)
                    results.append(data)
            except Exception as e:
                print(f"  Warning: Failed to load {result_file}: {e}")
    
    return results


def build_classification_prompt(result: Dict[str, Any]) -> str:
    """Build the classification prompt for a single swap result."""
    source = result.get("source", {})
    target = result.get("target", {})
    raw = result.get("raw_output", {})
    
    source_state = source.get("state", "unknown")
    source_capital = source.get("capital", "unknown")
    target_state = target.get("state", "unknown")
    target_capital = target.get("capital", "unknown")
    
    prompt = raw.get("prompt", "")
    steered = raw.get("steered", "")
    
    return f"""Classify this steering experiment result.

SOURCE: {source_state} (capital: {source_capital})
TARGET: {target_state} (capital: {target_capital})

PROMPT: "{prompt}"
STEERED OUTPUT: "{steered}"

Classify into exactly ONE tier:
- PERFECT: Output contains the target capital ({target_capital})
- TARGET_STATE_CITY: Output contains a city in {target_state} (not the capital)
- TARGET_STATE_ONLY: Output references {target_state} but no specific city
- SUPPRESSED_ONLY: Source capital ({source_capital}) suppressed, but no target info
- SOURCE_PERSISTS: Source capital ({source_capital}) still appears in output
- WRONG_STATE: Output mentions a different state entirely

Respond with ONLY the tier name (e.g., "PERFECT" or "SUPPRESSED_ONLY")."""


def create_batch_requests(results: List[Dict[str, Any]], model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
    """Create batch request objects in OpenAI format."""
    requests = []
    
    for i, result in enumerate(results):
        prompt = build_classification_prompt(result)
        
        # Create unique ID from source->target
        source_slug = result.get("source", {}).get("slug", f"src_{i}")
        target_slug = result.get("target", {}).get("slug", f"tgt_{i}")
        custom_id = f"{source_slug}__to__{target_slug}"
        
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise classifier. Respond with only the tier name."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 50,
                "temperature": 0
            }
        }
        requests.append(request)
    
    return requests


def submit_batch(requests: List[Dict[str, Any]], output_dir: Path) -> Optional[str]:
    """Submit batch job to OpenAI."""
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai")
        return None
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        return None
    
    client = OpenAI(api_key=api_key)
    
    # Write requests to JSONL file
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "batch_requests.jsonl"
    
    print(f"Writing {len(requests)} requests to {jsonl_path}...")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req) + "\n")
    
    # Upload file
    print("Uploading file to OpenAI...")
    with open(jsonl_path, "rb") as f:
        file_response = client.files.create(file=f, purpose="batch")
    
    file_id = file_response.id
    print(f"  File uploaded: {file_id}")
    
    # Create batch
    print("Creating batch job...")
    batch = client.batches.create(
        input_file_id=file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": "Swap classification for 50x50 experiment"}
    )
    
    batch_id = batch.id
    print(f"  Batch created: {batch_id}")
    print(f"  Status: {batch.status}")
    
    # Save batch info
    batch_info = {
        "batch_id": batch_id,
        "file_id": file_id,
        "status": batch.status,
        "created_at": batch.created_at,
        "request_count": len(requests)
    }
    
    info_path = output_dir / "batch_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(batch_info, f, indent=2)
    
    print(f"\nBatch submitted successfully!")
    print(f"  Batch ID: {batch_id}")
    print(f"  Requests: {len(requests)}")
    print(f"  Info saved to: {info_path}")
    print(f"\nCheck status with:")
    print(f"  python classify_swaps_batch.py status --batch-id {batch_id}")
    
    return batch_id


def check_status(batch_id: str) -> Dict[str, Any]:
    """Check batch job status."""
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed")
        return {}
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return {}
    
    client = OpenAI(api_key=api_key)
    batch = client.batches.retrieve(batch_id)
    
    status_info = {
        "id": batch.id,
        "status": batch.status,
        "created_at": batch.created_at,
        "completed_at": getattr(batch, "completed_at", None),
        "failed_at": getattr(batch, "failed_at", None),
        "request_counts": {
            "total": batch.request_counts.total,
            "completed": batch.request_counts.completed,
            "failed": batch.request_counts.failed
        },
        "output_file_id": getattr(batch, "output_file_id", None),
        "error_file_id": getattr(batch, "error_file_id", None)
    }
    
    print(f"Batch Status: {batch.status}")
    print(f"  Total requests: {batch.request_counts.total}")
    print(f"  Completed: {batch.request_counts.completed}")
    print(f"  Failed: {batch.request_counts.failed}")
    
    if batch.status == "completed":
        print(f"\nBatch completed! Download results with:")
        print(f"  python classify_swaps_batch.py download --batch-id {batch_id} --output-dir _analysis_batch")
    elif batch.status == "failed":
        print(f"\nBatch failed!")
        if batch.error_file_id:
            print(f"  Error file: {batch.error_file_id}")
    else:
        progress = batch.request_counts.completed / max(batch.request_counts.total, 1) * 100
        print(f"  Progress: {progress:.1f}%")
    
    return status_info


def download_results(batch_id: str, output_dir: Path) -> bool:
    """Download and parse batch results."""
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed")
        return False
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return False
    
    client = OpenAI(api_key=api_key)
    batch = client.batches.retrieve(batch_id)
    
    if batch.status != "completed":
        print(f"ERROR: Batch not completed yet. Status: {batch.status}")
        return False
    
    if not batch.output_file_id:
        print("ERROR: No output file available")
        return False
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download output file
    print(f"Downloading results...")
    content = client.files.content(batch.output_file_id)
    
    results_path = output_dir / "batch_results.jsonl"
    with open(results_path, "wb") as f:
        f.write(content.read())
    
    print(f"  Saved to: {results_path}")
    
    # Parse results
    print("Parsing results...")
    classifications = {}
    tier_counts = {tier.name: 0 for tier in SwapTier}
    
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            result = json.loads(line)
            custom_id = result.get("custom_id", "")
            response = result.get("response", {})
            
            if response.get("status_code") == 200:
                body = response.get("body", {})
                choices = body.get("choices", [])
                if choices:
                    tier_str = choices[0].get("message", {}).get("content", "").strip().upper()
                    
                    # Map to SwapTier - exact match first, then partial
                    tier = None
                    # Clean up response
                    tier_str = tier_str.replace("_", "").replace(" ", "").upper()
                    
                    # Try exact match first
                    tier_mapping = {
                        "PERFECT": SwapTier.PERFECT,
                        "TARGETSTATECITY": SwapTier.TARGET_STATE_CITY,
                        "TARGETSTATEONLY": SwapTier.TARGET_STATE_ONLY,
                        "SUPPRESSEDONLY": SwapTier.SUPPRESSED_ONLY,
                        "SOURCEPERSISTS": SwapTier.SOURCE_PERSISTS,
                        "WRONGSTATE": SwapTier.WRONG_STATE,
                    }
                    
                    for key, value in tier_mapping.items():
                        if key in tier_str:
                            tier = value
                            break
                    
                    if tier is not None:
                        classifications[custom_id] = tier.name
                        tier_counts[tier.name] += 1
                    else:
                        classifications[custom_id] = "UNKNOWN"
                        print(f"  Warning: Unknown tier '{tier_str}' for {custom_id}")
            else:
                print(f"  Warning: Failed request for {custom_id}")
    
    # Save classifications
    class_path = output_dir / "classifications.json"
    with open(class_path, "w", encoding="utf-8") as f:
        json.dump(classifications, f, indent=2)
    
    print(f"\nClassification complete!")
    print(f"  Total classified: {len(classifications)}")
    print(f"\nTier distribution:")
    for tier_name, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / len(classifications) * 100
            print(f"  {tier_name}: {count} ({pct:.1f}%)")
    
    print(f"\nResults saved to: {class_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Batch classify swap results using OpenAI Batch API",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit batch classification job")
    submit_parser.add_argument("--output-dir", type=str, default="_analysis_batch",
                               help="Output directory for batch files")
    submit_parser.add_argument("--swaps-dir", type=str, default=None,
                               help="Swaps directory (default: auto-detect)")
    submit_parser.add_argument("--model", type=str, default="gpt-4o-mini",
                               help="Model to use (default: gpt-4o-mini)")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check batch job status")
    status_parser.add_argument("--batch-id", type=str, required=True,
                               help="Batch ID to check")
    
    # Download command
    download_parser = subparsers.add_parser("download", help="Download batch results")
    download_parser.add_argument("--batch-id", type=str, required=True,
                                 help="Batch ID to download")
    download_parser.add_argument("--output-dir", type=str, default="_analysis_batch",
                                 help="Output directory")
    
    args = parser.parse_args()
    
    if args.command == "submit":
        # Find swaps directory
        if args.swaps_dir:
            swaps_dir = Path(args.swaps_dir)
        else:
            # Auto-detect
            possible_paths = [
                Path("../../..") / "output" / "usa_states_batch" / "_swaps",
                Path("output") / "usa_states_batch" / "_swaps",
                Path("C:/Github/circuit_tracer-prompt_rover/output/usa_states_batch/_swaps"),
            ]
            swaps_dir = None
            for p in possible_paths:
                if p.exists():
                    swaps_dir = p
                    break
            
            if not swaps_dir:
                print("ERROR: Could not find swaps directory. Use --swaps-dir")
                return 1
        
        print(f"Loading swap results from: {swaps_dir}")
        results = load_all_swap_results(swaps_dir)
        print(f"  Loaded {len(results)} results")
        
        if not results:
            print("ERROR: No results found")
            return 1
        
        print(f"\nCreating batch requests...")
        requests = create_batch_requests(results, args.model)
        print(f"  Created {len(requests)} requests")
        
        output_dir = Path(args.output_dir)
        batch_id = submit_batch(requests, output_dir)
        
        if batch_id:
            return 0
        return 1
    
    elif args.command == "status":
        check_status(args.batch_id)
        return 0
    
    elif args.command == "download":
        output_dir = Path(args.output_dir)
        if download_results(args.batch_id, output_dir):
            return 0
        return 1
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

