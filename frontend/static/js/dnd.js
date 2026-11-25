/**
 * CADENCE Drag-and-Drop Utility (SortableJS wrapper for squad board)
 */
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    const sortableLists = document.querySelectorAll('.sortable-list');
    sortableLists.forEach(function (list) {
      Sortable.create(list, {
        group: 'squads',
        animation: 150,
        ghostClass: 'opacity-50',
        onEnd: function (evt) {
          const cadetId = evt.item.dataset.cadetId;
          const newSquadId = evt.to.id.replace('squad-', '');
          fetch('/api/cadets/' + cadetId + '/move', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({ to_squad_id: newSquadId })
          }).then(r => r.json()).then(data => {
            if (data.success) {
              window.showToast('Cadet moved successfully', 'success');
            } else {
              window.showToast('Failed to move cadet', 'error');
              evt.item.remove();
              evt.from.insertBefore(evt.item, evt.from.children[evt.oldIndex]);
            }
          });
        }
      });
    });
  });
})();
