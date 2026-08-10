---
id: f10wq3
title: How do recorders turn DOM events into durable semantic steps and selectors?
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:research
parent: idnzwf
created: 2026-08-08T07:07:40Z
updated: 2026-08-08T08:11:39Z
---

Research from primary sources. The product's core risk: a recorded click must replay weeks later after page changes. Answer:

- How do Chrome DevTools Recorder, Playwright codegen, rrweb, and commercial recorders (e.g. Axiom, Browserflow, UI.Vision) represent recorded actions and choose selectors?
- Selector durability strategies: ranked selector lists (role/text/test-id/CSS/XPath), fallbacks, self-healing; what does the evidence say works?
- What must the recorder capture at record time to enable good selectors later (accessibility tree, element attributes, screenshots)?
- How do these map to Playwright locators at replay time?

The answer gates the workflow data model node and the recording-extension prototype.

## Notes

**claude** — 2026-08-08T08:11:13Z

# Research: how recorders turn DOM events into durable semantic steps and selectors

## Question

The product's core risk: a recorded click must replay weeks later after the page changed. Four sub-questions:

1. How do Chrome DevTools Recorder, Playwright codegen, and rrweb represent a recorded action, and how does each pick selectors?
2. What do commercial recorders do, and what published evidence exists on selector durability and self-healing?
3. What must the recorder capture *at record time* to enable good selectors later?
4. How do recorded selectors map onto Playwright locators at replay time?

## Answer

**Store a ranked list of verified alternative selectors per action, not one selector.** Chrome DevTools Recorder does exactly this (`selectors: Selector[]`, first-match-wins at replay); Playwright codegen deliberately stores exactly one, because codegen writes source code a human will maintain — that is an authoring tool's constraint, not ours. We persist to a database and replay unattended, so we take the Recorder's shape and Playwright's ranking.

**rrweb is not a candidate.** It emits no selectors at all — nodes are integer ids in a per-session mirror, and replay happens inside rrweb's own rebuilt iframe. Its element identity is meaningless against a fresh page load. rrweb is a session-replay tool; it can only ever be a *viewer* for us, never a source of steps.

**The ranking to use is Playwright's codegen score table**, because it is the ranking our own replay engine's locators are built for: test-id → role+name → placeholder → label → alt → text → title → CSS #id → role-without-name → input type/name → tag → nth → CSS parent-chain. Verify every candidate resolves uniquely to the recorded element *at record time* before persisting it (both Selenium IDE and Playwright codegen do this; it is cheap and it is what makes a stored alternative trustworthy).

**The one hard architectural constraint, and it is a v1 decision:** computed ARIA role and accessible name are **not reachable from a content script**. There is no web-platform API for them; they require `chrome.debugger` + CDP `Accessibility.*` from the service worker — the same privileged path DevTools Recorder itself takes. And accessible name derives from *other* elements (`aria-labelledby` targets, subtree text), so it cannot be reconstructed later from the stored target element alone. **If we want role+name selectors — the top-ranked durable strategy in both Playwright's ranking and Playwright's own docs — the extension must request the `debugger` permission at capture time.** This cannot be deferred to a later version without re-recording every workflow.

**On self-healing: don't build it for v1.** The only published quantitative evidence (two peer-reviewed studies) measured *XPath generators* and a *weighted voting ensemble*, not modern semantic locators, and every commercial self-healing claim is mechanism-described but accuracy-unvalidated. A ranked list of verified alternatives captures most of the available benefit at a fraction of the complexity. Revisit healing when we have run data showing what actually breaks.

**Replay mapping: implement ordered fallback ourselves; do not use `locator.or()`.** `or()` matches the union, which trips Playwright's strict-mode violation exactly when two alternatives both still match. Correct loop: for each candidate in rank order, resolve, `count() == 1` → act; otherwise next. Record which candidate won, so a step that has drifted onto its 4th-ranked selector is visible in the UI.

---

## Findings

### 1. How the open-source recorders represent an action

**Chrome DevTools Recorder / `@puppeteer/replay` (v4.0.2, read 2026-08-08)**

