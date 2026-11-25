/**
 * CADENCE WebSocket Client (connects to /ws with exponential backoff).
 * Handles live event notifications, HTMX fragment refreshes, bell updates,
 * and close code 4401 (unauthenticated -> redirect to /login).
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
  const MAX_RETRY_MS = 30000;

  function resolveTargets(payload) {
    const targets = ["#bell"];
    const eid = payload.entity_id;
    switch (payload.event) {
      case "dashboard.refresh":
        targets.push("#stat-cards");
        break;
      case "attendance.updated":
        if (eid) {
          targets.push(`#sheet-${eid}`, `#timeline-${eid}`);
        }
        break;
      case "leave.updated":
        targets.push("#leave-queue");
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

    if (window.CadenceToast) {
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
    });

    socket.addEventListener("message", (evt) => {
      try {
        const data = JSON.parse(evt.data);
        handleIncomingEvent(data);
      } catch (_err) {
        // Ignore malformed frame
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
    window.setTimeout(() => {
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

  document.addEventListener("DOMContentLoaded", connect);

  window.CadenceWS = {
    send,
    emitLocal: handleIncomingEvent,
  };
})();
