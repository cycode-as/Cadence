/**
 * CADENCE WebSocket Client (Section 8.4).
 * Connects to /ws with exponential backoff, redirects on close code 4401,
 * falls back to dev emitter when disconnected in dev mode, maps events to
 * HTMX fragment refreshes, triggers toasts, bumps #bell, and notifies charts.
 */
(function () {
  const EVENT_LABELS = {
    "attendance.updated": { title: "Attendance Updated", type: "info" },
    "leave.updated": { title: "Leave Status Updated", type: "info" },
    "notice.created": { title: "New Unit Notice", type: "success" },
    "dashboard.refresh": { title: "Dashboard Refreshed", type: "info" },
    "presence.updated": { title: "Reviewer Presence", type: "warning" },
  };

  let socket = null;
  let retryDelayMs = 1000;
  let reconnectTimer = null;
  const MAX_RETRY_MS = 30000;

  function resolveTargets(payload) {
    const targets = ["#bell"];
    const eid = payload.entity_id;

    switch (payload.event) {
      case "dashboard.refresh":
        targets.push("#stat-cards");
        break;
      case "attendance.updated":
        targets.push("#stat-cards");
        if (eid) {
          targets.push(`#sheet-${eid}`, `#timeline-${eid}`);
        }
        break;
      case "leave.updated":
        targets.push("#leave-queue", "#stat-cards");
        if (eid) {
          targets.push(`#timeline-${eid}`);
        }
        break;
      case "notice.created":
        targets.push("#notice-list");
        break;
      case "presence.updated":
        if (eid) {
          targets.push(`#presence-${eid}`);
        }
        break;
      default:
        break;
    }
    return targets;
  }

  function handleIncomingEvent(payload) {
    if (!payload || !payload.event) return;

    const meta = EVENT_LABELS[payload.event] || {
      title: payload.event,
      type: "info",
    };

    if (window.CadenceToast && payload.event !== "presence.updated") {
      const scopeInfo = payload.scope_type ? `Scope: ${payload.scope_type}` : "";
      window.CadenceToast.show({
        title: meta.title,
        message: payload.message || scopeInfo || "Live update received.",
        type: meta.type,
      });
    }

    if (window.htmx) {
      resolveTargets(payload).forEach((selector) => {
        const el = document.querySelector(selector);
        if (el) {
          window.htmx.trigger(el, "refresh");
        }
      });
    }

    document.dispatchEvent(
      new CustomEvent("cadence:ws-event", { detail: payload })
    );
  }

  function updateWsBadge(status) {
    const badge = document.getElementById("ws-status-dot");
    if (!badge) return;
    badge.dataset.status = status;
    badge.title = `Live channel: ${status}`;
    badge.classList.remove("bg-emerald-400", "bg-amber-400", "bg-rose-400");
    if (status === "connected") {
      badge.classList.add("bg-emerald-400");
    } else if (status === "connecting") {
      badge.classList.add("bg-amber-400");
    } else {
      badge.classList.add("bg-rose-400");
    }
  }

  function connect() {
    const body = document.body;
    if (!body || body.dataset.wsEnabled !== "true") return;
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/ws`;
    updateWsBadge("connecting");

    try {
      socket = new WebSocket(url);
    } catch (_err) {
      scheduleReconnect();
      return;
    }

    socket.addEventListener("open", () => {
      retryDelayMs = 1000;
      updateWsBadge("connected");
      document.dispatchEvent(new CustomEvent("cadence:ws-open"));
    });

    socket.addEventListener("message", (evt) => {
      try {
        const data = JSON.parse(evt.data);
        handleIncomingEvent(data);
      } catch (_err) {
        // Ignore non-JSON frame
      }
    });

    socket.addEventListener("close", (evt) => {
      updateWsBadge("disconnected");
      if (evt.code === 4401) {
        window.location.href = "/login";
        return;
      }
      scheduleReconnect();
    });

    socket.addEventListener("error", () => {
      updateWsBadge("disconnected");
    });
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      retryDelayMs = Math.min(retryDelayMs * 2, MAX_RETRY_MS);
      connect();
    }, retryDelayMs);
  }

  function send(data) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  async function emitDevFallback(eventName, extras = {}) {
    try {
      const res = await fetch("/dev/emit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event: eventName, ...extras }),
      });
      if (res.ok) {
        const data = await res.json();
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          handleIncomingEvent(data.emitted || { event: eventName, ...extras });
        }
        return true;
      }
    } catch (_err) {
      // Ignore network errors and trigger locally below
    }
    handleIncomingEvent({
      event: eventName,
      scope_type: "BATTALION",
      message: `Simulated ${eventName} locally (dev fallback)`,
      ...extras,
    });
    return false;
  }

  document.addEventListener("DOMContentLoaded", connect);

  window.CadenceWS = {
    connect,
    send,
    emitLocal: handleIncomingEvent,
    emitDevFallback,
    isConnected: () => Boolean(socket && socket.readyState === WebSocket.OPEN),
  };
})();