- A recording is a `UserFlow`: `{title, timeout?, selectorAttribute?, steps: Step[]}`. `selectorAttribute` overrides the built-in test-attribute list (doc comment: *"The name of the attribute to use to generate selectors instead of regular CSS selectors."*). — `puppeteer/replay` `src/Schema.ts`
- `StepType` is exactly: `change, click, close, customStep, doubleClick, emulateNetworkConditions, hover, keyDown, keyUp, navigate, scroll, setViewport, waitForElement, waitForExpression`. — same file
- Field layering: `BaseStep {type, timeout?, assertedEvents?}` → `StepWithTarget {target?}` → `StepWithFrame {frame?: number[]}` → `StepWithSelectors {selectors: Selector[]}`. Per-type extras: click → `deviceType, button, offsetX, offsetY, duration`; change → `value`; keyDown/keyUp → `key`; navigate → `url`; setViewport → `width, height, deviceScaleFactor, isMobile, hasTouch, isLandscape`; waitForElement → `operator, count, visible, properties, attributes`. — same file
- **The key type: `Selector = string | string[]`.** The outer list is *alternatives* (OR, tried in order); the inner array is a *descent path* (AND, chained through shadow roots — last element targets the element, preceding elements are ancestor/shadow-host hops). Doc comment: *"A list of alternative selectors that lead to selection of a single element"*, emitted *"to improve reliability of the replay as some selectors might get outdated over time."* — same file
- Replay is **first-match-wins, not consensus**: `querySelectorsAll` loops the alternatives and returns on the first that yields any element; each part is chained through `el.shadowRoot ?? el`. — `src/PuppeteerRunnerExtension.ts` ~L408–452
- Selector kinds: `css, aria, text, xpath, pierce`, non-CSS emitted with a string prefix (`aria/`, `text/`, `xpath/`, `pierce/`). — `Schema.ts` + devtools-frontend `front_end/panels/recorder/injected/SelectorComputer.ts`
- **Default emission order is `['aria', 'css', 'xpath', 'pierce', 'text']`.** If a custom selector attribute is configured it flips to `['css', 'xpath', 'pierce', 'aria', 'text']`, with the in-source comment *"Custom DOM attributes indicate a preference for CSS/XPath selectors."* — `SelectorComputer.ts` L32–108
- Built-in test-attribute list, *"Most common attributes first"*: `data-testid, data-test, data-qa, data-cy, data-test-id, data-qa-id, data-testing`. — same file
- The ARIA computer is not a DOM query: it takes injected `AccessibilityBindings {getAccessibleName(node), getAccessibleRole(node)}` and walks the a11y tree, producing parts like `Name`, `[role="button"]`, or `Name[role="button"]`, each required to resolve uniquely. — `injected/selectors/ARIASelector.ts`

**Playwright codegen (v1.62.1 / main, read 2026-08-08)**

- Internal representation is `ActionInContext {pageGuid, action, signals}`. `ActionName` ∈ `check, click, hover, closePage, fill, navigate, openPage, press, select, uncheck, setInputFiles, assertText, assertValue, assertChecked, assertVisible, assertSnapshot`. `Signal` ∈ `navigation, popup, download, dialog, expect`, attached to the action. — `packages/isomorphic/codegen/actions.d.ts`
- **`ActionWithSelector = {name, ariaSnapshot?, selector: string, ref?}` — exactly one selector string, no alternatives list.** — same file
- Priority is a numeric score, **lower is better** (`packages/injected/src/selectorGenerator.ts` L37–68): testId **1**, other `data-test*` **2**, iframe-by-attribute **10**, role+name **100**, placeholder **120**, label **140**, alt-text **160**, text **180**, title **200**, text-regex **250**, CSS `#id` **500**, role-without-name **510**, CSS input-type-name **520**, CSS tag name **530**, nth **10000**, CSS parent-chain fallback **10000000**. `kExactPenalty = 5` is added to the `*Exact` variants (role+name exact = 105, etc.).
- The algorithm sorts candidates by score, then takes **the first that both matches the target and returns exactly one element** — in-source comment: *"Perfect strict match. All other candidates are strictly worse because they are sorted by score."* Falls back to `:nth-match`/parent-chain CSS if nothing is unique. This is *why* codegen emits one already-verified locator. — same file L121–200
- Docs confirm: *"Playwright will look at your page and figure out the best locator, prioritizing role, text and test id locators… If the generator identifies multiple elements matching the locator, it will improve the locator to make it resilient and uniquely identify the target element."* — https://playwright.dev/docs/codegen
- **No public API for selector generation.** `generateSelector` lives in the injected-script bundle (`packages/injected/src/selectorGenerator.ts`) and appears nowhere in `packages/playwright-core/types/types.d.ts` (27,078 lines) — internal only. We cannot call Playwright to generate a selector; we reimplement the ranking in the extension.

