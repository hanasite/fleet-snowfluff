// 飞行雪绒 Service Worker — 让手机添加桌面快捷方式 + 后台通知
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(clients.claim()));
self.addEventListener('push', (e) => {
  if (!e.data) return;
  try {
    const d = e.data.json();
    self.registration.showNotification(d.title || '飞行雪绒', {
      body: d.body || '',
      icon: '/icon.png',
      tag: 'fleet-snowfluff',
    });
  } catch(_) {}
});
