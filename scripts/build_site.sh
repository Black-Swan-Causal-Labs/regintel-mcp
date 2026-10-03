#!/bin/sh
# Assemble the Cloudflare Pages site for one docket's Docket Lens into site/public.
#   sh scripts/build_site.sh FDA-2020-D-2307
set -e
cd "$(dirname "$0")/.."
.venv/bin/python scripts/build_explorer.py "$1"
rm -rf site/public && mkdir -p site/public
cp "explorer/$1/index.html" "explorer/$1/analysis.json" site/public/
printf 'User-agent: *\nDisallow: /\n' > site/public/robots.txt
echo "ready: cd site && npx wrangler pages deploy public --project-name docket-lens"
