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
A named, editable sequence of Steps that a user records in the browser and owns. The unit that is edited, scheduled, and run.
_Avoid_: recording, automation, script

**Step**:
One semantic action inside a Workflow. The v1 step types: navigate, click, type, select, download, extract, wait, pause-for-takeover.
_Avoid_: action, event, command

**Run**:
One execution of a Workflow, with its own status and artifacts.
_Avoid_: execution, job

**Variable**:
A named input that a Workflow declares, either plain or secret. Step values reference Variables by name; the values arrive per Run. A secret Variable is stored encrypted and never travels in a Batch's rows.
_Avoid_: parameter, placeholder

**Batch**:
One Workflow plus a list of input rows, where each row supplies the Workflow's Variables and produces one Run. The Runs execute sequentially.
_Avoid_: bulk run, campaign

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

**Artifact**:
A file that a Run produces: a screenshot, a download, or a trace.
_Avoid_: attachment, output file
