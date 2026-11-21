// Encrypt a page for the public GitHub Pages site so it opens only with a passcode.
// usage: node tracker/encrypt.mjs <plain.html> <gate-template.html> <out.html>   (passcode in env DOCS_PASSCODE)
// PBKDF2-SHA256 (600k iterations) → AES-256-GCM. The page decrypts with WebCrypto in the browser.
// A short numeric passcode can be brute-forced offline: this keeps casual visitors out, nothing more.
import { readFileSync, writeFileSync } from "node:fs";
import { webcrypto as wc } from "node:crypto";

const [plainPath, gatePath, outPath] = process.argv.slice(2);
const pass = (process.env.DOCS_PASSCODE || "").trim();
if (!plainPath || !gatePath || !outPath || !pass) { console.error("usage: DOCS_PASSCODE=… node encrypt.mjs plain gate out"); process.exit(1); }

const ITER = 600000;
const salt = wc.getRandomValues(new Uint8Array(16)), iv = wc.getRandomValues(new Uint8Array(12));
const base = await wc.subtle.importKey("raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveKey"]);
const key = await wc.subtle.deriveKey({ name: "PBKDF2", salt, iterations: ITER, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
const ct = new Uint8Array(await wc.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(readFileSync(plainPath, "utf8"))));
const b64 = u => Buffer.from(u).toString("base64");
const payload = JSON.stringify({ v: 1, iter: ITER, salt: b64(salt), iv: b64(iv), ct: b64(ct) });
const gate = readFileSync(gatePath, "utf8");
if (!gate.includes("/*__PAYLOAD__*/null")) { console.error("gate template has no payload marker"); process.exit(1); }
writeFileSync(outPath, gate.replace("/*__PAYLOAD__*/null", payload));
console.log(`encrypted ${plainPath} → ${outPath} (${(ct.length / 1024).toFixed(0)} KB)`);
