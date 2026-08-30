const WEB_SCHEMES = new Set(["http:", "https:"]);

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

export function originPattern(origin) {
  return `${origin}/*`;
}

function namesAScheme(text) {
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(text);
}

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
