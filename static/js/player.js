/* ------------------------------------------------------------------ */
/* Watch page — YouTube IFrame Player API                           */
/* ------------------------------------------------------------------ */

(function initWatchPlayer() {
  const configEl = document.getElementById("player-config");
  const playerEl = document.getElementById("player");
  if (!configEl || !playerEl) return;

  const config = JSON.parse(configEl.textContent);
  const {
    videoId,
    minWatchTimeSeconds = 0,
    secondsRemaining: initialSecondsRemaining = 0,
    unlimited = true,
  } = config;

  const backBtn = document.getElementById("back-btn");
  const minWatchNotice = document.getElementById("min-watch-notice");
  const minWatchNoticeText = document.getElementById("min-watch-notice-text");
  const remainingMinutesEl = document.getElementById("remaining-minutes");
  const limitOverlay = document.getElementById("limit-overlay");

  let player = null;
  let secondsWatchedThisSession = 0;
  let secondsRemaining = initialSecondsRemaining;
  let minWatchUnlocked = minWatchTimeSeconds === 0;
  let dailyLimitReached = false;
  let historySent = false;
  let playTickTimer = null;
  let watchtimeTimer = null;

  const YT_PLAYING = 1;
  const YT_ENDED = 0;

  function formatMinutes(seconds) {
    const total = Math.max(0, Math.ceil(Number(seconds) / 60));
    return total === 1 ? "1 minute" : `${total} minutes`;
  }

  function updateMinWatchUI() {
    if (minWatchUnlocked) return;

    const remaining = minWatchTimeSeconds - secondsWatchedThisSession;
    if (remaining <= 0) {
      unlockMinWatch();
      return;
    }

    if (minWatchNoticeText) {
      minWatchNoticeText.textContent = `Watch for ${formatMinutes(remaining)} before leaving`;
    }
  }

  function unlockMinWatch() {
    if (minWatchUnlocked) return;
    minWatchUnlocked = true;

    if (backBtn) {
      backBtn.classList.remove("is-locked");
      backBtn.classList.add("is-unlocked");
      backBtn.removeAttribute("aria-disabled");
      backBtn.removeAttribute("tabindex");
    }

    if (minWatchNotice) {
      minWatchNotice.classList.add("is-hiding");
      minWatchNotice.addEventListener(
        "animationend",
        () => minWatchNotice.classList.add("hidden"),
        { once: true }
      );
    }
  }

  function updateRemainingDisplay() {
    if (!remainingMinutesEl || unlimited) return;
    remainingMinutesEl.textContent = String(Math.max(0, Math.floor(secondsRemaining / 60)));
  }

  function showDailyLimitOverlay() {
    dailyLimitReached = true;
    if (player && player.pauseVideo) {
      player.pauseVideo();
    }
    if (limitOverlay) {
      limitOverlay.classList.remove("hidden");
    }
    if (playerEl) {
      playerEl.setAttribute("aria-hidden", "true");
    }
    stopTimers();
  }

  function stopTimers() {
    if (playTickTimer) {
      clearInterval(playTickTimer);
      playTickTimer = null;
    }
    if (watchtimeTimer) {
      clearInterval(watchtimeTimer);
      watchtimeTimer = null;
    }
  }

  async function postWatchtime(seconds) {
    try {
      const res = await fetch("/api/watchtime", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: videoId, seconds }),
      });
      if (!res.ok) return;
      const data = await res.json();

      if (data.allowed === false) {
        showDailyLimitOverlay();
        return;
      }

      if (!unlimited && typeof data.seconds_remaining === "number") {
        secondsRemaining = data.seconds_remaining;
        updateRemainingDisplay();
      }
    } catch {
      /* ignore network errors during playback */
    }
  }

  function reportHistory(completed) {
    if (historySent || secondsWatchedThisSession === 0) return;
    historySent = true;

    const body = JSON.stringify({
      video_id: videoId,
      seconds_watched: secondsWatchedThisSession,
      completed,
    });

    fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  }

  function isPlaying() {
    return player && player.getPlayerState && player.getPlayerState() === YT_PLAYING;
  }

  function startTimers() {
    if (playTickTimer || dailyLimitReached) return;

    playTickTimer = setInterval(() => {
      if (!isPlaying()) return;

      secondsWatchedThisSession += 1;
      updateMinWatchUI();
    }, 1000);

    watchtimeTimer = setInterval(() => {
      if (!isPlaying()) return;
      postWatchtime(10);
    }, 10000);
  }

  function onPlayerStateChange(event) {
    if (event.data === YT_PLAYING) {
      startTimers();
    }

    if (event.data === YT_ENDED) {
      reportHistory(true);
      stopTimers();
    }
  }

  window.onYouTubeIframeAPIReady = function onYouTubeIframeAPIReady() {
    player = new YT.Player("player", {
      videoId,
      playerVars: {
        enablejsapi: 1,
        rel: 0,
        modestbranding: 1,
      },
      events: {
        onStateChange: onPlayerStateChange,
      },
    });
  };

  if (backBtn) {
    backBtn.addEventListener("click", (e) => {
      if (!minWatchUnlocked) {
        e.preventDefault();
      }
    });
  }

  window.addEventListener("beforeunload", () => {
    reportHistory(false);
  });

  updateMinWatchUI();
  updateRemainingDisplay();

  const tag = document.createElement("script");
  tag.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(tag);
})();
