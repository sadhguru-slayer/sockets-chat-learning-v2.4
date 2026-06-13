const API_URL = "http://127.0.0.1:8000";
let socket = null;
let me = null;
// ================= DOM =================
const tabs = document.querySelectorAll(".tab-btn");
const conversationList = document.getElementById("conversationList");
const addBtn = document.getElementById("addBtn");

const conversationTitle = document.getElementById("conversationTitle");
const menuBtn = document.getElementById("menuBtn");
const menuDropdown = document.getElementById("menuDropdown");
const leaveGroupBtn = document.getElementById("leaveGroupBtn");
const addMembersBtn = document.getElementById("addMembersBtn");

// modals
const actionModal = document.getElementById("actionModal");
const createModal = document.getElementById("createModal");
const joinModal = document.getElementById("joinModal");

// action modal
const openCreateBtn = document.getElementById("openCreateBtn");
const openJoinBtn = document.getElementById("openJoinBtn");
const actionCancelBtn = document.getElementById("actionCancelBtn");

// create modal
const createGroupName = document.getElementById("createGroupName");
const createParticipants = document.getElementById("createParticipants");
const createCancelBtn = document.getElementById("createCancelBtn");
const createSubmitBtn = document.getElementById("createSubmitBtn");

// join modal
const joinConversationId = document.getElementById("joinConversationId");
const joinCancelBtn = document.getElementById("joinCancelBtn");
const joinSubmitBtn = document.getElementById("joinSubmitBtn");

// WS
let latestOnlineUsers = [];
const inputSection = document.getElementById("message-input-container");
const messageInput = document.querySelector(".message-input-container input");
const sendBtn = document.querySelector(".message-input-container button");
let typingTimer = null;
// ================= STATE =================
let activeTab = "groups";
let selectedConversation = null;

const data = {
  chats: [],
  groups: []
};

// ================= INIT =================
document.addEventListener("DOMContentLoaded", async () => {
  await requireAuth();
  me = await getMe();
  
  await fetchGroups();
  renderList();
});




// ================= HELPERS =================

function formatTime(ts) {
    if (!ts) return "";

    return new Date(ts).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
    });
}
function isMe(sender_id) {
return sender_id === me.id;
}

function getMessageMeta(msg) {
    return {
        isMe: msg.sender_id === me.id,
        isSystem: msg.type === "SYSTEM" || msg.type === "system",
    };
}

function show(el) {
  el.classList.remove("hidden");
}

function hide(el) {
  el.classList.add("hidden");
}

// ================= FETCH GROUPS =================
async function fetchGroups() {
  try {
    const response = await fetch(`${API_URL}/chat/groups`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    if (!response.ok) {
  if (response.status === 401) {
    window.location.href = "/login";
    return;
  }
  throw new Error("Failed to load groups");
}
    const groups = await response.json();

    data.groups = groups.map(group => ({
      id: group.id,
      name: group.title,
      type: group.type,
      role:group.role
    }));

    if (activeTab === "groups") {
      renderList();
    }
  } catch (err) {
    console.error(err);
    alert(err.message);
  }
}

async function fetchParticipants(groupId) {
    try {
        const response = await fetch(
            `${API_URL}/chat/groups/${groupId}/fetch-members`,
            {
                headers: {
                    Authorization:
                        `Bearer ${token}`
                }
            }
        );

        const members =
            await response.json();

        selectedConversation.members =
            members;

        return members;
    } catch (err) {
        console.error(err);
        return [];
    }
}

// ================= RENDER =================
function renderList() {
  conversationList.innerHTML = "";

  const conversations = data[activeTab];

  if (!conversations.length) {
    conversationList.innerHTML = "<p>No conversations found</p>";
    return;
  }

  conversations.forEach(item => {
    const div = document.createElement("div");
    div.className = "conversation-item";

    if (selectedConversation && selectedConversation.id === item.id) {
      div.classList.add("active");
    }

    div.innerHTML = `<strong>${item.name}</strong>`;

    div.addEventListener("click", () => {
      selectConversation(item);
    });

    conversationList.appendChild(div);
  });
}

// ===================== WS ================
async function connectWs(conversation) {
  // close previous socket
  if (socket) {
    socket.close();
    socket = null;
  }

  socket = new WebSocket(
    `ws://127.0.0.1:8000/ws/${conversation.id}?token=${token}`
  );

  socket.onopen = () => {
    console.log("WebSocket connected:", conversation.id);
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // console.log("PARSED WS:", data);
    if (data.event === "online_users") {
      latestOnlineUsers = data.users;
      updateOnlineStatus(data.users);
    }
    if (data.event === "typing") {
  if (data.sender_id === me.id) return; // CRITICAL
      renderTypingIndicator(data);
}
const allowedEvents = ["message.created", "leave", "join"];

if (allowedEvents.includes(data.event)) {
    renderMessage({
        message: data.message,
        sender_id: data.sender_id,
        username: data.username,
        timestamp: data.timestamp,
        type: data.type || "CHAT"
    });
}
  };

  socket.onclose = (e) => {
    console.log("WebSocket closed:", e.code, e.reason);
    socket = null;
  };
}

function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || !socket) return;

  socket.send(JSON.stringify({
    event: "message.created",
    message: text
  }));

  messageInput.value = "";
}
// ============ TYPING ================



