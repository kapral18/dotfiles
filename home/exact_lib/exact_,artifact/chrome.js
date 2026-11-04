const $ = (id) => document.getElementById(id);
const ARTIFACT_NAME = window.__AGENT_ARTIFACT_NAME__ || "artifact.html";
const ARTIFACT_TOKEN = window.__AGENT_ARTIFACT_TOKEN__ || "";
let context = {};
let multiContexts = [];
let tray = [];
let feedbackActive = false;
let sending = false;

const CONTEXT_FIELDS = ["selection", "selector", "text", "note", "url", "title", "artifact_id", "entity_id", "entity_kind", "entity_label", "entity_summary", "entity", "entity_ancestors", "relations", "role", "label", "rect", "ancestors", "source"];

function anchorContext(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return Object.fromEntries(CONTEXT_FIELDS.filter((field) => Object.hasOwn(raw, field)).map((field) => [field, raw[field]]));
}

function apiPath(prefix) {
  return prefix + encodeURIComponent(ARTIFACT_NAME);
}

function summarizeContext(value) {
  if (value.selection) return ["Selection", value.selection];
  if (value.text) return ["Element", value.text];
  if (value.selector) return ["Target", value.selector];
  return ["No anchor yet.", "Click content or select text in the artifact."];
}

function setStatus(text) {
  $("status").textContent = text;
}

function resetAnchorContext() {
  context = {};
  multiContexts = [];
  $("context").innerHTML = "<strong>No anchor yet.</strong><span>Click or select content. Alt-click expands the pinned area. Cmd-click adds targets.</span>";
  $("anchorTitle").textContent = "Pinned selection";
  $("anchorSelector").textContent = "";
  $("anchorText").textContent = "";
  $("dock").classList.remove("expanded");
  setStatus("Artifact loaded. Click, select text, Cmd-click for multi-target, or Alt-click a pinned area to expand.");
}

function expandDock() {
  $("dock").classList.add("expanded");
}

function postCaptureState() {
  const frame = $("artifact");
  if (frame.contentWindow) {
    frame.contentWindow.postMessage({ type: "agent-artifact-capture", enabled: feedbackActive }, "*");
  }
}

function setFeedbackActive(enabled) {
  feedbackActive = Boolean(enabled);
  document.body.classList.toggle("feedback-active", feedbackActive);
  $("feedbackToggle").setAttribute("aria-expanded", String(feedbackActive));
  $("feedbackToggle").textContent = feedbackActive ? "Close feedback" : "Feedback";
  postCaptureState();
  if (feedbackActive) {
    setStatus("Feedback mode enabled. Click or select content to pin an anchor; Cmd-click pins additional targets.");
  }
}

function renderAnchorCard(value) {
  if (multiContexts.length) {
    $("anchorTitle").textContent = multiContexts.length + " targets pinned";
    $("anchorSelector").textContent = "multi-target";
    $("anchorText").textContent = multiContexts.map((item, index) => (index + 1) + ". " + (item.text || item.selector || "target")).join("  -  ");
    return;
  }
  const [label, detail] = summarizeContext(value);
  $("anchorTitle").textContent = label;
  $("anchorSelector").textContent = value.selector || "selection";
  $("anchorText").textContent = detail;
}

function anchorLabel(item) {
  if (item.targets && item.targets.length) {
    const first = item.targets[0];
    return item.targets.length + " targets: " + (first.text || first.selector || "selection");
  }
  return item.selection || item.text || item.selector || "Unanchored feedback";
}

function renderTray() {
  const trayEl = $("tray");
  trayEl.innerHTML = "";
  tray.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "tray-item";
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = (index + 1) + ". " + anchorLabel(item);
    const detail = document.createElement("span");
    detail.textContent = item.prompt;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      tray.splice(index, 1);
      renderTray();
      setStatus(tray.length ? tray.length + " item(s) queued." : "Tray cleared.");
    });
    body.appendChild(title);
    body.appendChild(detail);
    row.appendChild(body);
    row.appendChild(remove);
    trayEl.appendChild(row);
  });
}

