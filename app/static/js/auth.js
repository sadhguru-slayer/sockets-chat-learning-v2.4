let currentUser = null;

async function refreshAccessToken() {
    const refreshToken = localStorage.getItem("refresh_token");

    if (!refreshToken) {
        return false;
    }

    try {
        const response = await fetch("/auth/refresh", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                refresh_token: refreshToken
            })
        });

        if (!response.ok) {
            return false;
        }

        const data = await response.json();

        localStorage.setItem(
            "access_token",
            data.access_token
        );

        return true;

    } catch {
        return false;
    }
}

async function requireAuth() {
    let accessToken = localStorage.getItem("access_token");

    if (!accessToken) {
        const refreshed = await refreshAccessToken();

        if (!refreshed) {
            window.location.href = "/login";
            return false;
        }
    }

    return true;
}

async function getMe() {
    if (currentUser) {
        return currentUser;
    }

    let accessToken = localStorage.getItem("access_token");

    if (!accessToken) {
        const refreshed = await refreshAccessToken();

        if (!refreshed) {
            window.location.href = "/login";
            return null;
        }

        accessToken = localStorage.getItem("access_token");
    }

    const response = await fetch("/auth/me", {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${accessToken}`
        }
    });

    if (response.status === 401) {
        const refreshed = await refreshAccessToken();

        if (!refreshed) {
            window.location.href = "/login";
            return null;
        }

        return getMe();
    }

    if (!response.ok) {
        throw new Error("Failed to fetch user");
    }

    currentUser = await response.json();
    return currentUser;
}