sendBtn.addEventListener("click", sendMessage);

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});
messageInput.addEventListener("input", () => {
  if (!socket) return;

  clearTimeout(typingTimer);

  typingTimer = setTimeout(() => {
    socket.send(JSON.stringify({
      event: "typing"
    }));
  }, 200); // adjust delay as needed (200–500ms is typical)
});


function renderMessage(msg) {
    const container = document.getElementById("messages");
  if (!container) {
        console.warn("messages container not mounted yet");
        return;
    }
    console.log(msg);
    const meta = getMessageMeta(msg);

    const div = document.createElement("div");

    if (meta.isSystem) {
        div.className = "message system";
        div.innerHTML = `
            <div class="system-bubble">
                ${escapeHtml(msg.message)}
                <span class="time">${formatTime(msg.timestamp)}</span>
            </div>
        `;
    }

    else if (meta.isMe) {
        div.className = "message me";
        div.innerHTML = `
            <div class="bubble me-bubble">
                <div class="text">${escapeHtml(msg.message)}</div>
                <div class="meta">
                    <span class="time">${formatTime(msg.timestamp)}</span>
                </div>
            </div>
        `;
    }

    else {
        div.className = "message other";
        div.innerHTML = `
            <div class="avatar-small">
                ${getInitials(msg.username || "U")}
            </div>

            <div class="bubble other-bubble">
                <div class="username">${escapeHtml(msg.username || "Unknown")}</div>
                <div class="text">${escapeHtml(msg.message)}</div>
                <div class="meta">
                    <span class="time">${formatTime(msg.timestamp)}</span>
                </div>
            </div>
        `;
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function loadConversationHistory() {
    if (!selectedConversation) return;

    const container = document.getElementById("messages");

    if (!container) {
        console.warn("messages container not found. Component not mounted.");
        return;
    }

    const response = await fetch(
        `${API_URL}/chat/conversations/${selectedConversation.id}/messages`,
        {
            headers: { Authorization: `Bearer ${token}` }
        }
    );

    const messages = await response.json();

    container.innerHTML = "";

    messages.forEach(msg => {
        renderMessage({
            message: msg.message,
            sender_id: msg.sender_id,
            username: msg.username,
            timestamp: msg.timestamp,
            type: msg.type
        });
    });
}

// ================= SELECT =================
async function selectConversation(conversation) {
  inputSection.classList = "message-input-container";
  selectedConversation = conversation;

  conversationTitle.textContent = conversation.name;
  leaveGroupBtn.style.display =
    conversation.type === "GROUP" ? "block" : "none";

  addMembersBtn.style.display =
    ["OWNER", "ADMIN"].includes(conversation.role)
      ? "block"
      : "none";
  // await loadMessagesView();
  menuBtn.classList.remove('hidden');
  await loadConversationHistory();
  await connectWs(conversation);
  renderList();
}

// ================ UPDATE ONLINE USERS ===============
function updateOnlineStatus(users) {
    const onlineSet = new Set(users.map(u => u.id));

    onlineSet.forEach(id => {
        const el = document.querySelector(`[data-user-id="${id}"]`);
        if (!el) return;

        const dot = el.querySelector(".status-dot");
        const text = el.querySelector(".status-text");

        if (dot) dot.className = "status-dot online";
        if (text) text.textContent = "Online";
    });

    document.querySelectorAll(".member-item").forEach(el => {
        const id = Number(el.dataset.userId);
        if (onlineSet.has(id)) return;

        const dot = el.querySelector(".status-dot");
        const text = el.querySelector(".status-text");

        if (dot) dot.className = "status-dot offline";
        if (text) text.textContent = "Offline";
    });
}
// ================= MODALS =================

// open main action modal
addBtn.addEventListener("click", () => {
  show(actionModal);
});

// choose create
openCreateBtn.addEventListener("click", () => {
  hide(actionModal);
  show(createModal);
});

// choose join
openJoinBtn.addEventListener("click", () => {
  hide(actionModal);
  show(joinModal);
});

// cancel action modal
actionCancelBtn.addEventListener("click", () => {
  hide(actionModal);
});

// cancel create
createCancelBtn.addEventListener("click", () => {
  hide(createModal);
});

// cancel join
joinCancelBtn.addEventListener("click", () => {
  hide(joinModal);
});

// ================= CREATE GROUP =================
createSubmitBtn.addEventListener("click", async () => {
  try {
    const title = createGroupName.value.trim();

    if (!title) return alert("Group name required");

    const participants = createParticipants.value
      .split(",")
      .map(id => Number(id.trim()))
      .filter(Boolean);

    const res = await fetch(`${API_URL}/chat/groups`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ title, participants })
    });

    const data = await res.json();

    if (!res.ok) {
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }
  throw new Error(data.detail);
}
    alert("Group created");

    hide(createModal);
    createGroupName.value = "";
    createParticipants.value = "";

    await fetchGroups();
  } catch (err) {
    alert(err.message);
  }
});

