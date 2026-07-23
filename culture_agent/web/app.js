const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const suggestions = document.querySelector("#suggestions");
const memoryList = document.querySelector("#memory-list");
const chatView = document.querySelector("#chat-view");
const libraryView = document.querySelector("#library-view");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function addMessage(role, text, pending = false) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  if (role === "assistant") {
    article.innerHTML = `<div class="avatar">栖</div><div class="bubble ${pending ? "typing" : ""}"><p>${escapeHtml(text)}</p></div>`;
  } else {
    article.innerHTML = `<div class="bubble"><p>${escapeHtml(text)}</p></div>`;
  }
  messages.append(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
  return article;
}

function renderMemories(memories = []) {
  if (!memories.length) {
    memoryList.innerHTML = `<div class="empty-memory">这次回答没有读取历史记录。</div>`;
    return;
  }
  memoryList.innerHTML = memories.map(item => `
    <div class="memory-item">
      <strong>《${escapeHtml(item.title)}》</strong>
      <span>${item.kind === "film" ? "电影" : "书籍"} · ${item.rating ?? "未评分"}/10</span>
      <p>${escapeHtml(item.reflection || "没有心得")}</p>
    </div>
  `).join("");
}

async function sendMessage(text) {
  const clean = text.trim();
  if (!clean) return;
  addMessage("user", clean);
  suggestions.classList.add("hidden");
  input.value = "";
  const pending = addMessage("assistant", "正在读取相关记忆…", true);
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: clean })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "请求失败");
    pending.remove();
    addMessage("assistant", data.reply);
    renderMemories(data.memories);
    if (data.created_entry) await loadLibrary();
  } catch (error) {
    pending.remove();
    addMessage("assistant", `抱歉，刚才没有处理成功：${error.message}`);
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
});

suggestions.addEventListener("click", event => {
  if (event.target.tagName === "BUTTON") sendMessage(event.target.textContent);
});

document.querySelector("#new-chat").addEventListener("click", () => {
  messages.querySelectorAll(".message:not(:first-child)").forEach(node => node.remove());
  suggestions.classList.remove("hidden");
  renderMemories([]);
  switchView("chat");
  input.focus();
});

document.querySelectorAll(".nav-item").forEach(button => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach(button => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  chatView.classList.toggle("hidden", view !== "chat");
  libraryView.classList.toggle("hidden", view !== "library");
  if (view === "library") loadLibrary();
}

async function loadLibrary() {
  const response = await fetch("/api/library");
  const { entries } = await response.json();
  const grid = document.querySelector("#library-grid");
  const empty = document.querySelector("#empty-library");
  document.querySelector("#entry-count").textContent = `${entries.length} 条记录`;
  empty.classList.toggle("hidden", entries.length > 0);
  grid.innerHTML = entries.map(item => `
    <article class="entry-card">
      <span class="entry-kind">${item.kind === "film" ? "FILM · 电影" : "BOOK · 书籍"}</span>
      <h3>《${escapeHtml(item.title)}》</h3>
      <span class="rating">${item.rating == null ? "未评分" : `${item.rating}/10`}</span>
      <p>${escapeHtml(item.reflection || "还没有写下心得。")}</p>
      <div class="tags">${item.tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
    </article>
  `).join("");
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    document.querySelector("#model-pill").textContent = `● ${data.model}`;
  } catch {
    document.querySelector("#model-pill").textContent = "● disconnected";
  }
}

loadHealth();
loadLibrary();

