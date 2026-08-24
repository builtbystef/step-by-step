(() => {
  if (globalThis.stepByStepRecorderInstalled) return;
  globalThis.stepByStepRecorderInstalled = true;

  const pageLoad = crypto.randomUUID();
  let sequence = 0;
  let extract = null;
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
      element.textContent ||
        (element instanceof HTMLInputElement && element.type !== "password" ? element.value : ""),
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

  function controlDescription(element) {
    const label = element.labels?.[0];
    const labelText = label
      ? normalized(
          [...label.childNodes]
            .filter((node) => node.nodeType === Node.TEXT_NODE)
            .map((node) => node.textContent)
            .join(" "),
        )
      : "";
    return labelText || element.placeholder || "field";
  }

  function showWarning(unsupported) {
    if (
      unsupported === null ||
      [...document.querySelectorAll('[data-step-by-step-warning="unsupported"]')].some(
        (warning) => warning.textContent === unsupported.warning,
      )
    )
      return;
    const warning = document.createElement("div");
    warning.dataset.stepByStepWarning = "unsupported";
    warning.setAttribute("role", "alert");
    warning.textContent = unsupported.warning;
    Object.assign(warning.style, {
      position: "fixed",
      inset: "16px 16px auto 16px",
      zIndex: "2147483647",
      padding: "12px",
      background: "white",
      color: "black",
      border: "2px solid currentColor",
    });
    document.documentElement.append(warning);
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

  chrome.runtime.onMessage.addListener((message, _sender, respond) => {
    if (message?.type === "recorder-arm-extract") {
      extract = message.extract;
      respond({ armed: true });
    } else if (message?.type === "recorder-warning" && message.unsupported) {
      showWarning(message.unsupported);
    }
  });

  const warnedFrames = new WeakSet();
  setInterval(() => {
    const frame = document.activeElement;
    if (!(frame instanceof HTMLIFrameElement) || warnedFrames.has(frame)) return;
    let unreachable = false;
    try {
      unreachable = frame.contentDocument === null;
    } catch {
      unreachable = true;
    }
    if (!unreachable) return;
    warnedFrames.add(frame);
    const unsupported = {
      reason: "cross-origin-frame",
      warning:
        "The workflow can't reach this embedded part of the page later. The step was recorded anyway.",
    };
    showWarning(unsupported);
    send({
      type: "recorder-event",
      event: "click",
      correlation: correlationFor(frame),
      pageLoad,
      candidates: candidatesFor(frame),
      description: frame.title || "embedded action",
      unsupported,
    });
  }, 100);

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
      const armed = extract;
      if (armed !== null) {
        extract = null;
        event.preventDefault();
        event.stopImmediatePropagation();
      }
      send({
        type: "recorder-event",
        event: armed === null ? "click" : "extract",
        correlation: correlationFor(element),
        pageLoad,
        candidates: candidatesFor(element),
        description: normalized(element.textContent).slice(0, 120),
        ...(armed === null ? {} : { extract: armed }),
      });
    },
    true,
  );

  addEventListener(
    "change",
    (event) => {
      const element = event.target;
      if (
        !(
          element instanceof HTMLInputElement ||
          element instanceof HTMLTextAreaElement ||
          element instanceof HTMLSelectElement
        )
      )
        return;
      if (
        element instanceof HTMLInputElement &&
        ["button", "checkbox", "radio", "submit"].includes(element.type)
      )
        return;
      const isSelect = element instanceof HTMLSelectElement;
      send({
        type: "recorder-event",
        event: isSelect ? "select" : "type",
        correlation: correlationFor(element),
        pageLoad,
        candidates: candidatesFor(element),
        description: controlDescription(element),
        value:
          element instanceof HTMLInputElement && element.type === "password" ? "" : element.value,
        needsSecret: element instanceof HTMLInputElement && element.type === "password",
      });
    },
    true,
  );
})();