// ================= JOIN GROUP =================
joinSubmitBtn.addEventListener("click", async () => {
  try {
    const conversation_id = Number(joinConversationId.value);

    if (!conversation_id) return alert("Enter conversation ID");

    const res = await fetch(`${API_URL}/chat/groups/join`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ conversation_id })
    });

    const data = await res.json();

    if (!res.ok) {
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }
  throw new Error(data.detail);
}
    
    alert(data.message);

    hide(joinModal);
    joinConversationId.value = "";

    await fetchGroups();
  } catch (err) {
    alert(err.message);
  }
});
// ================= ADD MEMBERS ================

document.getElementById("addMembersBtn").addEventListener("click", async () => {
    // console.log("Clicked");

    const userId = prompt("Enter user ID");
    if (!userId) return;

    const response = await fetch(
        `${API_URL}/chat/groups/add-members`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({
                group_id: selectedConversation.id,
                participants: [Number(userId)]
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail);
        return;
    }

    // Success with no warnings
    if (data.status === "OK" && data.message.length === 0) {
        alert("Member added");
        return;
    }

    // Success but warnings/errors returned by backend
    if (data.status === "OK" && data.message.length > 0) {
        alert(data.message.join("\n"));
        return;
    }
});
// ================= LEAVE GROUP =================
leaveGroupBtn.addEventListener("click", async () => {
  if (!selectedConversation || selectedConversation.type !== "GROUP") return;

  const confirmed = confirm(`Leave ${selectedConversation.name}?`);
  if (!confirmed) return;

  try {
    const response = await fetch(
      `${API_URL}/chat/groups/${selectedConversation.id}/leave`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );

    const result = await response.json();

    if (!response.ok) throw new Error(result.detail);

    alert(result.message);

    selectedConversation = null;
    conversationTitle.textContent = "Select Chat";
    messagesContainer.innerHTML="";
    inputSection.classList = 'message-input-container hidden';
    menuBtn.classList.add('hidden');
    

    await fetchGroups();
  } catch (err) {
    alert(err.message);
  }
});

// ================= UI EVENTS =================
let typingTimeout = null;

const typingUsers = new Map();

function renderTypingIndicator(data) {
  const el = document.getElementById("typingIndicator");
  if (!el) return;

  typingUsers.set(data.sender_id, data.username);

  const names = Array.from(typingUsers.values());

  el.textContent =
    names.length === 1
      ? `${names[0]} is typing...`
      : `${names.join(", ")} are typing...`;

  el.style.display = "block";

  clearTimeout(window.typingTimeout);

  window.typingTimeout = setTimeout(() => {
    typingUsers.clear();
    el.style.display = "none";
  }, 1200);
}

async function loadComponent(path) {
    // console.log("Loading:", path);

    const response = await fetch(path);

    // console.log("Response URL:", response.url);
    // console.log("Status:", response.status);

    const text = await response.text();

    // console.log("Response text:", text);

    return text;
}



async function renderChatInfo() {
    const html = await loadComponent(
        "/static/components/chat-info.html"
    );

    messagesContainer.innerHTML = html;

    document.getElementById(
        "chatName"
    ).textContent = selectedConversation.name;
}

// =================== RENDER GROUP =================
let activeMemberId = null;

async function renderGroupInfo() {
  const html = await loadComponent(
    "/static/components/group-info.html"
  );
  const messageView = document.getElementById("messagesView")
  messageView.classList.add("hidden");
    const infoView = document.getElementById("infoView");

    infoView.innerHTML = html;
    infoView.classList.remove("hidden");
    const menu = document.getElementById("memberMenu");
const removeBtn = document.getElementById("removeMemberBtn");
const extraBtn = document.getElementById("extraActionBtn");

    const { name, role, members = [] } = selectedConversation;

    const groupNameEl = document.getElementById("groupName");
    const groupRoleEl = document.getElementById("groupRole");
    const membersListEl = document.getElementById("membersList");
    const closeBtn = document.getElementById("closeGroupInfoBtn");
    // console.log(closeBtn)

    groupNameEl.textContent = name || "Unnamed Group";
    groupRoleEl.textContent = role || "MEMBER";

    const sortedMembers = [
        ...members.filter(m => m.id === me.id),
        ...members.filter(m => m.id !== me.id)
    ];

    membersListEl.innerHTML = sortedMembers
        .map(renderMemberItem)
        .join("");

    // Restore online status
    if (latestOnlineUsers.length > 0) {
        updateOnlineStatus(latestOnlineUsers);
    }

    // Close button
    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
    document.getElementById("infoView")
        .classList.add("hidden");

    document.getElementById("messagesView")
        .classList.remove("hidden");
      });
    }
}

