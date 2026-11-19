"use strict";
/* Enterprise RAG console.
   Security: all dynamic content is inserted with textContent / DOM nodes, never innerHTML, so model output cannot inject markup.
   The one exception is `ico()`, which sets innerHTML from the constant ICONS table below (no user data ever reaches it).
   CSP is script-src 'self' / style-src 'self': no inline handlers or style attributes. Element.style.* (CSSOM) is allowed. */

const $ = (id) => document.getElementById(id);
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
};
const NS = "http://www.w3.org/2000/svg";
const s = (tag, attrs = {}, ...kids) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) el.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
};

/* ------------------------------------------------------------ icons (constant, trusted markup) */
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  chat: '<path d="M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3 20.5l1.6-5A8.5 8.5 0 1 1 21 11.5z"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 3-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.4c2 .7 3.5 2.4 3.5 5.1"/>',
  chart: '<path d="M3 3v18h18"/><path d="m7 15 4-5 3 3 5-7"/>',
  list: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 12h6M9 16h6"/>',
  sliders: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeoff: '<path d="M3 3l18 18M10.6 6.2A9.8 9.8 0 0 1 12 6c6.4 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.6 7.6A16.6 16.6 0 0 0 2 12s3.6 6 10 6c1.7 0 3.2-.4 4.5-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  pencil: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  power: '<path d="M12 3v9M6.4 6.6a8 8 0 1 0 11.2 0"/>',
  shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.1 8.2 7.5 9.5 4.4-1.3 7.5-4.9 7.5-9.5V6z"/><path d="m8.8 12.2 2.3 2.3 4.3-4.6"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  send: '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/>',
  thumb: '<path d="M7 11v9H4v-9zM7 11l4-8c1.7 0 2.5 1.2 2.2 3L13 9h5.5a2 2 0 0 1 2 2.3l-1.2 7a2 2 0 0 1-2 1.7H7"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  alert: '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17.5v.01"/>',
};
const ico = (name, cls) => { const el = s("svg", { viewBox: "0 0 24 24", class: "ico" + (cls ? " " + cls : ""), "aria-hidden": "true" }); el.innerHTML = ICONS[name] || ""; return el; };

/* ------------------------------------------------------------ state, helpers */
const state = { token: sessionStorage.getItem("token") || localStorage.getItem("token"), me: null, view: null, convId: null, onSearch: null };
const SENS = ["public", "internal", "confidential", "restricted"];
const ROLE_LABEL = { admin: "Administrator", manager: "Manager", employee: "Employee" };
// Demo sign-in shortcuts for the seeded accounts (see seed.py). Delete this array, and the #demo-logins block, before production.
const DEMO = [["Admin", "admin", "Admin@12345"], ["Manager", "eng_mgr", "Manager@12345"], ["Employee", "eng_emp", "Employee@12345"]];

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (opts.json) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const r = await fetch(path, { ...opts, headers });
  if (r.status === 401 && state.token) { logout(); throw new Error("Your session expired. Sign in again."); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed (" + r.status + ")");
  return data;
}
function toast(msg, err) {
  const t = h("div", { class: "toast" + (err ? " err" : ""), role: err ? "alert" : "status" }, msg); $("toasts").append(t); setTimeout(() => t.remove(), 4500);
}
const cap = (x) => !x ? "" : x.length <= 2 ? x.toUpperCase() : x[0].toUpperCase() + x.slice(1);
const chip = (text, cls) => h("span", { class: "chip " + (cls || text) }, String(text).replace(/_/g, " "));
const toDate = (v) => { if (!v) return null; const d = new Date(/(Z|[+-]\d\d:?\d\d)$/.test(v) ? v : v.replace(" ", "T") + "Z"); return isNaN(d) ? null : d; };
const fmtDate = (v) => { const d = toDate(v); return d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : ""; };
const fmtStamp = (v) => { const d = toDate(v); return d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + ", " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : ""; };
const dayLabel = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const secs = (ms) => ms ? (ms / 1000).toFixed(1) + " s" : "n/a";
const pageHead = (title, sub, ...right) => h("div", { class: "page-head" }, h("div", {}, h("h1", {}, title), h("p", { class: "sub" }, sub)), right.length ? h("div", { class: "toolbar" }, right) : null);

