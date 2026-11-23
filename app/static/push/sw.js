self.addEventListener("push", (event) => {
    let title = "Omni";
    let body = "Новое сообщение";
    if (event.data) {
        try {
            const data = event.data.json();
            title = data.title || title;
            body = data.body || body;
        } catch (e) {
            body = event.data.text();
        }
    }
    event.waitUntil((async () => {
        const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
        if (windows.some((client) => client.focused || client.visibilityState === "visible")) return;
        try {
            const cache = await caches.open("omni-presence");
            const cached = await cache.match("/presence");
            if (cached) {
                const data = await cached.json();
                if (typeof data.at === "number" && Date.now() - data.at < 4000) return;
            }
        } catch (e) {}
        await self.registration.showNotification(title, {
            body: body,
            icon: "/static/icon-192.png"
        });
    })());
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    event.waitUntil(self.clients.openWindow("/static/push/go.html"));
});
