/**
 * CADENCE Toast Notification Manager
 * Handles programmatic toasts and global HTMX HTTP error toasts (403, 409, 5xx).
 */
(function () {
  const TYPE_CLASSES = {
    info: "border-l-4 border-l-sky-600",
    success: "border-l-4 border-l-emerald-600",
    warning: "border-l-4 border-l-amber-500",
    error: "border-l-4 border-l-rose-600",
  };

  const BADGE_CLASSES = {
    info: "badge-info",
    success: "badge-success",
    warning: "badge-warning",
    error: "badge-error",
  };

  function getContainer() {
    return document.getElementById("toast-container");
  }

  function show({
    title = "Update",
    message = "",
    type = "info",
    duration = 4500,
    actionLabel = null,
    onAction = null,
  } = {}) {
    const container = getContainer();
    if (!container) return;

    const item = document.createElement("div");
    const borderClass = TYPE_CLASSES[type] || TYPE_CLASSES.info;
    const badgeClass = BADGE_CLASSES[type] || BADGE_CLASSES.info;

    item.setAttribute("role", "status");
    item.className = `cadence-card cadence-toast-enter ${borderClass} p-3.5 shadow-lg max-w-sm w-full pointer-events-auto flex items-start justify-between gap-3`;

    const body = document.createElement("div");
    body.className = "min-w-0 flex-1";

    const header = document.createElement("div");
    header.className = "flex items-center gap-2";

    const tag = document.createElement("span");
    tag.className = `badge badge-xs ${badgeClass}`;
    header.appendChild(tag);

    const heading = document.createElement("p");
    heading.className = "text-sm font-semibold truncate";
    heading.textContent = title;
    header.appendChild(heading);

    body.appendChild(header);

    if (message) {
      const text = document.createElement("p");
      text.className = "text-xs mt-1 opacity-80 break-words";
      text.textContent = message;
      body.appendChild(text);
    }

    if (actionLabel && typeof onAction === "function") {
      const actionBtn = document.createElement("button");
      actionBtn.type = "button";
      actionBtn.className = "btn btn-xs btn-outline mt-2";
      actionBtn.textContent = actionLabel;
      actionBtn.addEventListener("click", () => {
        onAction();
        item.remove();
      });
      body.appendChild(actionBtn);
    }

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "btn btn-ghost btn-xs px-1.5";
    closeBtn.setAttribute("aria-label", "Dismiss notification");
    closeBtn.textContent = "×";
    closeBtn.addEventListener("click", () => item.remove());

    item.appendChild(body);
    item.appendChild(closeBtn);
    container.appendChild(item);

    if (duration > 0) {
      window.setTimeout(() => {
        if (item.parentNode) item.remove();
      }, duration);
    }
  }

  // Global HTMX error feedback (409 Conflict -> reload prompt, 403 -> scope error)
  document.addEventListener("htmx:responseError", (evt) => {
    const xhr = evt.detail && evt.detail.xhr;
    if (!xhr) return;
    let errMsg = "";
    try {
      const parsed = JSON.parse(xhr.responseText);
      errMsg = parsed && parsed.error && parsed.error.message ? parsed.error.message : "";
    } catch (_e) {
      errMsg = "";
    }

    if (xhr.status === 409) {
      show({
        title: "Conflict Detected",
        message: errMsg || "This sheet changed, reload to see the latest version.",
        type: "warning",
        duration: 8000,
        actionLabel: "Reload",
        onAction: () => window.location.reload(),
      });
    } else if (xhr.status === 403) {
      show({
        title: "Access Restricted",
        message: errMsg || "This record is outside your unit scope.",
        type: "error",
      });
    } else if (xhr.status === 401) {
      window.location.href = "/login";
    } else if (xhr.status >= 500) {
      show({
        title: "Server Error",
        message: errMsg || "Could not complete the request. Please try again.",
        type: "error",
      });
    }
  });

  window.CadenceToast = { show };
})();
