export function pageBridge(protocol) {
  const own = window.location.origin;

  if (window.stepByStepBridge === protocol.version) {
    return;
  }
  window.stepByStepBridge = protocol.version;

  window.addEventListener("message", (event) => {
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
        .catch(() => {});
      return;
    }
    if (
      message.type !== protocol.handshake &&
      message.type !== protocol.recordingPending &&
      message.type !== protocol.recordingToken
    ) {
      return;
    }
    if (message.type === protocol.handshake) {
      if (typeof message.nonce !== "string" || message.instanceOrigin !== own) return;
    } else if (message.backendOrigin !== undefined && message.backendOrigin !== own) {
      return;
    }

    chrome.runtime
      .sendMessage(
        message.type === protocol.handshake
          ? {
              channel: protocol.channel,
              type: protocol.handshake,
              nonce: message.nonce,
              instanceOrigin: own,
            }
          : message,
      )
      .then((reply) => {
        if (reply && reply.accepted === true) {
          window.postMessage(
            {
              channel: protocol.channel,
              type: reply.type ?? protocol.accepted,
              version: protocol.version,
              ...(typeof reply.sessionId === "string" ? { sessionId: reply.sessionId } : {}),
            },
            own,
          );
        }
      })
      .catch(() => {});
  });

  if (protocol.recordingStatus) {
    chrome.runtime
      .sendMessage({ channel: protocol.channel, type: protocol.recordingStatus })
      .then((reply) => {
        if (reply?.type === protocol.recordingTokenExpired) {
          window.postMessage(
            {
              channel: protocol.channel,
              type: reply.type,
              version: protocol.version,
              sessionId: reply.sessionId,
            },
            own,
          );
        }
      })
      .catch(() => {});
  }

  chrome.runtime.onMessage?.addListener((message) => {
    if (
      message?.type === protocol.recordingTokenExpired ||
      message?.type === protocol.recordingFinished ||
      message?.type === protocol.repickCandidates
    ) {
      window.postMessage(
        {
          channel: protocol.channel,
          type: message.type,
          version: protocol.version,
          sessionId: message.sessionId,
          ...(typeof message.stepId === "string" ? { stepId: message.stepId } : {}),
          ...(Array.isArray(message.candidates) ? { candidates: message.candidates } : {}),
        },
        own,
      );
    }
  });

  window.postMessage(
    { channel: protocol.channel, type: protocol.ready, version: protocol.version },
    own,
  );
}