function openModal(children, wide) {
  const body = $("modal-body"); body.className = "modal-card" + (wide ? " wide" : ""); body.replaceChildren(...children);
  $("modal").classList.remove("hidden");
  (body.querySelector("input:not([type=checkbox]),select,textarea") || body.querySelector("button"))?.focus();
}
function closeModal() { $("modal").classList.add("hidden"); }
$("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeModal(); closeMenu(); document.body.classList.remove("nav-open"); } });

function pager(total, page, size, noun, onPage) {
  const pages = Math.max(1, Math.ceil(total / size)); const from = total ? (page - 1) * size + 1 : 0, to = Math.min(total, page * size);
  const b = (label, p, o = {}) => h("button", { type: "button", "aria-label": o.label, "aria-current": o.cur ? "page" : null, disabled: o.dis, onclick: () => onPage(p) }, label);
  const start = Math.max(1, Math.min(page - 2, pages - 4)), nums = [];
  for (let p = start; p <= Math.min(pages, start + 4); p++) nums.push(b(String(p), p, { cur: p === page, label: "Page " + p }));
  return h("div", { class: "pager" }, h("span", {}, `Showing ${from}–${to} of ${total} ${noun}`),
    h("div", { class: "pages" }, b(ico("left"), page - 1, { dis: page <= 1, label: "Previous page" }), nums, b(ico("right"), page + 1, { dis: page >= pages, label: "Next page" })));
}

/* ------------------------------------------------------------ charts (hand-built SVG: no libraries, CSP friendly) */
function niceMax(v) {
  if (v <= 4) return 4;
  const p = 10 ** Math.floor(Math.log10(v / 4)), f = v / 4 / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p * 4;
}
function lineChart(labels, series, label) {
  const W = 640, H = 250, pl = 40, pr = 16, pt = 14, pb = 30, iw = W - pl - pr, ih = H - pt - pb, n = labels.length;
  const max = niceMax(Math.max(0, ...series.flatMap((x) => x.values)));
  const X = (i) => pl + (n === 1 ? iw / 2 : iw * i / (n - 1)), Y = (v) => pt + ih - ih * v / max;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": label });
  for (let i = 0; i <= 4; i++) {
    const y = pt + ih * i / 4;
    svg.append(s("line", { x1: pl, x2: W - pr, y1: y, y2: y, class: "gl" }), s("text", { x: pl - 8, y: y + 4, class: "axis", "text-anchor": "end" }, Math.round(max * (4 - i) / 4)));
  }
  const step = Math.ceil(n / 7);
  labels.forEach((t, i) => { if (i % step === 0 || i === n - 1) svg.append(s("text", { x: X(i), y: H - 8, class: "axis", "text-anchor": "middle" }, t)); });
  for (const ser of series) {
    const pts = ser.values.map((v, i) => [X(i), Y(v)]);
    if (n > 1) {
      let d = `M${pts[0][0]},${pts[0][1]}`;
      for (let i = 0; i < n - 1; i++) {
        const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
        const c1 = [p1[0] + (p2[0] - p0[0]) / 6, Math.min(pt + ih, Math.max(pt, p1[1] + (p2[1] - p0[1]) / 6))];
        const c2 = [p2[0] - (p3[0] - p1[0]) / 6, Math.min(pt + ih, Math.max(pt, p2[1] - (p3[1] - p1[1]) / 6))];
        d += ` C${c1} ${c2} ${p2}`;
      }
      svg.append(s("path", { d: `${d} L${pts[n - 1][0]},${pt + ih} L${pts[0][0]},${pt + ih} Z`, class: "area " + ser.cls }), s("path", { d, class: "ln " + ser.cls }));
    }
    pts.forEach(([x, y], i) => svg.append(s("circle", { cx: x, cy: y, r: 4, class: "pt " + ser.cls }, s("title", {}, `${labels[i]}: ${ser.values[i]} ${ser.name.toLowerCase()}`))));
  }
  return svg;
}
function donut(parts, total) {
  const R = 54, C = 2 * Math.PI * R, svg = s("svg", { viewBox: "0 0 140 140", class: "donut", role: "img", "aria-label": "Documents by sensitivity" });
  svg.append(s("circle", { cx: 70, cy: 70, r: R, class: "ring-bg" }));
  let off = 0;
  for (const p of parts) {
    const len = C * p.value / total, dash = Math.max(len - 2, 0);
    svg.append(s("circle", { cx: 70, cy: 70, r: R, class: "ring " + p.cls, "stroke-dasharray": `${dash} ${C - dash}`, "stroke-dashoffset": -off, transform: "rotate(-90 70 70)" }, s("title", {}, `${p.label}: ${p.value}`)));
    off += len;
  }
  svg.append(s("text", { x: 70, y: 72, class: "d-num", "text-anchor": "middle" }, total), s("text", { x: 70, y: 90, class: "d-lbl", "text-anchor": "middle" }, "Documents"));
  return svg;
}
const kpi = (cls, icon, label, value, sub) => h("div", { class: "kpi " + cls }, h("div", { class: "tile" }, ico(icon)), h("div", {}, h("small", {}, label), h("b", {}, value ?? "n/a"), sub ? h("em", {}, sub) : null));

/* ------------------------------------------------------------ theme */
function setTheme(t) {
  document.documentElement.dataset.theme = t; localStorage.setItem("theme", t);
  $("theme").replaceChildren(ico(t === "dark" ? "sun" : "moon")); $("login-theme").replaceChildren(ico(t === "dark" ? "sun" : "moon")); $("theme").setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
  if (state.view === "settings" && state.me) VIEWS.settings();
}
const theme = () => document.documentElement.dataset.theme;
$("theme").onclick = () => setTheme(theme() === "dark" ? "light" : "dark");
$("login-theme").onclick = $("theme").onclick;
$("menu-btn").append(ico("menu")); $("search-ico").append(ico("search"));
$("logout").append(ico("logout"), "Logout");
setTheme(localStorage.getItem("theme") || "dark");

/* ------------------------------------------------------------ auth */
$("demo-logins").replaceChildren(...DEMO.map(([label, u, p]) => h("button", { type: "button", class: "btn", onclick: () => signIn(u, p) }, ico("user"), "Login as " + label)));
$("login-form").addEventListener("submit", (e) => { e.preventDefault(); signIn($("u").value, $("p").value); });
$("forgot").onclick = () => toast("Ask an administrator to reset your password.");
$("pw-toggle").onclick = () => {
  const show = $("p").type === "password"; $("p").type = show ? "text" : "password";
  $("pw-toggle").setAttribute("aria-pressed", show); $("pw-toggle").setAttribute("aria-label", show ? "Hide password" : "Show password"); $("pw-toggle").replaceChildren(ico(show ? "eyeoff" : "eye"));
};
function saveToken(token, remember) {
  sessionStorage.removeItem("token"); localStorage.removeItem("token");
  (remember ? localStorage : sessionStorage).setItem("token", token); state.token = token;
}
async function signIn(username, password) {
  $("login-err").textContent = ""; $("login-ok").textContent = ""; $("login-btn").disabled = true;
  try {
    const d = await api("/api/login", { method: "POST", json: { username, password } });
    saveToken(d.access_token, $("remember").checked); $("p").value = ""; await boot();
  } catch (err) { $("login-err").textContent = err.message; }
  $("login-btn").disabled = false;
}

/* ---- sign-up, Google ---- */
let AUTH = { signup: "off", google: false };
function showAuth(mode) {
  $("login-form").classList.toggle("hidden", mode !== "login"); $("signup-form").classList.toggle("hidden", mode !== "signup");
}
async function loadAuthConfig() {
  try { AUTH = await api("/api/auth/config"); } catch { AUTH = { signup: "off", google: false }; }  // older backend: hide both
  $("to-signup").classList.toggle("hidden", AUTH.signup === "off");
  for (const id of ["sso-login", "sso-signup"]) $(id).classList.toggle("hidden", !AUTH.google);
  $("signup-sub").textContent = AUTH.signup === "approval" ? "New accounts are reviewed by an administrator before first sign-in" : "Sign up with your email";
}
const clearAuthMsgs = () => { for (const id of ["login-err", "login-ok", "signup-err"]) $(id).textContent = ""; };
$("show-signup").onclick = () => { clearAuthMsgs(); showAuth("signup"); }; $("show-login").onclick = () => { clearAuthMsgs(); showAuth("login"); };
for (const b of document.querySelectorAll("[data-google]")) b.onclick = () => { location.href = "/api/auth/google/login"; };
$("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault(); const err = $("signup-err"); err.textContent = "";
  const username = $("su-name").value.trim(), email = $("su-email").value.trim(), pw = $("su-pass").value;
  if (!/^[A-Za-z0-9_.-]{3,64}$/.test(username)) return void (err.textContent = "Username must be 3 to 64 characters: letters, numbers, dot, dash or underscore.");
  if (pw.length < 8) return void (err.textContent = "Password must be at least 8 characters.");
  if (pw !== $("su-pass2").value) return void (err.textContent = "The two passwords don't match.");
  $("signup-btn").disabled = true;
  try {
    const d = await api("/api/signup", { method: "POST", json: { username, email, password: pw } });
    $("su-pass").value = $("su-pass2").value = "";
    if (d.access_token) { saveToken(d.access_token, false); await boot(); }
    else { showAuth("login"); $("login-ok").textContent = d.message; $("u").value = email; }
  } catch (ex) { err.textContent = ex.message; }
  $("signup-btn").disabled = false;
});
const SSO_ERRORS = { cancelled: "Google sign-in was cancelled.", state: "That sign-in attempt expired. Please try again.", google: "Google could not verify your account. Please try again.",
  domain: "That email domain is not allowed to sign in here.", closed: "Sign-up is turned off. Ask an administrator for an account.",
  inactive: "Your account is waiting for administrator approval, or has been deactivated." };
