/**
 * The address a person types in the popup, read as the one thing the rest of
 * the extension works in: an origin.
 *
 * An origin is what a permission is granted for, what a content script may be
 * injected into, and what the service worker may fetch. Two spellings of one
 * instance must therefore not become two connections, and anything that is not
 * a web address must not become a permission request at all.
 */

const WEB_SCHEMES = new Set(["http:", "https:"]);

/**
 * `{origin}` for an address this extension can connect to, `{problem}` for one
 * it cannot.
 *
 * A verdict rather than an exception, because every outcome here is something
 * the popup says to the person who typed it, not a failure of the extension.
 *
 * An address with no scheme is read as https. A self-hoster types
 * `steps.example.com`, and guessing the scheme the public web uses is better
 * than refusing what they meant — while `http://localhost:3000` is kept as
 * typed, because an instance on a private network is a real instance.
 */
export function readInstanceUrl(typed) {
  const text = typed.trim();
  if (text === "") {
    return { problem: "empty" };
  }

  if (schemeWithoutAnAuthority(text)) {
    return { problem: "unsupported-scheme" };
  }

  const parsed = parse(namesAScheme(text) ? text : `https://${text}`);
  if (parsed === null) {
    return { problem: "malformed" };
  }
  if (!WEB_SCHEMES.has(parsed.protocol)) {
    return { problem: "unsupported-scheme" };
  }
  return { origin: parsed.origin };
}

/** The match pattern that asks for one origin, whole, and nothing beside it. */
export function originPattern(origin) {
  return `${origin}/*`;
}

/**
 * Whether the text already names a scheme, as opposed to beginning with a host.
 *
 * The authority's `//` is the test, because `steps.example.com:8443` names a
 * scheme to a URL parser — `steps.example.com` — and means a port to the person
 * who typed it.
 */
function namesAScheme(text) {
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(text);
}

/**
 * Whether the text is a `javascript:` or `mailto:` sort of URL: a scheme, and
 * then something that is not a host at all.
 *
 * A colon followed by digits is a port on a host that was typed without a
 * scheme, and that is the one case this must not claim.
 */
function schemeWithoutAnAuthority(text) {
  return !namesAScheme(text) && /^[a-z][a-z0-9+.-]*:(?!\d)/i.test(text);
}

function parse(text) {
  try {
    return new URL(text);
  } catch {
    return null;
  }
}
