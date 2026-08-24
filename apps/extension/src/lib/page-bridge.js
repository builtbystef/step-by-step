/**
 * The content script, as a function the service worker injects.
 *
 * It is a function rather than a file because a content script cannot import a
 * module, and the protocol's names would otherwise be written twice — once
 * here and once in `handshake.js` — with nothing to keep them the same. The
 * service worker hands them over in `protocol` instead, and Chrome injects
 * this function's own source into the page's isolated world.
 *
 * Everything it accepts is checked before it is forwarded, which is the first
 * of the two gates the connect handshake passes: this one knows where the
 * message came from, and the service worker knows what was asked for. Nothing
 * here decides anything — a page could say all of this and be lying, and the
 * nonce it cannot know is what the worker holds it to.
 */
export function pageBridge(protocol) {
  const own = window.location.origin;

  // The worker injects on every load of the connected tab, and a page that
  // reloads itself would otherwise collect a listener per load.
  if (window.stepByStepBridge === protocol.version) {
    return;
  }
  window.stepByStepBridge = protocol.version;

  window.addEventListener("message", (event) => {
    // Not from this document's own window — a frame, an opener, or another
    // tab — and so not the connect page this attempt opened.
    if (event.source !== window || event.origin !== own) {
      return;
    }
    const message = event.data;
    if (typeof message !== "object" || message === null) {
      return;
    }
    if (message.channel !== protocol.channel) {
      return;
    }
    if (message.type === protocol.probe) {
      chrome.runtime
        .sendMessage({ channel: protocol.channel, type: protocol.probe, instanceOrigin: own })
        .then((reply) => {
          if (reply && reply.connected === true) {
            window.postMessage(
              { channel: protocol.channel, type: protocol.ready, version: reply.version },
              own,
            );
          }
        })
        .catch(() => {
          // A stopped or updating worker is silence, which is exactly what the
          // page's bounded probe knows how to interpret.
        });
      return;
    }
    if (message.type !== protocol.handshake) {
      return;
    }
    if (typeof message.nonce !== "string" || message.instanceOrigin !== own) {
      return;
    }

    chrome.runtime
      .sendMessage({
        channel: protocol.channel,
        type: protocol.handshake,
        nonce: message.nonce,
        instanceOrigin: own,
      })
      .then((reply) => {
        if (reply && reply.accepted === true) {
          window.postMessage(
            { channel: protocol.channel, type: protocol.accepted, version: protocol.version },
            own,
          );
        }
      })
      .catch(() => {
        // The worker was restarting, or the popup closed the attempt. The page
        // announces itself again, so nothing here has to retry.
      });
  });

  // The page is already loaded by the time this arrives, so it is told rather
  // than asked: whatever it posted before this listener existed was missed.
  window.postMessage(
    { channel: protocol.channel, type: protocol.ready, version: protocol.version },
    own,
  );
}