**rrweb (master, read 2026-08-08)**

- **Produces no selectors whatsoever.** Nodes get a monotonic integer at serialization: `let _id = 1; export function genId(): number { return _id++ }`. — `packages/rrweb-snapshot/src/snapshot.ts` L36–41, 1032
- Identity is the `Mirror` (`idNodeMap: Map`, `nodeMetaMap: WeakMap`) with `getId(n)` returning `-1` for unserialized nodes. — `packages/rrweb-snapshot/src/utils.ts`
- Every interaction event stores `mirror.getId(target)` as an integer. No CSS/XPath string is ever computed. — `packages/rrweb/src/record/observer.ts`
- Replay rebuilds the snapshot into rrweb's **own iframe** and resolves events via `this.mirror.getNode(d.id)`; `querySelector` appears twice in the whole replayer and never for event targeting. — `packages/rrweb/src/replay/index.ts`
- Consequence: an rrweb recording carries no element identity that survives outside its own session. Converting rrweb events to automation would require re-deriving selectors from the serialized tree, which rrweb does not do.

### 2. Commercial recorders and the durability evidence

**Selenium IDE (source read, `SeleniumHQ/selenium-ide` @ `5d595cd`, 2024-11-22)**

- Builders are registered in priority order (in-source comment: *"order listed dictates priority"*): `css:data-test-id` (tries `data-test-id` then `data-test`), `id`, `linkText`, `name`, `css:data-attr`, `css:finder`, `xpath:link`, `xpath:img`, `xpath:attributes`, `xpath:idRelative`, `xpath:href`, `xpath:position`, `xpath:innerText`. — `.../preload/locator-builders.ts` L298–566
- **`buildAll()` verifies each candidate before keeping it** — runs `findElement(locator)` and pushes only if the resolved element `== el`. The full verified list is persisted per command as `targets?: [string, string][]`. — `locator-builders.ts` L62–100; `packages/side-model/src/types.ts` L10
- **Contradiction worth recording: runtime fallback is present in the API surface but commented out.** Every command threads `fallbackTargets` down to `waitForElement`, but `elementIsLocated` tries only the primary locator and returns `null` otherwise. The fallback loop is commented out with the note that fallback selectors *"are not visible or editable enough for now. They create points of user confusion and are not necessary for the vast majority of cases."* The integration test is `it.skip('should perform locator fallback', ...)`. — `packages/side-runtime/src/webdriver.ts` L1443–1462; `playback-webdriver.spec.ts` L223
- Official Selenium docs describe the alternatives as an authoring affordance only (*"a drop-down list accessible at the right end of the Target field"*), with no playback-fallback claim — consistent with the source, and against the widespread secondary belief that Selenium IDE falls back at runtime. — https://www.selenium.dev/documentation/legacy/selenium_ide/

**Healenium (source read; `healenium-web` @ `c1e4f83`, algorithm in `com.epam.healenium:tree-comparing` v0.4.14)**

- Stores per element the **full ancestor path**, each node carrying `tag, index, innerText, id, classes (set), attributes (map)`, extracted by an injected JS. — `NodeService.java` L41–88
- Triggers on `NoSuchElement`; docs: *"Healenium catches NoSuchElement exception, triggers the LSC algorithm, passes the current page state, gets previous successful locator path, compares them, and generates the list of healed locators… It takes the locator with the highest score."* — https://healenium.io/docs/how_healenium_works
- Two-stage scoring: path distance = **Longest Common Subsequence** (`LCSPathDistance`), node distance = weighted heuristic (`HeuristicNodeDistance`). It enumerates **all leaf paths** of the new DOM. — `HealingService.java` L60; `PathFinder.java`
- Weights (v0.4.14): TAG 100.0, LCS 100.0, ID 50.0, CLASS 40.0, innerText 30.0, other attribute 30.0, **INDEX 0.0**; normalized to [0,1]. Bails to 0.0 if `curPathHeight > 5 && LCSDistance/curPathHeight < 0.7`. Levenshtein used for id/innerText (threshold 0.3) and classes/attributes (0.75). — `HeuristicNodeDistance.java` L11–27, L114–141
- Healed node → locator via an escalating CSS-detail ladder, accepting the first matching exactly one unclaimed element: `{TAG,ID}` → `{TAG,CLASS}` → `{PARENT,TAG,ID,CLASS}` → `{PARENT,TAG,CLASS,POSITION}` → `{PARENT,TAG,ID,CLASS,ATTRIBUTES}` → `{PATH}`. — `HealingService.java` L38–45, L84–116
- Configurable gate: `score-cap` default **0.6**, `recovery-tries` default **1**, candidates capped at 1000. — https://healenium.io/docs/download_and_install/hlm_web

