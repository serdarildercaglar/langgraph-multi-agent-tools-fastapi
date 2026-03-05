// ===== MARKDOWN SETUP =====
marked.setOptions({
    highlight: function (code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try { return hljs.highlight(code, { language: lang }).value; } catch (_) {}
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true,
});

// ===== UTILITIES =====
function generateId(prefix, length = 12) {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let id = prefix + '_';
    for (let i = 0; i < length; i++) {
        id += chars[Math.floor(Math.random() * chars.length)];
    }
    return id;
}

function formatTime(date) {
    return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function renderMarkdown(text) {
    try { return marked.parse(text); }
    catch { return text; }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== STATE =====
let apiBase = null; // set on connect
let isConnected = false;
let isProcessing = false;
let currentStreamMode = 'non-stream';
let currentAgent = null;
let sessionId = generateId('session');

// Cumulative stats
let totalInputTokens = 0;
let totalOutputTokens = 0;
let totalAllTokens = 0;
let requestCount = 0;
let totalProcessingTime = 0;

// Stream state
let currentAssistantEl = null;
let streamBuffer = '';

// ===== DOM REFS =====
const $ = (id) => document.getElementById(id);

const dom = {
    sidebar: $('sidebar'),
    sidebarToggle: $('sidebarToggle'),
    sidebarClose: $('sidebarClose'),
    apiUrlInput: $('apiUrlInput'),
    connectBtn: $('connectBtn'),
    connectionStatus: $('connectionStatus'),
    userIdInput: $('userIdInput'),
    sessionIdInput: $('sessionIdInput'),
    appIdInput: $('appIdInput'),
    newSessionBtn: $('newSessionBtn'),
    messageArea: $('messageArea'),
    messageInput: $('messageInput'),
    sendButton: $('sendButton'),
    topbarAgent: $('topbarAgent'),
    topbarStatus: $('topbarStatus'),
    modeBadge: $('modeBadge'),
    progressBar: $('progressBar'),
    eventBanner: $('eventBanner'),
    eventBannerIcon: $('eventBannerIcon'),
    eventBannerText: $('eventBannerText'),
    inputTokens: $('inputTokens'),
    outputTokens: $('outputTokens'),
    totalTokens: $('totalTokens'),
    requestCountEl: $('requestCount'),
    avgTime: $('avgTime'),
    clearChatBtn: $('clearChatBtn'),
};

// ===== INIT =====
dom.sessionIdInput.value = sessionId;
dom.sendButton.disabled = true;
dom.messageInput.disabled = true;
dom.messageInput.placeholder = 'Önce bir API\'ye bağlanın...';

// ===== SIDEBAR =====
let overlay = null;

function openSidebar() {
    dom.sidebar.classList.add('open');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);
        overlay.addEventListener('click', closeSidebar);
    }
    requestAnimationFrame(() => overlay.classList.add('visible'));
}

function closeSidebar() {
    dom.sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('visible');
}

dom.sidebarToggle.addEventListener('click', openSidebar);
dom.sidebarClose.addEventListener('click', closeSidebar);

// ===== CONNECTION =====
function setConnectionStatus(status, text) {
    dom.connectionStatus.className = `connection-status ${status}`;
    dom.connectionStatus.querySelector('.connection-text').textContent = text;
}

async function connectToApi() {
    const url = dom.apiUrlInput.value.trim().replace(/\/+$/, '');
    if (!url) return;

    dom.connectBtn.disabled = true;
    dom.connectBtn.textContent = '...';
    setConnectionStatus('connecting', 'Bağlanıyor...');

    try {
        const res = await fetch(`${url}/agents?format=json`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        apiBase = url;
        isConnected = true;

        // Populate agents
        const selector = $('agentSelector');
        selector.innerHTML = data.agents.map((agent, i) => {
            const isFirst = i === 0;
            return `<button class="agent-btn${isFirst ? ' active' : ''}" data-agent="${escapeHtml(agent.name)}" title="${escapeHtml(agent.description)}">
                <span class="agent-icon">🤖</span>
                <span class="agent-label">${escapeHtml(agent.name)}</span>
            </button>`;
        }).join('');

        bindAgentButtons();

        // Set first agent as current
        if (data.agents.length > 0) {
            currentAgent = data.agents[0].name;
            dom.topbarAgent.textContent = `🤖 ${currentAgent}`;
        }

        // Enable chat
        dom.sendButton.disabled = false;
        dom.messageInput.disabled = false;
        dom.messageInput.placeholder = 'Mesajınızı yazın...';
        dom.messageInput.focus();

        // Update UI
        setConnectionStatus('connected', `Bağlı — ${data.agents.length} agent`);
        dom.connectBtn.textContent = 'Bağlı';
        dom.connectBtn.classList.add('connected');
        setStatus('Hazır', '');

        // Show connected welcome
        showConnectedWelcome(data.agents);

        console.log(`Connected to ${url} — ${data.agents.length} agents`);

    } catch (err) {
        isConnected = false;
        apiBase = null;
        setConnectionStatus('error', `Hata: ${err.message}`);
        dom.connectBtn.textContent = 'Bağlan';
        dom.connectBtn.classList.remove('connected');
        dom.sendButton.disabled = true;
        dom.messageInput.disabled = true;
        dom.messageInput.placeholder = 'Önce bir API\'ye bağlanın...';
        setStatus('Bağlı değil', 'error');
    } finally {
        dom.connectBtn.disabled = false;
    }
}

function disconnectApi() {
    isConnected = false;
    apiBase = null;
    currentAgent = null;

    dom.connectBtn.textContent = 'Bağlan';
    dom.connectBtn.classList.remove('connected');
    setConnectionStatus('disconnected', 'Bağlı değil');

    dom.sendButton.disabled = true;
    dom.messageInput.disabled = true;
    dom.messageInput.placeholder = 'Önce bir API\'ye bağlanın...';

    $('agentSelector').innerHTML = '';
    dom.topbarAgent.textContent = '🤖 ---';
    setStatus('Bağlı değil', '');

    // Reset welcome
    dom.messageArea.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🔌</div>
            <h2>Hoş geldiniz!</h2>
            <p>Başlamak için sol panelden API URL'nizi girin ve <strong>Bağlan</strong> butonuna tıklayın.</p>
        </div>
    `;
}

function showConnectedWelcome(agents) {
    const agentChips = agents.slice(0, 5).map(a =>
        `<button class="chip" data-agent="${escapeHtml(a.name)}" title="${escapeHtml(a.description)}">🤖 ${escapeHtml(a.name)}</button>`
    ).join('');

    dom.messageArea.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">✅</div>
            <h2>Bağlantı başarılı!</h2>
            <p>${agents.length} agent bulundu. Mesajınızı yazarak sohbete başlayabilirsiniz.</p>
            <div class="welcome-chips">${agentChips}</div>
        </div>
    `;

    // Bind agent chips as quick-select
    dom.messageArea.querySelectorAll('.chip[data-agent]').forEach(chip => {
        chip.addEventListener('click', () => {
            const agentName = chip.dataset.agent;
            // Select agent in sidebar
            document.querySelectorAll('.agent-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.agent === agentName);
            });
            currentAgent = agentName;
            dom.topbarAgent.textContent = `🤖 ${agentName}`;
            dom.messageInput.focus();
        });
    });
}

dom.connectBtn.addEventListener('click', () => {
    if (isConnected) {
        disconnectApi();
    } else {
        connectToApi();
    }
});

dom.apiUrlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        if (isConnected) disconnectApi();
        connectToApi();
    }
});

