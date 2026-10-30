// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Flamerix AI (https://flamerix.ai)

if (typeof Bun !== "undefined" && Bun.main.startsWith("/$bunfs/")) {
  const timers = require("node:timers");
  const verdicts = new WeakMap();
  const wrappers = new Map();
  const promisify = Symbol.for("nodejs.util.promisify.custom");

  function isSummary(callback) {
    if (typeof callback !== "function") return false;
    if (!verdicts.has(callback)) {
      const source = Function.prototype.toString.call(callback);
      verdicts.set(callback, source.includes("[AgentSummary] Timer fired") || source.includes("agent_summary"));
    }
    return verdicts.get(callback);
  }

  function wrap(original) {
    if (wrappers.has(original)) return wrappers.get(original);
    const wrapped = function (callback, delay, ...args) {
      if (!isSummary(callback)) return original(callback, delay, ...args);
      // Larger delays overflow to 1 ms; unref keeps this cancellable handle from holding the process open.
      const handle = original(() => {}, 2 ** 31 - 1);
      handle.unref();
      return handle;
    };
    Object.defineProperty(wrapped, "name", { value: original.name });
    if (original.__promisify__) wrapped.__promisify__ = original.__promisify__;
    if (original[promisify]) wrapped[promisify] = original[promisify];
    wrappers.set(original, wrapped);
    return wrapped;
  }

  for (const name of ["setTimeout", "setInterval"]) {
    globalThis[name] = wrap(globalThis[name]);
    timers[name] = wrap(timers[name]);
  }
}
