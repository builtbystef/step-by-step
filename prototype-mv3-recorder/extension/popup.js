// PROTOTYPE — disposable.
const $ = (id) => document.getElementById(id);

async function refresh() {
  const status = await chrome.runtime.sendMessage({ cmd: "status" }).catch(() => null);
  const { recording } = await chrome.storage.local.get("recording");
  $("status").textContent = status?.active
    ? `RECORDING — ${status.steps} steps`
    : recording
      ? `stopped — ${recording.steps.length} steps captured`
      : "idle";
  if (recording) $("json").value = JSON.stringify(recording, null, 2);
}

$("start").addEventListener("click", async () => {
  const res = await chrome.runtime.sendMessage({ cmd: "start" });
  if (!res.ok) $("status").textContent = `start failed: ${res.error}`;
  else refresh();
});

$("stop").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ cmd: "stop" });
  refresh();
});

$("download").addEventListener("click", async () => {
  const { recording } = await chrome.storage.local.get("recording");
  if (!recording) return;
  const url =
    "data:application/json;base64," +
    btoa(unescape(encodeURIComponent(JSON.stringify(recording, null, 2))));
  chrome.downloads.download({ url, filename: "proto-recording.json", conflictAction: "overwrite" });
});

refresh();
setInterval(refresh, 700);
