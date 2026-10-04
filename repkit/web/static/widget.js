/* repkit embed script.

   Add the chat to any page:

     <script src="https://chat.example.com/widget.js" defer></script>

   It adds a launcher button and, when opened, an iframe holding the chat panel.
   The iframe keeps the panel's styles and scripts apart from the host page.

   Optional attributes on the script tag:
     data-repkit-server="https://chat.example.com"   server origin, if not the script's own
     data-repkit-open="true"                          open the panel on load
     data-repkit-pacing="off"                         show replies without typing delays

   The page can drive it through window.repkit: open(), close(), send(text), reset().
   It fires "repkit:ready", "repkit:turn" and "repkit:reset" events on window. */

(() => {
  "use strict";

  const script = document.currentScript;
  const options = script ? script.dataset : {};
  const server = (options.repkitServer || (script ? new URL(script.src).origin : location.origin))
    .replace(/\/$/, "");

  const CHAT_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/></svg>';

  const STYLES = `
    :host {
      all: initial;
      position: fixed;
      right: max(16px, env(safe-area-inset-right, 0px));
      bottom: max(16px, env(safe-area-inset-bottom, 0px));
      z-index: 2147483000;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }
    :host([data-position="left"]) { right: auto; left: max(16px, env(safe-area-inset-left, 0px)); }
    [hidden] { display: none !important; }
    .launcher {
      display: flex; align-items: center; gap: 8px; margin-left: auto;
      padding: 11px 16px; border: 0; border-radius: 999px;
      background: var(--accent); color: var(--on-accent);
      font: 600 14.5px/1.2 inherit; font-family: inherit; cursor: pointer;
      box-shadow: 0 12px 32px rgba(15, 15, 20, 0.22);
    }
    :host([data-position="left"]) .launcher { margin-left: 0; }
    :host([data-corners="sharp"]) .launcher { border-radius: 4px; }
    .launcher:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
    .launcher svg { width: 18px; height: 18px; flex: none; }
    .frame {
      display: block;
      width: min(400px, calc(100vw - 32px));
      height: min(640px, calc(100vh - 32px));
      border: 1px solid rgba(120, 120, 130, 0.28);
      border-radius: 16px;
      background: Canvas;
      box-shadow: 0 16px 44px rgba(15, 15, 20, 0.22), 0 2px 6px rgba(15, 15, 20, 0.08);
    }
    :host([data-corners="sharp"]) .frame { border-radius: 4px; }
    :host([data-corners="round"]) .frame { border-radius: 26px; }
    @media (max-width: 480px) {
      :host(.open) { inset: 0; }
      :host(.open) .frame { width: 100%; height: 100%; border: 0; border-radius: 0; }
    }
  `;

  const state = { open: false, ready: false, queue: [] };
  const ui = {};

  /* Black or white, whichever reads better on the pack's accent colour. */
  function inkFor(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const linear = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    const luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
    return luminance > 0.4 ? "#18181b" : "#ffffff";
  }

  function post(message) {
    if (!state.ready) {
      state.queue.push(message);
      return;
    }
    ui.frame.contentWindow.postMessage({ source: "repkit-host", ...message }, server);
  }

  /* The panel is only loaded once someone opens it, so it costs the page nothing until then. */
  function ensureFrame() {
    if (ui.frame) return;
    const frame = document.createElement("iframe");
    frame.className = "frame";
    frame.title = ui.label;
    frame.src = `${server}/chat${options.repkitPacing === "off" ? "?nopacing" : ""}`;
    ui.frame = frame;
    ui.root.append(frame);
  }

  function open() {
    if (state.open || !ui.host) return;
    state.open = true;
    ensureFrame();
    ui.host.classList.add("open");
    ui.launcher.hidden = true;
    ui.frame.hidden = false;
    ui.launcher.setAttribute("aria-expanded", "true");
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    ui.host.classList.remove("open");
    ui.frame.hidden = true;
    ui.launcher.hidden = false;
    ui.launcher.setAttribute("aria-expanded", "false");
    ui.launcher.focus({ preventScroll: true });
  }

  function onPanelMessage(event) {
    if (!ui.frame || event.source !== ui.frame.contentWindow) return;
    if (event.origin !== server || !event.data || event.data.source !== "repkit") return;
    const { type, detail } = event.data;
    if (type === "close") close();
    if (type === "ready") {
      state.ready = true;
      for (const message of state.queue.splice(0)) post(message);
    }
    if (type === "ready" || type === "turn" || type === "reset") {
      window.dispatchEvent(new CustomEvent(`repkit:${type}`, { detail }));
    }
  }

  function build(config) {
    const { rep, widget } = config;
    const host = document.createElement("div");
    host.id = "repkit-widget";
    host.dataset.position = widget.position;
    host.dataset.corners = widget.corners;
    host.style.setProperty("--accent", widget.accent);
    host.style.setProperty("--on-accent", inkFor(widget.accent));
    const root = host.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = STYLES;

    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.className = "launcher";
    launcher.innerHTML = CHAT_ICON;
    const label = document.createElement("span");
    label.textContent = widget.launcher_label;
    launcher.append(label);
    launcher.setAttribute("aria-expanded", "false");
    launcher.addEventListener("click", open);

    root.append(style, launcher);
    Object.assign(ui, { host, root, launcher, label: `Chat with ${rep.name} at ${rep.company}` });
    document.body.append(host);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.open) close();
    });
  }

  async function init() {
    let config;
    try {
      const response = await fetch(`${server}/api/config`);
      if (!response.ok) throw new Error(String(response.status));
      config = await response.json();
    } catch {
      // No chat is better than a broken launcher on someone's shop.
      console.warn("repkit: could not load the chat configuration from", server);
      return;
    }
    build(config);
    window.addEventListener("message", onPanelMessage);
    window.repkit = {
      open,
      close,
      send: (text) => (open(), post({ type: "send", text: String(text) })),
      reset: () => post({ type: "reset" }),
    };
    if (options.repkitOpen === "true") open();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
