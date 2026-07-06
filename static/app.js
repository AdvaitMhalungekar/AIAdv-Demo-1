/**
 * PrimeNest Realty — Chatbot Frontend Application
 * Handles session management, messaging, and UI interactions.
 */

// ─── State ──────────────────────────────────────────────────────────────────
let currentSessionId = null;
let isWaitingForResponse = false;

// ─── DOM Elements ───────────────────────────────────────────────────────────
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const sessionList = document.getElementById('sessionList');
const welcomeScreen = document.getElementById('welcomeScreen');
const typingIndicator = document.getElementById('typingIndicator');
const chatHeaderTitle = document.getElementById('chatHeaderTitle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');

// ─── API Helper ─────────────────────────────────────────────────────────────
async function api(url, options = {}) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// ─── Session Management ─────────────────────────────────────────────────────

async function loadSessions() {
    try {
        const data = await api('/api/sessions');
        renderSessionList(data.sessions);
    } catch (err) {
        console.error('Failed to load sessions:', err);
    }
}

function renderSessionList(sessions) {
    if (!sessions || sessions.length === 0) {
        sessionList.innerHTML = `
            <div class="empty-sessions">
                <div class="empty-icon">💬</div>
                <p>No conversations yet</p>
            </div>
        `;
        return;
    }

    sessionList.innerHTML = sessions.map(session => `
        <div class="session-item ${session.id === currentSessionId ? 'active' : ''}" 
             data-session-id="${session.id}" onclick="switchSession(${session.id})">
            <span class="session-icon">💬</span>
            <span class="session-title" title="${escapeHtml(session.title)}">${escapeHtml(session.title)}</span>
            <button class="session-delete" onclick="event.stopPropagation(); deleteSession(${session.id})" 
                    title="Delete conversation" aria-label="Delete conversation">✕</button>
        </div>
    `).join('');
}

async function createNewSession() {
    try {
        const data = await api('/api/sessions', {
            method: 'POST',
            body: JSON.stringify({ title: 'New Chat' }),
        });
        currentSessionId = data.session_id;
        await loadSessions();
        clearMessages();
        showWelcomeScreen();
        chatHeaderTitle.textContent = 'PrimeNest AI Assistant';
        closeSidebarMobile();
    } catch (err) {
        console.error('Failed to create session:', err);
    }
}

async function switchSession(sessionId) {
    if (sessionId === currentSessionId) return;
    currentSessionId = sessionId;
    await loadSessions();
    await loadMessages(sessionId);
    closeSidebarMobile();
}

async function deleteSession(sessionId) {
    try {
        await api(`/api/sessions/${sessionId}`, { method: 'DELETE' });
        if (sessionId === currentSessionId) {
            currentSessionId = null;
            clearMessages();
            showWelcomeScreen();
            chatHeaderTitle.textContent = 'PrimeNest AI Assistant';
        }
        await loadSessions();
    } catch (err) {
        console.error('Failed to delete session:', err);
    }
}

// ─── Message Handling ───────────────────────────────────────────────────────

async function loadMessages(sessionId) {
    try {
        const data = await api(`/api/sessions/${sessionId}/messages`);
        clearMessages();

        if (data.messages.length === 0) {
            showWelcomeScreen();
        } else {
            hideWelcomeScreen();
            data.messages.forEach(msg => {
                appendMessage(msg.role, msg.content, msg.timestamp, false);
            });
            scrollToBottom();
        }
    } catch (err) {
        console.error('Failed to load messages:', err);
    }
}

async function sendMessage(text) {
    if (!text.trim() || isWaitingForResponse) return;

    // Ensure session exists
    if (!currentSessionId) {
        await createNewSession();
    }

    const userMessage = text.trim();
    chatInput.value = '';
    chatInput.style.height = 'auto';
    updateSendButton();

    // Hide welcome, show message
    hideWelcomeScreen();
    appendMessage('user', userMessage, new Date().toISOString(), true);
    scrollToBottom();

    // Show typing
    isWaitingForResponse = true;
    showTyping();

    try {
        const data = await api('/api/chat', {
            method: 'POST',
            body: JSON.stringify({
                session_id: currentSessionId,
                message: userMessage,
            }),
        });

        hideTyping();
        appendMessage('assistant', data.response, new Date().toISOString(), true);
        scrollToBottom();

        // Refresh session list for updated title
        await loadSessions();
    } catch (err) {
        hideTyping();
        appendMessage('assistant', '⚠️ Sorry, something went wrong. Please try again.', new Date().toISOString(), true);
        console.error('Chat error:', err);
    } finally {
        isWaitingForResponse = false;
    }
}

