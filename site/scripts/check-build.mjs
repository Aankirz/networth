// The line we never cross, checked on what ships. Run after `npm run build`.
// 1. The site's own source sends no verdict words and prints no figure of its own.
// 2. Nothing in .next/ names a server secret or carries a Slack or OpenAI style key.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const SOURCE_DIRS = ["app", "components", "lib"];
const BANNED_WORDS = [
  /\bleans?\b/i, /\bbuy\b/i, /\bsell\b/i, /\bscores?\b/i, /\brank(ed|ing|s)?\b/i, /\bF&O\b/,
  /\bfutures\b/i, /\ballocat(e|ion)\b/i, /\bguarantee(d)?\b/i, /\bmultibagger\b/i, /\bsure[- ]shot\b/i,
  /\bskyrocket/i, /\bto the moon\b/i, /\bcan'?t lose\b/i, /\brecommend(ed|s|ation)?\b/i,
  /🟢|🔴|⚪/u,
];
// A rupee amount or a percentage written into the site is a number the server didn't send.
const OWN_FIGURES = [/₹\s?\d/u, /\d+(\.\d+)?\s?%(?![\w-])/];
const SECRET_NAMES = [
  "AI_GATEWAY_API_KEY", "EXA_API_KEY", "FRED_API_KEY", "KEIKI_API_KEY", "KEIKI_SIGNING_SECRET",
  "LINK_SIGNING_SECRET", "OPENAI_API_KEY", "SNAPTRADE_CONSUMER_KEY", "TELEGRAM_BOT_TOKEN",
  "TELEGRAM_WEBHOOK_SECRET", "ANTHROPIC_API_KEY",
];
const KEY_SHAPES = [/\bxox[abposr]-[A-Za-z0-9-]{8,}/, /\bsk-[A-Za-z0-9_-]{16,}/];

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (name !== "cache") yield* files(path);
    } else if (/\.(tsx?|m?js|json|html|css|txt|rsc|body|map)$/.test(name)) yield path;
  }
}

const problems = [];
for (const dir of SOURCE_DIRS) {
  for (const path of files(dir)) {
    const text = readFileSync(path, "utf8").replace(/^\s*(\/\/|\*|\/\*).*$/gm, "");
    for (const re of BANNED_WORDS) {
      const hit = text.match(re);
      if (hit) problems.push(`${path}: "${hit[0]}" (${re})`);
    }
    // Figures only count where a reader sees them: JSX text, not styles or drawing geometry.
    const shown = [...text.matchAll(/>([^<>{}]+)</g)].map((m) => m[1]).join("\n");
    for (const re of OWN_FIGURES) {
      const hit = shown.match(re);
      if (hit) problems.push(`${path}: shows "${hit[0]}" (${re})`);
    }
  }
}
for (const path of files(".next")) {
  const text = readFileSync(path, "utf8");
  for (const name of SECRET_NAMES) if (text.includes(name)) problems.push(`${path}: names ${name}`);
  for (const re of KEY_SHAPES) if (re.test(text)) problems.push(`${path}: looks like a key (${re})`);
  if (/NEXT_PUBLIC_NETWORTH/.test(text)) problems.push(`${path}: a NEXT_PUBLIC_ Networth variable`);
}

if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("check-build: no verdict words, no figures of our own, no secrets in .next/");