**Commercial, what each actually documents**

- **Testim** — "Smart Locators": *"analyzes potentially hundreds of attributes… assigns weights to the attributes to uniquely identify the element"*; *"If some attributes change, the Smart Locator will use other attributes."* Attribute list, weighting function, and threshold **not published**. One number is documented: *"If a locator score drops below 70%, Testim automatically attempts to improve that locator."* — docs.tricentis.com/testim
- **mabl** — the most thoroughly documented. Per-step "element history" of collected attributes, optionally **ancestor elements** and custom test-ID attributes; matching is a model-match: *"mabl looks for a strong match to the model of the element learned from past runs"*, including *"comparing partial matches to the model."* Advanced auto-heal (cloud only, and only after the test *"has run successfully in a plan at least 5 times"*) *"uses generative AI to identify semantic similarities."* Low-confidence matches **fail the step rather than heal**; the model updates only on a **passing plan run**. Hand-written CSS/XPath find steps are explicitly **excluded** from healing. — help.mabl.com/hc/en-us/articles/19078583792404
- **Katalon** — ordered strategies (*"XPath (default), Attributes, CSS, Image, and Smart Locator"*), user-reorderable, *"tries to generate the object locator with the method at the top first. If it fails, it will try alternative methods, from the top down."* Healing tries other stored locators; if all fail, an LLM *"analyze[s] signals such as page source, accessibility tree, full-page screenshot, and element screenshots."* — docs.katalon.com (updated April 2026)
- **UI.Vision** — documents genuine runtime fallback: *"The IDE records and keeps all possible locators and uses them if the primary locator (as picked by the IDE) fails… After the search for the primary locator times out, the IDE tries every secondary locator in the list, until one matches."* Strategies: ID, Name, Link, XPath, CSS, plus visual (Image, OCR). Candidate-generation heuristic undocumented. — ui.vision/rpa/docs/selenium-ide/locators
- **Axiom.ai** — **undocumented**. Selector-tool pages cover point-and-click selection and custom CSS, but publish nothing about derivation, storage, or fallback. Only documented failure behavior is binary: *"if the selected element is missing, Axiom will throw an error and stop the run"*, unless "Optional click" is set. No self-healing claimed. — axiom.ai/docs
- **Browserflow** — **no source found**. The product pivoted; `app.browserflow.io/docs` now serves an OpenAPI spec for a LinkedIn scraping API with no mention of element identification. Former recorder docs not publicly reachable.

**Published evidence — the only quantitative data that exists**