function addCurrentToTray() {
  const prompt = $("prompt").value.trim();
  if (!prompt) {
    setStatus("Write feedback before adding to the tray.");
    return false;
  }
  const item = { ...context, prompt };
  if (multiContexts.length) {
    item.targets = multiContexts.slice();
    item.selector = multiContexts[0].selector || "";
    item.text = multiContexts[0].text || "";
    item.selection = "";
  }
  tray.push(item);
  if (multiContexts.length) {
    multiContexts = [];
    const frame = $("artifact");
    if (frame.contentWindow) {
      frame.contentWindow.postMessage({ type: "agent-artifact-multi-clear" }, "*");
    }
  }
  $("prompt").value = "";
  renderTray();
  setStatus(tray.length + " item(s) queued. Add more anchors or send batch.");
  return true;
}

window.addEventListener("message", (event) => {
  if (event.source !== $("artifact").contentWindow) return;
  if (event.data && event.data.type === "agent-artifact-ready") {
    resetAnchorContext();
    postCaptureState();
  } else if (feedbackActive && event.data && event.data.type === "agent-artifact-multi-context") {
    multiContexts = Array.isArray(event.data.contexts) ? event.data.contexts.map(anchorContext) : [];
    if (multiContexts.length) {
      $("context").innerHTML = "<strong>Multi-target</strong><span></span>";
      $("context").querySelector("span").textContent = multiContexts.length + " target(s) pinned; one prompt addresses all of them.";
      renderAnchorCard(context);
      expandDock();
      setStatus(multiContexts.length + " target(s) pinned. Cmd-click toggles more; a plain click returns to single-anchor mode.");
    } else if (!context.selector && !context.selection) {
      resetAnchorContext();
    }
  } else if (feedbackActive && event.data && event.data.type === "agent-artifact-context") {
    context = anchorContext(event.data.context);
    multiContexts = [];
    const [label, detail] = summarizeContext(context);
    $("context").innerHTML = "<strong>" + label + "</strong><span></span>";
    $("context").querySelector("span").textContent = detail;
    renderAnchorCard(context);
    expandDock();
    setStatus("Anchor pinned. The dock expanded upward for selection feedback.");
  }
});

async function sendFeedbackBatch() {
  if (sending) return;
  if ($("prompt").value.trim() && !addCurrentToTray()) return;
  if (!tray.length) {
    setStatus("Add at least one feedback item before sending.");
    return;
  }
  const items = tray.slice();
  sending = true;
  $("send").disabled = true;
  setStatus("Sending " + items.length + " feedback item(s)...");
  try {
    const response = await fetch(apiPath("/api/feedback/"), {
      method: "POST",
      headers: { "content-type": "application/json", "x-artifact-token": ARTIFACT_TOKEN },
      body: JSON.stringify({ items }),
    });
    if (response.ok) {
      tray = tray.filter((item) => !items.includes(item));
      renderTray();
      setStatus("Queued " + items.length + " feedback item(s).");
    } else {
      setStatus("Failed to queue feedback batch. Items remain in the tray.");
    }
  } catch (error) {
    setStatus("Failed to queue feedback batch. Items remain in the tray.");
  } finally {
    sending = false;
    $("send").disabled = false;
  }
}

$("add").onclick = addCurrentToTray;
$("send").onclick = sendFeedbackBatch;
$("clear").onclick = () => {
  tray = [];
  $("prompt").value = "";
  renderTray();
  setStatus("Tray cleared.");
};
$("prompt").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    addCurrentToTray();
  }
});
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    $("prompt").value = button.dataset.prompt;
    $("prompt").focus();
  });
});
$("feedbackToggle").onclick = () => setFeedbackActive(!feedbackActive);
$("end").onclick = async () => {
  await fetch(apiPath("/api/end/"), { method: "POST", headers: { "x-artifact-token": ARTIFACT_TOKEN } });
  setStatus("Session ended.");
};