async function finishSso() {  // returning from Google: location.hash is #sso=<one-time code> or #sso_error=<reason>
  const hash = new URLSearchParams(location.hash.slice(1)); const code = hash.get("sso"), bad = hash.get("sso_error");
  if (!code && !bad) return false;
  history.replaceState(null, "", location.pathname);  // never leave the code in the address bar / history
  if (bad) { $("login-err").textContent = SSO_ERRORS[bad] || "Google sign-in failed."; return false; }
  try { const d = await api("/api/auth/exchange", { method: "POST", json: { code } }); saveToken(d.access_token, false); return true; }
  catch (e) { $("login-err").textContent = e.message; return false; }
}
function logout() {
  sessionStorage.removeItem("token"); localStorage.removeItem("token"); state.token = null; state.me = null; state.view = null;
  closeMenu(); closeModal(); showAuth("login"); $("gsearch").value = ""; $("app").classList.add("hidden"); $("login").classList.remove("hidden");
}
$("logout").onclick = logout;

function closeMenu() { $("menu").classList.add("hidden"); $("user-chip").setAttribute("aria-expanded", "false"); }
$("user-chip").onclick = (e) => { e.stopPropagation(); const open = $("menu").classList.toggle("hidden") === false; $("user-chip").setAttribute("aria-expanded", open); };
document.addEventListener("click", (e) => { if (!$("menu").contains(e.target)) closeMenu(); });
$("menu-btn").onclick = () => document.body.classList.toggle("nav-open");
$("scrim").onclick = () => document.body.classList.remove("nav-open");
$("gsearch").addEventListener("input", (e) => state.onSearch?.(e.target.value));
$("gsearch").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); if (state.view !== "library") go("library"); } });

const NAV = [["dashboard", "Dashboard", "home", true], ["ask", "AI Assistant", "chat"], ["library", "Documents", "file"], ["users", "Users & Access", "users", true],
  ["analytics", "Analytics", "chart", true], ["audit", "Audit Logs", "list", true], ["settings", "Settings", "sliders"]];
async function boot() {
  if (!state.token) return logout();
  try { state.me = await api("/api/me"); } catch { return logout(); }
  $("login").classList.add("hidden"); $("app").classList.remove("hidden");
  const m = state.me, admin = m.role === "admin";
  $("nav").replaceChildren(...NAV.filter(([, , , adminOnly]) => admin || !adminOnly).map(([id, label, icon]) => h("button", { class: "nav-btn", "data-v": id, onclick: () => go(id) }, ico(icon), label)));
  $("role-card").replaceChildren(ico("shield"), h("div", {}, h("b", {}, "Role: " + ROLE_LABEL[m.role]), h("span", { class: "pill" }, admin ? "Full Access" : "Up to " + SENS[Math.min(m.clearance, 3)]), h("small", {}, cap(m.department) + " department")));
  $("user-chip").replaceChildren(h("span", { class: "avatar" }, m.username[0].toUpperCase()), h("span", { class: "uname" }, cap(m.username)), ico("down"));
  $("menu").replaceChildren(h("div", { class: "who" }, h("b", {}, m.username), h("span", { class: "muted" }, ROLE_LABEL[m.role] + ", " + cap(m.department))),
    h("button", { class: "nav-btn", role: "menuitem", onclick: () => go("settings") }, ico("sliders"), "Settings"),
    h("button", { class: "nav-btn", role: "menuitem", onclick: () => { closeMenu(); setTheme(theme() === "dark" ? "light" : "dark"); } }, ico("sun"), "Switch theme"),
    h("button", { class: "nav-btn", role: "menuitem", onclick: logout }, ico("logout"), "Logout"));
  go(admin ? "dashboard" : "ask");
}
const VIEWS = {};
async function go(view, convId = null) {
  if (NAV.find((n) => n[0] === view)?.[3] && state.me.role !== "admin") view = "ask";
  state.view = view; state.onSearch = null; if (view === "ask") state.convId = convId;
  document.body.classList.remove("nav-open"); closeMenu();
  $("main").className = view === "ask" ? "full" : "";
  for (const b of $("nav").children) { if (b.dataset.v === view) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); }
  try { await VIEWS[view](); }
  catch (e) { $("main").replaceChildren(h("div", { class: "card" }, h("h2", {}, "Something went wrong"), h("p", { class: "muted" }, e.message))); }
  $("main").focus({ preventScroll: true });
}

