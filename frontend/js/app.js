/* -------------------------------------------------------------
   Clinical RCG Scientific Assistant Javascript Main Core
   Handles: Auth, Document Management, Document-centric Chat, SSE Streaming
   ------------------------------------------------------------- */

// Determine API base dynamically to support both Docker compose (with Nginx proxy) and local dev
const API_BASE = (window.location.port === "3000" && !window.location.pathname.startsWith('/api') && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"))
  ? "http://localhost:8000/api"
  : "/api";
let currentToken = localStorage.getItem("token") || null;
let currentUsername = localStorage.getItem("username") || null;
let activeDocumentId = null;
let allDocuments = [];

// Toast Alerts
function showToast(message, duration = 3000) {
    const toast = document.getElementById("alert-toast");
    const toastMsg = document.getElementById("alert-toast-message");
    toastMsg.textContent = message;
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, duration);
}

// Check Authentication State on load
function checkAuth() {
    const authContainer = document.getElementById("auth-container");
    const appContainer = document.getElementById("app-container");
    const userDisplay = document.getElementById("user-display");

    if (currentToken) {
        authContainer.classList.add("hidden");
        appContainer.classList.remove("hidden");
        userDisplay.textContent = currentUsername;
        loadDocuments();
    } else {
        authContainer.classList.remove("hidden");
        appContainer.classList.add("hidden");
    }
}

// -------------------------------------------------------------
// Authentication Event Handlers & API Calls
// -------------------------------------------------------------
async function handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById("login-username").value;
    const passwordInput = document.getElementById("login-password").value;

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: usernameInput, password: passwordInput })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Authentication failed");
        }

        const data = await response.json();
        currentToken = data.access_token;
        currentUsername = data.username;
        localStorage.setItem("token", currentToken);
        localStorage.setItem("username", currentUsername);
        
        showToast(`Welcome back, ${currentUsername}!`);
        checkAuth();
    } catch (err) {
        showToast(err.message);
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const usernameInput = document.getElementById("register-username").value;
    const passwordInput = document.getElementById("register-password").value;

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: usernameInput, password: passwordInput })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Registration failed");
        }

        const data = await response.json();
        currentToken = data.access_token;
        currentUsername = data.username;
        localStorage.setItem("token", currentToken);
        localStorage.setItem("username", currentUsername);

        showToast("Account created successfully!");
        checkAuth();
    } catch (err) {
        showToast(err.message);
    }
}

function handleLogout() {
    currentToken = null;
    currentUsername = null;
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    activeDocumentId = null;
    allDocuments = [];
    updateActiveDocumentUI();
    showToast("Logged out successfully");
    checkAuth();
}

// -------------------------------------------------------------
// Document Management
// -------------------------------------------------------------
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });

        if (!response.ok) throw new Error("Failed to load documents");

        allDocuments = await response.json();
        renderDocumentsTable(allDocuments);
    } catch (err) {
        showToast(err.message);
    }
}

function renderDocumentsTable(documents) {
    const tbody = document.getElementById("documents-tbody");
    tbody.innerHTML = "";

    if (documents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--color-text-muted);">No documents found. Upload one to get started.</td></tr>`;
        return;
    }

    documents.forEach(doc => {
        const formattedDate = new Date(doc.created_at).toLocaleDateString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric'
        });

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td style="font-weight: 500;">${doc.filename}</td>
            <td><span class="badge-status ${doc.status}">${doc.status}</span></td>
            <td>${doc.page_count}</td>
            <td>${formattedDate}</td>
            <td class="action-links">
                <a class="chat-doc-btn" data-id="${doc.id}" data-name="${doc.filename}" data-status="${doc.status}">Chat</a>
                <a class="delete-doc-btn" data-id="${doc.id}">Delete</a>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Add event listeners to chat buttons
    document.querySelectorAll(".chat-doc-btn").forEach(link => {
        link.addEventListener("click", (e) => {
            const id = e.target.getAttribute("data-id");
            const name = e.target.getAttribute("data-name");
            const status = e.target.getAttribute("data-status");
            openDocumentChat(id, name, status);
        });
    });

    // Add event listeners to delete buttons
    document.querySelectorAll(".delete-doc-btn").forEach(link => {
        link.addEventListener("click", (e) => {
            const id = e.target.getAttribute("data-id");
            deleteDocument(id);
        });
    });
}

