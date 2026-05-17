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
  const jellyfinHome = `http://${host}:8096/`;
  const playerTag = kind === "video"
    ? `<video src="${streamUrl}" controls autoplay playsinline></video>`
    : `<audio src="${streamUrl}" controls autoplay></audio>`;
  const hevcHint = kind === "video"
    ? `<p class="muted" style="margin-top: 8px;">
         视频是否一片黑？Insta360 默认 HEVC/H.265 编码，Chrome / Cursor 内置浏览器不解码，
         <a href="${jellyfinHome}" target="_blank">用 Jellyfin 打开</a> 会自动转码 H.264。
       </p>`
    : "";
  c.innerHTML = `
    <h2>${escapeHtml(title)}</h2>
    ${playerTag}
    ${hevcHint}
    <div class="url-row">
      <input id="dlna-url" value="${dlnaUrl}" readonly>
      <button class="btn" onclick="copyUrl()">复制 DLNA 直链</button>
    </div>
    <p class="muted" style="margin-top: 10px;">DLNA 直链给投影仪/小爱等局域网客户端用（minidlna 8200 端口）。</p>
  `;
  modal.classList.remove("hidden");
}

function closeModal(ev) {
  if (ev && ev.target.id !== "modal") return;
  const modal = document.getElementById("modal");
  modal.classList.add("hidden");
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
