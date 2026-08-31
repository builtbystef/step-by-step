(() => {
  if (globalThis.stepByStepRecorderInstalled) return;
  globalThis.stepByStepRecorderInstalled = true;

  const pageLoad = [...crypto.getRandomValues(new Uint8Array(16))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  let sequence = 0;
  let extract = null;
  // Long enough for the click a press usually becomes to arrive first.
  const PRESS_WITHOUT_CLICK_MS = 300;
  let press = null;
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

    // Playwright's get_by_label reads aria-label too, so this rides the label kind.
    // An element whose subtree text is an unusable blob often still names itself here.
    const aria = element.getAttribute("aria-label");
    if (aria && unique(`[aria-label="${selectorEscaped(aria)}"]`, element)) {
      candidates.push({ kind: "label", value: normalized(aria) });
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

  function cross() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 16 16");
    svg.setAttribute("width", "14");
    svg.setAttribute("height", "14");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.5");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M4 4l8 8M12 4l-8 8");
    svg.append(path);
    return svg;
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
    // The app's warn Callout, said in full here: this box lands in a page whose
    // own stylesheet it cannot borrow anything from.
    Object.assign(warning.style, {
      position: "fixed",
      inset: "16px 16px auto 16px",
      zIndex: "2147483647",
      boxSizing: "border-box",
      display: "flex",
      alignItems: "flex-start",
      gap: "12px",
      margin: "0",
      padding: "12px 16px",
      font: "600 13px/1.45 system-ui, sans-serif",
      textAlign: "left",
      background: "#fdf3e0",
      color: "#9a6700",
      border: "1px solid rgb(154 103 0 / 30%)",
      borderLeftWidth: "3px",
      borderRadius: "0",
      boxShadow: "0 6px 16px rgb(19 19 22 / 12%)",
    });

    const said = document.createElement("span");
    said.style.flex = "1";
    said.textContent = unsupported.warning;

    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.setAttribute("aria-label", "Dismiss this warning");
    // Drawn rather than written, so the box still reads as only its warning, and
    // built node by node because a page with Trusted Types refuses innerHTML.
    dismiss.append(cross());
    Object.assign(dismiss.style, {
      all: "unset",
      cursor: "pointer",
      flex: "none",
      display: "flex",
      margin: "-2px -4px 0 0",
      padding: "2px",
      color: "inherit",
    });
    dismiss.addEventListener("click", () => warning.remove());

    warning.append(said, dismiss);
    document.documentElement.append(warning);
  }

  function actionable(target) {
    if (!(target instanceof Element)) return null;
    // The recorder's own warning box belongs to no Workflow, dismissing it least of all.
    if (target.closest("[data-step-by-step-warning]")) return null;
    return (
      target.closest("a,button,input,select,textarea,summary,[role],[onclick],label") ?? target
    );
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
    if (message?.type === "recorder-read-storage") {
      const entries = (storage) => {
        try {
          return Object.entries(storage).map(([name, value]) => ({ name, value }));
        } catch {
          return [];
        }
      };
      respond({
        origin: location.origin,
        localStorage: entries(localStorage),
        sessionStorage: entries(sessionStorage),
      });
    } else if (message?.type === "recorder-arm-extract") {
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
      const correlation = correlationFor(element);
      const primary = event.button === 0;
      send({ type: "recorder-ax", correlation, pageLoad, press: primary });
      if (!primary) return;
      // A control that acts on the press rather than the click — a search suggestion,
      // say — moves the page out from under the pointer, so the release lands on
      // whatever replaced it and no click event is ever dispatched. What was pressed
      // has to be described now, while it is still on the page.
      const pressed = {
        correlation,
        element,
        url: location.href,
        candidates: candidatesFor(element),
        description: normalized(element.textContent).slice(0, 120),
      };
      press = pressed;
      setTimeout(() => {
        if (press !== pressed) return;
        press = null;
        // Only a press that visibly did something: one that changed the page, or took
        // what was pressed off it. Anything else is a drag, or a press thought better of.
        if (location.href === pressed.url && pressed.element.isConnected) return;
        send({
          type: "recorder-event",
          event: "click",
          correlation: pressed.correlation,
          pageLoad,
          candidates: pressed.candidates,
          description: pressed.description,
        });
      }, PRESS_WITHOUT_CLICK_MS);
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
      press = null;
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
