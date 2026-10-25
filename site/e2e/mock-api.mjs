// A stand-in for the Python API on Maritime, serving the fixtures in e2e/fixtures. Those are
// written from the real API run against the test world, and tests/test_web_api_contract.py
// checks they still match the contract.
import { createHmac, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";

const fixture = (name) => readFileSync(new URL(`./fixtures/${name}.json`, import.meta.url), "utf8");
const USER_TOKEN = "e2eToken.4102444800.abcdef0123456789";
const COMMANDS = new Set(["brief", "range", "plan", "holdings", "help"]);
const TOO_MANY = "That's a lot of questions in one hour, so I'm taking a short break. I'll answer again in a little while.";

function turnFor(text) {
  const t = text.toLowerCase();
  if (t.includes("happened")) return fixture("turn-news");
  if (t.includes("plan")) return fixture("turn-plan-range");
  if (t.includes("why")) return fixture("turn-history");
  return fixture("turn-text");
}

function error(res, status, code, words) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: code, message: { title: "", body: [{ kind: "text", text: words }], detail: [], footer: "", preview: null } }));
}

// Signed-in routes. The site signs with the test secret from playwright.config.ts. A subject that
// starts "linked-" is already linked; anyone else links with GOOD_CODE, which works once.
// 975310 plays a code someone already redeemed.
const WEB_SECRET = process.env.NETWORTH_WEB_SECRET ?? "";
const GOOD_CODE = "246810";
const linked = new Set();
const used = new Set(["975310"]);
const NOT_LINKED = "Send /weblink to @networth_professor_bot and type the code here.";
const BAD_CODE = "That code didn't work. A code works once and only for 10 minutes. Send /weblink to the bot for a new one.";

function visitorOf(req) {
  const token = (req.headers.authorization ?? "").replace(/^Bearer /, "");
  const [version, payload, mac] = token.split(".");
  if (version !== "v1" || !payload || !mac || !WEB_SECRET) return null;
  const want = Buffer.from(createHmac("sha256", WEB_SECRET).update(`v1.${payload}`).digest("base64url"));
  const got = Buffer.from(mac);
  if (got.length !== want.length || !timingSafeEqual(got, want)) return null;
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString());
  return claims.exp > Date.now() / 1000 ? claims : null;
}

function web(req, res, route) {
  const visitor = visitorOf(req);
  if (!visitor) return error(res, 401, "signed_out", "Your sign-in has run out. Sign in again to go on.");
  const isLinked = () => visitor.sub.startsWith("linked-") ? !linked.has(`forgot:${visitor.sub}`) : linked.has(visitor.sub);
  if (route === "me") return json(res, JSON.stringify({ linked: isLinked(), name: visitor.name }));
  if (route === "forget") {
    linked.delete(visitor.sub);
    linked.add(`forgot:${visitor.sub}`);
    return json(res, JSON.stringify({ linked: false }));
  }
  if (route === "link") {
    return read(req, (body) => {
      const code = String(body.code ?? "").replace(/\s/g, "");
      if (code !== GOOD_CODE || used.has(code)) return error(res, 400, "bad_code", BAD_CODE);
      used.add(code);
      linked.add(visitor.sub);
      json(res, JSON.stringify({ linked: true, name: visitor.name }));
    });
  }
  if (!isLinked()) return error(res, 403, "not_linked", NOT_LINKED);
  if (route === "dashboard") return json(res, fixture("dashboard"));
  read(req, (body) => json(res, route === "command" ? fixture(`command-${COMMANDS.has(body.name) ? body.name : "help"}`) : turnFor(String(body.text ?? ""))));
}

function json(res, body) {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(body);
}

function read(req, done) {
  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => done(JSON.parse(body || "{}")));
}

createServer((req, res) => {
  const url = new URL(req.url, "http://mock");
  if (url.pathname === "/api/track-record") return json(res, fixture("track-record"));
  const signed = url.pathname.match(/^\/api\/web\/(me|link|forget|dashboard|chat|command)$/);
  if (signed) return web(req, res, signed[1]);
  const user = url.pathname.match(/^\/api\/u\/([^/]+)\/(dashboard|chat|command)$/);
  const demo = url.pathname.match(/^\/api\/demo\/(dashboard|chat|command)$/);
  const route = demo?.[1] ?? user?.[2];
  if (!route || (user && decodeURIComponent(user[1]) !== USER_TOKEN)) {
    return error(res, 404, "not_found", "This link has expired or isn't right. Type /plan in the bot for a fresh one.");
  }
  if (route === "dashboard") return json(res, fixture(demo ? "demo-dashboard" : "dashboard"));
  read(req, (body) => {
    // Long enough to see the thinking state, short enough to keep the run quick.
    setTimeout(() => {
      if (route === "command") {
        // /plan plays an API that has no command route yet, so the fallback stays tested.
        if (body.name === "plan") return res.writeHead(404, { "content-type": "application/json" }).end('{"detail":"Not Found"}');
        return COMMANDS.has(body.name) ? json(res, fixture(`command-${body.name}`)) : error(res, 422, "failed", "");
      }
      const text = String(body.text ?? "");
      if (text.includes("one too many")) return error(res, 429, "rate_limited", TOO_MANY);
      json(res, turnFor(text));
    }, 300);
  });
}).listen(Number(process.env.MOCK_PORT ?? 4010), "127.0.0.1");
