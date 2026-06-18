/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, "0");

  if (h > 0) {
    return `${h}:${pad(m)}:${pad(s)}`;
  }
  return `${m}:${pad(s)}`;
}

function formatSeconds(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);

  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  if (m > 0) return `${m}m`;
  return "0m";
}

function escapeHtml(text) {
  const el = document.createElement("span");
  el.textContent = text ?? "";
  return el.innerHTML;
}

/* ------------------------------------------------------------------ */
/* Browse page                                                        */
/* ------------------------------------------------------------------ */

(function initBrowsePage() {
  const videoGrid = document.getElementById("video-grid");
  if (!videoGrid) return;

  let currentChannel = null;
  let currentSearch = "";
  let currentPage = 1;
  let isLoading = false;
  let totalPages = 0;

  const channelFilter = document.getElementById("channel-filter");
  const searchInput = document.getElementById("search-input");
  const loadMoreBtn = document.getElementById("load-more");

  const channelNames = {};
  if (channelFilter) {
    channelFilter.querySelectorAll(".channel-btn[data-channel-id]").forEach((btn) => {
      const id = btn.dataset.channelId;
      if (id) {
        channelNames[id] = btn.textContent.trim();
      }
    });
  }

  function setActiveChannelButton(channelId) {
    if (!channelFilter) return;
    channelFilter.querySelectorAll(".channel-btn").forEach((btn) => {
      const id = btn.dataset.channelId || null;
      const isActive =
        (channelId === null && id === null) || id === channelId;
      btn.classList.toggle("active", isActive);
      btn.classList.remove("is-active");
    });
  }

  function showSpinner() {
    videoGrid.innerHTML =
      '<div class="empty-state"><div class="spinner spinner--lg" aria-hidden="true"></div></div>';
  }

  function showEmptyState() {
    videoGrid.innerHTML = `
      <div class="empty-state">
        <p class="empty-state__title">No videos found</p>
        <p class="empty-state__message">Try a different search or channel filter.</p>
      </div>`;
  }

  function buildVideoCard(video) {
    const channelName = channelNames[video.channel_id] || video.channel_id || "Unknown channel";
    const card = document.createElement("div");
    card.className = "video-card";
    card.dataset.videoId = video.video_id;
    card.innerHTML = `
      <div class="thumbnail-wrap">
        <img src="${escapeHtml(video.thumbnail_url || "")}" alt="" loading="lazy">
        <span class="duration-badge">${formatDuration(video.duration_seconds)}</span>
      </div>
      <div class="card-info">
        <h3 class="card-title">${escapeHtml(video.title)}</h3>
        <p class="card-channel">${escapeHtml(channelName)}</p>
      </div>`;
    return card;
  }

  function updateLoadMoreButton() {
    if (!loadMoreBtn) return;
    const hasMore = currentPage < totalPages;
    loadMoreBtn.classList.toggle("hidden", !hasMore);
    loadMoreBtn.disabled = isLoading;
  }

  async function fetchVideos(append = false) {
    if (isLoading) return;
    isLoading = true;
    updateLoadMoreButton();

    if (!append) {
      showSpinner();
    }

    const params = new URLSearchParams({ page: String(currentPage) });
    if (currentChannel) params.set("channel_id", currentChannel);
    if (currentSearch) params.set("search", currentSearch);

    try {
      const res = await fetch(`/api/videos?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      totalPages = data.pages || 0;

      if (!append) {
        videoGrid.innerHTML = "";
      }

      if (!data.videos || data.videos.length === 0) {
        if (!append) showEmptyState();
      } else {
        const fragment = document.createDocumentFragment();
        data.videos.forEach((video) => {
          fragment.appendChild(buildVideoCard(video));
        });
        videoGrid.appendChild(fragment);
      }
    } catch {
      if (!append) {
        videoGrid.innerHTML = `
          <div class="empty-state">
            <p class="empty-state__title">Could not load videos</p>
            <p class="empty-state__message">Check your connection and try again.</p>
          </div>`;
      }
    } finally {
      isLoading = false;
      updateLoadMoreButton();
    }
  }

  if (channelFilter) {
    channelFilter.addEventListener("click", (e) => {
      const btn = e.target.closest(".channel-btn");
      if (!btn) return;

      const channelId = btn.dataset.channelId || null;
      if (channelId === currentChannel || (channelId === null && currentChannel === null)) {
        return;
      }

      currentChannel = channelId;
      currentPage = 1;
      setActiveChannelButton(currentChannel);
      fetchVideos(false);
    });
  }

  if (searchInput) {
    searchInput.addEventListener(
      "input",
      debounce(() => {
        const query = searchInput.value.trim();
        if (query === currentSearch) return;
        currentSearch = query;
        currentPage = 1;
        fetchVideos(false);
      }, 400)
    );
  }

  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", () => {
      if (isLoading || currentPage >= totalPages) return;
      currentPage += 1;
      fetchVideos(true);
    });
  }

  videoGrid.addEventListener("click", (e) => {
    const card = e.target.closest(".video-card");
    if (!card) return;
    const videoId = card.dataset.videoId;
    if (videoId) {
      window.location.href = `/watch/${videoId}`;
    }
  });

  setActiveChannelButton(currentChannel);
  fetchVideos(false);
})();

/* ------------------------------------------------------------------ */
/* Watch time (nav bar)                                               */
/* ------------------------------------------------------------------ */

(function initWatchtimeDisplay() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  let display = document.getElementById("watchtime-display");
  if (!display) {
    display = document.createElement("span");
    display.id = "watchtime-display";
    display.className = "watchtime-display";
    display.setAttribute("aria-live", "polite");
    header.appendChild(display);
  }

  fetch("/api/watchtime")
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (!data) return;
      if (data.unlimited) {
        display.textContent = "";
        display.classList.add("hidden");
        return;
      }
      display.textContent = `${formatSeconds(data.seconds_remaining)} left`;
    })
    .catch(() => {});
})();
