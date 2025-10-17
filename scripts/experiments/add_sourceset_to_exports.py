#!/usr/bin/env python3
"""
Aggiunge sourceSetSlug e sourceSetName ai JSON esportati per Neuronpedia
"""
import json
import glob

def patch_neuronpedia_json(filepath):
    """Aggiunge metadata sourceSet se mancante"""
    print(f"\nPatching: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Skip se non è un dizionario
    if not isinstance(data, dict):
        print("   [SKIP] Non e' un dict, formato incompatibile")
        return
    
    # Verifica se esiste metadata
    if 'metadata' not in data:
        print("   [!] Nessuna chiave 'metadata', aggiungo")
        data['metadata'] = {}
    
    # Aggiungi sourceSet se mancante
    metadata = data['metadata']
    changed = False
    
    if 'sourceSetSlug' not in metadata:
        metadata['sourceSetSlug'] = "gemmascope-transcoder-16k"
        changed = True
        print("   [+] Aggiunto sourceSetSlug")
    
    if 'sourceSetName' not in metadata:
        metadata['sourceSetName'] = "GEMMASCOPE - TRANSCODER -16K"
        changed = True
        print("   [+] Aggiunto sourceSetName")
    
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   [OK] Salvato: {filepath}")
    else:
        print("   [i] Gia aggiornato")

def main():
    print("Patch sourceSet nei JSON Neuronpedia")
    print("=" * 60)
    
    # Trova tutti i JSON neuronpedia in output/
    patterns = [
        "output/*neuronpedia*.json",
        "output/subgraph*.json"
    ]
    
    files = set()
    for pattern in patterns:
        files.update(glob.glob(pattern))
    
    if not files:
        print("[!] Nessun file trovato")
        return
    
    print(f"Trovati {len(files)} file da processare\n")
    
    for filepath in sorted(files):
        try:
            patch_neuronpedia_json(filepath)
        except Exception as e:
            print(f"   [ERR] Errore: {e}")
    
    print("\n[OK] Patch completato!")

if __name__ == "__main__":
    main()

