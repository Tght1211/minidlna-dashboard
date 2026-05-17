async function api(url, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body && typeof body === "object") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = "请求失败";
    try { const j = await r.json(); msg = j.error || msg; } catch {}
    alert(msg);
    return null;
  }
  return r.json();
}

function refresh() { location.reload(); }

async function toggleWatcher(enabled) {
  const ok = await api("/api/watcher", "POST", { enabled });
  if (ok) location.reload();
}

async function addDir(ev) {
  ev.preventDefault();
  const path = document.getElementById("newpath").value.trim();
  const types = document.getElementById("newtypes").value;
  if (!path) return;
  const ok = await api("/api/add_dir", "POST", { path, types });
  if (ok && ok.ok) {
    alert("已添加，minidlna 重启中…");
    setTimeout(refresh, 2500);
  } else if (ok && !ok.ok) {
    alert(ok.error || "添加失败");
  }
}

async function removeDir(path) {
  if (!confirm(`确定移除媒体目录?\n${path}`)) return;
  const ok = await api("/api/remove_dir", "POST", { path });
  if (ok && ok.ok) {
    alert("已移除，minidlna 重启中…");
    setTimeout(refresh, 2500);
  }
}

function openItem(id, streamUrl, dlnaUrl, kind, title) {
  const modal = document.getElementById("modal");
  const c = document.getElementById("modal-content");
  const host = location.hostname;
  const cleanTitle = decodeEntities(title);
  modal.classList.remove("hidden");
  if (kind === "audio") {
    renderAudioPlayer(c, { id, streamUrl, dlnaUrl, title: cleanTitle });
  } else if (kind === "image") {
    renderImageViewer(c, { id, streamUrl, dlnaUrl, title: cleanTitle });
  } else {
    renderVideoPlayer(c, { id, streamUrl, dlnaUrl, title: cleanTitle, host });
  }
}

function decodeEntities(s) {
  const t = document.createElement("textarea");
  let cur = String(s ?? "");
  // Some titles in the minidlna DB are double-encoded ("&amp;amp;"); loop
  // until decoding is a no-op or the string stops changing.
  for (let i = 0; i < 3; i++) {
    t.innerHTML = cur;
    const next = t.value;
    if (next === cur) break;
    cur = next;
  }
  return cur;
}

function renderImageViewer(c, { streamUrl, dlnaUrl, title }) {
  c.classList.remove("audio-player-modal");
  c.classList.add("image-viewer-modal");
  // Build navigable list from all image cards currently on the page.
  const cards = [...document.querySelectorAll('[data-kind="image"]')];
  const list = cards.map(el => ({
    streamUrl: el.dataset.stream,
    dlnaUrl: el.dataset.dlna,
    title: decodeEntities(el.dataset.title),
  }));
  let idx = Math.max(0, list.findIndex(x => x.streamUrl === streamUrl));
  if (idx === -1) {
    list.unshift({ streamUrl, dlnaUrl, title });
    idx = 0;
  }

  function paint() {
    const cur = list[idx];
    c.innerHTML = `
      <button class="iv-nav iv-prev" ${idx === 0 ? "disabled" : ""} aria-label="prev">‹</button>
      <button class="iv-nav iv-next" ${idx >= list.length - 1 ? "disabled" : ""} aria-label="next">›</button>
      <div class="iv-stage">
        <img class="iv-img" src="${escapeAttr(cur.streamUrl)}" alt="${escapeAttr(cur.title)}">
      </div>
      <div class="iv-bar">
        <div class="iv-title">${escapeHtml(cur.title)}</div>
        <div class="iv-meta">${idx + 1} / ${list.length}</div>
        <div class="iv-url">
          <input id="dlna-url" value="${escapeAttr(cur.dlnaUrl)}" readonly>
          <button class="btn small ghost" onclick="copyUrl()">复制 DLNA</button>
          <a class="btn small ghost" href="${escapeAttr(cur.streamUrl)}" download>下载原图</a>
        </div>
      </div>
    `;
    c.querySelector(".iv-prev").addEventListener("click", () => { if (idx > 0) { idx--; paint(); } });
    c.querySelector(".iv-next").addEventListener("click", () => { if (idx < list.length - 1) { idx++; paint(); } });
    // Click on image toggles zoom
    const img = c.querySelector(".iv-img");
    img.addEventListener("click", () => img.classList.toggle("zoom"));
  }

  // Keyboard navigation while modal open
  function onKey(e) {
    if (document.getElementById("modal").classList.contains("hidden")) {
      document.removeEventListener("keydown", onKey);
      return;
    }
    if (e.key === "ArrowLeft" && idx > 0) { idx--; paint(); }
    else if (e.key === "ArrowRight" && idx < list.length - 1) { idx++; paint(); }
  }
  document.addEventListener("keydown", onKey);

  paint();
}

