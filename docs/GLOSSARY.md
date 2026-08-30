# Glossary

The project's shared language. The rules: use one term for each concept — the rejected synonyms go under _Avoid_. A definition is one or two sentences that say what the term IS, not what it does. Only terms specific to this project belong here — general concepts from programming do not. No implementation details. Group the terms under subheadings when clusters appear.

The entry format:

```
**{{Term}}**:
{{Definition.}}
_Avoid_: {{rejected synonyms}}
```

## Language

**Workflow**:
A named, editable sequence of Steps recorded in the browser, belonging to one Organization. The unit that is edited, scheduled, and run.
_Avoid_: recording, automation, script

**Step**:
One semantic action inside a Workflow. The v1 step types: navigate, click, type, select, download, extract, wait, pause-for-takeover.
_Avoid_: action, event, command

**Run**:
One execution of a Workflow, with its own status and artifacts. Status moves queued → running ⇄ waiting_for_human, then to one of succeeded, failed, or cancelled.
_Avoid_: execution, job

**Failure Reason**:
The closed set of why a failed Run ended: `step_failed`, `auth_challenge`, `takeover_timeout`, `takeover_abandoned`, `run_timeout`, `worker_lost`, `missing_secret`, or `startup_failed`.
_Avoid_: error code, exception, crash reason

**Variable**:
A named input that a Workflow declares, either plain or secret. Step values reference Variables by name; a secret Variable binds to a Secret by id with the name cached for display, and its value never travels in a Batch's rows.
_Avoid_: parameter, placeholder

**Batch**:
One Workflow plus a list of input rows. Its rows run in order, one at a time.
_Avoid_: bulk run, campaign

**Batch Row**:
One set of non-secret Variable values inside a Batch. It may have more than one Run when a user re-runs it.
_Avoid_: input, record, item

**Draft**:
The single mutable copy of a Workflow's Steps that the recorder and editor modify. Publishing it produces a Version.
_Avoid_: working copy, unsaved version

**Version**:
An immutable, numbered copy of a Workflow's Steps, created by publishing the Draft. Runs, Schedules, and Batches execute Versions.
_Avoid_: revision, snapshot, release

**Step Result**:
The record of one Step's execution inside one Run: status, timing, the selector that matched, error, Artifacts, and any extracted value.
_Avoid_: step run, step log

**Schedule**:
A cron-based trigger owned by a Workflow that launches Runs of its latest published Version.
_Avoid_: cron job, timer

**Occurrence**:
One moment at which a Schedule was due, whether or not a Run resulted. An Occurrence that produced no Run is a hole in the Schedule's history, and it carries the reason.
_Avoid_: tick, firing, scheduled event

**Artifact**:
A file that a Run produces: a screenshot, a download, or a trace.
_Avoid_: attachment, output file

**Secret**:
A named, encrypted value in an Organization's vault, on which a member may keep a Personal Override. A Workflow's secret Variable binds to a Secret by id, and the value itself never appears in step payloads, logs, or Artifacts.
_Avoid_: credential, vault entry

**Auth State**:
Saved signed-in browser state (cookies and web storage) for one site in an Organization's vault, captured with consent from the extension or written back by a Worker, and subject to Personal Overrides. A Run's browser receives the applicable Auth State for the sites it touches before it starts.
_Avoid_: session state, storage state, login blob

**Personal Override**:
A member's own value for an Organization's Secret, or their own saved login for a domain (with or without a shared record for it), resolved ahead of the Organization's values for Runs that member starts; Scheduled and Batch Runs never use them.
_Avoid_: personal secret, private copy

**Organization**:
The tenant. Every Workflow, Run, Batch, Schedule, Secret, and Auth State belongs to exactly one Organization, and users act inside one through a Membership.
_Avoid_: team, workspace, tenant, account

**Membership**:
The link between a user and one Organization, carrying a role — owner, admin, or member — that sets what the user may do there. An Organization has exactly one owner.
_Avoid_: seat, org user

**Invitation**:
An emailed offer to join an Organization with a given role. Accepting it — by signing in with the invited address — creates the Membership.
_Avoid_: invite link, provisioning

**Sign-in Code**:
A short-lived, single-use code emailed to an address; entering it proves control of the address and signs the user in. The only authentication method — there are no passwords.
_Avoid_: OTP, magic link, verification code

**Target**:
The description of the page element a Step should use, including an ordered list of Selector Candidates.
_Avoid_: element, locator, selector

**Selector Candidate**:
One ranked way to identify a Target on a page. A Target keeps several candidates so it can survive small page changes.
_Avoid_: selector, locator

**Selector Drift**:
The condition where a Step uses a lower-ranked Selector Candidate than the one recorded as best, showing that the page has changed under the Workflow.
_Avoid_: selector rot, degraded selector, healing signal

**Re-pick**:
The repair action for one Step's target: the user points at the intended element on the live page through the extension, and a fresh verified selector candidate list replaces the Step's old one in the Draft.
_Avoid_: re-record element, selector refresh, heal

**Worker**:
A long-lived process that executes at most one Run at a time, with an exclusive browser for that Run. The number of Workers is the instance's total Run concurrency.
_Avoid_: runner, executor, agent

**Auth Challenge**:
A page condition, such as a sign-in prompt, MFA request, or CAPTCHA, that requires human attention before safe automation can continue.
_Avoid_: login error, blocker

**Takeover**:
The interval where a human controls a paused Run's browser directly, while automation is suspended. It begins when the user takes control of a Run that is waiting for a human, and ends when control is handed back, the Run is abandoned, or the deadline passes.
_Avoid_: handoff, intervention, manual mode
