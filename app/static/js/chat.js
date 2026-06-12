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
    `ws://localhost:8000/ws/${conversation.id}?token=${token}`
  );

  socket.onopen = () => {
    console.log("WebSocket connected:", conversation.id);
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === "online_users") {
      latestOnlineUsers = data.users;
      updateOnlineStatus(data.users);
    }

    if (data.event === "MESSAGE_CREATED") {
      renderIncomingMessage(data);
    }
  };

  socket.onclose = (e) => {
    console.log("WebSocket closed:", e.code, e.reason);
    socket = null;
  };
}

// ================= SELECT =================
async function selectConversation(conversation) {
  selectedConversation = conversation;

  conversationTitle.textContent = conversation.name;

  leaveGroupBtn.style.display =
    conversation.type === "GROUP" ? "block" : "none";

  addMembersBtn.style.display =
    ["OWNER", "ADMIN"].includes(conversation.role)
      ? "block"
      : "none";

  await connectWs(conversation);
  await renderMessages();
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
    console.log("Clicked");

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

    await fetchGroups();
  } catch (err) {
    alert(err.message);
  }
});

// ================= UI EVENTS =================
async function loadComponent(path) {
    const response = await fetch(path);

    if (!response.ok) {
        throw new Error(`Failed loading ${path}`);
    }

    return await response.text();
}

async function renderMessages() {
    const html = await loadComponent(
        "/static/components/messages.html"
    );

    messagesContainer.innerHTML = html;

    document.getElementById(
        "msgConversationName"
    ).textContent = selectedConversation.name;
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
async function renderGroupInfo() {
    const html = await loadComponent("/static/components/group-info.html");
    messagesContainer.innerHTML = html;

    const { name, role, members = [] } = selectedConversation;

    const groupNameEl = document.getElementById("groupName");
    const groupRoleEl = document.getElementById("groupRole");
    const membersListEl = document.getElementById("membersList");

    groupNameEl.textContent = name || "Unnamed Group";
    groupRoleEl.textContent = role || "-";

    const sortedMembers = [
    ...members.filter(m => m.id === me.id),
    ...members.filter(m => m.id !== me.id)
    ];

    membersListEl.innerHTML = sortedMembers
    .map(renderMemberItem)
    .join("");

    // 🔥 IMPORTANT: re-apply online status AFTER render
    if (latestOnlineUsers.length > 0) {
        updateOnlineStatus(latestOnlineUsers);
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

                <span class="status-dot ${isOnline ? "online" : "offline"}"></span>
            </div>

            <div class="member-info">
                <div class="member-name">
                 ${escapeHtml(isMe ? username + " (You)" : username)}    
                </div>

                <div class="member-meta">
                    <span class="role">${escapeHtml(role)}</span>
                    • 
                    <span class="status-text">
                        ${isOnline || isMe ? "Online" : "Offline"}
                    </span>
                    • ID: ${member.id}
                </div>
            </div>

        </li>
    `;
}

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
        if (!selectedConversation) return;

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

