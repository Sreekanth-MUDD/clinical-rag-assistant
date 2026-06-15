/* -------------------------------------------------------------
   Sanofi RCG Scientific Assistant Javascript Main Core
   Handles: Auth, Experiment CRUD, Document Uploads, SSE Streaming
   ------------------------------------------------------------- */

const API_BASE = "http://localhost:8000/api";
let currentToken = localStorage.getItem("token") || null;
let currentUsername = localStorage.getItem("username") || null;
let selectedExperiments = new Set();
let allExperiments = [];
let activeUploadExpId = null;

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
        loadExperiments();
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
    selectedExperiments.clear();
    updateScopeSelectionUI();
    showToast("Logged out successfully");
    checkAuth();
}

// -------------------------------------------------------------
// Experiment Run management
// -------------------------------------------------------------
async function loadExperiments() {
    try {
        const response = await fetch(`${API_BASE}/experiments`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });

        if (!response.ok) throw new Error("Failed to load experiments");

        allExperiments = await response.json();
        renderExperimentsTable(allExperiments);
    } catch (err) {
        showToast(err.message);
    }
}

function renderExperimentsTable(experiments) {
    const tbody = document.getElementById("experiments-tbody");
    tbody.innerHTML = "";

    if (experiments.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--color-text-muted);">No RCG experiments found. Create one to get started.</td></tr>`;
        return;
    }

    experiments.forEach(exp => {
        const isChecked = selectedExperiments.has(exp.id) ? "checked" : "";
        const formattedDate = new Date(exp.created_at).toLocaleDateString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric'
        });

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><input type="checkbox" class="exp-checkbox" data-id="${exp.id}" ${isChecked}></td>
            <td style="font-weight: 500;">${exp.name}</td>
            <td>${exp.disease_area}</td>
            <td style="font-size: 0.85rem; color: var(--color-text-secondary);">${exp.model_type}</td>
            <td><span class="badge-status completed">${exp.status}</span></td>
            <td>${formattedDate}</td>
            <td class="action-links">
                <a class="manage-docs-btn" data-id="${exp.id}" data-name="${exp.name}">Docs / Ingestion</a>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Add event listeners to checkboxes
    document.querySelectorAll(".exp-checkbox").forEach(chk => {
        chk.addEventListener("change", (e) => {
            const expId = e.target.getAttribute("data-id");
            if (e.target.checked) {
                selectedExperiments.add(expId);
            } else {
                selectedExperiments.delete(expId);
            }
            updateScopeSelectionUI();
        });
    });

    // Add event listeners to manage docs links
    document.querySelectorAll(".manage-docs-btn").forEach(link => {
        link.addEventListener("click", (e) => {
            const id = e.target.getAttribute("data-id");
            const name = e.target.getAttribute("data-name");
            openDocsModal(id, name);
        });
    });
}

function updateScopeSelectionUI() {
    const selectedCount = selectedExperiments.size;
    const placeholder = document.getElementById("selected-list-placeholder");
    const chipsContainer = document.getElementById("selected-experiments-chips");
    const chatTrigger = document.getElementById("btn-chat-trigger");
    const chatScopedSub = document.getElementById("chat-scoped-sub");
    
    // Scoped Sub display
    chatScopedSub.textContent = `Scoped: ${selectedCount} experiment(s)`;

    if (selectedCount === 0) {
        placeholder.classList.remove("hidden");
        chipsContainer.classList.add("hidden");
        chatTrigger.classList.add("hidden");
        document.getElementById("chat-sidebar").classList.remove("open");
    } else {
        placeholder.classList.add("hidden");
        chipsContainer.classList.remove("hidden");
        chatTrigger.classList.remove("hidden");
        
        chipsContainer.innerHTML = "";
        selectedExperiments.forEach(id => {
            const exp = allExperiments.find(e => e.id === id);
            if (exp) {
                const chip = document.createElement("div");
                chip.className = "chip animate-fade";
                chip.innerHTML = `
                    <span>${exp.name}</span>
                    <span class="remove-chip" data-id="${id}">&times;</span>
                `;
                chipsContainer.appendChild(chip);
            }
        });

        // Add remove click event
        document.querySelectorAll(".remove-chip").forEach(removeBtn => {
            removeBtn.addEventListener("click", (e) => {
                const id = e.target.getAttribute("data-id");
                selectedExperiments.delete(id);
                // Uncheck in table
                const checkbox = document.querySelector(`.exp-checkbox[data-id="${id}"]`);
                if (checkbox) checkbox.checked = false;
                
                updateScopeSelectionUI();
            });
        });
    }
}

