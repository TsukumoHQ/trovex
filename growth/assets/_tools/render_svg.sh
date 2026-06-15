#!/usr/bin/env bash
# Rasterize a brand SVG to an exact-size PNG using resvg + installed Fira fonts.
# Usage: render_svg.sh <in.svg> <out.png> [zoom]
set -euo pipefail
in="$1"; out="$2"; zoom="${3:-1}"
resvg --zoom "$zoom" --font-family "Fira Sans" "$in" "$out"
echo "rendered $out"
