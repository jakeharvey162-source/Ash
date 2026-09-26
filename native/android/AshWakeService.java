package com.jakeharvey.ash;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import androidx.core.app.NotificationCompat;

import org.json.JSONArray;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public class AshWakeService extends Service implements RecognitionListener {
    public static final String ACTION_PAUSE = "com.jakeharvey.ash.WAKE_PAUSE";
    public static final String ACTION_RESUME = "com.jakeharvey.ash.WAKE_RESUME";
    public static final String ACTION_STOP = "com.jakeharvey.ash.WAKE_STOP";
    private static final String PREFS = "ash_wake_service";
    private static final String CHANNEL = "ash_wake_channel";
    private static final int NOTIFICATION_ID = 8301;

    private SpeechRecognizer recognizer;
    private Intent recognizerIntent;
    private Handler handler;
    private boolean listening = false;
    private boolean destroyed = false;
    private long cooldownUntil = 0L;
    private PowerManager.WakeLock cpuLock;

    @Override
    public void onCreate() {
        super.onCreate();
        handler = new Handler(Looper.getMainLooper());
        createChannel();
        acquireCpuLock();
        setupRecognizer();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? "" : String.valueOf(intent.getAction());
        SharedPreferences prefs = getSharedPreferences(PREFS, 0);
        if (ACTION_STOP.equals(action)) {
            prefs.edit().putBoolean("enabled", false).putBoolean("paused", true).apply();
            stopRecognizer();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return START_NOT_STICKY;
        }
        if (ACTION_PAUSE.equals(action)) prefs.edit().putBoolean("paused", true).apply();
        if (ACTION_RESUME.equals(action)) prefs.edit().putBoolean("paused", false).apply();

        startForeground(NOTIFICATION_ID, buildNotification());
        if (shouldListen()) restartSoon(120);
        else stopRecognizer();
        return START_STICKY;
    }

    private boolean shouldListen() {
        SharedPreferences prefs = getSharedPreferences(PREFS, 0);
        return prefs.getBoolean("enabled", false)
            && !prefs.getBoolean("paused", true)
            && System.currentTimeMillis() >= cooldownUntil
            && SpeechRecognizer.isRecognitionAvailable(this);
    }

    private void setupRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) return;
        recognizer = SpeechRecognizer.createSpeechRecognizer(this);
        recognizer.setRecognitionListener(this);
        recognizerIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 900L);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 650L);
    }

    private void startRecognizer() {
        if (destroyed || !shouldListen() || recognizer == null || listening) return;
        try {
            listening = true;
            recognizer.startListening(recognizerIntent);
        } catch (Exception ignored) {
            listening = false;
            restartSoon(800);
        }
    }

    private void stopRecognizer() {
        listening = false;
        if (recognizer != null) {
            try { recognizer.cancel(); } catch (Exception ignored) {}
        }
    }

    private void restartSoon(long delay) {
        if (handler == null) return;
        handler.removeCallbacksAndMessages(null);
        handler.postDelayed(() -> {
            if (!destroyed && shouldListen()) startRecognizer();
        }, delay);
    }

    private List<String> wakePhrases() {
        SharedPreferences prefs = getSharedPreferences(PREFS, 0);
        String wake = prefs.getString("wake_word", "Ash");
        Set<String> set = new LinkedHashSet<>();
        if (wake != null && !wake.trim().isEmpty()) {
            set.add(wake.trim().toLowerCase(Locale.US));
            set.add(("hey " + wake).trim().toLowerCase(Locale.US));
            set.add(("okay " + wake).trim().toLowerCase(Locale.US));
            set.add(("ok " + wake).trim().toLowerCase(Locale.US));
        }
        try {
            JSONArray a = new JSONArray(prefs.getString("aliases", "[]"));
            for (int i = 0; i < a.length(); i++) {
                String alias = a.optString(i, "").trim().toLowerCase(Locale.US);
                if (!alias.isEmpty()) set.add(alias);
            }
        } catch (Exception ignored) {}
        return new ArrayList<>(set);
    }

    private String extractCommand(String raw) {
        if (raw == null) return null;
        String lower = raw.trim().toLowerCase(Locale.US);
        for (String phrase : wakePhrases()) {
            int idx = lower.indexOf(phrase);
            if (idx < 0) continue;
            boolean leftOk = idx == 0 || !Character.isLetterOrDigit(lower.charAt(idx - 1));
            int end = idx + phrase.length();
            boolean rightOk = end >= lower.length() || !Character.isLetterOrDigit(lower.charAt(end));
            if (!leftOk || !rightOk) continue;
            return raw.substring(Math.min(raw.length(), end)).replaceFirst("^[\\s,.:;!?-]+", "").trim();
        }
        return null;
    }

    private void inspectResults(ArrayList<String> matches) {
        if (matches == null || matches.isEmpty() || System.currentTimeMillis() < cooldownUntil) return;
        for (String text : matches) {
            String command = extractCommand(text);
            if (command == null) continue;
            cooldownUntil = System.currentTimeMillis() + 6500L;
            getSharedPreferences(PREFS, 0).edit()
                .putString("pending_command", command)
                .putLong("pending_command_at", System.currentTimeMillis())
                .apply();
            launchAsh(command);
            return;
        }
    }

    private void launchAsh(String command) {
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            PowerManager.WakeLock screen = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, "Ash:ScreenWake");
            try { screen.acquire(5000L); } catch (Exception ignored) {}
        }
        Intent open = new Intent(this, MainActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        open.putExtra("ash_wake_command", command == null ? "" : command);
        startActivity(open);
        restartSoon(7000L);
    }

    private android.app.Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        SharedPreferences prefs = getSharedPreferences(PREFS, 0);
        String wake = prefs.getString("wake_word", "Ash");
        return new NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Ash background wake")
            .setContentText("Listening for “" + wake + "” in the background and while the screen is locked.")
            .setContentIntent(pending)
            .setOngoing(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL, "Ash background wake", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Keeps Ash wake-word listening active when you leave or lock the app.");
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) manager.createNotificationChannel(channel);
    }

    private void acquireCpuLock() {
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm == null) return;
        cpuLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Ash:WakeService");
        try { cpuLock.acquire(); } catch (Exception ignored) {}
    }

    @Override public void onReadyForSpeech(Bundle params) { listening = true; }
    @Override public void onBeginningOfSpeech() {}
    @Override public void onRmsChanged(float rmsdB) {}
    @Override public void onBufferReceived(byte[] buffer) {}
    @Override public void onEndOfSpeech() { listening = false; }
    @Override public void onError(int error) { listening = false; restartSoon(error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY ? 1200L : 450L); }
    @Override public void onResults(Bundle results) { listening = false; inspectResults(results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)); restartSoon(350L); }
    @Override public void onPartialResults(Bundle partialResults) { inspectResults(partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)); }
    @Override public void onEvent(int eventType, Bundle params) {}

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        // The foreground service is intentionally independent from the app task.
        // Re-arm recognition when the user swipes Ash away so hands-free wake can
        // continue while the device is locked or another app is foregrounded.
        if (shouldListen()) restartSoon(350L);
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        destroyed = true;
        stopRecognizer();
        if (recognizer != null) {
            try { recognizer.destroy(); } catch (Exception ignored) {}
            recognizer = null;
        }
        if (cpuLock != null && cpuLock.isHeld()) {
            try { cpuLock.release(); } catch (Exception ignored) {}
        }
        if (handler != null) handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
