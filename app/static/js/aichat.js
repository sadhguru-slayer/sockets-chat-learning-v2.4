const API_BASE = "http://127.0.0.1:8000";

const chatMessages = document.getElementById("chatMessages");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const newChatBtn = document.getElementById("newChatBtn");

/* -----------------------------
   ADD MESSAGE (SAFE RENDER)
------------------------------*/
function addUserMessage(text) {
    const div = document.createElement("div");
    div.classList.add("message", "user");
    div.textContent = text;
    chatMessages.appendChild(div);
}

/* -----------------------------
   ADD AI MESSAGE (MARKDOWN + HIGHLIGHT)
------------------------------*/
function addAIMessage(markdownText) {
    const div = document.createElement("div");
    div.classList.add("message", "ai");

    // Convert markdown → HTML
    div.innerHTML = marked.parse(markdownText);

    chatMessages.appendChild(div);

    // Highlight code blocks
    div.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });
}

/* -----------------------------
   ADD THINKING BLOCK
------------------------------*/
function addThinking(text) {
    const div = document.createElement("div");
    div.classList.add("message", "thinking");

    div.innerHTML = `
        <strong>Thinking:</strong><br>
        ${text.replace(/\n/g, "<br>")}
    `;

    chatMessages.appendChild(div);
}

/* -----------------------------
   SEND MESSAGE
------------------------------*/
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    addUserMessage(message);
    messageInput.value = "";

    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        // Thinking (optional)
        if (data.thinking) {
            addThinking(data.thinking);
        }

        // AI response (Markdown)
        if (data.response) {
            addAIMessage(data.response);
        }

        chatMessages.scrollTop = chatMessages.scrollHeight;

    } catch (error) {
        console.error("Error:", error);

        addAIMessage("❌ Error connecting to server.");
    }
}

/* -----------------------------
   NEW CHAT
------------------------------*/
async function newChat() {
    try {
        await fetch(`${API_BASE}/new-chat`, {
            method: "POST"
        });

        chatMessages.innerHTML = "";

        addAIMessage("🆕 New conversation started.");

    } catch (error) {
        console.error(error);
    }
}

/* -----------------------------
   EVENTS
------------------------------*/
sendBtn.addEventListener("click", sendMessage);

messageInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        sendMessage();
    }
});

newChatBtn.addEventListener("click", newChat);