- **Leotta, Stocco, Ricca, Tonella, "ROBULA+", *JSEP* 28(3):177–204, 2016**, DOI 10.1002/smr.1771. 8 open-source apps, two consecutive releases each, **1110 elements**, hand-built element mapping as oracle. Broken locators out of 1110: **absolute XPath 871 (78%)**, **id-based relative XPath 557 (50%)**, **Montoto 282**, **Selenium IDE 248**, **ROBULA 334**, **ROBULA+ 91**. Verbatim: *"ROBULA+ reduces the locators fragility on average by 90% w.r.t. absolute locators and by 63% w.r.t. Selenium IDE locators."* The same authors' earlier finding: *"58% of the 791 XPath locators were broken from a release to the next one."*
- **Leotta et al., "Using Multi-Locators to Increase the Robustness of Web Test Cases", *IEEE ICST 2015*, pp. 1–10**, DOI 10.1109/ICST.2015.7102611. 6 apps, **675 elements**, 5 generators run in parallel per element, results **voted** on with per-generator weights. Single-strategy breakage: absolute 449 (67%), relative id-based 331 (49%), Montoto 151 (22%), Selenium IDE 16%, ROBULA+ 78 (12%). **Weighted ensemble: 55 broken (8%) — a 29.5% reduction vs the best single strategy**, against a theoretical floor of 46 for those 5 generators. Overhead *"negligible (2–3% at most)."* Hand-set weights reported as equivalent to cross-validated ones: ROBULA+ 0.90, Selenium IDE 0.85, Montoto 0.80, relative id-based 0.50, absolute 0.33.
- **The ensemble has a hard ceiling**, stated in the paper: *"if all locators in L are broken when used to query the evolved DOM D′, the multi-locator has no chance of being able to select the right element… This sets an upper bound to the robustness achievable by any multi-locator."* Voting can also pick the **wrong** element when broken locators converge — the paper's worked example has 3 broken locators out-voting 2 correct ones under uniform weights.
- **Caveat that bounds how far we should carry these numbers:** both studies compare *XPath generation strategies* on 2015-era apps. Neither evaluates role/accessible-name or test-id locators, which are the top of Playwright's ranking. The papers establish that (a) structural locators break at high rates, (b) redundancy helps materially, and (c) verified generation beats naive generation — they do not establish a ranking for semantic locators.
- **No first-party evidence found for any commercial self-healing claim.** Testim, mabl, Katalon, and UI.Vision publish mechanism descriptions and zero accuracy, false-heal-rate, or robustness measurements. No vendor benchmark, no dataset, no reproducible study. **No peer-reviewed evaluation of Healenium was found either**, despite its algorithm being fully readable; its constants (score-cap 0.6, the 0.7 LCS bail-out, the 100/50/40/30 weights, INDEX at zero) appear to be unvalidated engineering choices.

### 3. What must be captured at record time

**The content-script ceiling (the architectural finding)**

- Content scripts share the page DOM — *"An isolated world is a private execution environment that isn't accessible to the page or other extensions"*, but they can *"read details of the web pages the browser visits, make changes to them."* So tag, attributes, text, ancestry, `getBoundingClientRect`, and `scrollX/Y` are all available synchronously in an event listener. — https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
- Content scripts *"can only directly access"* `storage`, `i18n`, `dom`, and some `runtime`; *"content scripts are unable to access other APIs directly."* `chrome.debugger` must therefore be driven from the **service worker**. — same page
- **There is no web-platform API exposing computed role/name to page or content scripts.** WICG AOM Phase 4 (query computed a11y tree) is *Partial* in all engines; the a11y-tree query surface shipped instead as **WebDriver endpoints** `GET .../element/{id}/computedrole` and `.../computedlabel`. Earlier element-level JS syntaxes in Chrome and Firefox were abandoned in favor of the WebDriver interface. — https://wicg.github.io/aom/caniuse.html; https://w3c.github.io/webdriver/#get-computed-role
- The a11y tree therefore requires CDP. The `Accessibility` domain (**Experimental**) provides `getFullAXTree`, `getPartialAXTree` (*"the accessibility node and partial accessibility tree for this DOM node… plus its ancestors, siblings and children"*), `queryAXTree`, `getAXNodeAndAncestors`; each `AXNode` carries `role` (*"whether explicit or implicit"*) and `name`. — https://chromedevtools.github.io/devtools-protocol/tot/Accessibility/
- **`Accessibility` is on the MV3 `chrome.debugger` allowlist**: *"the chrome.debugger API does not provide access to all Chrome DevTools Protocol Domains. The available domains are: Accessibility, Audits, CacheStorage, Console, CSS, Database, Debugger, DOM, DOMDebugger, DOMSnapshot, Emulation, Fetch, IO, Input, Inspector, Log, Network, Overlay, Page, Performance, Profiler, Runtime, Storage, Target, Tracing, WebAudio, WebAuthn."* Requires the `"debugger"` manifest permission. — https://developer.chrome.com/docs/extensions/reference/api/debugger
- **This is exactly the path DevTools Recorder takes.** `RecordingSession.ts` resumes `SDK.AccessibilityModel` per target, adds CDP bindings via `runtimeModel.addBinding({name, executionContextName: DEVTOOLS_RECORDER_WORLD_NAME})`, then injects with `pageAgent().invoke_addScriptToEvaluateOnNewDocument({source, worldName, includeCommandLineAPI: true})`, where the script is `DevToolsRecorder.startRecording({getAccessibleName, getAccessibleRole}, {...})`. Console Utilities are DevTools-only: *"These functions only work when you call them from the Chrome DevTools Console. They won't work if you try to call them in your scripts."* — `front_end/panels/recorder/models/RecordingSession.ts`; https://developer.chrome.com/docs/devtools/console/utilities
- **Accessible name must be computed at record time, not reconstructed later.** accname's algorithm is a precedence order — `aria-labelledby`, then `aria-label`, then native host-language labeling (HTML `label`, `alt`, `title`), then element content — so the name is derived from *other* elements and cannot be recovered from the stored target element's own attributes. — https://w3c.github.io/accname/ (W3C ED, 29 May 2026)