function renderMemberItem(member) {
    const username = member.username || "Unknown";
    const role = member.role || "member";
    const initials = getInitials(username);
    const isOnline = member.status === "online";
  // console.log(me);
    const isMe = member.id === me.id;

    return `
        <li class="member-item ${isMe ? "me" : ""}" data-user-id="${member.id}">
            
            <div class="avatar-wrapper">
                <div class="avatar">
                    ${initials}
                </div>

                <span class="status-dot ${isOnline ? "online" : ""}"></span>
            </div>

            <div class="member-info">
                <div class="member-name">
                 ${escapeHtml(isMe ? username + " (You)" : username)}    
                </div>

                <div class="member-meta">
                    <span class="role">${escapeHtml(role)}</span>
                    
                    • ID: ${member.id}
                </div>
            </div>
             <div class="member-actions">
                ${!isMe ?  `<button class="member-menu-btn" data-id="${member.id}">
                
                <div></div>
                <div></div>
                <div></div>
                </button>` : ""}
                </div>

        </li>
    `;
}


document.addEventListener("click", async (e) => {

    // 3-dot menu click
    if (e.target.closest(".member-menu-btn")) {

        const btn = e.target.closest(".member-menu-btn");

        activeMemberId = Number(btn.dataset.id);

        const menu = document.getElementById("memberMenu");
        const removeBtn = document.getElementById("removeMemberBtn");

        if (!menu || !removeBtn) return;

       const member = selectedConversation.members.find(
    m => m.id === activeMemberId
);

const currentUserRole = selectedConversation.role;

const canModerate =
    currentUserRole === "ADMIN" ||
    currentUserRole === "OWNER";

const canRemove =
    canModerate &&
    member &&
    member.id !== me.id &&                // can't remove yourself
    member.role !== "ADMIN" &&            // can't remove admins
    member.role !== "OWNER";              // can't remove owner

removeBtn.style.display =
    canRemove ? "block" : "none";

        menu.style.top = `${e.pageY}px`;
        menu.style.left = `${e.pageX}px`;

        menu.classList.remove("hidden");

        return;
    }

    // remove member click
    if (e.target.id === "removeMemberBtn") {

        if (!activeMemberId) return;

        if (!confirm("Remove this member?")) return;

        const res = await fetch(
            `${API_URL}/chat/groups/remove-member`,
            {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    group_id: selectedConversation.id,
                    member_id: activeMemberId
                })
            }
        );

        const data = await res.json();

        if (!res.ok) {
            alert(data.detail || "Failed");
            return;
        }

        document
            .getElementById("memberMenu")
            ?.classList.add("hidden");

        await fetchParticipants(selectedConversation.id);
        await renderGroupInfo();

        return;
    }

    // hide menu
    const menu = document.getElementById("memberMenu");

    if (
        menu &&
        !e.target.closest(".member-menu-btn") &&
        !e.target.closest("#memberMenu")
    ) {
        menu.classList.add("hidden");
    }
});

