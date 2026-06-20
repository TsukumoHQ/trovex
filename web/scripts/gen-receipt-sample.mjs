import { Resvg } from "/tmp/og-preview/node_modules/@resvg/resvg-js/index.js";
import { writeFileSync } from "node:fs";
const C={stage:'#06080d',fg:'#e6edf3',muted:'#9aa6b8',subtle:'#74808f',accent:'#22c55e',sans:"Fira Sans, sans-serif",mono:"Fira Code, monospace"};
const pct="~64%", sub="2.3M tokens/mo · ~$1,840/mo";
const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="${C.stage}"/>
<rect x="64" y="58" width="20" height="20" fill="${C.accent}"/>
<text x="98" y="75" font-family="${C.mono}" font-size="28" fill="${C.fg}">trovex</text>
<text x="1136" y="74" text-anchor="end" font-family="${C.mono}" font-size="20" fill="${C.subtle}" letter-spacing="2">SAVINGS RECEIPT</text>
<text x="62" y="320" font-family="${C.sans}" font-weight="700" font-size="200" letter-spacing="-6" fill="${C.accent}">${pct}</text>
<text x="70" y="404" font-family="${C.sans}" font-weight="700" font-size="58" letter-spacing="-1" fill="${C.fg}">fewer tokens per lookup</text>
<text x="70" y="476" font-family="${C.mono}" font-size="30" fill="${C.muted}">${sub}</text>
<line x1="64" y1="544" x2="1136" y2="544" stroke="rgba(148,163,184,0.16)" stroke-width="1"/>
<text x="64" y="582" font-family="${C.mono}" font-size="22" fill="${C.accent}">trovex.dev/savings</text>
<text x="1136" y="582" text-anchor="end" font-family="${C.mono}" font-size="20" fill="${C.subtle}">measure your own →</text>
</svg>`;
const r=new Resvg(svg,{font:{fontDirs:["/Users/loic/Library/Fonts"],defaultFontFamily:"Fira Sans",loadSystemFonts:true},fitTo:{mode:"width",value:1200}});
writeFileSync("/tmp/receipt-sample.png",r.render().asPng());
console.log("rendered /tmp/receipt-sample.png");