**Structural concerns that must be captured, not derived**

- **Shadow DOM**: Recorder emits **one selector per shadow boundary** — in-source: *"selectors cannot cross ShadowRoot borders, so the actual goal is to find the minimal selector that is unique within a root node. We then need to repeat this for each shadow root"*, looping `root = node.getRootNode()`, unshifting a selector, then `node = root instanceof ShadowRoot ? root.host : root`. — `injected/selectors/CSSSelector.ts`
- **Frames**: Recorder captures `frame?: number[]` — *"an array of zero-based indexes that identify an iframe that can be nested."* A positional path. Playwright can instead address frames by **name** (`page.frame('frame-login')`) or **URL** (`page.frame({url: /.*domain.*/})`) — more durable when frame order shifts, so capture name and URL alongside the index. — `Schema.ts`; https://developer.chrome.com/docs/devtools/recorder/reference; https://playwright.dev/docs/frames
- **Separate targets** (popups/new tabs): `target?: Target`, default `"main"` — *"a URL for the Chrome DevTools Protocol (CDP) target, the default `main` keyword refers to the current page."*
- **Click offset**: `offsetX`/`offsetY`, *"Relative to the top-left of the element content box, in pixels,"* defaulting to element center — a within-element coordinate, not a viewport box.
- **Element expectations**: `WaitForElementStep` captures `operator ('>='|'=='|'<=', default '==')`, `count (default 1)`, `visible (default true)`, `attributes`, `properties` — i.e. a recorded assertion about the element's state, independent of the selector.
- **Post-action navigation**: `assertedEvents?`, restricted to *"a single `navigation` event"* — the record-time capture of what the action was expected to cause.
- **Recorder JSON has no screenshot and no DOM-snapshot field** (the `StepType` enum above is complete). If we want those, they come via CDP `DOMSnapshot.captureSnapshot` — *"the full DOM tree of the root node (including iframes, template contents, and imported documents) in a flattened array, as well as layout and white-listed computed style information"*, with `includeDOMRects` for *"offset, scroll, and client rectangles."* `DOMSnapshot` is debugger-allowlisted. — https://chromedevtools.github.io/devtools-protocol/tot/DOMSnapshot/
- **Implicit roles must be captured, not just explicit `role=`**: Playwright's role locator follows *"W3C specifications for ARIA role, ARIA attributes and accessible name"* and *"many html elements like `<button>` have an implicitly defined role that is recognized by the role locator."* — https://playwright.dev/docs/locators

### 4. Mapping to Playwright locators at replay

