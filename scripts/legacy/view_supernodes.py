#!/usr/bin/env python3
"""
Viewer semplice per visualizzare i supernodi antropologici
"""

import json
import webbrowser
import os
import tempfile

def create_html_viewer():
    """Crea viewer HTML per SVG supernodi"""
    
    print("🎨 CREAZIONE HTML VIEWER")
    print("=" * 40)
    
    try:
        # Leggi SVG
        with open("output/anthropological_supernodes_visualization.svg", 'r') as f:
            svg_content = f.read()
        
        # Leggi dati supernodi
        with open("output/visualization_graph_data.json", 'r') as f:
            graph_data = json.load(f)
        
        # Leggi statistiche finali
        with open("output/final_anthropological_optimized.json", 'r') as f:
            final_results = json.load(f)
        
        stats = final_results.get('comprehensive_statistics', {})
        quality_metrics = final_results.get('quality_metrics', {})
        
        # Crea HTML completo
        html_content = f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strategia Antropologica: Supernodi Visualizzazione</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.2em;
            font-weight: 300;
        }}
        .header p {{
            margin: 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .visualization-container {{
            text-align: center;
            margin: 30px 0;
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .stat-label {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .supernodes-list {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }}
        .supernode-item {{
            background: white;
            margin: 10px 0;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .semantic {{
            border-left-color: #1976d2;
        }}
        .computational {{
            border-left-color: #7b1fa2;
        }}
        .supernode-name {{
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 5px;
        }}
        .supernode-details {{
            font-size: 0.9em;
            color: #6c757d;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9em;
            border-top: 1px solid #dee2e6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Strategia Antropologica per Supernodi</h1>
            <p>Visualizzazione interattiva dei 54 supernodi generati automaticamente</p>
        </div>
        
        <div class="content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{stats.get('total_supernodes', 'N/A')}</div>
                    <div class="stat-label">Supernodi Totali</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.get('total_features_covered', 'N/A')}</div>
                    <div class="stat-label">Feature Coperte</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats.get('coverage_percentage', 0):.1f}%</div>
                    <div class="stat-label">Coverage Totale</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{quality_metrics.get('semantic_avg_coherence', 0):.3f}</div>
                    <div class="stat-label">Coerenza Semantica</div>
                </div>
            </div>
            
            <div class="visualization-container">
                <h3>Grafo Supernodi Antropologici</h3>
                {svg_content}
            </div>
            
            <div class="supernodes-list">
                <h3>Dettagli Supernodi Visualizzati</h3>
'''

        # Aggiungi lista supernodi
        for supernode in graph_data['supernodes']:
            supernode_type = supernode['type']
            html_content += f'''
                <div class="supernode-item {supernode_type}">
                    <div class="supernode-name">{supernode['name']}</div>
                    <div class="supernode-details">
                        Tipo: {supernode_type.title()} | 
                        Feature: {supernode['n_features']} | 
                        Attivazione: {supernode['activation']:.3f} |
                        Figli: {len(supernode['children'])}
                    </div>
                </div>
'''

        html_content += f'''
            </div>
        </div>
        
        <div class="footer">
            <p>Generato automaticamente dalla Strategia Antropologica per Supernodi</p>
            <p>Basato su Circuit Tracing (Anthropic) + Prompt Rover methodology</p>
        </div>
    </div>
</body>
</html>'''
        
        return html_content
        
    except Exception as e:
        print(f"❌ Errore creazione viewer: {e}")
        return None

def main():
    """Main function per viewer HTML"""
    
    print("🌐 HTML VIEWER SUPERNODI ANTROPOLOGICI")
    print("=" * 50)
    
    html_content = create_html_viewer()
    
    if html_content:
        # Salva HTML
        html_path = "output/anthropological_supernodes_viewer.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTML viewer creato: {html_path}")
        
        # Apri nel browser
        abs_path = os.path.abspath(html_path)
        print(f"🌐 Apertura nel browser: {abs_path}")
        
        try:
            webbrowser.open(f"file://{abs_path}")
            print("✅ Browser aperto automaticamente")
        except Exception as e:
            print(f"⚠️ Apertura manuale necessaria: {e}")
            print(f"📂 Apri manualmente: {abs_path}")
        
        return html_path
    else:
        print("❌ Fallimento creazione HTML viewer")

if __name__ == "__main__":
    main()
