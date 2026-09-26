package com.jakeharvey.ash;

import android.Manifest;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "AshWake")
public class AshWakePlugin extends Plugin {
    private static final String PREFS = "ash_wake_service";

    @PluginMethod
    public void configure(PluginCall call) {
        boolean enabled = call.getBoolean("enabled", false);
        boolean paused = call.getBoolean("paused", true);
        String wakeWord = call.getString("wakeWord", "Ash");
        JSArray aliases = call.getArray("aliases", new JSArray());

        SharedPreferences prefs = getContext().getSharedPreferences(PREFS, 0);
        prefs.edit()
            .putBoolean("enabled", enabled)
            .putBoolean("paused", paused)
            .putString("wake_word", wakeWord == null ? "Ash" : wakeWord)
            .putString("aliases", aliases == null ? "[]" : aliases.toString())
            .apply();

        if (!enabled) {
            Intent stop = new Intent(getContext(), AshWakeService.class);
            stop.setAction(AshWakeService.ACTION_STOP);
            getContext().startService(stop);
            call.resolve(status());
            return;
        }

        if (ContextCompat.checkSelfPermission(getContext(), Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(getActivity(), new String[]{Manifest.permission.RECORD_AUDIO}, 4901);
            call.reject("Microphone permission is required before background wake can run.");
            return;
        }

        Intent service = new Intent(getContext(), AshWakeService.class);
        service.setAction(paused ? AshWakeService.ACTION_PAUSE : AshWakeService.ACTION_RESUME);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) getContext().startForegroundService(service);
        else getContext().startService(service);
        call.resolve(status());
    }

    @PluginMethod
    public void setPaused(PluginCall call) {
        boolean paused = call.getBoolean("paused", true);
        getContext().getSharedPreferences(PREFS, 0).edit().putBoolean("paused", paused).apply();
        Intent service = new Intent(getContext(), AshWakeService.class);
        service.setAction(paused ? AshWakeService.ACTION_PAUSE : AshWakeService.ACTION_RESUME);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) getContext().startForegroundService(service);
        else getContext().startService(service);
        call.resolve(status());
    }

    @PluginMethod
    public void consumePending(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS, 0);
        String command = prefs.getString("pending_command", "");
        long at = prefs.getLong("pending_command_at", 0L);
        prefs.edit().remove("pending_command").remove("pending_command_at").apply();
        JSObject out = new JSObject();
        out.put("command", command == null ? "" : command);
        out.put("at", at);
        call.resolve(out);
    }

    @PluginMethod
    public void status(PluginCall call) {
        call.resolve(status());
    }

    private JSObject status() {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS, 0);
        JSObject out = new JSObject();
        out.put("enabled", prefs.getBoolean("enabled", false));
        out.put("paused", prefs.getBoolean("paused", true));
        out.put("wakeWord", prefs.getString("wake_word", "Ash"));
        out.put("permissionGranted", ContextCompat.checkSelfPermission(getContext(), Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED);
        return out;
    }
}
