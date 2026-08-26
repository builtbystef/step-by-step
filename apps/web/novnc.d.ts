declare module "@novnc/novnc/lib/rfb" {
  export default class RFB {
    constructor(
      target: HTMLElement,
      urlOrChannel: string | WebSocket,
      options?: { shared?: boolean; wsProtocols?: string[] },
    );
    viewOnly: boolean;
    scaleViewport: boolean;
    clipViewport: boolean;
    focusOnClick: boolean;
    background: string;
    addEventListener(type: string, listener: (ev: Event) => void): void;
    removeEventListener(type: string, listener: (ev: Event) => void): void;
    disconnect(): void;
    focus(options?: FocusOptions): void;
  }
}