function updateActiveDocumentUI() {
    const placeholder = document.getElementById("active-doc-placeholder");
    const chipsContainer = document.getElementById("active-doc-chip");
    const chatTrigger = document.getElementById("btn-chat-trigger");
    const chatScopedSub = document.getElementById("chat-scoped-sub");
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("btn-send-chat");

    if (!activeDocumentId) {
        placeholder.classList.remove("hidden");
        chipsContainer.classList.add("hidden");
        chatTrigger.classList.add("hidden");
        document.getElementById("chat-sidebar").classList.remove("open");
        chatScopedSub.textContent = "Document: None selected";
        chatInput.disabled = true;
        sendBtn.disabled = true;
    } else {
        const doc = allDocuments.find(d => d.id === activeDocumentId);
        if (doc) {
            placeholder.classList.add("hidden");
            chipsContainer.classList.remove("hidden");
            chatTrigger.classList.remove("hidden");
            chatScopedSub.textContent = `Document: ${doc.filename}`;
            
            chipsContainer.innerHTML = `
                <div class="chip animate-fade">
                    <span>${doc.filename}</span>
                    <span class="remove-chip" data-id="${doc.id}">&times;</span>
                </div>
            `;

            // Enable chat if document is ready
            if (doc.status === "ready") {
                chatInput.disabled = false;
                sendBtn.disabled = false;
                chatInput.placeholder = "Ask a question about this document...";
            } else {
                chatInput.disabled = true;
                sendBtn.disabled = true;
                chatInput.placeholder = "Document is being processed...";
            }

            // Add remove click event
            document.querySelectorAll(".remove-chip").forEach(removeBtn => {
                removeBtn.addEventListener("click", (e) => {
                    const id = e.target.getAttribute("data-id");
                    activeDocumentId = null;
                    updateActiveDocumentUI();
                });
            });
        }
    }
}

async function deleteDocument(documentId) {
    if (!confirm("Are you sure you want to delete this document?")) return;

    try {
        const response = await fetch(`${API_BASE}/documents/${documentId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${currentToken}` }
        });

        if (!response.ok) throw new Error("Failed to delete document");

        showToast("Document deleted successfully");
        if (activeDocumentId === documentId) {
            activeDocumentId = null;
            updateActiveDocumentUI();
        }
        loadDocuments();
    } catch (err) {
        showToast(err.message);
    }
}

// -------------------------------------------------------------
// Document Upload
// -------------------------------------------------------------
async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(`${API_BASE}/documents/upload`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${currentToken}` },
            body: formData
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Upload failed");
        }

        showToast("PDF uploaded! Ingestion pipeline started.");
        document.getElementById("upload-doc-modal").classList.add("hidden");
        loadDocuments();
    } catch (err) {
        showToast(err.message);
    }
}

function pollDocumentStatus(docId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/documents/${docId}/status`, {
                headers: { "Authorization": `Bearer ${currentToken}` }
            });
            if (!response.ok) return;

            const data = await response.json();
            
            // Update document in allDocuments array
            const docIndex = allDocuments.findIndex(d => d.id === docId);
            if (docIndex !== -1) {
                allDocuments[docIndex].status = data.status;
                allDocuments[docIndex].page_count = data.page_count;
                renderDocumentsTable(allDocuments);
            }

            // Update active document UI if this is the active document
            if (activeDocumentId === docId) {
                updateActiveDocumentUI();
            }

            if (data.status === "ready" || data.status === "error") {
                clearInterval(interval);
            }
        } catch (e) {
            console.error("Polling error", e);
            clearInterval(interval);
        }
    }, 2000);
}