async function handleCreateExperiment(e) {
    e.preventDefault();
    const name = document.getElementById("exp-name").value;
    const disease = document.getElementById("exp-disease").value;
    const modelType = document.getElementById("exp-model-type").value;

    try {
        const response = await fetch(`${API_BASE}/experiments`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${currentToken}`
            },
            body: JSON.stringify({ name, disease_area: disease, model_type: modelType })
        });

        if (!response.ok) throw new Error("Failed to create experiment");

        showToast("Experiment run created!");
        document.getElementById("new-experiment-modal").classList.add("hidden");
        document.getElementById("new-experiment-form").reset();
        loadExperiments();
    } catch (err) {
        showToast(err.message);
    }
}

// -------------------------------------------------------------
// Documents / Ingestion
// -------------------------------------------------------------
async function openDocsModal(experimentId, experimentName) {
    activeUploadExpId = experimentId;
    document.getElementById("docs-modal-title").textContent = `Clinical Documents: ${experimentName}`;
    document.getElementById("docs-modal").classList.remove("hidden");
    loadDocuments(experimentId);
}

async function loadDocuments(experimentId) {
    const docList = document.getElementById("docs-scroll-list");
    docList.innerHTML = `<p style="text-align: center; color: var(--color-text-muted); padding: 20px;">Fetching documents...</p>`;

    try {
        const response = await fetch(`${API_BASE}/experiments/${experimentId}/documents`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });

        if (!response.ok) throw new Error("Failed to fetch documents");

        const documents = await response.json();
        renderDocumentsList(documents);
    } catch (err) {
        docList.innerHTML = `<p style="text-align: center; color: var(--status-error); padding: 20px;">${err.message}</p>`;
    }
}

function renderDocumentsList(documents) {
    const docList = document.getElementById("docs-scroll-list");
    docList.innerHTML = "";

    if (documents.length === 0) {
        docList.innerHTML = `<p style="text-align: center; color: var(--color-text-muted); padding: 20px;">No documents uploaded to this experiment yet.</p>`;
        return;
    }

    documents.forEach(doc => {
        const item = document.createElement("div");
        item.className = "doc-list-item";
        item.innerHTML = `
            <div class="doc-info">
                <span class="doc-name">${doc.filename}</span>
                <span class="doc-meta">Pages: ${doc.page_count} | Uploaded: ${new Date(doc.created_at).toLocaleDateString()}</span>
            </div>
            <span class="badge-status ${doc.status}" id="doc-status-${doc.id}">${doc.status}</span>
        `;
        docList.appendChild(item);

        // If processing or pending, poll status
        if (doc.status === "pending" || doc.status === "processing") {
            pollDocumentStatus(doc.id);
        }
    });
}

function pollDocumentStatus(docId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/documents/${docId}/status`, {
                headers: { "Authorization": `Bearer ${currentToken}` }
            });
            if (!response.ok) return;

            const data = await response.json();
            const badge = document.getElementById(`doc-status-${docId}`);
            if (badge) {
                badge.className = `badge-status ${data.status}`;
                badge.textContent = data.status;
            }

            if (data.status === "ready" || data.status === "error") {
                clearInterval(interval);
                // Reload list to get updated page count
                if (activeUploadExpId) {
                    loadDocuments(activeUploadExpId);
                }
            }
        } catch (e) {
            console.error("Polling error", e);
            clearInterval(interval);
        }
    }, 2000);
}

async function uploadFile(file) {
    if (!activeUploadExpId) return;

    const formData = new FormData();
    formData.append("file", file);

    const docList = document.getElementById("docs-scroll-list");
    const progressMsg = document.createElement("div");
    progressMsg.style.padding = "10px";
    progressMsg.style.color = "var(--accent-purple)";
    progressMsg.textContent = "Uploading PDF clinical document...";
    docList.prepend(progressMsg);

    try {
        const response = await fetch(`${API_BASE}/experiments/${activeUploadExpId}/upload`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${currentToken}` },
            body: formData
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Upload failed");
        }

        showToast("PDF Uploaded! Ingestion pipeline started.");
        loadDocuments(activeUploadExpId);
    } catch (err) {
        showToast(err.message);
        loadDocuments(activeUploadExpId);
    }
}

// -------------------------------------------------------------
// Chat AI Assistant & SSE Streaming
// -------------------------------------------------------------
async function handleSendChat(e) {
    e.preventDefault();
    const chatInput = document.getElementById("chat-input");
    const queryText = chatInput.value.trim();
    if (!queryText || selectedExperiments.size === 0) return;

    chatInput.value = "";
    
    // Render User Message
    appendMessage(queryText, "user-message");
    
    // Render Assistant Message Placeholder
    const assistantMsgElement = appendMessage("", "assistant-message");
    assistantMsgElement.innerHTML = `<p class="typing-indicator">Analyzing context documents...</p>`;
    
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
                experiment_ids: Array.from(selectedExperiments)
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
    document.getElementById("new-experiment-form").addEventListener("submit", handleCreateExperiment);
    document.getElementById("chat-form").addEventListener("submit", handleSendChat);

    // Modals control
    const expModal = document.getElementById("new-experiment-modal");
    document.getElementById("btn-new-exp-modal").addEventListener("click", () => expModal.classList.remove("hidden"));
    document.getElementById("btn-close-modal").addEventListener("click", () => expModal.classList.add("hidden"));
    document.getElementById("btn-cancel-modal").addEventListener("click", () => expModal.classList.add("hidden"));

    const docsModal = document.getElementById("docs-modal");
    document.getElementById("btn-close-docs-modal").addEventListener("click", () => {
        docsModal.classList.add("hidden");
        activeUploadExpId = null;
        loadExperiments(); // Reload to refresh table statuses if changed
    });

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

    // Check All Checkbox
    document.getElementById("check-all-experiments").addEventListener("change", (e) => {
        const checkboxes = document.querySelectorAll(".exp-checkbox");
        checkboxes.forEach(chk => {
            chk.checked = e.target.checked;
            const id = chk.getAttribute("data-id");
            if (e.target.checked) {
                selectedExperiments.add(id);
            } else {
                selectedExperiments.delete(id);
            }
        });
        updateScopeSelectionUI();
    });

    // Search filter
    document.getElementById("experiment-search").addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        const filtered = allExperiments.filter(exp => 
            exp.name.toLowerCase().includes(query) || 
            exp.disease_area.toLowerCase().includes(query) ||
            exp.model_type.toLowerCase().includes(query)
        );
        renderExperimentsTable(filtered);
    });
});