// ===== AGENT SELECTOR =====
function bindAgentButtons() {
    document.querySelectorAll('.agent-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.agent-btn').forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            currentAgent = btn.dataset.agent;
            const icon = btn.querySelector('.agent-icon').textContent;
            dom.topbarAgent.textContent = `${icon} ${currentAgent}`;
        });
    });
}

// ===== MODE TOGGLE =====
document.querySelectorAll('.mode-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentStreamMode = btn.dataset.mode;

        if (currentStreamMode === 'stream') {
            dom.modeBadge.textContent = '📡 Stream';
        } else {
            dom.modeBadge.textContent = '⚡ Non-Stream';
        }
    });
});

// ===== SESSION =====
dom.newSessionBtn.addEventListener('click', () => {
    sessionId = generateId('session');
    dom.sessionIdInput.value = sessionId;
    clearChat();
});

// ===== CLEAR CHAT =====
dom.clearChatBtn.addEventListener('click', clearChat);

function clearChat() {
    if (isConnected) {
        dom.messageArea.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">👋</div>
                <h2>Yeni sohbet</h2>
                <p>Mesajınızı yazarak başlayabilirsiniz.</p>
            </div>
        `;
    } else {
        dom.messageArea.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🔌</div>
                <h2>Hoş geldiniz!</h2>
                <p>Başlamak için sol panelden API URL'nizi girin ve <strong>Bağlan</strong> butonuna tıklayın.</p>
            </div>
        `;
    }
}