// -------------------------------------------------------------
// Document Chat Interface
// -------------------------------------------------------------
async function openDocumentChat(documentId, documentName, status) {
    activeDocumentId = documentId;
    updateActiveDocumentUI();
    
    const chatSidebar = document.getElementById("chat-sidebar");
    chatSidebar.classList.add("open");
    
    // Update chat scope info
    const chatScopeInfo = document.getElementById("chat-scope-info");
    chatScopeInfo.innerHTML = `
        <div class="chip animate-fade">
            <span>${documentName}</span>
        </div>
    `;

    // Clear and reload chat messages
    const chatMessages = document.getElementById("chat-messages");
    chatMessages.innerHTML = "";

    if (status === "ready") {
        // Load chat history
        await loadChatHistory(documentId);
    } else {
        chatMessages.innerHTML = `
            <div class="message assistant-message glass-message">
                <p>Document is being processed. Please wait until the status changes to "ready" before asking questions.</p>
            </div>
        `;
    }
}

async function loadChatHistory(documentId) {
    const chatMessages = document.getElementById("chat-messages");
    
    try {
        const response = await fetch(`${API_BASE}/documents/${documentId}/chat-history`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });

        if (!response.ok) throw new Error("Failed to load chat history");

        const data = await response.json();
        
        if (data.messages.length === 0) {
            chatMessages.innerHTML = `
                <div class="message assistant-message glass-message">
                    <p>Hello! I am your RCG Scientific Assistant. I have indexed this document.</p>
                    <p>Ask me anything regarding the content, results, demographics, endpoints, or any other information from this document.</p>
                </div>
            `;
        } else {
            data.messages.forEach(msg => {
                const className = msg.role === "user" ? "user-message" : "assistant-message";
                const msgDiv = document.createElement("div");
                msgDiv.className = `message ${className} animate-fade`;
                
                if (msg.role === "assistant") {
                    msgDiv.innerHTML = `<p>${formatMessageContent(msg.content)}</p>`;
                } else {
                    msgDiv.innerHTML = `<p>${msg.content}</p>`;
                }
                
                chatMessages.appendChild(msgDiv);
            });
            scrollChatToBottom();
        }
    } catch (err) {
        console.error("Error loading chat history:", err);
        chatMessages.innerHTML = `
            <div class="message assistant-message glass-message">
                <p>Hello! I am your RCG Scientific Assistant. I have indexed this document.</p>
                <p>Ask me anything regarding the content, results, demographics, endpoints, or any other information from this document.</p>
            </div>
        `;
    }
}

