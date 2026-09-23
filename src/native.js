let cap = null;

async function loadCapacitor() {
  if (cap) return cap;
  try {
    const core = await import('@capacitor/core');
    const [app,browser,clipboard,device,haptics,notifications,preferences,share] = await Promise.all([
      import('@capacitor/app'),
      import('@capacitor/browser'),
      import('@capacitor/clipboard'),
      import('@capacitor/device'),
      import('@capacitor/haptics'),
      import('@capacitor/local-notifications'),
      import('@capacitor/preferences'),
      import('@capacitor/share')
    ]);
    cap = {
      Capacitor: core.Capacitor,
      App: app.App,
      Browser: browser.Browser,
      Clipboard: clipboard.Clipboard,
      Device: device.Device,
      Haptics: haptics.Haptics,
      LocalNotifications: notifications.LocalNotifications,
      Preferences: preferences.Preferences,
      Share: share.Share
    };
    return cap;
  } catch {
    return null;
  }
}

export async function nativeAvailable() {
  const c = await loadCapacitor();
  return Boolean(c?.Capacitor?.isNativePlatform?.());
}

export async function getDeviceInfo() {
  const c = await loadCapacitor();
  if (!c) return { platform: 'web', model: 'browser', operatingSystem: navigator.platform || 'web' };
  try {
    const info = await c.Device.getInfo();
    return { ...info, native: c.Capacitor.isNativePlatform() };
  } catch {
    return { platform: 'web', model: 'browser', operatingSystem: navigator.platform || 'web' };
  }
}

export async function openUrl(url) {
  const c = await loadCapacitor();
  if (c?.Capacitor?.isNativePlatform()) return c.Browser.open({ url });
  window.open(url, '_blank', 'noopener,noreferrer');
}

export async function shareText(title, text, url='') {
  const c = await loadCapacitor();
  if (c?.Share) return c.Share.share({ title, text, url, dialogTitle: title });
  if (navigator.share) return navigator.share({ title, text, url });
  throw new Error('Sharing is not supported on this device.');
}

export async function copyText(text) {
  const c = await loadCapacitor();
  if (c?.Clipboard) return c.Clipboard.write({ string: text });
  return navigator.clipboard.writeText(text);
}

export async function notify(title, body) {
  const c = await loadCapacitor();
  if (c?.LocalNotifications) {
    const permission = await c.LocalNotifications.requestPermissions();
    if (permission.display !== 'granted') throw new Error('Notification permission was not granted.');
    return c.LocalNotifications.schedule({
      notifications: [{ id: Math.floor(Date.now()/1000)%2147483647, title, body, schedule: { at: new Date(Date.now()+500) } }]
    });
  }
  if ('Notification' in window) {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Notification permission was not granted.');
    new Notification(title,{ body });
    return;
  }
  throw new Error('Notifications are not supported on this device.');
}

export async function haptic() {
  const c = await loadCapacitor();
  if (!c?.Haptics) return;
  try { await c.Haptics.impact({ style: 'LIGHT' }); } catch {}
}

export async function savePreference(key, value) {
  const c = await loadCapacitor();
  if (c?.Preferences) return c.Preferences.set({ key, value });
  localStorage.setItem(key, value);
}

export async function loadPreference(key) {
  const c = await loadCapacitor();
  if (c?.Preferences) return (await c.Preferences.get({ key })).value;
  return localStorage.getItem(key);
}
