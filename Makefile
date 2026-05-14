.PHONY: help setup demo test batch html5 ci clean serve

help:
	@echo "PDF-to-DITA Converter — make targets"
	@echo ""
	@echo "  setup    Install Python deps + JDK + DITA-OT (one-time)"
	@echo "  demo     Run the sample PDF through the pipeline + show a-k checklist"
	@echo "  test     Run on every PDF in test_data/, report PASS/FAIL per file"
	@echo "  batch    Convert every PDF in INPUT=dir (override) into OUTPUT=out/"
	@echo "  html5    Build HTML5 from the most recent output/m_*.ditamap"
	@echo "  ci       Headless end-to-end check used by GitHub Actions"
	@echo "  serve    Start the web demo on http://localhost:8000"
	@echo "  clean    Remove .cache/, output/, demo_output/, html5/"

setup:
	./setup.sh

demo:
	./run_demo.sh

test:
	./test_runner.sh test_data/ output/

INPUT  ?= test_data
OUTPUT ?= output/batch

batch:
	python3 batch.py $(INPUT) -o $(OUTPUT)

# Build HTML5 from the most recently produced ditamap.
html5:
	@MAP=$$(ls -t output/m_*.ditamap 2>/dev/null | head -1); \
	if [ -z "$$MAP" ]; then echo "No ditamap in output/. Run 'make demo' first."; exit 1; fi; \
	echo "Building HTML5 from $$MAP"; \
	dita -i "$$PWD/$$MAP" -f html5 -o "$$PWD/html5" --processing-mode=strict
	@echo "Open: $$PWD/html5/index.html"

ci:
	python3 -m pip install -q -r requirements.txt
	python3 main.py test_data/synthetic_alert_system.pdf -o output/ci/
	@test -f output/ci/m_synthetic_alert_system.ditamap || (echo "ditamap missing"; exit 1)
	@echo "CI: pipeline + DITA-OT validation passed"

serve:
	python3 demo_server.py

clean:
	rm -rf .cache output demo_output demo_uploads html5