document.addEventListener("click", (e) => {
    const menu = document.getElementById("memberMenu");
    if (!menu) return;

    if (!e.target.closest(".member-menu-btn") &&
        !e.target.closest("#memberMenu")) {
        menu.classList.add("hidden");
    }
});


function getInitials(name) {
    return name
        .split(" ")
        .map(w => w[0])
        .slice(0, 2)
        .join("")
        .toUpperCase();
}

// basic XSS protection (important if usernames come from server)
function escapeHtml(str) {
    return str.replace(/[&<>"']/g, m => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    }[m]));
}


// =============== Conversation Title Click ==================
conversationTitle.addEventListener(
    "click",
    async () => {
      // console.log(selectedConversation);
      if (!selectedConversation) return;
      
      // console.log(selectedConversation.type);
      if (
        selectedConversation.type ===
        "GROUP"
        ) {
            await fetchParticipants(
                selectedConversation.id
            );

            await renderGroupInfo();
        } else {
            await renderChatInfo();
        }
    }
);

// tabs
tabs.forEach(btn => {
  // console.log(btn)
  btn.addEventListener("click", async () => {
    tabs.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    activeTab = btn.dataset.tab;

    if (activeTab === "groups") {
      await fetchGroups();   // ✅ WAIT FOR DATA
    }

    renderList();            // ✅ NOW SAFE
  });
});

// menu dropdown
menuBtn.addEventListener("click", () => {

  menuDropdown.classList.toggle("hidden");
});

document.addEventListener("click", e => {
  if (!menuBtn.contains(e.target) && !menuDropdown.contains(e.target)) {
    menuDropdown.classList.add("hidden");
  }
});

