(function initWatchtimePage() {
  const panel = document.getElementById("watchtime-panel");
  if (!panel) return;

  function showErrorState() {
    panel.innerHTML = `
      <div class="empty-state">
        <p class="empty-state__title">Could not load watch time</p>
        <p class="empty-state__message">Check your connection and try again.</p>
      </div>`;
  }

  function renderBreakdown(breakdown) {
    if (!breakdown || breakdown.length === 0) {
      return `
        <p class="watchtime-breakdown__empty">No videos watched today yet.</p>`;
    }

    const items = breakdown
      .map(
        (entry) => `
        <li class="watchtime-breakdown__item">
          <a href="/watch/${escapeHtml(entry.video_id)}" class="watchtime-breakdown__title">
            ${escapeHtml(entry.title)}
          </a>
          <span class="watchtime-breakdown__seconds">${formatDuration(entry.seconds_watched)}</span>
        </li>`
      )
      .join("");

    return `<ul class="watchtime-breakdown__list">${items}</ul>`;
  }

  fetch("/api/watchtime")
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => {
      const usedMinutes = Math.floor((data.seconds_watched_today || 0) / 60);
      const totalMinutes = Math.floor((data.limit || 0) / 60);
      const unlimited = data.unlimited;

      let summaryText;
      let fillWidth;
      let fillClass = "progress-fill";

      if (unlimited) {
        summaryText = "Unlimited";
        fillWidth = 100;
        fillClass += " progress-fill--unlimited";
      } else {
        summaryText = `${usedMinutes} of ${totalMinutes} minutes used`;
        const ratio = data.limit > 0 ? data.seconds_watched_today / data.limit : 0;
        fillWidth = Math.min(100, Math.max(0, ratio * 100));
      }

      panel.innerHTML = `
        <div class="watchtime-summary">
          <p class="watchtime-summary__text">${escapeHtml(summaryText)}</p>
          <div class="progress-bar" role="progressbar" aria-valuenow="${Math.round(fillWidth)}" aria-valuemin="0" aria-valuemax="100" aria-label="Daily watch time used">
            <div class="${fillClass}" style="width: ${fillWidth}%"></div>
          </div>
          <p class="watchtime-reset-notice">Resets at midnight UTC</p>
        </div>
        <section class="watchtime-breakdown">
          <h2 class="watchtime-breakdown__heading">Today</h2>
          ${renderBreakdown(data.today_breakdown)}
        </section>`;
    })
    .catch(showErrorState);
})();
