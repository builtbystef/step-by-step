// PROTOTYPE — disposable. Interaction capture + ranked selector candidates.
// Ranking follows Playwright codegen's score order (f10wq3): testid, role+name
// (added service-worker-side from CDP), placeholder, label, alt, text, title,
// css #id, input name, tag, css path. Every candidate is verified unique
// against the live DOM before it is stored.

let recCounter = 0;
let extractMode = false;
// recIds are scoped to this page load, so service-worker caches never collide
// across navigations.
const pageTag = Math.random().toString(36).slice(2, 8);

const norm = (t) => (t || "").replace(/\s+/g, " ").trim();
const esc = (v) => CSS.escape(v);

function uniqueCss(sel, el) {
  try {
    const m = document.querySelectorAll(sel);
    return m.length === 1 && m[0] === el;
  } catch {
    return false;
  }
}

function cssPath(el) {
  const parts = [];
  let node = el;
  while (node && node.nodeType === 1 && node !== document.body) {
    let part = node.tagName.toLowerCase();
    const siblings = [...(node.parentNode?.children || [])].filter(
      (c) => c.tagName === node.tagName
    );
    if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
    parts.unshift(part);
    if (uniqueCss(parts.join(" > "), el)) break;
    node = node.parentNode;
  }
  return parts.join(" > ");
}

function computeCandidates(el) {
  const out = [];
  const tag = el.tagName.toLowerCase();

  for (const a of ["data-testid", "data-test", "data-test-id", "data-qa", "data-cy"]) {
    const v = el.getAttribute(a);
    if (v) {
      out.push({ kind: "testid", attr: a, value: v, verified: uniqueCss(`[${a}="${esc(v)}"]`, el) });
      break;
    }
  }

  // role+name candidate is inserted ahead of these by the service worker.

  const ph = el.getAttribute("placeholder");
  if (ph)
    out.push({ kind: "placeholder", value: ph, verified: uniqueCss(`[placeholder="${esc(ph)}"]`, el) });

  let labelText = null;
  if (el.id) {
    const l = document.querySelector(`label[for="${esc(el.id)}"]`);
    if (l) labelText = norm(l.textContent);
  }
  if (!labelText) labelText = el.getAttribute("aria-label");
  if (labelText) {
    const sameLabel = [...document.querySelectorAll("label")].filter(
      (l) => norm(l.textContent) === labelText
    );
    const sameAria = [...document.querySelectorAll(`[aria-label="${esc(labelText)}"]`)];
    out.push({ kind: "label", value: labelText, verified: sameLabel.length + sameAria.length === 1 });
  }

  const alt = el.getAttribute("alt");
  if (alt) out.push({ kind: "alt", value: alt, verified: uniqueCss(`[alt="${esc(alt)}"]`, el) });

  const clickable =
    ["a", "button", "summary"].includes(tag) ||
    (tag === "input" && ["submit", "button"].includes(el.type));
  if (clickable) {
    const t = tag === "input" ? norm(el.value) : norm(el.textContent);
    if (t && t.length <= 80) {
      const same = [...document.querySelectorAll(tag)].filter(
        (e) => norm(tag === "input" ? e.value : e.textContent) === t
      );
      out.push({ kind: "text", value: t, verified: same.length === 1 });
    }
  }

  const title = el.getAttribute("title");
  if (title) out.push({ kind: "title", value: title, verified: uniqueCss(`[title="${esc(title)}"]`, el) });

  if (el.id) out.push({ kind: "css", value: `#${esc(el.id)}`, verified: uniqueCss(`#${esc(el.id)}`, el) });

  if ((tag === "input" || tag === "select" || tag === "textarea") && el.name) {
    const s = `${tag}[name="${esc(el.name)}"]`;
    out.push({ kind: "css", value: s, verified: uniqueCss(s, el) });
  }

  if (uniqueCss(tag, el)) out.push({ kind: "css", value: tag, verified: true });

  const path = cssPath(el);
  out.push({ kind: "css", value: path, verified: uniqueCss(path, el) });

  return out;
}

