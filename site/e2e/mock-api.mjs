// A stand-in for the Python API on Maritime, serving the fixtures in e2e/fixtures. Those are
// written from the real API run against the test world, and tests/test_web_api_contract.py
// checks they still match the contract.
import { readFileSync } from "node:fs";
import { createServer } from "node:http";

const fixture = (name) => readFileSync(new URL(`./fixtures/${name}.json`, import.meta.url), "utf8");
const USER_TOKEN = "e2eToken.4102444800.abcdef0123456789";

function turnFor(text) {
  const t = text.toLowerCase();
  if (t.includes("happened")) return fixture("turn-news");
  if (t.includes("plan")) return fixture("turn-plan-range");
  if (t.includes("why")) return fixture("turn-history");
  return fixture("turn-text");
}

function notFound(res) {
  res.writeHead(404, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: "not_found", message: { title: "", body: [{ kind: "text", text: "This link has expired or isn't right. Type /plan in the bot for a fresh one." }], detail: [], footer: "Research, not advice.", preview: null } }));
}

createServer((req, res) => {
  const url = new URL(req.url, "http://mock");
  const user = url.pathname.match(/^\/api\/u\/([^/]+)\/(dashboard|chat)$/);
  const demo = url.pathname.match(/^\/api\/demo\/(dashboard|chat)$/);
  const route = demo?.[1] ?? user?.[2];
  if (!route || (user && decodeURIComponent(user[1]) !== USER_TOKEN)) return notFound(res);
  if (route === "dashboard") {
    res.writeHead(200, { "content-type": "application/json" });
    return res.end(fixture(demo ? "demo-dashboard" : "dashboard"));
  }
  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => {
    const { text } = JSON.parse(body || "{}");
    // Long enough to see the thinking state, short enough to keep the run quick.
    setTimeout(() => {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(turnFor(String(text ?? "")));
    }, 300);
  });
}).listen(Number(process.env.MOCK_PORT ?? 4010), "127.0.0.1");