- **Priority guidance**: *"Playwright comes with multiple built-in locators. To make tests resilient, we recommend prioritizing user-facing attributes and explicit contracts such as `page.getByRole()`."* And: *"We recommend prioritizing role locators to locate elements, as it is the closest way to how users and assistive technology perceive the page."* — `docs/src/locators.md`
- Test IDs are the most resilient but not user-facing: *"Testing by test ids is the most resilient way of testing as even if your text or role of the attribute changes, the test will still pass. … However testing by test ids is not user facing."*
- **CSS/XPath, explicit**: *"XPath and CSS selectors can be tied to the DOM structure or implementation. These selectors can break when the DOM structure changes."* Long chains are *"an example of a **bad practice** that leads to unstable tests."* — `docs/src/locators.md`
- Note a divergence to be aware of: the docs' *prose* list order is `getByRole, getByText, getByLabel, getByPlaceholder, getByAltText, getByTitle, getByTestId`, while the codegen *score table* puts testId first and placeholder/label ahead of text. The score table is the implemented behavior; the prose list is presentation order. Follow the score table.
- **API surface**, all `getBy*` added in **v1.27**: `getByRole` (options `name`, `exact`, plus `checked, disabled, expanded, includeHidden, level, pressed, selected`), `getByText`, `getByLabel`, `getByPlaceholder`, `getByAltText`, `getByTitle`, `getByTestId`; `page.locator(selector)` for CSS/XPath with auto-detection.
- `getByRole` `name`: *"By default, matching is case-insensitive and searches for a substring, use `exact` to control this behavior."* Text matching *"always normalizes whitespace, even with exact match"* — multiple spaces collapse, line breaks become spaces, leading/trailing trimmed.
- Test-id attribute is configurable: `selectors.setTestIdAttribute(name)` (v1.27), or `use: {testIdAttribute: 'data-pw'}`; *"To match elements with any of several attributes, pass them as a comma-separated list, e.g. `\"data-pw,data-ti\"`."*
- **`locator.or()` (v1.33) is the wrong tool for ranked fallback**: *"Creates a locator matching all elements that match one or both of the two locators"*, with the caveat *"when both locators match something, the resulting locator will have multiple matches, potentially causing a locator strictness violation."* Docs pair it with `first()` for disambiguation — which defeats the ranking. Also available: `locator.and()` (v1.34), `locator.filter()` (v1.22), and a CSS-only comma list (`'button:has-text("Log in"), button:has-text("Sign in")'`).
- **Strict mode**: *"Locators are strict. This means that all operations on locators that imply some target DOM element will throw an exception if more than one element matches."* Opting out via `first()/last()/nth()` is *"**not recommended** because when your page changes, Playwright may click on an element you did not intend"* — and specifically: *"the page might change, and the locator will point to a completely different element from the one you expected."* Frame locators are strict too. **This is why a stale ambiguous selector should be rejected and the next candidate tried, rather than resolved with `.first()`.**
- **Actionability** before every action: **Visible** (non-empty bounding box, no `visibility:hidden`), **Stable** (*"same bounding box for at least two consecutive animation frames"*), **Enabled**, **Receives Events** (element is the hit target at the action point), **Editable**. click/dblclick/tap/check require visible+stable+enabled+receives-events; fill/clear require visible+enabled+editable; focus/press/setInputFiles/blur perform none. *"If the required checks do not pass within the given `timeout`, action fails with the `TimeoutError`."* — https://playwright.dev/docs/actionability
- **Timeout trap**: the **JS** binding defaults action timeout to `0` — *"no timeout"*; **Python/Java/.NET** default to `30000`. Our workers are Python, so 30s applies, but set it explicitly rather than inheriting.
- **Shadow DOM**: *"All locators in Playwright by default work with elements in Shadow DOM. The exceptions are: Locating by XPath does not pierce shadow roots. Closed-mode shadow roots are not supported."* (There is no `:has-text` exception in current docs — `:has-text()` is a Playwright CSS pseudo-class and CSS pierces open shadow DOM.) **Consequence: an XPath-only capture is not durable across shadow boundaries; and closed shadow roots are unreachable at replay regardless of what we capture.**
- **Frames**: `page.frameLocator()` / `locator.frameLocator()` (v1.17), `locator.contentFrame()` and `frameLocator.owner()` (v1.43). *"Page-level interactions (like `click`) are assumed to operate in the main frame"* — frames must be addressed explicitly.

---

## Unresolved

- **The UX cost of the `debugger` permission.** Chrome shows a persistent infobar while `chrome.debugger` is attached, and the permission is prominent at install. I did not verify the exact current banner text/behavior in MV3, nor whether it can be suppressed for an extension the user installed deliberately. This is the main counter-pressure against the role+name capture path and should be checked directly (it is a concrete, cheap thing to test in the recording-extension prototype, `zm0rfq`).
- **Whether `Accessibility` domain CDP calls are fast enough to run per-event during recording.** DevTools Recorder does it, but under a developer's tolerance for latency, not an end user's. `getPartialAXTree` on the target node should be cheap, but no primary source gives numbers. Prototype question.
- **How well semantic locators (role+name, test-id, label) actually survive real page change.** The two papers measured XPath generators only, on 2015-era apps. No study evaluates Playwright-era locators. We are extrapolating from Playwright's design rationale, not from measurement — and no one has published the measurement.
- **Whether ordered fallback or weighted voting is right for us.** The papers show voting beats the best single strategy by 29.5%, but they measured voting across *five XPath generators*, all fallible in similar ways. With a test-id or role+name locator at the top of the list, a first-match-wins ordering may already capture most of the benefit, and voting introduces the documented failure mode where broken locators converge and out-vote correct ones. Not resolvable from sources; needs run data.
- **Closed shadow roots and cross-origin iframes.** Playwright states closed shadow roots are unsupported; I did not chase what fraction of real sites this affects, or whether the recorder can detect and warn at record time.