/* ------------------------------------------------------------ AI assistant */
function renderAnswer(text, onCite) {
  const box = h("div", { class: "answer" }); let list = null;
  const inline = (t) => t.split(/(\[\d{1,2}\])/).map((p) => /^\[\d{1,2}\]$/.test(p) ? h("button", { class: "cite", "aria-label": "Open source " + p.slice(1, -1), onclick: () => onCite(+p.slice(1, -1)) }, p.slice(1, -1)) : p.replace(/\*\*/g, ""));
  for (const line of text.split("\n")) {
    const b = line.match(/^\s*[-*•]\s+(.*)/) || line.match(/^\s*\d+[.)]\s+(.*)/);
    if (b) { if (!list) { list = h("ul"); box.append(list); } list.append(h("li", {}, inline(b[1]))); }
    else if (line.trim()) { list = null; box.append(h("p", {}, inline(line))); } else list = null;
  }
  return box;
}
const STATUS = {
  verified: "Answer checked against the cited passages",
  uncited: "The model gave no citations. Treat this answer with caution and check the sources",
  model_unavailable: "The answer model is offline. Showing the passages that matched",
  no_evidence: "No supporting passage found in documents you can access",
};
function openSource(src) {
  if (src.redacted) return;
  api(`/api/documents/${src.doc_id}/chunks/${src.chunk_index}`).then((d) => {
    openModal([h("h2", { id: "modal-title" }, d.filename, chip(d.sensitivity)),
      ...d.passages.map((p) => h("div", { class: "passage" + (p.chunk_index === d.focus ? " focus" : "") }, p.page ? h("div", { class: "muted" }, "Page " + p.page) : null, p.text)),
      h("div", { class: "modal-actions" }, h("button", { class: "btn", onclick: closeModal }, "Close"))], true);
  }).catch((e) => toast(e.message, true));
}
function aiBubble(m) {
  const srcs = m.sources || [], wrap = h("div", { class: "msg-ai" });
  const st = STATUS[m.citation_status];
  if (st) wrap.append(h("div", { class: "status " + (m.citation_status || "") }, ico(m.citation_status === "verified" ? "shield" : m.citation_status === "no_evidence" ? "search" : "alert"), st));
  wrap.append(renderAnswer(m.content ?? m.answer, (n) => { const x = srcs.find((y) => y.n === n); if (x) openSource(x); }));
  if (srcs.length) {
    const cards = h("div", { class: "evidence hidden" }, srcs.map((x) => x.redacted ? h("div", { class: "ev" }, h("b", {}, x.filename)) :
      h("button", { class: "ev " + x.sensitivity, onclick: () => openSource(x) }, h("b", {}, (x.n ? x.n + ". " : "") + x.filename + (x.page ? ", page " + x.page : "")), h("span", {}, x.snippet || ""))));
    const toggle = h("button", { class: "src-toggle", "aria-expanded": "false", onclick: () => { const open = cards.classList.toggle("hidden") === false; toggle.setAttribute("aria-expanded", open); } }, "Sources (" + srcs.length + ")", ico("down"));
    wrap.append(h("div", { class: "srcbar" }, h("div", { class: "srcpills" }, srcs.map((x) => x.redacted ? h("span", { class: "src-pill gone" }, x.filename) :
      h("button", { class: "src-pill " + x.sensitivity, title: "Open passage", onclick: () => openSource(x) }, (x.n ? x.n + ". " : "") + x.filename + (x.page ? " (Page " + x.page + ")" : "")))), toggle), cards);
  }
  const id = m.id ?? m.message_id, meta = h("div", { class: "meta" });
  const fb = (r, el) => api(`/api/messages/${id}/feedback`, { method: "POST", json: { rating: r } }).then(() => { for (const b of meta.querySelectorAll(".icon-btn")) b.classList.remove("on"); el.classList.add("on"); }).catch((e) => toast(e.message, true));
  const up = h("button", { "aria-label": "Helpful", class: "icon-btn up" + (m.feedback === 1 ? " on" : ""), onclick: () => fb(1, up) }, ico("thumb"));
  const dn = h("button", { "aria-label": "Not helpful", class: "icon-btn down" + (m.feedback === -1 ? " on" : ""), onclick: () => fb(-1, dn) }, ico("thumb"));
  meta.append(up, dn, m.latency_ms ? secs(m.latency_ms) : ""); wrap.append(meta);
  return wrap;
}
const aiRow = (m) => h("div", { class: "row-ai" }, h("span", { class: "avatar ai" }, ico("cpu")), aiBubble(m));
const userRow = (text) => h("div", { class: "row-user" }, h("div", { class: "msg-user" }, text), h("span", { class: "avatar" }, state.me.username[0].toUpperCase()));

