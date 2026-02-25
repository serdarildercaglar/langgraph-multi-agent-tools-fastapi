// ===== CONFIGURATION =====
const API_BASE = 'http://localhost:8080';
const CHAT_ENDPOINT = `${API_BASE}/chat`;
const STREAM_ENDPOINT = `${API_BASE}/chat/stream`;

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

// ===== STATE =====
let isProcessing = false;
let currentStreamMode = 'non-stream';
let currentAgent = 'main';
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

// ===== AGENT SELECTOR =====
document.querySelectorAll('.agent-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.agent-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentAgent = btn.dataset.agent;
        const icon = btn.querySelector('.agent-icon').textContent;
        dom.topbarAgent.textContent = `${icon} ${currentAgent}`;
    });
});

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

// ===== WELCOME CHIPS =====
document.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
        dom.messageInput.value = chip.dataset.message;
        sendMessage();
    });
});

// ===== CLEAR CHAT =====
dom.clearChatBtn.addEventListener('click', clearChat);

function clearChat() {
    dom.messageArea.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">👋</div>
            <h2>Merhaba!</h2>
            <p>Multi-Agent sisteme hoş geldiniz. Size nasıl yardımcı olabilirim?</p>
            <div class="welcome-chips">
                <button class="chip" data-message="Mevcut ürünleri listele">📦 Ürünleri listele</button>
                <button class="chip" data-message="Siparişlerimi göster">🛒 Siparişlerim</button>
                <button class="chip" data-message="Yardım">❓ Yardım</button>
            </div>
        </div>
    `;
    // Re-bind chips
    document.querySelectorAll('.chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            dom.messageInput.value = chip.dataset.message;
            sendMessage();
        });
    });
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
        dom.sendButton.disabled = false;
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
        const res = await fetch(CHAT_ENDPOINT, {
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
        const res = await fetch(STREAM_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let pendingEvent = 'message'; // default SSE event type

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
                    pendingEvent = 'message'; // reset after consuming
                    continue;
                }

                // Empty line = end of SSE block (already handled above)
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
            // Keep partial content but show error
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
            // Stream complete
            break;

        case 'error':
            contentEl.classList.remove('streaming');
            currentAssistantEl.className = 'message error';
            contentEl.innerHTML = escapeHtml(payload.message || 'Bilinmeyen hata');
            setStatus('Hata', 'error');
            break;

        default:
            // Unknown event, try to extract content anyway
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
    if (!text || isProcessing) return;

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
    setStatus('Hazır', '');
    dom.messageInput.focus();
    console.log(`Multi-Agent Chat UI initialized`);
    console.log(`Chat: ${CHAT_ENDPOINT} | Stream: ${STREAM_ENDPOINT}`);
    console.log(`Session: ${sessionId}`);
});