function escapeAttr(s) { return String(s ?? "").replace(/"/g, "&quot;"); }

function renderVideoPlayer(c, { streamUrl, dlnaUrl, title }) {
  c.classList.remove("audio-player-modal");
  c.classList.add("video-player-modal");
  c.innerHTML = `
    <div class="vp-topbar">
      <div class="vp-title">${escapeHtml(title)}</div>
    </div>
    <video class="vp-video" src="${streamUrl}" controls autoplay playsinline></video>
    <div class="vp-bottombar">
      <input id="dlna-url" value="${escapeAttr(dlnaUrl)}" readonly title="DLNA 直链给投影仪/小爱（minidlna 8200 端口）">
      <button class="btn small" onclick="copyUrl()">复制 DLNA</button>
      <span class="vp-hint">HEVC 在 Chrome / Cursor 解码不了 → 用 Safari，或把上面链接给投影仪</span>
    </div>
  `;
}

function hashHue(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

function parseTitle(raw) {
  const m = raw.match(/^(.*?)\s+-\s+(.+)$/);
  if (m) return { artist: m[1].trim(), song: m[2].trim() };
  return { artist: "", song: raw };
}

function fmtTime(sec) {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function renderAudioPlayer(c, { streamUrl, dlnaUrl, title }) {
  c.classList.add("audio-player-modal");
  const { artist, song } = parseTitle(title);
  const hue = hashHue(song || title);
  const initial = (song[0] || "♪").toUpperCase();
  c.innerHTML = `
    <div class="ap">
      <div class="ap-cover" id="ap-cover" style="--h:${hue}">
        <div class="ap-disc">
          <div class="ap-art">
            <span class="ap-letter">${escapeHtml(initial)}</span>
          </div>
        </div>
      </div>
      <div class="ap-info">
        <div class="ap-song" title="${escapeHtml(song)}">${escapeHtml(song)}</div>
        <div class="ap-artist">${artist ? escapeHtml(artist) : "未知艺术家"}</div>
      </div>
      <div class="ap-progress">
        <span class="ap-time" id="ap-cur">0:00</span>
        <div class="ap-bar" id="ap-bar">
          <div class="ap-bar-track">
            <div class="ap-bar-fill" id="ap-fill"></div>
            <div class="ap-bar-thumb" id="ap-thumb"></div>
          </div>
        </div>
        <span class="ap-time" id="ap-dur">0:00</span>
      </div>
      <div class="ap-controls">
        <button class="ap-play" id="ap-play" aria-label="play/pause">
          <svg viewBox="0 0 24 24" width="22" height="22" id="ap-icon-play"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
          <svg viewBox="0 0 24 24" width="22" height="22" id="ap-icon-pause" style="display:none"><path fill="currentColor" d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>
        </button>
      </div>
      <audio id="ap-audio" src="${streamUrl}" autoplay preload="metadata"></audio>
      <div class="ap-dlna">
        <input id="dlna-url" value="${dlnaUrl}" readonly>
        <button class="btn ghost small" onclick="copyUrl()">复制 DLNA 直链</button>
      </div>
    </div>
  `;
  wireAudioPlayer();
}

function wireAudioPlayer() {
  const audio = document.getElementById("ap-audio");
  const cover = document.getElementById("ap-cover");
  const playBtn = document.getElementById("ap-play");
  const iconPlay = document.getElementById("ap-icon-play");
  const iconPause = document.getElementById("ap-icon-pause");
  const bar = document.getElementById("ap-bar");
  const fill = document.getElementById("ap-fill");
  const thumb = document.getElementById("ap-thumb");
  const tCur = document.getElementById("ap-cur");
  const tDur = document.getElementById("ap-dur");

  function setPlayingUI(playing) {
    iconPlay.style.display = playing ? "none" : "";
    iconPause.style.display = playing ? "" : "none";
    cover.classList.toggle("playing", playing);
  }
  playBtn.addEventListener("click", () => {
    if (audio.paused) audio.play(); else audio.pause();
  });
  audio.addEventListener("play", () => setPlayingUI(true));
  audio.addEventListener("pause", () => setPlayingUI(false));
  audio.addEventListener("ended", () => setPlayingUI(false));
  audio.addEventListener("loadedmetadata", () => {
    tDur.textContent = fmtTime(audio.duration);
  });
  audio.addEventListener("timeupdate", () => {
    if (dragging) return;
    const pct = (audio.currentTime / (audio.duration || 1)) * 100;
    fill.style.width = `${pct}%`;
    thumb.style.left = `${pct}%`;
    tCur.textContent = fmtTime(audio.currentTime);
  });

  let dragging = false;
  function seekAt(clientX) {
    const r = bar.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
    fill.style.width = `${pct * 100}%`;
    thumb.style.left = `${pct * 100}%`;
    tCur.textContent = fmtTime((audio.duration || 0) * pct);
    return pct;
  }
  bar.addEventListener("mousedown", e => { dragging = true; seekAt(e.clientX); });
  document.addEventListener("mousemove", e => { if (dragging) seekAt(e.clientX); });
  document.addEventListener("mouseup", e => {
    if (!dragging) return;
    dragging = false;
    const pct = seekAt(e.clientX);
    if (audio.duration) audio.currentTime = audio.duration * pct;
  });

  const observer = new MutationObserver(() => {
    if (document.getElementById("modal").classList.contains("hidden")) {
      audio.pause();
      observer.disconnect();
    }
  });
  observer.observe(document.getElementById("modal"), { attributes: true, attributeFilter: ["class"] });
}

function closeModal(ev) {
  if (ev && ev.target.id !== "modal") return;
  const modal = document.getElementById("modal");
  const body = document.querySelector(".modal-body");
  modal.classList.add("hidden");
  if (body) body.classList.remove("audio-player-modal", "image-viewer-modal", "video-player-modal");
  document.getElementById("modal-content").innerHTML = "";
}

async function copyUrl() {
  const inp = document.getElementById("dlna-url");
  try {
    await navigator.clipboard.writeText(inp.value);
    inp.style.borderColor = "var(--accent)";
    setTimeout(() => inp.style.borderColor = "", 700);
  } catch {
    inp.select(); document.execCommand("copy");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
});

// HUD clock
(function clock() {
  const el = document.getElementById("hud-clock");
  if (!el) return;
  function tick() {
    const d = new Date();
    const pad = n => String(n).padStart(2, "0");
    el.textContent = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  tick();
  setInterval(tick, 1000);
})();

function initInfiniteScroll({ kind, folder, q, total, loaded, pageSize }) {
  const container = document.getElementById("items-container");
  const sentinel = document.getElementById("load-sentinel");
  const counter = document.getElementById("loaded-count");
  if (!container || !sentinel) return;
  let offset = loaded;
  let fetching = false;
  let done = offset >= total;

  function escapeAttr(s) { return String(s ?? "").replace(/"/g, "&quot;"); }
  function fmtSize(n) {
    if (!n) return "-";
    const u = ["B", "KB", "MB", "GB", "TB"];
    let i = 0; let v = Number(n);
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return i === 0 ? `${n} B` : `${v.toFixed(1)} ${u[i]}`;
  }
  function fmtDur(d) {
    if (!d) return "-";
    return String(d).split(".")[0];
  }
  function buildCard(item) {
    if (item.kind === "audio") {
      return `<a class="row-item" href="#"
        data-id="${item.id}" data-stream="${escapeAttr(item.stream_url)}"
        data-dlna="${escapeAttr(item.dlna_url)}" data-kind="audio"
        data-title="${escapeAttr(item.title)}">
        <span class="ico">♪</span>
        <span class="title">${escapeHtml(item.title)}</span>
        <span class="sub">${fmtDur(item.duration)} · ${fmtSize(item.size)}</span>
      </a>`;
    }
    const badge = item.kind === "image"
      ? `<span class="badge badge-image">PHOTO</span>`
      : `<span class="badge badge-video">VIDEO</span>`;
    const sub = item.kind === "image"
      ? `${item.resolution || "—"} · ${fmtSize(item.size)}`
      : `${fmtDur(item.duration)} · ${item.resolution || ""} · ${fmtSize(item.size)}`;
    return `<a class="media-card ${item.kind}" href="#"
      data-id="${item.id}" data-stream="${escapeAttr(item.stream_url)}"
      data-dlna="${escapeAttr(item.dlna_url)}" data-kind="${item.kind}"
      data-title="${escapeAttr(item.title)}">
      <div class="thumb">
        <img loading="lazy" src="${escapeAttr(item.thumb_url)}"
          onload="this.classList.add('loaded');this.parentNode.classList.add('loaded')"
          onerror="this.parentNode.classList.add('noimg')">
        ${badge}
        <span class="hover-play">▶</span>
      </div>
      <div class="meta">
        <div class="title">${escapeHtml(item.title)}</div>
        <div class="sub">${sub}</div>
      </div>
    </a>`;
  }

  async function loadNext() {
    if (fetching || done) return;
    fetching = true;
    try {
      const params = new URLSearchParams({ kind, offset: String(offset) });
      if (folder) params.set("folder", folder);
      if (q) params.set("q", q);
      const r = await fetch(`/api/items?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      if (!data.items.length) { done = true; sentinel.remove(); return; }
      const html = data.items.map(buildCard).join("");
      container.insertAdjacentHTML("beforeend", html);
      offset += data.items.length;
      if (counter) counter.textContent = String(offset);
      if (offset >= total) { done = true; sentinel.remove(); }
    } catch (e) {
      console.error(e);
    } finally {
      fetching = false;
    }
  }

  const io = new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting)) loadNext();
  }, { rootMargin: "400px" });
  io.observe(sentinel);
}

// Delegate clicks on .media-card / .row-item to the player modal.
document.addEventListener("click", e => {
  const el = e.target.closest("[data-stream]");
  if (!el) return;
  e.preventDefault();
  openItem(
    el.dataset.id,
    el.dataset.stream,
    el.dataset.dlna,
    el.dataset.kind,
    el.dataset.title,
  );
});
