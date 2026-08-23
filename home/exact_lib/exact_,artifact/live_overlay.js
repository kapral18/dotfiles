(() => {
  const NAME = __NAME_JSON__;
  const BASE_URL = __BASE_URL_JSON__;
  const LIVE_OVERLAY_CSS = __LIVE_OVERLAY_CSS_JSON__;
  const LIVE_OVERLAY_HTML = __LIVE_OVERLAY_HTML_JSON__;
  const HOST_ID = "__agent_artifact_live_overlay";
  const HOVER_ID = "__agentArtifactHover";
  const SELECTED_ID = "__agentArtifactSelected";
  const MULTI_CLASS = "__agentArtifactMulti";
  const ENTITY_ATTR = "data-artifact-id";
  const MANIFEST_ID = "agent-artifact-manifest";

  const existing = document.getElementById(HOST_ID);
  if (existing && existing.__agentArtifactDestroy) existing.__agentArtifactDestroy();

  const host = document.createElement("div");
  host.id = HOST_ID;
  host.style.all = "initial";
  host.style.position = "fixed";
  host.style.zIndex = "2147483647";
  host.style.inset = "0";
  host.style.pointerEvents = "none";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `<style>${LIVE_OVERLAY_CSS}</style>${LIVE_OVERLAY_HTML}`;
  document.documentElement.appendChild(host);

  const $ = (id) => root.getElementById(id);
  const hoverBox = $(HOVER_ID);
  const selectedBox = $(SELECTED_ID);
  let hovered = null;
  let selected = null;
  let multiSelected = [];
  let multiBoxes = [];
  let context = {};
  let tray = [];
  let pendingBatches = [];
  let paused = false;
  let manifestCache = null;
  let manifestLoaded = false;

  function compactText(value) {
    return (value || "").trim().replace(/\s+/g, " ").slice(0, 260);
  }

  function cssPath(el) {
    if (!el || !el.tagName) return "";
    const parts = [];
    for (let node = el; node && node.nodeType === 1 && parts.length < 6; node = node.parentElement) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        part += "#" + CSS.escape(node.id);
        parts.unshift(part);
        break;
      }
      const testid = node.getAttribute("data-test-subj") || node.getAttribute("data-testid");
      if (testid) part += `[${node.hasAttribute("data-test-subj") ? "data-test-subj" : "data-testid"}="${CSS.escape(testid)}"]`;
      const parent = node.parentElement;
      if (parent && !testid) {
        const same = [...parent.children].filter((x) => x.tagName === node.tagName);
        if (same.length > 1) part += ":nth-of-type(" + (same.indexOf(node) + 1) + ")";
      }
      parts.unshift(part);
    }
    return parts.join(" > ");
  }

  function selectionText() {
    return String((window.getSelection && window.getSelection()) || "").trim();
  }

  function targetFor(el, expand) {
    if (!el || !el.closest) return el;
    if (expand) return areaTargetFor(el);
    return el.closest("[data-artifact-id], a, button, input, textarea, select, [role], [data-test-subj], [data-testid], article, section, li, tr, th, td, h1, h2, h3, p, pre, blockquote") || el;
  }

  function areaTargetFor(el) {
    if (!el || !el.closest) return el;
    const cell = el.closest("td, th");
    if (cell && cell.parentElement) return cell.parentElement;
    return el.closest("[data-artifact-id], [data-test-subj], [data-testid], [role='dialog'], [role='row'], [role='tabpanel'], article, section, main, aside, nav, form, li, tr, blockquote, pre, figure") || el;
  }

  function expandedTargetFor(el) {
    const base = selected && selected.contains(el) ? selected : targetFor(el, true);
    if (!base || base === document.documentElement) return document.documentElement;
    return base.parentElement || document.documentElement;
  }

  function roleOf(el) {
    if (!el) return "";
    return el.getAttribute("role") || el.tagName.toLowerCase();
  }

  function labelOf(el) {
    if (!el) return "";
    return compactText(el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("name") || el.innerText || el.textContent);
  }

  function rectOf(el) {
    const rect = el.getBoundingClientRect();
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    };
  }

  function ancestorsOf(el) {
    const values = [];
    for (let node = el; node && node.nodeType === 1 && values.length < 5; node = node.parentElement) {
      values.push({
        selector: cssPath(node),
        role: roleOf(node),
        label: labelOf(node),
      });
    }
    return values;
  }

  function manifest() {
    if (manifestLoaded) return manifestCache;
    manifestLoaded = true;
    const node = document.getElementById(MANIFEST_ID) || document.querySelector('script[type="application/json"][data-artifact-manifest]');
    if (!node || !node.textContent.trim()) return manifestCache;
    try {
      const value = JSON.parse(node.textContent);
      if (value && typeof value === "object") manifestCache = value;
    } catch (_error) {
      manifestCache = null;
    }
    return manifestCache;
  }

  function manifestEntities() {
    const value = manifest();
    return value && value.entities && typeof value.entities === "object" ? value.entities : {};
  }

  function manifestRelations() {
    const value = manifest();
    const relations = value && (value.relations || value.edges);
    return Array.isArray(relations) ? relations : [];
  }

  function relationTouches(relation, id) {
    return relation && (relation.from === id || relation.to === id || relation.source === id || relation.target === id);
  }

  function carrierFor(el) {
    return el && el.closest ? el.closest("[" + ENTITY_ATTR + "]") : null;
  }

  function entityFor(el) {
    const carrier = carrierFor(el);
    if (!carrier) return null;
    const id = carrier.getAttribute(ENTITY_ATTR) || "";
    if (!id) return null;
    const raw = manifestEntities()[id] || {};
    const entity = {
      id,
      kind: String(raw.kind || carrier.dataset.artifactKind || carrier.getAttribute("role") || carrier.tagName.toLowerCase()),
      label: String(raw.label || raw.title || carrier.dataset.artifactLabel || carrier.dataset.artifactTitle || labelOf(carrier)),
    };
    if (raw.summary || carrier.dataset.artifactSummary) entity.summary = String(raw.summary || carrier.dataset.artifactSummary);
    if (raw.parent || carrier.dataset.artifactParent) entity.parent = String(raw.parent || carrier.dataset.artifactParent);
    if (Array.isArray(raw.tags)) entity.tags = raw.tags.map(String).slice(0, 12);
    return entity;
  }

  function entityAncestorsFor(entity) {
    const entities = manifestEntities();
    const values = [];
    const seen = new Set([entity && entity.id]);
    let parent = entity && entity.parent;
    while (parent && values.length < 8 && !seen.has(parent)) {
      seen.add(parent);
      const raw = entities[parent] || {};
      values.push({
        id: parent,
        kind: String(raw.kind || ""),
        label: String(raw.label || raw.title || parent),
      });
      parent = raw.parent;
    }
    return values;
  }

  function semanticContextFor(el) {
    const entity = entityFor(el);
    if (!entity) return {};
    const currentManifest = manifest() || {};
    const relations = manifestRelations().filter((relation) => relationTouches(relation, entity.id)).slice(0, 16);
    const context = {
      artifact_id: String(currentManifest.artifactId || currentManifest.id || ""),
      entity_id: entity.id,
      entity_kind: entity.kind,
      entity_label: entity.label,
      entity,
    };
    if (entity.summary) context.entity_summary = entity.summary;
    const ancestors = entityAncestorsFor(entity);
    if (ancestors.length) context.entity_ancestors = ancestors;
    if (relations.length) context.relations = relations;
    return context;
  }

  function contextFor(el, selection) {
    return {
      source: "live-overlay",
      url: location.href,
      title: document.title,
      selector: cssPath(el),
      role: roleOf(el),
      label: labelOf(el),
      text: compactText(el.innerText || el.textContent),
      selection: selection || selectionText(),
      rect: rectOf(el),
      ancestors: ancestorsOf(el),
      ...semanticContextFor(el),
    };
  }

  function showBox(box, el) {
    if (!el) {
      box.hidden = true;
      return;
    }
    const rect = el.getBoundingClientRect();
    box.hidden = false;
    box.style.left = rect.left + "px";
    box.style.top = rect.top + "px";
    box.style.width = rect.width + "px";
    box.style.height = rect.height + "px";
  }

  function summarize(value) {
    if (value.targets && value.targets.length) {
      const first = value.targets[0] || {};
      return value.targets.length + " targets: " + (first.selection || first.label || first.text || first.selector || "live targets");
    }
    return value.selection || value.label || value.text || value.selector || "No live target";
  }

  function setStatus(text) {
    $("status").textContent = text;
  }

  function clearMulti() {
    multiBoxes.forEach((box) => box.remove());
    multiBoxes = [];
    multiSelected = [];
  }

  function renderMultiBoxes() {
    multiBoxes.forEach((box) => box.remove());
    multiBoxes = [];
    multiSelected.forEach((item) => {
      const box = document.createElement("div");
      box.className = "box " + MULTI_CLASS;
      root.appendChild(box);
      showBox(box, item.el);
      multiBoxes.push(box);
    });
  }

  function syncHighlights() {
    showBox(hoverBox, hovered);
    showBox(selectedBox, selected);
    renderMultiBoxes();
  }

  function toggleMulti(el, expand, selection) {
    const target = targetFor(el, expand);
    if (!target) return;
    const index = multiSelected.findIndex((item) => item.el === target);
    if (index >= 0) {
      multiSelected.splice(index, 1);
    } else {
      multiSelected.push({ el: target, context: contextFor(target, selection || "") });
    }
    selected = null;
    showBox(selectedBox, null);
    renderMultiBoxes();
    if (multiSelected.length) {
      context = multiSelected[0].context;
      $("context").innerHTML = "<strong>Live multi-target.</strong><span></span>";
      $("context").querySelector("span").textContent = multiSelected.length + " target(s) pinned; one prompt addresses all of them.";
      setStatus(multiSelected.length + " target(s) pinned. Cmd-click toggles more; a plain click returns to single-target mode.");
    } else {
      context = {};
      $("context").innerHTML = "<strong>Live overlay armed.</strong><span>Click to pin. Cmd-click adds targets. Alt-click expands. Pause to use the app normally.</span>";
      setStatus("Multi-target selection cleared. Click to pin one live target.");
    }
  }

  function pin(el, expand, selection) {
    clearMulti();
    selected = targetFor(el, expand);
    context = contextFor(selected, selection || "");
    showBox(selectedBox, selected);
    $("context").innerHTML = "<strong>Live target pinned.</strong><span></span>";
    $("context").querySelector("span").textContent = summarize(context);
    setStatus("Pinned. Add feedback, Alt-click to expand, or pause to interact normally.");
  }

  function renderTray() {
    const trayEl = $("tray");
    trayEl.innerHTML = "";
    tray.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "item";
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = (index + 1) + ". " + summarize(item);
      const detail = document.createElement("span");
      detail.textContent = item.prompt;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        tray.splice(index, 1);
        renderTray();
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
    let item = { prompt, ...context };
    if (multiSelected.length) {
      const targets = multiSelected.map((entry) => entry.context);
      item = { prompt, ...targets[0], targets };
      clearMulti();
    }
    tray.push(item);
    $("prompt").value = "";
    renderTray();
    setStatus(tray.length + " item(s) queued.");
    return true;
  }

  async function sendFeedbackBatch() {
    if ($("prompt").value.trim() && !addCurrentToTray()) return;
    if (!tray.length) {
      setStatus("Add at least one feedback item before sending.");
      return;
    }
    const items = tray.slice();
    setStatus("Sending " + items.length + " live feedback item(s)...");
    try {
      const response = await fetch(BASE_URL + "/api/feedback/" + encodeURIComponent(NAME), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ items }),
      });
      if (response.ok) {
        const result = await response.json();
        tray = [];
        renderTray();
        setStatus("Queued batch " + result.batch_id + " with " + result.count + " item(s).");
      } else {
        setStatus("Failed to queue feedback batch.");
      }
    } catch (error) {
      pendingBatches.push({ items, error: String((error && error.message) || error || "fetch failed") });
      setStatus("Local post blocked. Batch kept in window.__agentArtifactLiveOverlay.drain().");
    }
  }

  function onPointerMove(event) {
    if (paused || host.contains(event.target)) return;
    hovered = targetFor(event.target, false);
    syncHighlights();
  }

  function onClick(event) {
    if (paused || host.contains(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const selection = selectionText();
    if (event.metaKey || event.ctrlKey) {
      toggleMulti(event.target, Boolean(selection), selection);
      return;
    }
    const target = event.altKey ? expandedTargetFor(event.target) : event.target;
    pin(target, Boolean(selection), selection);
  }

  function onMouseUp(event) {
    if (paused || host.contains(event.target)) return;
    if (event.metaKey || event.ctrlKey) return;
    const selection = selectionText();
    if (selection) pin(event.target, true, selection);
  }

  function updatePaused() {
    $("pause").textContent = paused ? "Resume" : "Pause";
    host.style.pointerEvents = "none";
    setStatus(paused ? "Capture paused. Use the page normally, then resume." : "Capture is on; page clicks are intercepted until paused.");
    if (paused) {
      showBox(hoverBox, null);
    }
  }

  function destroy() {
    document.removeEventListener("pointermove", onPointerMove, true);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("mouseup", onMouseUp, true);
    window.removeEventListener("scroll", syncHighlights, true);
    window.removeEventListener("resize", syncHighlights, true);
    clearMulti();
    host.remove();
    delete window.__agentArtifactLiveOverlay;
  }

  document.addEventListener("pointermove", onPointerMove, true);
  document.addEventListener("click", onClick, true);
  document.addEventListener("mouseup", onMouseUp, true);
  window.addEventListener("scroll", syncHighlights, true);
  window.addEventListener("resize", syncHighlights, true);
  $("add").addEventListener("click", addCurrentToTray);
  $("send").addEventListener("click", sendFeedbackBatch);
  $("clear").addEventListener("click", () => {
    tray = [];
    $("prompt").value = "";
    renderTray();
    setStatus("Tray cleared.");
  });
  $("end").addEventListener("click", async () => {
    await fetch(BASE_URL + "/api/end/" + encodeURIComponent(NAME), { method: "POST" });
    setStatus("Live feedback ended.");
  });
  $("pause").addEventListener("click", () => {
    paused = !paused;
    updatePaused();
  });
  $("remove").addEventListener("click", destroy);
  $("prompt").addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      addCurrentToTray();
    }
  });
  host.__agentArtifactDestroy = destroy;
  window.__agentArtifactLiveOverlay = {
    destroy,
    pause: () => {
      paused = true;
      updatePaused();
    },
    resume: () => {
      paused = false;
      updatePaused();
    },
    drain: () => pendingBatches.splice(0, pendingBatches.length),
  };
})();