// ===== MESSAGE RENDERING =====
function removeWelcome() {
    const welcome = dom.messageArea.querySelector('.welcome-message');
    if (welcome) welcome.remove();
}

function createMessageEl(role, content, agentName) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const avatars = { user: '👤', assistant: '🤖', error: '❌' };
    const senders = { user: 'Sen', assistant: agentName || currentAgent, error: 'Hata' };
    const time = formatTime(new Date());

    div.innerHTML = `
        <div class="message-avatar">${avatars[role] || '📋'}</div>
        <div class="message-body">
            <div class="message-meta">
                <span class="message-sender">${senders[role]}</span>
                ${role === 'assistant' && agentName ? `<span class="message-agent-badge">${agentName}</span>` : ''}
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${role === 'user' ? escapeHtml(content) : renderMarkdown(content)}</div>
        </div>
    `;
    return div;
}

function appendMessage(role, content, agentName) {
    removeWelcome();
    const el = createMessageEl(role, content, agentName);
    dom.messageArea.appendChild(el);
    dom.messageArea.scrollTop = dom.messageArea.scrollHeight;
    return el;
}

// ===== STATUS =====
function setStatus(text, type) {
    dom.topbarStatus.textContent = text;
    dom.topbarStatus.className = 'topbar-status' + (type ? ` ${type}` : '');
}

function setProcessing(active) {
    if (active) {
        dom.progressBar.classList.add('active');
        dom.sendButton.disabled = true;
        setStatus('İşleniyor...', 'processing');
    } else {
        dom.progressBar.classList.remove('active');
        dom.sendButton.disabled = !isConnected;
        hideEventBanner();
    }
}

// ===== EVENT BANNER =====
function showEventBanner(icon, text, type) {
    dom.eventBanner.classList.remove('hidden', 'tool-event', 'handoff-event');
    if (type) dom.eventBanner.classList.add(`${type}-event`);
    dom.eventBannerIcon.textContent = icon;
    dom.eventBannerText.textContent = text;
}

function hideEventBanner() {
    dom.eventBanner.classList.add('hidden');
}

// ===== USAGE STATS =====
function updateStats(usage, processingTime) {
    if (usage) {
        totalInputTokens += usage.prompt_tokens || 0;
        totalOutputTokens += usage.completion_tokens || 0;
        totalAllTokens += usage.total_tokens || 0;
    }

    requestCount++;
    totalProcessingTime += processingTime;

    animateStat(dom.inputTokens, totalInputTokens);
    animateStat(dom.outputTokens, totalOutputTokens);
    animateStat(dom.totalTokens, totalAllTokens);
    animateStat(dom.requestCountEl, requestCount);
    dom.avgTime.textContent = Math.round(totalProcessingTime / requestCount) + 'ms';
    flashStat(dom.avgTime);
}

function animateStat(el, value) {
    el.textContent = value.toLocaleString('tr-TR');
    flashStat(el);
}

function flashStat(el) {
    const item = el.closest('.stat-item');
    if (!item) return;
    item.classList.add('updated');
    setTimeout(() => item.classList.remove('updated'), 800);
}

// ===== BUILD REQUEST =====
function buildRequest(text) {
    return {
        app_id: dom.appIdInput.value || 'multi-agent-chat',
        user_id: dom.userIdInput.value || 'anonymous',
        agent_name: currentAgent,
        session_id: sessionId,
        messages: [{ role: 'user', content: text }],
    };
}