// -------------------------------------------------------------
// Chat AI Assistant & SSE Streaming
// -------------------------------------------------------------
async function handleSendChat(e) {
    e.preventDefault();
    const chatInput = document.getElementById("chat-input");
    const queryText = chatInput.value.trim();
    if (!queryText || !activeDocumentId) return;

    chatInput.value = "";
    
    // Render User Message
    appendMessage(queryText, "user-message");
    
    // Render Assistant Message Placeholder
    const assistantMsgElement = appendMessage("", "assistant-message");
    assistantMsgElement.innerHTML = `<p class="typing-indicator">Analyzing document...</p>`;
    
    // Clear sources carousel
    const sourcesPreview = document.getElementById("sources-preview");
    const sourcesCarousel = document.getElementById("sources-carousel");
    sourcesPreview.classList.add("hidden");
    sourcesCarousel.innerHTML = "";

    try {
        const response = await fetch(`${API_BASE}/chat/query`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${currentToken}`
            },
            body: JSON.stringify({
                query: queryText,
                document_id: activeDocumentId
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to query assistant");
        }

        // Parse SSE Stream chunk by chunk
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalAnswer = "";
        let currentEvent = "";
        
        assistantMsgElement.innerHTML = ""; // Remove typing indicator

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // Keep incomplete lines

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;

                if (trimmed.startsWith("event:")) {
                    currentEvent = trimmed.replace("event:", "").trim();
                } else if (trimmed.startsWith("data:")) {
                    const data = trimmed.replace("data:", "").trim();
                    
                    if (currentEvent === "token") {
                        // Append token
                        finalAnswer += data;
                        // Format formatting like newlines
                        assistantMsgElement.innerHTML = formatMessageContent(finalAnswer);
                        scrollChatToBottom();
                    } else if (currentEvent === "sources") {
                        const sources = JSON.parse(data);
                        renderSourcesList(sources);
                    } else if (currentEvent === "error") {
                        assistantMsgElement.innerHTML = `<p style="color: var(--status-error);">${data}</p>`;
                    }
                }
            }
        }
    } catch (err) {
        assistantMsgElement.innerHTML = `<p style="color: var(--status-error);">Error: ${err.message}</p>`;
    }
}

function appendMessage(text, className) {
    const container = document.getElementById("chat-messages");
    const msg = document.createElement("div");
    msg.className = `message ${className} animate-fade`;
    msg.innerHTML = `<p>${text}</p>`;
    container.appendChild(msg);
    scrollChatToBottom();
    return msg;
}

function scrollChatToBottom() {
    const container = document.getElementById("chat-messages");
    container.scrollTop = container.scrollHeight;
}

// Format newline characters to HTML breaks and clean basic bold/list tags from LLM output
function formatMessageContent(text) {
    let html = text
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>");
    
    // Formatting bullet points: lines starting with "- " or "* "
    html = html.replace(/^(?:-\s|\*\s)(.*?)(?:<br>|$)/gmi, "<li>$1</li>");
    // Group lists
    html = html.replace(/(<li>.*?<\/li>)/gs, "<ul>$1</ul>");
    
    return html;
}

function renderSourcesList(sources) {
    const sourcesPreview = document.getElementById("sources-preview");
    const sourcesCarousel = document.getElementById("sources-carousel");

    if (sources.length === 0) {
        sourcesPreview.classList.add("hidden");
        return;
    }

    sourcesPreview.classList.remove("hidden");
    sourcesCarousel.innerHTML = "";

    sources.forEach((src, idx) => {
        const card = document.createElement("div");
        card.className = "source-card";
        card.setAttribute("title", src.content_snippet);
        card.innerHTML = `
            <div class="source-card-file">[Source ${idx + 1}] ${src.filename}</div>
            <div class="source-card-page">Page ${src.page_number} (${src.content_type})</div>
        `;
        card.addEventListener("click", () => {
            showToast(`Snippet: "${src.content_snippet}"`, 6000);
        });
        sourcesCarousel.appendChild(card);
    });
}

// -------------------------------------------------------------
// Bind All Page Event Listeners
// -------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    // Check initial auth
    checkAuth();

    // Toggle Forms
    document.getElementById("go-to-register").addEventListener("click", (e) => {
        e.preventDefault();
        document.getElementById("login-form").classList.add("hidden");
        document.getElementById("register-form").classList.remove("hidden");
    });
    
    document.getElementById("go-to-login").addEventListener("click", (e) => {
        e.preventDefault();
        document.getElementById("login-form").classList.remove("hidden");
        document.getElementById("register-form").classList.add("hidden");
    });

    // Form Submissions
    document.getElementById("login-form").addEventListener("submit", handleLogin);
    document.getElementById("register-form").addEventListener("submit", handleRegister);
    document.getElementById("btn-logout").addEventListener("click", handleLogout);
    document.getElementById("chat-form").addEventListener("submit", handleSendChat);

    // Document Upload Modal
    const uploadModal = document.getElementById("upload-doc-modal");
    document.getElementById("btn-upload-doc-modal").addEventListener("click", () => uploadModal.classList.remove("hidden"));
    document.getElementById("btn-close-upload-modal").addEventListener("click", () => uploadModal.classList.add("hidden"));

    // Sidebar Chat drawer
    const chatSidebar = document.getElementById("chat-sidebar");
    document.getElementById("btn-chat-trigger").addEventListener("click", () => chatSidebar.classList.add("open"));
    document.getElementById("btn-close-chat").addEventListener("click", () => chatSidebar.classList.remove("open"));

    // Upload drag and drop
    const dropzone = document.getElementById("upload-dropzone");
    const fileInput = document.getElementById("doc-file-input");

    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) uploadFile(e.target.files[0]);
    });

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "var(--accent-purple)";
    });
    
    dropzone.addEventListener("dragleave", () => {
        dropzone.style.borderColor = "rgba(255, 255, 255, 0.15)";
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "rgba(255, 255, 255, 0.15)";
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    // Search filter
    document.getElementById("document-search").addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        const filtered = allDocuments.filter(doc => 
            doc.filename.toLowerCase().includes(query)
        );
        renderDocumentsTable(filtered);
    });
});
