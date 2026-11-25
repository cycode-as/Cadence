/**
 * CADENCE Live Presence Tracker
 * Sends presence.join / presence.leave messages over /ws for elements
 * annotated with data-presence-entity and data-presence-id.
 */
(function () {
  const joinedKeys = new Set();

  function getTrackedEntities() {
    const nodes = document.querySelectorAll("[data-presence-entity][data-presence-id]");
    const seen = new Map();
    nodes.forEach((node) => {
      const entity = node.dataset.presenceEntity;
      const entityId = node.dataset.presenceId;
      if (entity && entityId) {
        seen.set(`${entity}:${entityId}`, { entity, entity_id: entityId });
      }
    });
    return Array.from(seen.values());
  }

  function joinAll() {
    if (!window.CadenceWS || !window.CadenceWS.isConnected()) return;
    getTrackedEntities().forEach((item) => {
      const key = `${item.entity}:${item.entity_id}`;
      if (!joinedKeys.has(key)) {
        const sent = window.CadenceWS.send({
          type: "presence.join",
          entity: item.entity,
          entity_id: item.entity_id,
        });
        if (sent) {
          joinedKeys.add(key);
        }
      }
    });
  }

  function leaveAll() {
    if (!window.CadenceWS) return;
    joinedKeys.forEach((key) => {
      const [entity, entity_id] = key.split(":");
      window.CadenceWS.send({
        type: "presence.leave",
        entity,
        entity_id,
      });
    });
    joinedKeys.clear();
  }

  document.addEventListener("DOMContentLoaded", joinAll);
  document.addEventListener("cadence:ws-open", () => {
    joinedKeys.clear();
    joinAll();
  });
  window.addEventListener("pagehide", leaveAll);
  window.addEventListener("beforeunload", leaveAll);

  window.CadencePresence = {
    joinAll,
    leaveAll,
  };
})();
