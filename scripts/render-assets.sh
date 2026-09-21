#!/usr/bin/env bash
# Re-render the raster brand assets from their SVG/HTML sources with headless Chrome.
# Run after editing assets/icon*.svg, assets/mark-*.svg.
set -euo pipefail
cd "$(dirname "$0")/../assets"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
shot() { "$CHROME" --headless=new --disable-gpu --hide-scrollbars --default-background-color=00000000 "$@" 2>/dev/null; }
tmp=$(mktemp -d)
for sz in 1024 256 64 32; do
  printf '<html><body style="margin:0"><img src="file://%s/icon.svg" width="%s" height="%s"></body></html>' "$PWD" "$sz" "$sz" > "$tmp/w.html"
  shot --window-size="$sz,$sz" --screenshot="icon-$sz.png" "file://$tmp/w.html"
done
rm -rf "$tmp"
ls -la icon-*.png
