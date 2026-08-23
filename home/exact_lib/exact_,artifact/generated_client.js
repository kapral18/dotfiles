(() => {
  const STYLE_ID = "__agent_artifact_highlight_style";
  const ENTITY_ATTR = "data-artifact-id";
  const MANIFEST_ID = "agent-artifact-manifest";
  let hovered = null;
  let selected = null;
  let multiSelected = [];
  let captureEnabled = false;
  let manifestCache = null;
  let manifestLoaded = false;

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .__agent_artifact_hover {
        outline: 2px solid rgba(56, 189, 248, 0.72) !important;
        outline-offset: 3px !important;
        box-shadow: 0 0 0 6px rgba(56, 189, 248, 0.12) !important;
        cursor: crosshair !important;
        transition: outline-color 120ms ease, box-shadow 120ms ease !important;
      }
      .__agent_artifact_selected {
        outline: 3px solid #7c3aed !important;
        outline-offset: 4px !important;
        box-shadow: 0 0 0 8px rgba(124, 58, 237, 0.18) !important;
        transition: outline-color 160ms ease, box-shadow 160ms ease !important;
      }
      .__agent_artifact_multi {
        outline: 3px solid #14b8a6 !important;
        outline-offset: 4px !important;
        box-shadow: 0 0 0 8px rgba(20, 184, 166, 0.18) !important;
        transition: outline-color 160ms ease, box-shadow 160ms ease !important;
      }
    `;
    document.head.appendChild(style);
  }

  function cssPath(el) {
    if (!el || !el.tagName) return "";
    const parts = [];
    for (let node = el; node && node.nodeType === 1 && parts.length < 5; node = node.parentElement) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        part += "#" + CSS.escape(node.id);
        parts.unshift(part);
        break;
      }
      const parent = node.parentElement;
      if (parent) {
        const same = [...parent.children].filter((x) => x.tagName === node.tagName);
        if (same.length > 1) part += ":nth-of-type(" + (same.indexOf(node) + 1) + ")";
      }
      parts.unshift(part);
    }
    return parts.join(" > ");
  }

  function areaTargetFor(el) {
    if (!el || !el.closest) return el;
    const cell = el.closest("td, th");
    if (cell && cell.parentElement) return cell.parentElement;
    return el.closest("[data-artifact-id], [data-card], .card, .panel, .callout, article, section, li, tr, blockquote, pre, figure, aside") || el;
  }

  function compactText(value) {
    return (value || "").trim().replace(/\s+/g, " ").slice(0, 240);
  }

  function selectionText() {
    return String((window.getSelection && window.getSelection()) || "").trim();
  }

  function targetFor(el, expand) {
    if (!el || !el.closest) return el;
    if (expand) return areaTargetFor(el);
    return el.closest("[data-artifact-id], a, button, input, textarea, select, [role], [data-card], article, section, li, tr, th, td, h1, h2, h3, p, pre, blockquote") || el;
  }

  function clearMulti() {
    multiSelected.forEach((el) => el.classList.remove("__agent_artifact_multi"));
    multiSelected = [];
  }

  function clearHighlights() {
    if (hovered) hovered.classList.remove("__agent_artifact_hover");
    if (selected) selected.classList.remove("__agent_artifact_selected");
    hovered = null;
    selected = null;
    clearMulti();
  }

  function setCaptureEnabled(enabled) {
    captureEnabled = Boolean(enabled);
    if (!captureEnabled) clearHighlights();
  }

  function expandedTargetFor(el) {
    const base = selected && selected.contains(el) ? selected : targetFor(el, true);
    if (!base || base === document.documentElement) return document.documentElement;
    return base.parentElement || document.documentElement;
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
      label: String(raw.label || raw.title || carrier.dataset.artifactLabel || carrier.dataset.artifactTitle || compactText(carrier.innerText || carrier.textContent)),
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
      source: "artifact",
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
      selector: cssPath(el),
      text: compactText(el.innerText || el.textContent),
      selection: selection || selectionText(),
      ...semanticContextFor(el),
    };
  }

  function hover(el) {
    ensureStyle();
    const target = targetFor(el, false);
    if (hovered && hovered !== target) hovered.classList.remove("__agent_artifact_hover");
    hovered = target;
    if (hovered && hovered !== selected) hovered.classList.add("__agent_artifact_hover");
  }

  function mark(el, expand) {
    ensureStyle();
    const target = targetFor(el, expand);
    if (selected && selected !== target) selected.classList.remove("__agent_artifact_selected");
    if (hovered && hovered !== target) hovered.classList.remove("__agent_artifact_hover");
    selected = target;
    if (selected) selected.classList.add("__agent_artifact_selected");
    return selected;
  }

  function toggleMulti(el, expand) {
    ensureStyle();
    const target = targetFor(el, expand);
    if (!target || !target.classList) return;
    const index = multiSelected.indexOf(target);
    if (index >= 0) {
      multiSelected.splice(index, 1);
      target.classList.remove("__agent_artifact_multi");
    } else {
      multiSelected.push(target);
      target.classList.add("__agent_artifact_multi");
    }
    parent.postMessage(
      {
        type: "agent-artifact-multi-context",
        contexts: multiSelected.map((item) => contextFor(item)),
      },
      "*",
    );
  }

  let last = {};
  document.addEventListener(
    "pointermove",
    (event) => {
      if (!captureEnabled) return;
      hover(event.target);
    },
    true,
  );
  document.addEventListener(
    "click",
    (event) => {
      if (!captureEnabled) return;
      const selection = selectionText();
      if (event.altKey || event.metaKey || event.ctrlKey) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (event.metaKey || event.ctrlKey) {
        toggleMulti(event.target, Boolean(selection));
        return;
      }
      clearMulti();
      parent.postMessage({ type: "agent-artifact-multi-context", contexts: [] }, "*");
      const el = event.altKey ? mark(expandedTargetFor(event.target), false) : mark(event.target, Boolean(selection));
      last = contextFor(el, selection);
      parent.postMessage({ type: "agent-artifact-context", context: last }, "*");
    },
    true,
  );
  document.addEventListener("mouseup", (event) => {
    if (!captureEnabled) return;
    const selection = selectionText();
    if (selection) {
      const el = mark(event.target, true);
      last = { ...contextFor(el, selection), selection };
      parent.postMessage({ type: "agent-artifact-context", context: last }, "*");
    }
  });
  window.addEventListener("message", (event) => {
    if (event.source === parent && event.data && event.data.type === "agent-artifact-capture") {
      setCaptureEnabled(event.data.enabled);
    }
    if (event.source === parent && event.data && event.data.type === "agent-artifact-multi-clear") {
      clearMulti();
    }
  });
  parent.postMessage({ type: "agent-artifact-ready" }, "*");
})();
