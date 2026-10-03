// HTTP Basic Auth in front of every request to the Docket Lens demo site.
//
// Credentials live in Pages secrets (DEMO_USER, DEMO_PASS), never in this file or the repo.
// Fails CLOSED: if either secret is missing the site serves nothing (503), so a
// misconfigured deploy is never accidentally public. This gates a conference demo;
// it is not a substitute for real access control on sensitive data.

const REALM = "Docket Lens demo";

function unauthorized() {
  return new Response("Sign-in required.", {
    status: 401,
    headers: { "WWW-Authenticate": `Basic realm="${REALM}", charset="UTF-8"`, "cache-control": "no-store" },
  });
}

// Length-independent comparison so a wrong guess can't be timed character by character.
function safeEqual(a, b) {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

export async function onRequest({ request, env, next }) {
  if (!env.DEMO_USER || !env.DEMO_PASS) {
    return new Response("Site not configured.", { status: 503, headers: { "cache-control": "no-store" } });
  }
  const header = request.headers.get("Authorization") || "";
  const [scheme, encoded] = header.split(" ");
  if (scheme !== "Basic" || !encoded) return unauthorized();
  let user = "", pass = "";
  try {
    const decoded = new TextDecoder().decode(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0)));
    const i = decoded.indexOf(":");
    user = decoded.slice(0, i); pass = decoded.slice(i + 1);
  } catch { return unauthorized(); }
  if (!(safeEqual(user, env.DEMO_USER) & safeEqual(pass, env.DEMO_PASS))) return unauthorized();
  const res = await next();
  const out = new Response(res.body, res);
  out.headers.set("cache-control", "private, no-store");
  out.headers.set("x-robots-tag", "noindex, nofollow");
  return out;
}
