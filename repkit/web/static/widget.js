/* repkit chat widget.

   Embed on any page:

     <script src="https://chat.example.com/widget.js" defer></script>

   Optional attributes on the script tag:
     data-repkit-server="https://chat.example.com"   API origin, if not the script's own
     data-repkit-open="true"                          open the panel on load
     data-repkit-pacing="off"                         show replies without typing delays

   The page can drive it through window.repkit: open(), close(), send(text), reset().
   After every turn it fires a "repkit:turn" event on window with the server's response. */

(() => {
  "use strict";

  const script = document.currentScript;
  const options = script ? script.dataset : {};
  const server = (options.repkitServer || (script ? new URL(script.src).origin : location.origin))
    .replace(/\/$/, "");
  const pacing = options.repkitPacing !== "off";
  const STORAGE_KEY = "repkit:conversation";

  const ICONS = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    restart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.6-5.9"/><path d="M4 4v5h5"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  };

  const state = { config: null, id: null, open: false, busy: false, started: false };
  const ui = {};

  // -- storage: per-tab, and optional. A private window may refuse it. ----

  function remembered() {
    try {
      return sessionStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function remember(id) {
    try {
      if (id) sessionStorage.setItem(STORAGE_KEY, id);
      else sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* the chat still works for this page view */
    }
  }

  // -- server --------------------------------------------------------------

  async function api(path, body) {
    const response = await fetch(server + path, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const error = new Error(`request failed with ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  async function startConversation() {
    const created = await api("/api/conversations", {});
    state.id = created.id;
    remember(created.id);
    return created;
  }

  /* Reuse this tab's conversation if the server still has it. */
  async function loadConversation() {
    const saved = remembered();
    if (saved) {
      try {
        const existing = await api(`/api/conversations/${encodeURIComponent(saved)}`);
        state.id = existing.id;
        return existing;
      } catch (error) {
        if (error.status !== 404) throw error;
      }
    }
    return startConversation();
  }

  // -- drawing -------------------------------------------------------------

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    // textContent only: nothing the customer or the model writes is parsed as HTML.
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function scrollToEnd() {
    ui.log.scrollTop = ui.log.scrollHeight;
  }

  function addMessage(speaker, text) {
    const bubble = el("div", `rk-msg rk-${speaker === "customer" ? "customer" : "rep"}`, text);
    ui.log.append(bubble);
    scrollToEnd();
    return bubble;
  }

  function addNote(text, action) {
    const note = el("div", "rk-note", text);
    if (action) {
      const button = el("button", "", action.label);
      button.type = "button";
      button.addEventListener("click", () => {
        note.remove();
        action.run();
      });
      note.append(" ", button);
    }
    ui.log.append(note);
    scrollToEnd();
    return note;
  }

  function showTyping(on) {
    if (on && !ui.typing.isConnected) ui.log.append(ui.typing);
    if (!on) ui.typing.remove();
    if (on) scrollToEnd();
  }

  function setBusy(busy) {
    state.busy = busy;
    ui.send.disabled = busy || !ui.input.value.trim();
  }

  function setHandedOff(handedOff) {
    ui.status.hidden = !handedOff;
  }

  function drawTranscript(conversation) {
    ui.log.replaceChildren();
    for (const message of conversation.transcript) addMessage(message.from, message.text);
    setHandedOff(conversation.handed_off);
    // Suggestions are openers: once the customer has spoken, they are in the way.
    const customerSpoke = conversation.transcript.some((m) => m.from === "customer");
    ui.suggestions.hidden = customerSpoke || !ui.suggestions.childElementCount;
  }

  const sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000));

  /* Show the reply one bubble at a time, as if it were being typed. */
  async function playBubbles(bubbles) {
    for (const bubble of bubbles) {
      if (pacing) {
        showTyping(true);
        await sleep(bubble.delay);
      }
      showTyping(false);
      addMessage("rep", bubble.text);
    }
  }

  // -- actions -------------------------------------------------------------

  async function ensureStarted() {
    if (state.started) return;
    state.started = true;
    try {
      drawTranscript(await loadConversation());
    } catch {
      state.started = false;
      ui.log.replaceChildren();
      addNote("Couldn't reach the chat.", { label: "Try again", run: ensureStarted });
    }
  }

  async function deliver(text, retried) {
    try {
      return await api(`/api/conversations/${encodeURIComponent(state.id)}/messages`, { text });
    } catch (error) {
      // The server forgot this conversation (restart or timeout): start a new one, once.
      if (error.status === 404 && !retried) {
        await startConversation();
        return deliver(text, true);
      }
      throw error;
    }
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text || state.busy) return;
    await ensureStarted();
    if (!state.id) return;

    setBusy(true);
    ui.suggestions.hidden = true;
    const bubble = addMessage("customer", text);
    showTyping(true);
    try {
      const response = await deliver(text, false);
      showTyping(false);
      await playBubbles(response.bubbles);
      setHandedOff(response.handed_off);
      window.dispatchEvent(new CustomEvent("repkit:turn", { detail: { text, response } }));
    } catch {
      showTyping(false);
      bubble.remove();
      addNote("That didn't send.", { label: "Try again", run: () => send(text) });
    } finally {
      setBusy(false);
      if (state.open) ui.input.focus({ preventScroll: true });
    }
  }

  function open() {
    if (state.open || !ui.host) return;
    state.open = true;
    ui.host.classList.add("rk-open");
    ui.launcher.hidden = true;
    ui.panel.hidden = false;
    ui.launcher.setAttribute("aria-expanded", "true");
    ensureStarted().then(scrollToEnd);
    // preventScroll: focusing the composer must not move the host page.
    ui.input.focus({ preventScroll: true });
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    ui.host.classList.remove("rk-open");
    ui.panel.hidden = true;
    ui.launcher.hidden = false;
    ui.launcher.setAttribute("aria-expanded", "false");
    ui.launcher.focus({ preventScroll: true });
  }

  async function reset() {
    if (state.busy) return;
    remember(null);
    state.id = null;
    state.started = false;
    await ensureStarted();
    window.dispatchEvent(new CustomEvent("repkit:reset"));
  }

  // -- construction --------------------------------------------------------

  /* Black or white, whichever reads better on the pack's accent colour. */
  function inkFor(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const linear = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    const luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
    return luminance > 0.4 ? "#14181d" : "#ffffff";
  }

  function iconButton(icon, label, onClick) {
    const button = el("button", "rk-icon-button");
    button.type = "button";
    button.innerHTML = ICONS[icon];
    button.setAttribute("aria-label", label);
    button.title = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function build(config) {
    const { rep, widget } = config;
    const host = el("div");
    host.id = "repkit-widget";
    host.style.setProperty("--rk-accent", widget.accent);
    host.style.setProperty("--rk-on-accent", inkFor(widget.accent));
    const root = host.attachShadow({ mode: "open" });

    const style = el("link");
    style.rel = "stylesheet";
    style.href = `${server}/static/widget.css`;

    const launcher = el("button", "rk-launcher");
    launcher.type = "button";
    launcher.innerHTML = ICONS.chat;
    launcher.append(el("span", "", widget.launcher_label));
    launcher.setAttribute("aria-expanded", "false");
    launcher.addEventListener("click", open);

    const panel = el("section", "rk-panel");
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", `Chat with ${rep.name} at ${rep.company}`);

    const header = el("header", "rk-header");
    const who = el("div", "rk-who");
    who.append(
      el("span", "rk-name", rep.name),
      el("span", "rk-sub", `${rep.company} · ${config.disclosure}`),
    );
    header.append(
      el("div", "rk-avatar", rep.name.slice(0, 1).toUpperCase()),
      who,
      iconButton("restart", "Start a new chat", reset),
      iconButton("close", "Close chat", close),
    );

    const log = el("div", "rk-log");
    log.setAttribute("role", "log");
    log.setAttribute("aria-live", "polite");
    log.tabIndex = 0;

    const typing = el("div", "rk-typing");
    typing.setAttribute("aria-label", `${rep.name} is typing`);
    typing.append(el("span"), el("span"), el("span"));

    const suggestions = el("div", "rk-suggestions");
    for (const suggestion of widget.suggestions) {
      const chip = el("button", "", suggestion);
      chip.type = "button";
      chip.addEventListener("click", () => send(suggestion));
      suggestions.append(chip);
    }

    const status = el("div", "rk-status", "A member of the team is taking over this chat.");
    status.hidden = true;
    status.setAttribute("role", "status");

    const form = el("form", "rk-form");
    const input = el("textarea", "rk-input");
    input.rows = 1;
    input.maxLength = 2000;
    input.placeholder = "Write a message";
    input.setAttribute("aria-label", "Message");
    const sendButton = el("button", "rk-send");
    sendButton.type = "submit";
    sendButton.disabled = true;
    sendButton.innerHTML = ICONS.send;
    sendButton.setAttribute("aria-label", "Send");
    form.append(input, sendButton);

    const submit = () => {
      const text = input.value;
      if (!text.trim() || state.busy) return;
      input.value = "";
      input.style.height = "";
      send(text);
    };
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit();
    });
    input.addEventListener("input", () => {
      input.style.height = "";
      input.style.height = `${input.scrollHeight}px`;
      sendButton.disabled = state.busy || !input.value.trim();
    });
    input.addEventListener("keydown", (event) => {
      // Enter sends, Shift+Enter makes a new line. Leave IME composition alone.
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        submit();
      }
    });
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });

    const footnote = el(
      "p",
      "rk-footnote",
      `${rep.name} is an AI assistant. Ask for a person at any time.`,
    );

    panel.append(header, log, suggestions, status, form, footnote);
    root.append(style, launcher, panel);
    Object.assign(ui, {
      host, launcher, panel, log, typing, suggestions, status, input, send: sendButton,
    });
    document.body.append(host);
  }

  async function init() {
    try {
      state.config = await api("/api/config");
    } catch {
      // No chat is better than a broken launcher on someone's shop.
      console.warn("repkit: could not load the chat configuration from", server);
      return;
    }
    build(state.config);
    window.repkit = { open, close, send: (text) => (open(), send(text)), reset };
    window.dispatchEvent(new CustomEvent("repkit:ready", { detail: state.config }));
    if (options.repkitOpen === "true") open();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
