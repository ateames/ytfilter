(function initAdminPage() {
  const settingsForm = document.getElementById("settings-form");
  if (!settingsForm) return;

  const toast = document.getElementById("admin-toast");
  const channelList = document.getElementById("channel-list");
  const channelInput = document.getElementById("channel-input");
  const addChannelBtn = document.getElementById("add-channel-btn");
  const saveSettingsBtn = document.getElementById("save-settings-btn");

  let toastTimer;

  function getAdminToken() {
    return new URLSearchParams(window.location.search).get("token");
  }

  function parseChannelInput(input) {
    const trimmed = input.trim();
    const match = trimmed.match(/UC[\w-]{22}/);
    return match ? match[0] : null;
  }

  async function adminFetch(path, options = {}) {
    const token = getAdminToken();
    const headers = {
      ...(options.headers || {}),
      "X-Admin-Token": token || "",
    };

    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, { ...options, headers });
    let data = null;

    if (response.status !== 204) {
      const text = await response.text();
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { error: text };
        }
      }
    }

    if (!response.ok) {
      const message = data?.error || `Request failed (${response.status})`;
      throw new Error(message);
    }

    return data;
  }

  function showToast(message, type = "success") {
    if (!toast) return;
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.remove("hidden", "admin-toast--error", "admin-toast--success");
    toast.classList.add(type === "error" ? "admin-toast--error" : "admin-toast--success");
    toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
  }

  function escapeHtml(text) {
    const el = document.createElement("span");
    el.textContent = text ?? "";
    return el.innerHTML;
  }

  function renderChannelItem(channel) {
    const thumb = channel.thumbnail_url
      ? `<img class="admin-channel__thumb" src="${escapeHtml(channel.thumbnail_url)}" alt="" width="48" height="48" loading="lazy" />`
      : `<div class="admin-channel__thumb admin-channel__thumb--placeholder" aria-hidden="true"></div>`;

    return `
      <li class="admin-channel" data-channel-id="${escapeHtml(channel.channel_id)}">
        ${thumb}
        <div class="admin-channel__info">
          <p class="admin-channel__name">${escapeHtml(channel.channel_name)}</p>
          <p class="admin-channel__meta">${channel.video_count ?? 0} videos</p>
        </div>
        <div class="admin-channel__actions">
          <button type="button" class="btn admin-channel__refresh" data-action="refresh">Refresh</button>
          <button type="button" class="btn btn-danger admin-channel__remove" data-action="remove">Remove</button>
        </div>
      </li>
    `;
  }

  function renderChannelList(channels) {
    if (!channels.length) {
      channelList.innerHTML =
        '<li class="admin-channel-list__empty">No channels yet. Add one above.</li>';
      return;
    }
    channelList.innerHTML = channels.map(renderChannelItem).join("");
  }

  async function loadChannels() {
    try {
      const channels = await adminFetch("/api/admin/channels");
      renderChannelList(channels);
    } catch (err) {
      channelList.innerHTML = `<li class="admin-channel-list__empty">${escapeHtml(err.message)}</li>`;
      showToast(err.message, "error");
    }
  }

  async function loadStats() {
    try {
      const stats = await adminFetch("/api/admin/stats");
      document.getElementById("stat-total-videos").textContent = stats.total_videos;
      document.getElementById("stat-total-channels").textContent = stats.total_channels;
      document.getElementById("stat-sessions-today").textContent = stats.sessions_today;
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    saveSettingsBtn.disabled = true;

    const body = {
      min_video_length_seconds:
        Math.max(0, parseInt(document.getElementById("min-video-length").value, 10) || 0) * 60,
      min_watch_time_seconds:
        Math.max(0, parseInt(document.getElementById("min-watch-time").value, 10) || 0) * 60,
      max_daily_watch_seconds:
        Math.max(0, parseInt(document.getElementById("max-daily-watch").value, 10) || 0) * 60,
    };

    try {
      await adminFetch("/api/admin/settings", {
        method: "POST",
        body: JSON.stringify(body),
      });
      showToast("Settings saved");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      saveSettingsBtn.disabled = false;
    }
  });

  addChannelBtn.addEventListener("click", async () => {
    const raw = channelInput.value;
    const channelId = parseChannelInput(raw);
    if (!channelId) {
      showToast("Enter a valid channel ID or URL", "error");
      return;
    }

    addChannelBtn.disabled = true;
    try {
      const channel = await adminFetch("/api/admin/channels", {
        method: "POST",
        body: JSON.stringify({ channel_id: raw }),
      });
      channelInput.value = "";
      const existing = channelList.querySelector(`[data-channel-id="${channel.channel_id}"]`);
      if (existing) {
        existing.outerHTML = renderChannelItem(channel);
      } else {
        const empty = channelList.querySelector(".admin-channel-list__empty");
        if (empty) {
          channelList.innerHTML = renderChannelItem(channel);
        } else {
          channelList.insertAdjacentHTML("afterbegin", renderChannelItem(channel));
        }
      }
      showToast(`Added ${channel.channel_name}`);
      loadStats();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      addChannelBtn.disabled = false;
    }
  });

  channelInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addChannelBtn.click();
    }
  });

  channelList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;

    const item = btn.closest(".admin-channel");
    const channelId = item?.dataset.channelId;
    if (!channelId) return;

    if (btn.dataset.action === "remove") {
      const name = item.querySelector(".admin-channel__name")?.textContent || "this channel";
      if (!confirm(`Remove ${name} and all cached videos?`)) return;

      btn.disabled = true;
      try {
        await adminFetch(`/api/admin/channels/${encodeURIComponent(channelId)}`, {
          method: "DELETE",
        });
        item.remove();
        if (!channelList.querySelector(".admin-channel")) {
          channelList.innerHTML =
            '<li class="admin-channel-list__empty">No channels yet. Add one above.</li>';
        }
        showToast("Channel removed");
        loadStats();
      } catch (err) {
        showToast(err.message, "error");
        btn.disabled = false;
      }
      return;
    }

    if (btn.dataset.action === "refresh") {
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Refreshing…';

      try {
        const result = await adminFetch(
          `/api/admin/channels/${encodeURIComponent(channelId)}/refresh`,
          { method: "POST" }
        );
        const meta = item.querySelector(".admin-channel__meta");
        if (meta) {
          meta.textContent = `${result.videos_cached} videos`;
        }
        showToast("Channel refreshed");
        loadStats();
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    }
  });

  loadChannels();
  loadStats();
})();
