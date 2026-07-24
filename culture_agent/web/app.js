const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const suggestions = document.querySelector("#suggestions");
const memoryList = document.querySelector("#memory-list");
const chatView = document.querySelector("#chat-view");
const libraryView = document.querySelector("#library-view");
const isChineseUI = navigator.language.toLowerCase().startsWith("zh");
let conversationHistory = [];

const locale = {
  noMemory: isChineseUI ? "这次回答没有读取历史记录。" : "This reply did not read historical records.",
  film: isChineseUI ? "电影" : "Film",
  book: isChineseUI ? "书籍" : "Book",
  unrated: isChineseUI ? "未评分" : "Unrated",
  noReflection: isChineseUI ? "没有心得" : "No reflection yet",
  readingMemory: isChineseUI ? "正在读取相关记忆…" : "Reading relevant memories…",
  error: isChineseUI ? "抱歉，刚才没有处理成功：" : "Sorry, that did not work: ",
  records: isChineseUI ? "条记录" : "records",
};

const tagLabels = {
  slow_paced: { en: "slow-paced", zh: "慢节奏" },
  gentle: { en: "gentle", zh: "温柔" },
  restrained: { en: "restrained", zh: "克制" },
  family: { en: "family", zh: "家庭" },
  everyday_life: { en: "everyday life", zh: "人生观察" },
  mystery: { en: "mystery", zh: "悬疑" },
  science_fiction: { en: "science fiction", zh: "科幻" },
  romance: { en: "romance", zh: "浪漫" },
  humorous: { en: "humorous", zh: "幽默" },
  heavy: { en: "heavy", zh: "沉重" },
};

const legacyTagIds = Object.fromEntries(
  Object.entries(tagLabels).flatMap(([id, labels]) =>
    Object.values(labels).map(label => [label, id])
  )
);

function localizedTag(value) {
  const id = legacyTagIds[value] || value;
  const labels = tagLabels[id];
  return labels ? labels[isChineseUI ? "zh" : "en"] : value;
}

function applyBrowserLocale() {
  if (!isChineseUI) return;
  document.documentElement.lang = "zh-CN";
  document.title = "栖光 · Local Culture Agent";
  const copy = {
    "#brand-name": "栖光",
    "#new-chat": "＋ 新的对话",
    '[data-view="chat"]': "◌ 对话",
    '[data-view="library"]': "▦ 我的书影音",
    "#privacy-title": "本地记忆已开启",
    "#privacy-copy": "记录保存在你的设备上",
    "#chat-eyebrow": "你的私人文化伙伴",
    "#chat-title": "今天想聊点什么？",
    "#welcome-one": "你好。我可以陪你聊书和电影，也会在你允许时把评分与感受留在本地。",
    "#welcome-two": "试着告诉我：“我看完《一一》，9分，很喜欢它对日常生活的观察。”",
    "#composer-hint": "Enter 发送 · Shift + Enter 换行",
    "#library-title": "我的书影音",
    "#empty-title": "这里还很安静",
    "#empty-copy": "回到对话，告诉我你刚读完或看完的作品。",
    "#memory-title": "本次读取的记忆",
    "#memory-note": "你可以随时查看、纠正或删除记忆。模型不会直接修改数据库。",
  };
  Object.entries(copy).forEach(([selector, text]) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = text;
  });
  document.querySelector("#message-input").placeholder = "聊聊最近读过、看过或想看的……";
  const suggestionCopy = ["我最近喜欢什么？", "今天有点累，推荐一部电影", "看看我的本地记录"];
  document.querySelectorAll("#suggestions button").forEach((button, index) => {
    button.textContent = suggestionCopy[index];
  });
}

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
    memoryList.innerHTML = `<div class="empty-memory">${locale.noMemory}</div>`;
    return;
  }
  memoryList.innerHTML = memories.map(item => `
    <div class="memory-item">
      <strong>《${escapeHtml(item.title)}》</strong>
      <span>${item.kind === "film" ? locale.film : locale.book} · ${item.rating ?? locale.unrated}/10</span>
      <p>${escapeHtml(item.reflection || locale.noReflection)}</p>
    </div>
  `).join("");
}

async function sendMessage(text) {
  const clean = text.trim();
  if (!clean) return;
  addMessage("user", clean);
  suggestions.classList.add("hidden");
  input.value = "";
  const pending = addMessage("assistant", locale.readingMemory, true);
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: clean,
        history: conversationHistory.slice(-12)
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "请求失败");
    pending.remove();
    addMessage("assistant", data.reply);
    conversationHistory.push(
      { role: "user", content: clean },
      { role: "assistant", content: data.reply }
    );
    conversationHistory = conversationHistory.slice(-12);
    renderMemories(data.memories);
    if (data.created_entry) await loadLibrary();
  } catch (error) {
    pending.remove();
    addMessage("assistant", `${locale.error}${error.message}`);
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
  conversationHistory = [];
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
  document.querySelector("#entry-count").textContent = `${entries.length} ${locale.records}`;
  empty.classList.toggle("hidden", entries.length > 0);
  grid.innerHTML = entries.map(item => `
    <article class="entry-card">
      <span class="entry-kind">${item.kind === "film" ? `FILM · ${locale.film}` : `BOOK · ${locale.book}`}</span>
      <h3>《${escapeHtml(item.title)}》</h3>
      <span class="rating">${item.rating == null ? locale.unrated : `${item.rating}/10`}</span>
      <p>${escapeHtml(item.reflection || locale.noReflection)}</p>
      <div class="tags">${item.tags.map(tag => `<span>${escapeHtml(localizedTag(tag))}</span>`).join("")}</div>
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

applyBrowserLocale();
loadHealth();
loadLibrary();

