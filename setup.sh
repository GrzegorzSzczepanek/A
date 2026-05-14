#!/usr/bin/env bash
# Setup script for PDF-to-DITA conversion pipeline
# Installs Python dependencies and DITA-OT

set -e

echo "=== PDF-to-DITA Pipeline Setup ==="
echo

# System dependencies (poppler-utils for pdfimages)
echo "Checking system dependencies..."
if ! command -v pdfimages &> /dev/null; then
    echo "  Installing poppler-utils (for pdfimages)..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y poppler-utils 2>/dev/null || echo "  ⚠ Install poppler-utils manually: sudo apt-get install poppler-utils"
    elif command -v brew &> /dev/null; then
        brew install poppler 2>/dev/null || echo "  ⚠ Install poppler: brew install poppler"
    else
        echo "  ⚠ Install poppler-utils for image extraction support"
    fi
else
    echo "  ✓ poppler-utils available"
fi

# Python deps
echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet
echo "  ✓ Python packages installed"

# DITA-OT
DITA_OT_VERSION="4.3.1"
DITA_OT_DIR="$HOME/dita-ot-${DITA_OT_VERSION}"

if [ -f "$DITA_OT_DIR/bin/dita" ]; then
    echo "  ✓ DITA-OT ${DITA_OT_VERSION} already installed at ${DITA_OT_DIR}"
else
    echo "Installing DITA-OT ${DITA_OT_VERSION}..."
    cd /tmp
    curl -sLO "https://github.com/dita-ot/dita-ot/releases/download/${DITA_OT_VERSION}/dita-ot-${DITA_OT_VERSION}.zip"
    unzip -q "dita-ot-${DITA_OT_VERSION}.zip" -d "$HOME"
    rm "dita-ot-${DITA_OT_VERSION}.zip"
    echo "  ✓ DITA-OT installed at ${DITA_OT_DIR}"
fi

# Add to PATH
export PATH="${DITA_OT_DIR}/bin:$PATH"
echo "  Add to your shell: export PATH=\"${DITA_OT_DIR}/bin:\$PATH\""

# Verify Java
if java -version 2>/dev/null; then
    echo "  ✓ Java available"
else
    echo "  ⚠ Java not found! DITA-OT requires JDK 17+."
    echo "    Install: sudo apt install openjdk-21-jdk"
fi

# Test DITA-OT
if dita --version 2>/dev/null; then
    echo "  ✓ DITA-OT verified: $(dita --version)"
else
    echo "  ⚠ DITA-OT 'dita' command not found in PATH."
fi

echo
echo "=== Setup Complete ==="
echo
echo "Usage:"
echo "  # Single PDF:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  python main.py input.pdf -o output/"
echo
echo "  # Batch:"
echo "  python batch.py pdfs/ -o output/"
echo
echo "  # With DITA-OT validation:"
echo "  python main.py input.pdf --dita-ot ${DITA_OT_DIR}/bin/dita"