function appendMessage(role, content, timestamp, animate) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;
    if (!animate) row.style.animation = 'none';

    const avatarEmoji = role === 'assistant' ? '🏠' : '👤';
    const formattedTime = formatTime(timestamp);
    const formattedContent = formatMarkdown(content);

    row.innerHTML = `
        <div class="message-avatar">${avatarEmoji}</div>
        <div>
            <div class="message-bubble">${formattedContent}</div>
            <div class="message-time">${formattedTime}</div>
        </div>
    `;

    // Insert before typing indicator
    chatMessages.insertBefore(row, typingIndicator);
}

function clearMessages() {
    const messages = chatMessages.querySelectorAll('.message-row');
    messages.forEach(m => m.remove());
}

// ─── Welcome Screen ─────────────────────────────────────────────────────────

function showWelcomeScreen() {
    welcomeScreen.style.display = 'flex';
}

function hideWelcomeScreen() {
    welcomeScreen.style.display = 'none';
}

// ─── Typing Indicator ───────────────────────────────────────────────────────

function showTyping() {
    typingIndicator.classList.add('visible');
    scrollToBottom();
}

function hideTyping() {
    typingIndicator.classList.remove('visible');
}

// ─── UI Helpers ─────────────────────────────────────────────────────────────

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

function updateSendButton() {
    sendBtn.disabled = !chatInput.value.trim() || isWaitingForResponse;
}

function formatTime(isoString) {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
        });
    } catch {
        return '';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Simple markdown-to-HTML formatter.
 * Handles: bold, italic, headings, lists, line breaks, code, links, hr
 */
function formatMarkdown(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Headings (### -> h4, ## -> h3)
    html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');

    // Horizontal rule
    html = html.replace(/^---$/gm, '<hr>');

    // Unordered lists
    html = html.replace(/^[\s]*[-•] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Numbered lists
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Line breaks — convert double newlines to paragraphs, single to <br>
    html = html.replace(/\n\n+/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph if not already a block element
    if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<pre') && !html.startsWith('<hr')) {
        html = '<p>' + html + '</p>';
    }

    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');
    // Clean up paragraphs wrapping block elements
    html = html.replace(/<p>(<h[34]>)/g, '$1');
    html = html.replace(/(<\/h[34]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)<\/p>/g, '$1');
    html = html.replace(/<p>(<hr>)<\/p>/g, '$1');

    return html;
}

// ─── Mobile Sidebar ─────────────────────────────────────────────────────────

function openSidebarMobile() {
    sidebar.classList.add('open');
    sidebarOverlay.classList.add('visible');
}

function closeSidebarMobile() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('visible');
}

// ─── Event Listeners ────────────────────────────────────────────────────────

// Send button
sendBtn.addEventListener('click', () => {
    sendMessage(chatInput.value);
});

// Input handling
chatInput.addEventListener('input', () => {
    updateSendButton();
    // Auto-resize textarea
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(chatInput.value);
    }
});

// New chat
newChatBtn.addEventListener('click', createNewSession);

// Quick action buttons
document.querySelectorAll('.quick-action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const message = btn.dataset.message;
        if (message) {
            chatInput.value = message;
            sendMessage(message);
        }
    });
});

// Mobile menu
mobileMenuBtn.addEventListener('click', openSidebarMobile);
sidebarOverlay.addEventListener('click', closeSidebarMobile);

// ─── Call Modal DOM Elements ────────────────────────────────────────────────
const requestCallBtn = document.getElementById('requestCallBtn');
const callModalOverlay = document.getElementById('callModalOverlay');
const callModalClose = document.getElementById('callModalClose');
const callModalForm = document.getElementById('callModalForm');
const callModalSuccess = document.getElementById('callModalSuccess');
const callModalError = document.getElementById('callModalError');
const phoneInput = document.getElementById('phoneInput');
const phoneError = document.getElementById('phoneError');
const callSubmitBtn = document.getElementById('callSubmitBtn');
const callSubmitLoader = document.getElementById('callSubmitLoader');
const callDoneBtn = document.getElementById('callDoneBtn');
const callRetryBtn = document.getElementById('callRetryBtn');
const callErrorMsg = document.getElementById('callErrorMsg');


