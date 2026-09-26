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


export async function nativeSpeechRecognitionAvailable() {
  const core = await nativeCore();
  if (!core) return false;
  const mod = await loadPlugin('speech-recognition', () => import('@capgo/capacitor-speech-recognition'));
  const speech = mod?.SpeechRecognition;
  if (!speech) return false;
  try {
    const result = await speech.available();
    return Boolean(result?.available ?? result?.value ?? result);
  } catch {
    return true;
  }
}

export async function requestNativeSpeechRecognitionPermissions() {
  const core = await nativeCore();
  if (!core) return { speechRecognition: 'granted' };
  const mod = await loadPlugin('speech-recognition', () => import('@capgo/capacitor-speech-recognition'));
  const speech = mod?.SpeechRecognition;
  if (!speech) throw new Error('Native speech recognition is unavailable.');
  const current = await speech.checkPermissions?.().catch(() => null);
  if (current?.speechRecognition === 'granted') return current;
  return speech.requestPermissions();
}

export async function startNativeSpeechRecognition(options = {}, handlers = {}) {
  const core = await nativeCore();
  if (!core) return null;
  const mod = await loadPlugin('speech-recognition', () => import('@capgo/capacitor-speech-recognition'));
  const speech = mod?.SpeechRecognition;
  if (!speech) throw new Error('Native speech recognition is unavailable.');

  const handles = [];
  if (handlers.onPartial) {
    handles.push(await speech.addListener('partialResults', data => {
      const matches = Array.isArray(data?.matches) ? data.matches : [];
      handlers.onPartial(matches);
    }));
  }
  if (handlers.onState) {
    handles.push(await speech.addListener('listeningState', data => {
      handlers.onState(String(data?.status || ''));
    }));
  }

  let closed = false;
  const removeListeners = async () => {
    const pending = handles.splice(0).map(handle => handle?.remove?.()).filter(Boolean);
    await Promise.allSettled(pending);
  };
  const stop = async () => {
    if (closed) return;
    closed = true;
    try { await speech.stop(); } catch {}
    await removeListeners();
  };

  try {
    const result = await speech.start({
      language: options.language || navigator.language || 'en-US',
      maxResults: 3,
      partialResults: true,
      popup: false,
      allowForSilence: true
    });
    const matches = Array.isArray(result?.matches) ? result.matches : [];
    if (matches.length) handlers.onFinal?.(matches);
  } catch (error) {
    await removeListeners();
    throw error;
  }

  return { stop, removeListeners };
}


async function ashWakePlugin() {
  const core = await nativeCore();
  if (!core || core.Capacitor.getPlatform?.() !== 'android') return null;
  try { return core.registerPlugin('AshWake'); } catch { return null; }
}

export async function configureBackgroundWake({ enabled=false, paused=true, wakeWord='Ash', aliases=[] } = {}) {
  const plugin = await ashWakePlugin();
  if (!plugin) return { available:false };
  const result = await plugin.configure({
    enabled:Boolean(enabled),
    paused:Boolean(paused),
    wakeWord:String(wakeWord || 'Ash'),
    aliases:Array.isArray(aliases) ? aliases.map(x=>String(x)) : []
  });
  return { available:true, ...(result||{}) };
}

export async function pauseBackgroundWake(paused=true) {
  const plugin = await ashWakePlugin();
  if (!plugin) return { available:false };
  const result = await plugin.setPaused({ paused:Boolean(paused) });
  return { available:true, ...(result||{}) };
}

export async function consumeBackgroundWakeCommand() {
  const plugin = await ashWakePlugin();
  if (!plugin) return { available:false, command:'' };
  const result = await plugin.consumePending();
  return { available:true, command:String(result?.command||''), at:Number(result?.at||0) };
}

export async function backgroundWakeStatus() {
  const plugin = await ashWakePlugin();
  if (!plugin) return { available:false };
  const result = await plugin.status();
  return { available:true, ...(result||{}) };
}