VIEWS.ask = async function () {
  const thread = h("div", { class: "thread" });
  const input = h("textarea", { placeholder: "Ask anything about your documents…", "aria-label": "Your question", maxlength: 1000 });
  const send = h("button", { class: "send", "aria-label": "Send question" }, ico("send"));
  const list = h("div", { class: "conv-list" });
  const toEnd = () => { thread.scrollTop = thread.scrollHeight; };
  const loadConvs = async () => {
    const convs = await api("/api/conversations");
    list.replaceChildren(...(convs.length ? convs.map((c) => h("div", { class: "conv-row" + (c.id === state.convId ? " on" : "") },
      h("button", { class: "conv", title: c.title, "aria-current": c.id === state.convId ? "true" : null, onclick: () => go("ask", c.id) }, ico("chat"), h("span", {}, c.title)),
      h("button", { class: "icon-btn del", "aria-label": "Delete conversation " + c.title, onclick: async () => {
        if (!confirm("Delete this conversation?")) return;
        try { await api("/api/conversations/" + c.id, { method: "DELETE" }); c.id === state.convId ? go("ask") : loadConvs(); } catch (e) { toast(e.message, true); }
      } }, ico("x")))) : [h("p", { class: "muted" }, "No conversations yet.")]));
    return convs;
  };
  const ask = async (text) => {
    text = (text || input.value).trim(); if (text.length < 3) return;
    thread.querySelector(".hello")?.remove(); input.value = ""; send.disabled = true;
    thread.append(userRow(text));
    const wait = h("div", { class: "typing" }, h("span", { class: "avatar ai" }, ico("cpu")), h("i"), h("i"), h("i"), "Searching documents you can access…"); thread.append(wait); toEnd();
    try {
      const r = await api("/api/query", { method: "POST", json: { question: text, conversation_id: state.convId } });
      state.convId = r.conversation_id; wait.replaceWith(aiRow(r)); loadConvs();
    } catch (e) { wait.remove(); toast(e.message, true); }
    send.disabled = false; input.focus(); toEnd();
  };
  send.onclick = () => ask(); input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });
  const clearAll = async () => {
    const convs = await api("/api/conversations"); if (!convs.length || !confirm("Delete all " + convs.length + " conversations? This cannot be undone.")) return;
    try { await Promise.all(convs.map((c) => api("/api/conversations/" + c.id, { method: "DELETE" }))); toast("Chat history cleared"); } catch (e) { toast(e.message, true); }
    go("ask");
  };
  $("main").replaceChildren(pageHead("AI Assistant", "Ask questions from your enterprise documents"),
    h("div", { class: "chat-layout" },
      h("div", { class: "card history" }, h("div", { class: "card-head" }, h("h2", {}, "Chat History"), h("button", { class: "link", onclick: clearAll }, "Clear All")),
        h("button", { class: "btn wide new-chat", onclick: () => go("ask") }, ico("plus"), "New chat"), list),
      h("div", { class: "card chat-panel" }, thread, h("div", { class: "composer" }, input, send))));
  let loaded = false;
  if (state.convId) {
    try {
      const c = await api("/api/conversations/" + state.convId);
      for (const m of c.messages) thread.append(m.role === "user" ? userRow(m.content) : aiRow(m)); loaded = true; toEnd();
    } catch { state.convId = null; }
  }
  if (!loaded) thread.append(h("div", { class: "hello" }, h("span", { class: "avatar ai" }, ico("cpu")), h("h2", {}, "What do you need to know?"),
    h("p", {}, "Every answer cites the document and page it came from. If the documents don't say, the assistant tells you instead of guessing."),
    h("div", { class: "suggest" }, ["What is the leave policy?", "How do I request a laptop?", "Who approves overtime?"].map((q) => h("button", { onclick: () => ask(q) }, q)))));
  loadConvs(); input.focus();
};

/* ------------------------------------------------------------ documents */
function openUpload() {
  const m = state.me;
  const file = h("input", { type: "file", accept: ".pdf,.docx,.txt,.md", "aria-label": "File" });
  const dept = h("input", { value: m.department, "aria-label": "Department" });
  const sens = h("select", { "aria-label": "Sensitivity" }, SENS.map((x) => h("option", { value: x, selected: x === "internal" }, cap(x))));
  const roleBoxes = ["employee", "manager", "admin"].map((r) => h("input", { type: "checkbox", value: r, checked: true }));
  const btn = h("button", { class: "btn primary", onclick: async () => {
    if (!file.files[0]) return toast("Choose a file first", true);
    const roles = roleBoxes.filter((b) => b.checked).map((b) => b.value); if (!roles.length) return toast("Choose at least one role", true);
    const fd = new FormData(); fd.append("file", file.files[0]); fd.append("department", dept.value); fd.append("sensitivity", sens.value); fd.append("allowed_roles", roles.join(","));
    btn.disabled = true; btn.textContent = "Indexing…";
    try { await api("/api/documents", { method: "POST", body: fd }); closeModal(); toast("Uploaded and indexed"); go("library"); }
    catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "Upload"; }
  } }, ico("upload"), "Upload");
  openModal([h("h2", { id: "modal-title" }, "Upload a document"), h("p", { class: "muted" }, "PDF, DOCX, TXT or MD, up to 10 MB. It is indexed immediately."),
    h("label", {}, "File"), file,
    h("div", { class: "form-grid" }, h("div", {}, h("label", {}, "Department (or all)"), dept), h("div", {}, h("label", {}, "Sensitivity"), sens)),
    h("label", {}, "Roles that can read it"), h("div", { class: "checks" }, ["employee", "manager", "admin"].map((r, i) => h("label", { class: "check" }, roleBoxes[i], cap(r)))),
    h("div", { class: "modal-actions" }, h("button", { class: "btn", onclick: closeModal }, "Cancel"), btn)]);
}
VIEWS.library = async function () {
  const docs = await api("/api/documents"), canUp = state.me.can_upload, admin = state.me.role === "admin", SIZE = 8; let page = 1;
  const sensSel = h("select", { "aria-label": "Filter by sensitivity", onchange: () => { page = 1; draw(); } }, h("option", { value: "" }, "All sensitivity levels"), SENS.map((x) => h("option", { value: x }, cap(x))));
  const holder = h("div");
  const draw = () => {
    const q = $("gsearch").value.trim().toLowerCase(), sv = sensSel.value;
    const rows = docs.filter((d) => (!sv || d.sensitivity === sv) && (d.filename + " " + d.department).toLowerCase().includes(q));
    page = Math.min(page, Math.max(1, Math.ceil(rows.length / SIZE)));
    const slice = rows.slice((page - 1) * SIZE, page * SIZE);
    const body = slice.length ? slice.map((d, i) => h("tr", {}, h("td", { class: "num" }, (page - 1) * SIZE + i + 1), h("td", {}, h("div", { class: "fname" }, ico("file"), d.filename)), h("td", {}, cap(d.department)),
      h("td", {}, h("span", { title: "Readable by: " + d.allowed_roles.join(", ") }, chip(d.sensitivity))), h("td", {}, cap(d.owner)), h("td", {}, fmtDate(d.uploaded_at)),
      h("td", {}, h("div", { class: "actions" }, h("button", { class: "icon-btn view", title: "Preview", "aria-label": "Preview " + d.filename, onclick: () => openSource({ doc_id: d.id, chunk_index: 0 }) }, ico("eye")),
        admin ? h("button", { class: "icon-btn del", title: "Delete", "aria-label": "Delete " + d.filename, onclick: async () => {
          if (!confirm("Delete " + d.filename + "? It is removed from search immediately.")) return;
          try { await api("/api/documents/" + d.id, { method: "DELETE" }); toast("Deleted " + d.filename); go("library"); } catch (e) { toast(e.message, true); }
        } }, ico("trash")) : null)))) :
      [h("tr", {}, h("td", { colspan: 7, class: "empty" }, docs.length ? "No documents match this search." : "No documents yet. " + (canUp ? "Upload the first one." : "Ask your manager to upload policies.")))];
    holder.replaceChildren(h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["#", "Document Name", "Department", "Sensitivity", "Uploaded By", "Date", "Actions"].map((t, i) => h("th", { class: i === 0 ? "num" : "" }, t)))), h("tbody", {}, body))),
      pager(rows.length, page, SIZE, "documents", (p) => { page = p; draw(); }));
  };
  state.onSearch = () => { page = 1; draw(); };
  $("main").replaceChildren(pageHead("Document Management", "Upload and manage your knowledge base", canUp ? h("button", { class: "btn primary", onclick: openUpload }, ico("upload"), "Upload Document") : null),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("p", { class: "muted" }, "You see only documents your role, department, and clearance allow."), h("div", { class: "toolbar" }, sensSel)), holder));
  draw();
};