function targetOf(e) {
  const el = e.target.closest?.(
    "a,button,input,select,textarea,summary,[role],[onclick],label"
  );
  return el || e.target;
}

function mark(el) {
  let id = el.getAttribute("data-protorec");
  if (!id) {
    id = `${pageTag}-${++recCounter}`;
    el.setAttribute("data-protorec", id);
  }
  return id;
}

function send(msg) {
  try {
    const p = chrome.runtime.sendMessage(msg);
    p?.catch?.((e) => console.warn("[protorec] send rejected:", msg.type, String(e)));
  } catch (e) {
    console.warn("[protorec] send threw:", msg.type, String(e));
  }
}

console.log("[protorec] content script injected on", location.href);
send({ type: "cs-hello", url: location.href });

// Prefetch role+name over CDP before the click can navigate the page away.
addEventListener(
  "pointerdown",
  (e) => {
    if (e.target.closest?.("#proto-extract-toggle")) return;
    const el = targetOf(e);
    send({ type: "ax-prefetch", recId: mark(el), ts: Date.now() });
  },
  true
);

addEventListener(
  "focusin",
  (e) => {
    const el = e.target;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))
      send({ type: "ax-prefetch", recId: mark(el), ts: Date.now() });
  },
  true
);

addEventListener(
  "click",
  (e) => {
    console.log("[protorec] click event fired, target:", e.target.tagName);
    try {
      handleClick(e);
    } catch (err) {
      send({ type: "cs-error", where: "click", error: String(err?.stack || err) });
    }
  },
  true
);

function handleClick(e) {
    if (e.target.closest?.("#proto-extract-toggle")) return;
    const el = targetOf(e);
    const recId = el.getAttribute("data-protorec") || mark(el);
    if (extractMode) {
      e.preventDefault();
      e.stopPropagation();
      send({
        type: "evt",
        kind: "extract",
        recId,
        candidates: computeCandidates(el),
        capturedText: norm(el.textContent),
        url: location.href,
        ts: Date.now(),
        meta: { tag: el.tagName },
      });
      setToggle(false);
      return;
    }
    send({
      type: "evt",
      kind: "click",
      recId,
      candidates: computeCandidates(el),
      url: location.href,
      ts: Date.now(),
      meta: { tag: el.tagName, text: norm(el.textContent).slice(0, 60) },
    });
}

addEventListener(
  "change",
  (e) => {
    const el = e.target;
    const recId = el.getAttribute("data-protorec") || mark(el);
    if (el.tagName === "SELECT") {
      send({
        type: "evt",
        kind: "select",
        recId,
        candidates: computeCandidates(el),
        value: el.value,
        optionLabel: norm(el.selectedOptions[0]?.textContent),
        url: location.href,
        ts: Date.now(),
        meta: { tag: el.tagName },
      });
    } else if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
      if (["checkbox", "radio", "submit", "button"].includes(el.type)) return;
      send({
        type: "evt",
        kind: "fill",
        recId,
        candidates: computeCandidates(el),
        value: el.value,
        isPassword: el.type === "password",
        url: location.href,
        ts: Date.now(),
        meta: { tag: el.tagName },
      });
    }
  },
  true
);

// Floating extract-mode toggle, so extract steps can be recorded without popup access.
let toggleBtn;
function setToggle(on) {
  extractMode = on;
  if (toggleBtn) {
    toggleBtn.textContent = `EXTRACT: ${on ? "ON — next click extracts" : "off"}`;
    toggleBtn.style.background = on ? "#c0392b" : "#2c3e50";
  }
}
function injectToggle() {
  toggleBtn = document.createElement("button");
  toggleBtn.id = "proto-extract-toggle";
  toggleBtn.style.cssText =
    "position:fixed;bottom:12px;right:12px;z-index:2147483647;padding:8px 12px;" +
    "color:#fff;border:none;border-radius:4px;font:12px monospace;cursor:pointer;";
  toggleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setToggle(!extractMode);
  });
  document.body.appendChild(toggleBtn);
  setToggle(false);
}
if (document.body) injectToggle();
else addEventListener("DOMContentLoaded", injectToggle);