// ===== NON-STREAM HANDLER =====
async function sendNonStream(body) {
    const start = Date.now();

    try {
        const res = await fetch(`${apiBase}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const elapsed = Date.now() - start;

        if (data.success) {
            appendMessage('assistant', data.message?.content || 'Yanıt alınamadı', data.agent_name);
            updateStats(data.usage, elapsed);
            setStatus(`Tamamlandı (${elapsed}ms)`, '');
        } else {
            const errMsg = data.error?.message || 'Bilinmeyen hata';
            appendMessage('error', errMsg);
            setStatus('Hata', 'error');
        }
    } catch (err) {
        const elapsed = Date.now() - start;
        appendMessage('error', `Bağlantı hatası: ${err.message}`);
        setStatus(`Hata (${elapsed}ms)`, 'error');
    }
}

// ===== STREAM HANDLER =====
async function sendStream(body) {
    const start = Date.now();
    streamBuffer = '';

    // Create placeholder
    currentAssistantEl = appendMessage('assistant', '', currentAgent);
    const contentEl = currentAssistantEl.querySelector('.message-content');
    contentEl.classList.add('streaming');

    try {
        const res = await fetch(`${apiBase}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let pendingEvent = 'message';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                const trimmed = line.trim();

                if (trimmed.startsWith('event:')) {
                    pendingEvent = trimmed.substring(6).trim();
                    continue;
                }

                if (trimmed.startsWith('data:')) {
                    const jsonStr = trimmed.substring(5).trim();
                    if (!jsonStr) continue;

                    try {
                        const payload = JSON.parse(jsonStr);
                        handleSSE(pendingEvent, payload, contentEl);
                    } catch (e) {
                        console.warn('SSE parse error:', e);
                    }
                    pendingEvent = 'message';
                    continue;
                }
            }
        }

        // Finalize
        contentEl.classList.remove('streaming');
        hideEventBanner();

        const elapsed = Date.now() - start;
        updateStats(null, elapsed);
        setStatus(`Tamamlandı (${elapsed}ms)`, '');

    } catch (err) {
        contentEl.classList.remove('streaming');
        hideEventBanner();

        const elapsed = Date.now() - start;
        if (streamBuffer) {
            contentEl.innerHTML = renderMarkdown(streamBuffer);
        } else {
            contentEl.innerHTML = `Bağlantı hatası: ${escapeHtml(err.message)}`;
            currentAssistantEl.className = 'message error';
        }
        setStatus(`Hata (${elapsed}ms)`, 'error');
    }
}

function handleSSE(eventType, payload, contentEl) {
    switch (eventType) {
        case 'token':
            streamBuffer += payload.content || '';
            contentEl.innerHTML = renderMarkdown(streamBuffer);
            dom.messageArea.scrollTop = dom.messageArea.scrollHeight;
            break;

        case 'done':
            break;

        case 'error':
            contentEl.classList.remove('streaming');
            currentAssistantEl.className = 'message error';
            contentEl.innerHTML = escapeHtml(payload.message || 'Bilinmeyen hata');
            setStatus('Hata', 'error');
            break;

        default:
            if (payload.content) {
                streamBuffer += payload.content;
                contentEl.innerHTML = renderMarkdown(streamBuffer);
                dom.messageArea.scrollTop = dom.messageArea.scrollHeight;
            }
    }
}

// ===== MAIN SEND =====
async function sendMessage() {
    const text = dom.messageInput.value.trim();
    if (!text || isProcessing || !isConnected) return;

    isProcessing = true;
    setProcessing(true);

    // Show user message
    appendMessage('user', text);
    dom.messageInput.value = '';
    dom.messageInput.style.height = 'auto';

    const body = buildRequest(text);

    try {
        if (currentStreamMode === 'stream') {
            await sendStream(body);
        } else {
            await sendNonStream(body);
        }
    } catch (err) {
        appendMessage('error', `Beklenmeyen hata: ${err.message}`);
        setStatus('Hata', 'error');
    } finally {
        isProcessing = false;
        setProcessing(false);
    }
}

// ===== EVENT LISTENERS =====
dom.sendButton.addEventListener('click', sendMessage);

dom.messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Auto-resize textarea
dom.messageInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = this.scrollHeight + 'px';
});

// ===== STARTUP =====
window.addEventListener('load', () => {
    setStatus('Bağlı değil', '');
    dom.topbarAgent.textContent = '🤖 ---';
    console.log('Multi-Agent Chat UI initialized — waiting for connection');
});
