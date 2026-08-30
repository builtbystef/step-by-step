export type ReconcileVariable = {
  name: string;
  secret?: boolean;
};

export type MappingEntry = {
  variableName: string;
  header: string | null;
  suggested: boolean;
};

export type ReconcileResult = {
  confident: boolean;
  mapping: MappingEntry[];
  ignoredHeaders: string[];
  droppedSecretHeaders: string[];
};

export function normalize(value: string): string {
  return value.toLowerCase().replaceAll(/[^a-z0-9]/g, "");
}

export function reconcile(
  headers: readonly string[],
  variables: readonly ReconcileVariable[],
): ReconcileResult {
  const secrets = variables.filter((variable) => variable.secret === true);
  const plain = variables.filter((variable) => variable.secret !== true);
  const secretNormalized = new Set(secrets.map((variable) => normalize(variable.name)));

  const droppedSecretHeaders: string[] = [];
  const usable: string[] = [];
  for (const header of headers) {
    if (secretNormalized.has(normalize(header))) {
      droppedSecretHeaders.push(header);
    } else {
      usable.push(header);
    }
  }

  const exactByVariable = new Map<string, string[]>();
  for (const variable of plain) {
    exactByVariable.set(variable.name, []);
  }
  const exactByHeader = new Map<string, string[]>();
  for (const header of usable) {
    const key = normalize(header);
    const claimed: string[] = [];
    for (const variable of plain) {
      if (normalize(variable.name) === key) {
        claimed.push(variable.name);
        exactByVariable.get(variable.name)?.push(header);
      }
    }
    exactByHeader.set(header, claimed);
  }

  const uniqueExact = new Map<string, string>();
  let headerClaimsTwo = false;
  for (const header of usable) {
    const claimed = exactByHeader.get(header) ?? [];
    if (claimed.length > 1) {
      headerClaimsTwo = true;
    }
  }
  for (const variable of plain) {
    const matches = exactByVariable.get(variable.name) ?? [];
    if (matches.length !== 1) {
      continue;
    }
    const header = matches[0]!;
    if ((exactByHeader.get(header) ?? []).length === 1) {
      uniqueExact.set(variable.name, header);
    }
  }

  const everyCovered = plain.every((variable) => uniqueExact.has(variable.name));
  const confident = everyCovered && !headerClaimsTwo;

  const mapping: MappingEntry[] = plain.map((variable) => {
    const header = uniqueExact.get(variable.name);
    if (header !== undefined) {
      return { variableName: variable.name, header, suggested: false };
    }
    return { variableName: variable.name, header: null, suggested: false };
  });

  if (!confident) {
    const takenHeaders = new Set(uniqueExact.values());
    const remainingHeaders = usable.filter((header) => !takenHeaders.has(header));
    const unmatched = plain.filter((variable) => !uniqueExact.has(variable.name));

    const candidates = new Map<string, string[]>();
    for (const variable of unmatched) {
      const near = remainingHeaders.filter((header) =>
        isNearMatch(normalize(header), normalize(variable.name)),
      );
      candidates.set(variable.name, near);
    }

    const headerClaimCount = new Map<string, number>();
    for (const near of candidates.values()) {
      for (const header of near) {
        headerClaimCount.set(header, (headerClaimCount.get(header) ?? 0) + 1);
      }
    }

    for (const entry of mapping) {
      if (entry.header !== null) {
        continue;
      }
      const near = candidates.get(entry.variableName) ?? [];
      const unique = near.filter((header) => (headerClaimCount.get(header) ?? 0) === 1);
      if (unique.length === 1) {
        entry.header = unique[0]!;
        entry.suggested = true;
      }
    }
  }

  const assigned = new Set(
    mapping.map((entry) => entry.header).filter((header): header is string => header !== null),
  );
  const ignoredHeaders = usable.filter((header) => !assigned.has(header));

  return { confident, mapping, ignoredHeaders, droppedSecretHeaders };
}

function isNearMatch(left: string, right: string): boolean {
  if (left === "" || right === "") {
    return false;
  }
  if (left === right) {
    return true;
  }
  if (left.includes(right) || right.includes(left)) {
    return true;
  }
  return levenshtein(left, right) <= 2;
}

function levenshtein(left: string, right: string): number {
  if (left === right) {
    return 0;
  }
  if (left.length === 0) {
    return right.length;
  }
  if (right.length === 0) {
    return left.length;
  }
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let i = 0; i < left.length; i += 1) {
    let corner = i;
    previous[0] = i + 1;
    for (let j = 0; j < right.length; j += 1) {
      const nextCorner = previous[j + 1]!;
      const substitution = left[i] === right[j] ? 0 : 1;
      previous[j + 1] = Math.min(previous[j]! + 1, previous[j + 1]! + 1, corner + substitution);
      corner = nextCorner;
    }
  }
  return previous[right.length]!;
}
