let corePromise = null;
const pluginPromises = new Map();

async function loadCore() {
  if (corePromise) return corePromise;
  corePromise = import('@capacitor/core')
    .then((core) => core)
    .catch(() => null);
  return corePromise;
}

async function loadPlugin(key, loader) {
  if (pluginPromises.has(key)) return pluginPromises.get(key);
  const promise = loader().catch(() => null);
  pluginPromises.set(key, promise);
  return promise;
}

async function nativeCore() {
  const core = await loadCore();
  if (!core?.Capacitor?.isNativePlatform?.()) return null;
  return core;
}

export async function nativeAvailable() {
  return Boolean(await nativeCore());
}

export async function getDeviceInfo() {
  const core = await loadCore();
  if (!core) return { platform: 'web', model: 'browser', operatingSystem: navigator.platform || 'web' };

  try {
    const device = await loadPlugin('device', () => import('@capacitor/device'));
    if (!device?.Device) throw new Error('Device plugin unavailable');
    const info = await device.Device.getInfo();
    return { ...info, native: core.Capacitor.isNativePlatform() };
  } catch {
    return {
      platform: core.Capacitor.getPlatform?.() || 'web',
      model: 'browser',
      operatingSystem: navigator.platform || 'web',
      native: Boolean(core.Capacitor.isNativePlatform?.())
    };
  }
}

export async function openUrl(url) {
  const core = await nativeCore();
  if (core) {
    const browser = await loadPlugin('browser', () => import('@capacitor/browser'));
    if (browser?.Browser) return browser.Browser.open({ url });
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

export async function shareText(title, text, url='') {
  const core = await nativeCore();
  if (core) {
    const share = await loadPlugin('share', () => import('@capacitor/share'));
    if (share?.Share) return share.Share.share({ title, text, url, dialogTitle: title });
  }
  if (navigator.share) return navigator.share({ title, text, url });
  throw new Error('Sharing is not supported on this device.');
}

export async function copyText(text) {
  const core = await nativeCore();
  if (core) {
    const clipboard = await loadPlugin('clipboard', () => import('@capacitor/clipboard'));
    if (clipboard?.Clipboard) return clipboard.Clipboard.write({ string: text });
  }
  return navigator.clipboard.writeText(text);
}

export async function notify(title, body) {
  const core = await nativeCore();
  if (core) {
    const notifications = await loadPlugin('notifications', () => import('@capacitor/local-notifications'));
    if (notifications?.LocalNotifications) {
      const permission = await notifications.LocalNotifications.requestPermissions();
      if (permission.display !== 'granted') throw new Error('Notification permission was not granted.');
      return notifications.LocalNotifications.schedule({
        notifications: [{
          id: Math.floor(Date.now()/1000)%2147483647,
          title,
          body,
          schedule: { at: new Date(Date.now()+500) }
        }]
      });
    }
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
  const core = await nativeCore();
  if (!core) return;
  const haptics = await loadPlugin('haptics', () => import('@capacitor/haptics'));
  if (!haptics?.Haptics) return;
  try { await haptics.Haptics.impact({ style: 'LIGHT' }); } catch {}
}

export async function savePreference(key, value) {
  const core = await nativeCore();
  if (core) {
    const preferences = await loadPlugin('preferences', () => import('@capacitor/preferences'));
    if (preferences?.Preferences) return preferences.Preferences.set({ key, value });
  }
  localStorage.setItem(key, value);
}

export async function loadPreference(key) {
  const core = await nativeCore();
  if (core) {
    const preferences = await loadPlugin('preferences', () => import('@capacitor/preferences'));
    if (preferences?.Preferences) return (await preferences.Preferences.get({ key })).value;
  }
  return localStorage.getItem(key);
}