/* ------------------------------------------------------------ users & access */
function openUserAdd() {
  const uname = h("input", { placeholder: "e.g. jane.doe", "aria-label": "Username", autocomplete: "off" }), pw = h("input", { type: "password", placeholder: "8+ characters", "aria-label": "Temporary password", autocomplete: "new-password" });
  const role = h("select", { "aria-label": "Role" }, ["employee", "manager", "admin"].map((r) => h("option", { value: r }, ROLE_LABEL[r]))), dept = h("input", { placeholder: "e.g. engineering", "aria-label": "Department" });
  const btn = h("button", { class: "btn primary", onclick: async () => {
    btn.disabled = true;
    try { await api("/api/admin/users", { method: "POST", json: { username: uname.value, password: pw.value, role: role.value, department: dept.value } }); closeModal(); toast("Added " + uname.value); go("users"); }
    catch (e) { toast(e.message, true); btn.disabled = false; }
  } }, ico("plus"), "Add person");
  openModal([h("h2", { id: "modal-title" }, "Add a person"), h("p", { class: "muted" }, "They can sign in right away with the temporary password."),
    h("div", { class: "form-grid" }, h("div", {}, h("label", {}, "Username"), uname), h("div", {}, h("label", {}, "Temporary password"), pw), h("div", {}, h("label", {}, "Role"), role), h("div", {}, h("label", {}, "Department"), dept)),
    h("div", { class: "modal-actions" }, h("button", { class: "btn", onclick: closeModal }, "Cancel"), btn)]);
}
function openUserEdit(u) {
  const self = u.id === state.me.id;
  const role = h("select", { "aria-label": "Role", disabled: self }, ["employee", "manager", "admin"].map((r) => h("option", { value: r, selected: r === u.role }, ROLE_LABEL[r]))), dept = h("input", { value: u.department, "aria-label": "Department" });
  const btn = h("button", { class: "btn primary", onclick: async () => {
    const body = {}; if (!self && role.value !== u.role) body.role = role.value; if (dept.value.trim().toLowerCase() !== u.department) body.department = dept.value.trim();
    if (!Object.keys(body).length) return closeModal();
    btn.disabled = true;
    try { await api("/api/admin/users/" + u.id, { method: "PATCH", json: body }); closeModal(); toast("Updated " + u.username); go("users"); } catch (e) { toast(e.message, true); btn.disabled = false; }
  } }, "Save changes");
  openModal([h("h2", { id: "modal-title" }, "Edit " + u.username), self ? h("p", { class: "muted" }, "You cannot change your own role.") : null,
    h("div", { class: "form-grid" }, h("div", {}, h("label", {}, "Role"), role), h("div", {}, h("label", {}, "Department"), dept)),
    h("div", { class: "modal-actions" }, h("button", { class: "btn", onclick: closeModal }, "Cancel"), btn)]);
}
VIEWS.users = async function () {
  const users = await api("/api/admin/users"), SIZE = 8; let tab = "all", page = 1;
  const TABS = [["all", "All Users", () => true], ["admin", "Administrators", (u) => u.role === "admin"], ["manager", "Managers", (u) => u.role === "manager"], ["employee", "Employees", (u) => u.role === "employee"]];
  const tabs = h("div", { class: "tabs", role: "tablist" }), holder = h("div");
  const patch = async (u, body, msg) => { try { await api("/api/admin/users/" + u.id, { method: "PATCH", json: body }); toast(msg); } catch (e) { toast(e.message, true); } go("users"); };
  const draw = () => {
    tabs.replaceChildren(...TABS.map(([id, label, f]) => h("button", { role: "tab", "aria-selected": id === tab, onclick: () => { tab = id; page = 1; draw(); } }, `${label} (${users.filter(f).length})`)));
    const rows = users.filter(TABS.find((t) => t[0] === tab)[2]); page = Math.min(page, Math.max(1, Math.ceil(rows.length / SIZE)));
    const body = rows.slice((page - 1) * SIZE, page * SIZE).map((u, i) => h("tr", {}, h("td", { class: "num" }, (page - 1) * SIZE + i + 1),
      h("td", {}, h("div", { class: "fname" }, h("span", { class: "avatar sm" }, u.username[0].toUpperCase()), u.username, u.id === state.me.id ? h("span", { class: "muted" }, "(you)") : null)),
      h("td", {}, u.email || h("span", { class: "muted" }, "None")), h("td", {}, fmtDate(u.created_at)), h("td", {}, chip(ROLE_LABEL[u.role], u.role)), h("td", {}, cap(u.department)), h("td", {}, chip(u.is_active ? "Active" : "Inactive", u.is_active ? "active" : "inactive")),
      h("td", {}, h("div", { class: "actions" }, h("button", { class: "icon-btn edit", title: "Edit", "aria-label": "Edit " + u.username, onclick: () => openUserEdit(u) }, ico("pencil")),
        u.id === state.me.id ? null : h("button", { class: "icon-btn " + (u.is_active ? "del" : "view"), title: u.is_active ? "Deactivate" : "Reactivate", "aria-label": (u.is_active ? "Deactivate " : "Reactivate ") + u.username,
          onclick: () => { if (u.is_active && !confirm("Deactivate " + u.username + "? They are signed out immediately.")) return; patch(u, { is_active: !u.is_active }, (u.is_active ? "Deactivated " : "Reactivated ") + u.username); } }, ico("power"))))));
    holder.replaceChildren(h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["#", "Name", "Email", "Joined", "Role", "Department", "Status", "Actions"].map((t, i) => h("th", { class: i === 0 ? "num" : "" }, t)))),
      h("tbody", {}, body.length ? body : h("tr", {}, h("td", { colspan: 8, class: "empty" }, "No people in this group yet."))))), pager(rows.length, page, SIZE, "users", (p) => { page = p; draw(); }));
  };
  $("main").replaceChildren(pageHead("User Management & Access Control", "Manage users, roles and permissions", h("button", { class: "btn primary", onclick: openUserAdd }, ico("plus"), "Add User")), h("div", { class: "card" }, tabs, holder));
  draw();
};

