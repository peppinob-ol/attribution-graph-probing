ArXiv bundle for “Automated Circuit Interpretation via Probe Prompting”
======================================================================

Build
-----
1) Local TeX:
   - pdflatex main.tex
   - bibtex main
   - pdflatex main.tex
   - pdflatex main.tex

2) Overleaf:
   - Upload paper/ directory; ensure figures are PDF; fonts embedded.

Figures
-------
- Preferred source: docs/lesswrong_post/Automated Circuit Interpretation via Probe Prompting — LessWrong.html
- Use the helper script in tools/ to extract Cloudinary images and save as PDF under paper/figures/.
- Avoid red–green palettes; prefer colorblind-safe schemes.

Tables
------
- T1: Graph vs Subgraph metrics (Neuronpedia)
- T2: Baselines on behavioral coherence (Michael Jordan circuit)
- T3: Cross-prompt robustness (Dallas→Oakland)

Reproducibility
---------------
- Python deps: see repo requirements.txt
- Minimal run: scripts/00_*, 01_*, 02_* with provided example JSON and configs.
- Record git commit, config, and seeds in Appendix before submission.

Packaging
---------
- Submit either a single main.pdf or the TeX + figures + refs.bib bundle to arXiv (cs.CL).
- Include code/demo links in the arXiv metadata.


