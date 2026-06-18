(function initHistoryPage() {
  const container = document.getElementById("history-list");
  if (!container) return;

  function formatWatchedAt(isoString) {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const watchedStart = new Date(
      date.getFullYear(),
      date.getMonth(),
      date.getDate()
    );

    if (watchedStart.getTime() === todayStart.getTime()) {
      const time = date.toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      });
      return `Today ${time}`;
    }

    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  function buildEntry(entry) {
    const channelName = entry.channel_name || entry.channel_id || "Unknown channel";
    const item = document.createElement("article");
    item.className = "history-item";
    item.innerHTML = `
      <a href="/watch/${escapeHtml(entry.video_id)}" class="history-item__thumb">
        <img src="${escapeHtml(entry.thumbnail_url || "")}" alt="" loading="lazy" width="120" height="68">
      </a>
      <div class="history-item__body">
        <h2 class="history-item__title">
          <a href="/watch/${escapeHtml(entry.video_id)}">${escapeHtml(entry.title)}</a>
        </h2>
        <p class="history-item__channel">${escapeHtml(channelName)}</p>
        <p class="history-item__meta">
          <span class="history-item__date">${escapeHtml(formatWatchedAt(entry.watched_at))}</span>
          <span class="history-item__duration">Watched ${formatDuration(entry.seconds_watched)}</span>
        </p>
      </div>`;
    return item;
  }

  function showEmptyState() {
    container.innerHTML = `
      <div class="empty-state">
        <p class="empty-state__title">No watch history yet</p>
      </div>`;
  }

  function showErrorState() {
    container.innerHTML = `
      <div class="empty-state">
        <p class="empty-state__title">Could not load history</p>
        <p class="empty-state__message">Check your connection and try again.</p>
      </div>`;
  }

  fetch("/api/history")
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((entries) => {
      if (!entries || entries.length === 0) {
        showEmptyState();
        return;
      }

      container.innerHTML = "";
      const fragment = document.createDocumentFragment();
      entries.forEach((entry) => {
        fragment.appendChild(buildEntry(entry));
      });
      container.appendChild(fragment);
    })
    .catch(showErrorState);
})();
