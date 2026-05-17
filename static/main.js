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

function openItem(id, url, kind, title) {
  const modal = document.getElementById("modal");
  const c = document.getElementById("modal-content");
  const tag = kind === "video"
    ? `<video src="${url}" controls autoplay></video>`
    : `<audio src="${url}" controls autoplay></audio>`;
  c.innerHTML = `
    <h2>${escapeHtml(title)}</h2>
    <div class="muted">${url}</div>
    ${tag}
    <div class="url-row">
      <input id="dlna-url" value="${url}" readonly>
      <button class="btn" onclick="copyUrl()">复制链接</button>
    </div>
    <p class="muted" style="margin-top: 10px;">小爱/电视等 DLNA 客户端会通过原生 8200 端口访问这个 URL。</p>
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
