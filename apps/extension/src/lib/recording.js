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
  const byStep = new Map(bindings.map((binding) => [binding.stepId, binding]));
  const declared = new Map(variables.map((variable) => [variable.name, variable]));
  const boundVariables = new Map();

  const bound = steps.map((step) => {
    if (step.needsSecret !== true) return step;
    const binding = byStep.get(step.id);
    const name = binding?.name?.trim();
    if (!name) throw new Error("Bind every password Step before saving.");
    if (!VARIABLE_NAME.test(name)) throw new Error("Choose a valid Variable name.");
    if (
      typeof binding.secret?.id !== "string" ||
      binding.secret.id === "" ||
      typeof binding.secret?.name !== "string" ||
      binding.secret.name === ""
    ) {
      throw new Error("Choose or create a Secret for every password Step.");
    }
    const existing = declared.get(name);
    if (existing && existing.secret !== true) {
      throw new Error("A password Step needs a secret Variable.");
    }
    const variable = {
      ...(existing ?? { name }),
      secret: true,
      secretId: binding.secret.id,
      secretName: binding.secret.name,
    };
    const previous = boundVariables.get(name);
    if (previous && previous.secretId !== variable.secretId) {
      throw new Error("One secret Variable cannot use two Secrets.");
    }
    declared.set(name, variable);
    boundVariables.set(name, variable);
    const { needsSecret: _marker, ...ordinary } = step;
    return { ...ordinary, payload: { ...ordinary.payload, value: `{{${name}}}` } };
  });

  const existingNames = new Set(variables.map((variable) => variable.name));
  return {
    steps: bound,
    variables: [
      ...variables.map((variable) => declared.get(variable.name)),
      ...[...boundVariables.values()].filter((variable) => !existingNames.has(variable.name)),
    ],
  };
}

/**
 * The pending recording the app handed over, or null when the shape is wrong.
 *
 * Record and Re-pick share the handshake. Re-pick is scoped to one Step and
 * carries no Variables: the editor already has the Draft, and this session
 * will only replace that Step's candidates.
 */
export function readPendingRecording(message) {
  if (
    typeof message?.sessionId !== "string" ||
    typeof message?.token !== "string" ||
    typeof message?.backendOrigin !== "string" ||
    typeof message?.workflowId !== "string" ||
    typeof message?.workflowName !== "string"
  ) {
    return null;
  }
  if (message.mode === "record") {
    if (!Array.isArray(message.variables) || !Array.isArray(message.secrets)) return null;
    return {
      mode: "record",
      sessionId: message.sessionId,
      token: message.token,
      backendOrigin: message.backendOrigin,
      workflowId: message.workflowId,
      workflowName: message.workflowName,
      variables: message.variables,
      secrets: message.secrets,
    };
  }
  if (message.mode === "repick") {
    if (typeof message.stepId !== "string" || message.stepId === "") return null;
    return {
      mode: "repick",
      sessionId: message.sessionId,
      token: message.token,
      backendOrigin: message.backendOrigin,
      workflowId: message.workflowId,
      workflowName: message.workflowName,
      stepId: message.stepId,
    };
  }
  return null;
}