// ─── Call Modal Logic ───────────────────────────────────────────────────────

function openCallModal() {
    callModalOverlay.classList.add('visible');
    resetCallModal();
    // Focus phone input after animation
    setTimeout(() => phoneInput.focus(), 350);
}

function closeCallModal() {
    callModalOverlay.classList.remove('visible');
}

function resetCallModal() {
    callModalForm.style.display = 'block';
    callModalSuccess.style.display = 'none';
    callModalError.style.display = 'none';
    phoneInput.value = '';
    phoneError.textContent = '';
    callSubmitBtn.disabled = true;
    callSubmitBtn.classList.remove('loading');
}

function showCallSuccess() {
    callModalForm.style.display = 'none';
    callModalError.style.display = 'none';
    callModalSuccess.style.display = 'block';
}

function showCallError(message) {
    callModalForm.style.display = 'none';
    callModalSuccess.style.display = 'none';
    callModalError.style.display = 'block';
    callErrorMsg.textContent = message || 'Unable to initiate the call. Please try again.';
}

function validatePhone(value) {
    // Only allow digits
    const digits = value.replace(/\D/g, '');
    // Indian mobile numbers: 10 digits starting with 6-9
    if (digits.length === 0) return '';
    if (digits.length < 10) return 'Please enter a 10-digit mobile number';
    if (!/^[6-9]\d{9}$/.test(digits)) return 'Please enter a valid Indian mobile number';
    return '';
}

async function submitCallRequest() {
    const digits = phoneInput.value.replace(/\D/g, '');
    const error = validatePhone(digits);

    if (error) {
        phoneError.textContent = error;
        return;
    }

    // Show loading
    callSubmitBtn.classList.add('loading');
    callSubmitBtn.disabled = true;
    phoneError.textContent = '';

    try {
        const data = await api('/api/request-call', {
            method: 'POST',
            body: JSON.stringify({ phone_number: digits }),
        });

        if (data.success) {
            showCallSuccess();
        } else {
            showCallError(data.detail || 'Failed to initiate call.');
        }
    } catch (err) {
        console.error('Call request error:', err);
        // Try to extract error detail from API response
        let errorMessage = 'Unable to initiate the call. Please check your number and try again.';
        try {
            const errorData = await err.response?.json();
            if (errorData?.detail) errorMessage = errorData.detail;
        } catch {}
        showCallError(errorMessage);
    } finally {
        callSubmitBtn.classList.remove('loading');
        callSubmitBtn.disabled = false;
    }
}

// ─── Call Modal Event Listeners ─────────────────────────────────────────────

// Open modal
requestCallBtn.addEventListener('click', openCallModal);

// Close modal
callModalClose.addEventListener('click', closeCallModal);
callModalOverlay.addEventListener('click', (e) => {
    if (e.target === callModalOverlay) closeCallModal();
});

// Close with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && callModalOverlay.classList.contains('visible')) {
        closeCallModal();
    }
});

// Phone input validation
phoneInput.addEventListener('input', (e) => {
    // Only allow digits
    e.target.value = e.target.value.replace(/\D/g, '');
    const digits = e.target.value;
    const error = validatePhone(digits);
    phoneError.textContent = digits.length > 0 ? error : '';
    callSubmitBtn.disabled = digits.length !== 10 || error !== '';
});

// Submit on Enter
phoneInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !callSubmitBtn.disabled) {
        e.preventDefault();
        submitCallRequest();
    }
});

// Submit button
callSubmitBtn.addEventListener('click', submitCallRequest);

// Done button (success state)
callDoneBtn.addEventListener('click', closeCallModal);

// Retry button (error state)
callRetryBtn.addEventListener('click', () => {
    resetCallModal();
    setTimeout(() => phoneInput.focus(), 100);
});


// ─── Initialization ─────────────────────────────────────────────────────────

async function init() {
    await loadSessions();

    // If there are existing sessions, load the most recent one
    const data = await api('/api/sessions');
    if (data.sessions && data.sessions.length > 0) {
        const latestSession = data.sessions[0];
        currentSessionId = latestSession.id;
        await loadSessions(); // Refresh to highlight active
        await loadMessages(latestSession.id);
    }
}

// Start
init();
