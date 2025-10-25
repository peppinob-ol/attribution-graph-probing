import pandas as pd

# Leggi il CSV
df = pd.read_csv('output/2025-10-21T07-40_export_ENRICHED.csv')

print(f'Righe iniziali: {len(df)}')

# 1. Elimina le righe con 'errore' nella colonna supernode_label
df = df[df['supernode_label'] != 'errore']
print(f'Righe dopo eliminazione errori: {len(df)}')

# 2. Mapping delle trasformazioni
label_mapping = {
    # Say con parentesi → Say con virgolette
    'Say (Austin)': 'Say "Austin"',
    'Say (Capital)': 'Say "Capital"',
    'Say Austin': 'Say "Austin"',
    
    # Token funzionali e parole comuni → tra virgolette minuscolo
    'is': '"is"',
    'of': '"of"',
    'capital': '"capital"',
    'punctuation': '"punctuation"',
    'Containing': '"containing"',
    'Seat': '"seat"',
    
    # Questi rimangono invariati (già corretti):
    # 'Schema', 'Relationship', 'Texas', 'Dallas'
}

# Applica il mapping
df['supernode_label'] = df['supernode_label'].replace(label_mapping)

# Verifica le etichette finali uniche
print('\nEtichette finali uniche:')
for label in sorted(df['supernode_label'].unique()):
    count = len(df[df['supernode_label'] == label])
    print(f'  - {label:<25} ({count} righe)')

# Salva il file pulito
df.to_csv('output/2025-10-21T07-40_export_ENRICHED_CLEANED.csv', index=False, encoding='utf-8')
print(f'\nFile salvato: output/2025-10-21T07-40_export_ENRICHED_CLEANED.csv')
print(f'Righe finali: {len(df)}')

