(() => {
  if (globalThis.stepByStepRecorderInstalled) return;
  globalThis.stepByStepRecorderInstalled = true;

  const pageLoad = crypto.randomUUID();
  let sequence = 0;
  const normalized = (value) => (value ?? "").replace(/\s+/g, " ").trim();

  function selectorEscaped(value) {
    return CSS.escape(value);
  }

  function unique(selector, element) {
    try {
      const matches = document.querySelectorAll(selector);
      return matches.length === 1 && matches[0] === element;
    } catch {
      return false;
    }
  }

  function cssPath(element) {
    if (element.id) {
      const byId = `#${selectorEscaped(element.id)}`;
      if (unique(byId, element)) return byId;
    }
    const parts = [];
    let current = element;
    while (current instanceof Element && current !== document.documentElement) {
      let part = current.localName;
      const siblings = [...(current.parentElement?.children ?? [])].filter(
        (sibling) => sibling.localName === current.localName,
      );
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
      parts.unshift(part);
      const candidate = parts.join(" > ");
      if (unique(candidate, element)) return candidate;
      current = current.parentElement;
    }
    return parts.join(" > ");
  }

  function candidatesFor(element) {
    const candidates = [];
    const testid = element.getAttribute("data-testid");
    if (testid && unique(`[data-testid="${selectorEscaped(testid)}"]`, element)) {
      candidates.push({ kind: "testid", value: testid });
    }

    const placeholder = element.getAttribute("placeholder");
    if (placeholder && unique(`[placeholder="${selectorEscaped(placeholder)}"]`, element)) {
      candidates.push({ kind: "placeholder", value: placeholder });
    }

    const label = normalized([...(element.labels ?? [])].map((item) => item.textContent).join(" "));
    if (label) {
      const matches = [...document.querySelectorAll("input,textarea,select,button")].filter(
        (control) =>
          normalized([...(control.labels ?? [])].map((item) => item.textContent).join(" ")) ===
          label,
      );
      if (matches.length === 1 && matches[0] === element) {
        candidates.push({ kind: "label", value: label });
      }
    }

    const alt = element.getAttribute("alt");
    if (alt && unique(`[alt="${selectorEscaped(alt)}"]`, element)) {
      candidates.push({ kind: "alt", value: alt });
    }

    const text = normalized(
      element.textContent || (element instanceof HTMLInputElement ? element.value : ""),
    );
    if (text && text.length <= 120) {
      const matches = [...document.querySelectorAll(element.localName)].filter(
        (match) =>
          normalized(
            match.textContent || (match instanceof HTMLInputElement ? match.value : ""),
          ) === text,
      );
      if (matches.length === 1 && matches[0] === element) {
        candidates.push({ kind: "text", value: text });
      }
    }

    const title = element.getAttribute("title");
    if (title && unique(`[title="${selectorEscaped(title)}"]`, element)) {
      candidates.push({ kind: "title", value: title });
    }

    const css = cssPath(element);
    if (css && unique(css, element)) candidates.push({ kind: "css", value: css });
    return candidates;
  }

  function actionable(target) {
    return target instanceof Element
      ? (target.closest("a,button,input,select,textarea,summary,[role],[onclick],label") ?? target)
      : null;
  }

  function correlationFor(element) {
    let correlation = element.getAttribute("data-step-by-step-correlation");
    if (!correlation) {
      correlation = `${pageLoad}:${++sequence}`;
      element.setAttribute("data-step-by-step-correlation", correlation);
    }
    return correlation;
  }

  function send(message) {
    chrome.runtime.sendMessage(message).catch(() => {});
  }

  addEventListener(
    "pointerdown",
    (event) => {
      const element = actionable(event.target);
      if (!element) return;
      send({ type: "recorder-ax", correlation: correlationFor(element), pageLoad });
    },
    true,
  );

  addEventListener(
    "focusin",
    (event) => {
      const element = actionable(event.target);
      if (!element) return;
      send({ type: "recorder-ax", correlation: correlationFor(element), pageLoad });
    },
    true,
  );

  addEventListener(
    "click",
    (event) => {
      const element = actionable(event.target);
      if (!element) return;
      send({
        type: "recorder-event",
        event: "click",
        correlation: correlationFor(element),
        pageLoad,
        candidates: candidatesFor(element),
        description: normalized(element.textContent).slice(0, 120),
      });
    },
    true,
  );

  addEventListener(
    "change",
    (event) => {
      const element = event.target;
      if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) return;
      if (["button", "checkbox", "radio", "submit"].includes(element.type)) return;
      send({
        type: "recorder-event",
        event: "type",
        correlation: correlationFor(element),
        pageLoad,
        candidates: candidatesFor(element),
        description: normalized(element.labels?.[0]?.textContent || element.placeholder || "field"),
        value: element.type === "password" ? "" : element.value,
        needsSecret: element.type === "password",
      });
    },
    true,
  );
})();