---

## Sources

**Source code**
- `puppeteer/replay` — `src/Schema.ts`, `src/PuppeteerRunnerExtension.ts` (v4.0.2)
- `ChromeDevTools/devtools-frontend` — `front_end/panels/recorder/injected/SelectorComputer.ts`, `.../selectors/ARIASelector.ts`, `.../selectors/CSSSelector.ts`, `front_end/panels/recorder/models/RecordingSession.ts` (main @ 2026-08-08)
- `microsoft/playwright` — `packages/injected/src/selectorGenerator.ts`, `packages/isomorphic/codegen/actions.d.ts`, `packages/isomorphic/locatorGenerators.ts`, `packages/playwright-core/types/types.d.ts`, `docs/src/locators.md`, `docs/src/api/*.md` (v1.62.1 / main)
- `rrweb-io/rrweb` — `packages/rrweb-snapshot/src/snapshot.ts`, `.../utils.ts`, `packages/rrweb/src/record/observer.ts`, `packages/rrweb/src/replay/index.ts`, `packages/types/src/index.ts` (master)
- `SeleniumHQ/selenium-ide` @ `5d595cd` — `.../preload/locator-builders.ts`, `packages/side-runtime/src/webdriver.ts`, `packages/side-model/src/types.ts`, `packages/side-runtime/src/__tests__/integration/playback-webdriver.spec.ts`
- `healenium/healenium-web` @ `c1e4f83` — `service/NodeService.java`, `service/HealingService.java`; `com.epam.healenium:tree-comparing` v0.4.14 sources jar — `LCSPathDistance.java`, `PathFinder.java`, `HeuristicNodeDistance.java`

**Specifications**
- W3C Accessible Name and Description Computation (accname) — https://w3c.github.io/accname/ (ED, 29 May 2026)
- W3C WebDriver — https://w3c.github.io/webdriver/#get-computed-role
- WICG Accessibility Object Model support table — https://wicg.github.io/aom/caniuse.html
- Chrome DevTools Protocol (tip-of-tree) — `Accessibility` and `DOMSnapshot` domains

**Official documentation**
- https://developer.chrome.com/docs/devtools/recorder/reference
- https://developer.chrome.com/docs/devtools/console/utilities
- https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
- https://developer.chrome.com/docs/extensions/reference/api/debugger
- https://playwright.dev/docs/locators, /codegen, /best-practices, /actionability, /frames, /test-timeouts, /api/class-locator, /api/class-framelocator, /api/class-selectors
- https://www.selenium.dev/documentation/legacy/selenium_ide/
- https://healenium.io/docs/how_healenium_works, /docs/download_and_install/hlm_web
- https://docs.tricentis.com/testim (Smart Locators; locators-auto-improve)
- https://help.mabl.com/hc/en-us/articles/19078583792404-How-auto-heal-works
- https://docs.katalon.com/katalon-studio/maintain-tests/self-healing-tests-in-katalon-studio
- https://ui.vision/rpa/docs/selenium-ide/locators
- https://axiom.ai/docs/no-code-tool/the-builder/selector-tool/, /docs/reference/steps/click-element
- https://app.browserflow.io/docs (no relevant content; recorder docs unreachable)

**Peer-reviewed**
- Leotta, Stocco, Ricca, Tonella. "ROBULA+: an algorithm for generating robust XPath locators for web testing." *JSEP* 28(3):177–204, 2016. DOI 10.1002/smr.1771
- Leotta, Stocco, Ricca, Tonella. "Using Multi-Locators to Increase the Robustness of Web Test Cases." *Proc. 8th IEEE ICST*, 2015, pp. 1–10. DOI 10.1109/ICST.2015.7102611
