const VARIABLE_NAME = /^[A-Za-z_][A-Za-z0-9_-]*$/;

/** The explicit choices shown at save; no browser-state guess preselects one. */
export function captureChoices(options) {
  return options.map((option) => ({
    domain: option.domain,
    checked: false,
    scope: "organization",
    organizationSavedAt: option.organization_saved_at,
    personalSavedAt: option.personal_saved_at,
  }));
}

/** The destination-specific replacement sentence beneath a checked row. */
export function replacementHint(choice, scope, locale) {
  const personal = scope === "personal";
  const timestamp = personal ? choice.personalSavedAt : choice.organizationSavedAt;
  if (timestamp === null || timestamp === undefined) return "";
  const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(
    new Date(timestamp),
  );
  return personal ? `replaces your login saved on ${date}` : `replaces the login saved on ${date}`;
}

/** Turn password markers into ordinary type Steps before they reach finalize. */
export function bindSecretSteps(steps, bindings, variables) {
  const byStep = new Map(bindings.map((binding) => [binding.stepId, binding.name.trim()]));
  const declared = new Map(variables.map((variable) => [variable.name, variable]));
  const added = [];

  const bound = steps.map((step) => {
    if (step.needsSecret !== true) return step;
    const name = byStep.get(step.id);
    if (!name) throw new Error("Bind every password Step before saving.");
    if (!VARIABLE_NAME.test(name)) throw new Error("Choose a valid Variable name.");
    const existing = declared.get(name);
    if (existing && existing.secret !== true) {
      throw new Error("A password Step needs a secret Variable.");
    }
    if (!existing) {
      const variable = { name, secret: true };
      declared.set(name, variable);
      added.push(variable);
    }
    const { needsSecret: _marker, ...ordinary } = step;
    return { ...ordinary, payload: { ...ordinary.payload, value: `{{${name}}}` } };
  });

  return { steps: bound, variables: [...variables, ...added] };
}