/* ------------------------------------------------------------ dashboard, analytics */
function systemState(c) {
  const o = c.ollama, bad = [];
  if (!c.database.ok) bad.push("Database"); if (!c.vector_index.ok) bad.push("Vector index");
  if (!o.ok) bad.push("Ollama offline"); else { if (!o.chat_model_installed) bad.push("Answer model missing"); if (!o.embed_model_installed) bad.push("Embedding model missing"); }
  return bad.length ? { ok: false, text: "Degraded", sub: bad.join(", ") } : { ok: true, text: "Online", sub: "All systems healthy" };
}
VIEWS.dashboard = async function () {
  const [st, hc] = await Promise.all([api("/api/admin/stats"), api("/api/admin/health").catch(() => null)]);
  const sys = hc ? systemState(hc) : { ok: false, text: "Unknown", sub: "Health check failed" };
  const sens = st.docs_by_sensitivity, sensitive = (sens.confidential || 0) + (sens.restricted || 0), days = st.per_day;
  const activity = days.length ? lineChart(days.map((d) => dayLabel(d.day)), [{ name: "Answered", cls: "blue", values: days.map((d) => d.answered) }, { name: "Unanswered", cls: "violet", values: days.map((d) => d.unanswered) }], "Questions per day, answered and unanswered")
    : h("p", { class: "empty" }, "No questions yet. Activity appears here once people start asking.");
  const qa = (cls, icon, label, fn) => h("button", { class: cls, onclick: fn }, ico(icon), label);
  $("main").replaceChildren(pageHead("Dashboard", "Overview of your Enterprise RAG System", h("span", { class: "range" }, ico("clock"), "Last 14 days")),
    h("div", { class: "grid g-4" }, kpi("blue", "file", "Total Documents", st.documents, sensitive + " confidential or restricted"), kpi("green", "chat", "Total Queries", st.queries, st.unanswered + " unanswered"),
      kpi("violet", "users", "Active Users", st.active_users, "Active accounts"), kpi("amber " + (sys.ok ? "ok" : "bad"), "shield", "System Status", sys.text, sys.sub)),
    h("div", { class: "grid g-main" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Activity Overview"), h("div", { class: "legend" }, h("span", {}, h("i", { class: "c-blue" }), "Answered"), h("span", {}, h("i", { class: "c-violet" }), "Unanswered"))), activity),
      h("div", { class: "card qa-card" }, h("div", { class: "card-head" }, h("h2", {}, "Quick Actions")), h("div", { class: "qa" },
        qa("q1", "upload", "Upload Document", openUpload), qa("q2", "chat", "Ask AI Assistant", () => go("ask")), qa("q3", "users", "Manage Users", () => go("users")), qa("q4", "list", "View Logs", () => go("audit"))))));
};
VIEWS.analytics = async function () {
  const st = await api("/api/admin/stats"), days = st.per_day, fb = st.feedback, rated = fb.up + fb.down, sens = st.docs_by_sensitivity;
  const total = Object.values(sens).reduce((a, b) => a + b, 0), parts = SENS.filter((k) => sens[k]).map((k) => ({ cls: k, label: cap(k), value: sens[k] }));
  const trend = days.length ? lineChart(days.map((d) => dayLabel(d.day)), [{ name: "Queries", cls: "blue", values: days.map((d) => d.answered + d.unanswered) }], "Questions per day") : h("p", { class: "empty" }, "No questions asked yet.");
  const topMax = Math.max(1, ...st.top_sources.map((x) => x[1]));
  const top = st.top_sources.length ? st.top_sources.map(([n, c]) => { const t = h("div", { class: "t" }, h("i")); t.firstChild.style.width = (c / topMax) * 100 + "%"; return h("div", { class: "hrow" }, h("span", { title: n }, n), t, h("b", {}, c)); }) : [h("p", { class: "empty" }, "No cited documents yet.")];
  const row = (k, v) => h("div", {}, h("span", {}, k), h("b", {}, v));
  $("main").replaceChildren(pageHead("Analytics Dashboard", "Insights and trends", h("span", { class: "range" }, ico("clock"), "Last 14 days")),
    h("div", { class: "grid g-4" }, kpi("blue", "chat", "Total Queries", st.queries, st.unanswered + " unanswered"), kpi("green", "clock", "Median Response Time", secs(st.latency_ms.p50), "Slowest 5%: " + secs(st.latency_ms.p95)),
      kpi("violet", "shield", "Unauthorized Matches Blocked", st.blocked_candidates, "Stopped before reaching the model"), kpi("amber", "thumb", "Helpful Answers", rated ? Math.round(fb.up / rated * 100) + "%" : "n/a", fb.up + " helpful, " + fb.down + " not helpful")),
    h("div", { class: "grid g-main" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Query Trends"), h("div", { class: "legend" }, h("span", {}, h("i", { class: "c-blue" }), "Queries"))), trend),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Documents by Sensitivity")), total ? h("div", { class: "donut-row" }, donut(parts, total),
        h("div", { class: "dlegend" }, parts.map((p) => h("div", {}, h("i", { class: "c-" + p.cls }), p.label, h("span", {}, Math.round(p.value / total * 100) + "%")))) ) : h("p", { class: "empty" }, "No documents yet."))),
    h("div", { class: "grid g-2" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Most Cited Documents")), top),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Answer Quality & Security")), h("div", { class: "stat-list" },
        row("Unanswered questions (missing policies)", st.unanswered), row("Failed sign-ins", st.failed_logins), row("Injection attempts flagged", st.injection_flags), row("Documents", st.documents), row("Active users", st.active_users)))));
};

