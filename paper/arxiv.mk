SHELL := /bin/sh
TEX := pdflatex
BIB := bibtex
MAIN := main

all: pdf

pdf:
	$(TEX) $(MAIN).tex
	$(BIB) $(MAIN)
	$(TEX) $(MAIN).tex
	$(TEX) $(MAIN).tex

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).toc

.PHONY: all pdf clean