/* ------------------------------------------------------------ audit log */
VIEWS.audit = async function () {
  const logs = await api("/api/admin/audit?limit=500"), SIZE = 10; let page = 1;
  const actions = [...new Set(logs.map((l) => l.action))].sort();
  const fa = h("select", { "aria-label": "Filter by action", onchange: () => { page = 1; draw(); } }, h("option", { value: "" }, "All Actions"), actions.map((x) => h("option", { value: x }, cap(x.replace(/_/g, " ")))));
  const fo = h("select", { "aria-label": "Filter by outcome", onchange: () => { page = 1; draw(); } }, h("option", { value: "" }, "All outcomes"), ["allowed", "denied", "no_context"].map((x) => h("option", { value: x }, cap(x.replace(/_/g, " ")))));
  const holder = h("div");
  const draw = () => {
    const rows = logs.filter((l) => (!fa.value || l.action === fa.value) && (!fo.value || l.decision === fo.value)); page = Math.min(page, Math.max(1, Math.ceil(rows.length / SIZE)));
    const body = rows.slice((page - 1) * SIZE, page * SIZE).map((l, i) => h("tr", {}, h("td", { class: "num" }, (page - 1) * SIZE + i + 1), h("td", {}, fmtStamp(l.ts)), h("td", {}, l.username || "unknown"), h("td", {}, cap(l.action.replace(/_/g, " "))),
      h("td", { class: "wrap" }, l.sources.map((x) => x.filename).join(", ") || "None"), h("td", { class: "wrap" }, l.query || l.detail || ""), h("td", {}, chip(l.decision)), h("td", {}, l.blocked_candidates || ""), h("td", {}, l.latency_ms ? l.latency_ms + " ms" : "")));
    holder.replaceChildren(h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["#", "Timestamp", "User", "Action", "Resource", "Details", "Outcome", "Blocked", "Time taken"].map((t, i) => h("th", { class: i === 0 ? "num" : "" }, t)))),
      h("tbody", {}, body.length ? body : h("tr", {}, h("td", { colspan: 9, class: "empty" }, "No activity matches these filters."))))), pager(rows.length, page, SIZE, "events", (p) => { page = p; draw(); }));
  };
  $("main").replaceChildren(pageHead("Audit Logs", "Track all system activities", fa, fo), h("div", { class: "card" }, holder)); draw();
};

/* ------------------------------------------------------------ settings */
VIEWS.settings = async function () {
  const m = state.me, t = theme();
  const seg = h("div", { class: "segmented", role: "group", "aria-label": "Theme" }, [["dark", "Dark"], ["light", "Light"]].map(([v, l]) => h("button", { "aria-pressed": t === v, onclick: () => setTheme(v) }, l)));
  const row = (k, v) => h("div", {}, h("span", {}, k), h("b", {}, v));
  const cards = [h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Appearance")), h("p", { class: "muted" }, "Choose how the console looks on this device."), seg),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "Your Account")), h("div", { class: "stat-list" }, row("Username", m.username), row("Role", ROLE_LABEL[m.role]), row("Department", cap(m.department)),
      row("Can read up to", m.role === "admin" ? "Restricted (full access)" : cap(SENS[Math.min(m.clearance, 3)]))))];
  if (m.role === "admin") {
    const c = await api("/api/admin/health"), o = c.ollama;
    const hr = (name, ok, text) => h("div", { class: "hrow" }, h("span", { class: "dot" + (ok ? " ok" : "") }), h("b", {}, name), h("span", { class: "muted" }, text));
    cards.push(h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", {}, "System Health"), h("button", { class: "btn", onclick: () => go("settings") }, "Check again")),
      hr("Database", c.database.ok, c.database.ok ? "Connected" : c.database.error), hr("Vector index", c.vector_index.ok, c.vector_index.ok ? c.vector_index.chunks + " passages indexed" : c.vector_index.error),
      hr("Ollama", o.ok, o.ok ? "Reachable" : o.error),
      o.ok ? hr("Answer model " + o.chat_model, o.chat_model_installed, o.chat_model_installed ? "Installed" : "Not installed. Run: ollama pull " + o.chat_model) : null,
      o.ok ? hr("Embedding model " + o.embed_model, o.embed_model_installed, o.embed_model_installed ? "Installed" : "Not installed. Run: ollama pull " + o.embed_model) : null));
  }
  $("main").replaceChildren(pageHead("Settings", "Appearance, account and system status"), h("div", { class: "grid g-2" }, cards.slice(0, 2)), ...cards.slice(2));
};

loadAuthConfig();
finishSso().then(() => boot());
