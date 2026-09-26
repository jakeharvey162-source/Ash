package com.jakeharvey.ash;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

public class AshBootReceiver extends BroadcastReceiver {
    private static final String PREFS = "ash_wake_service";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
            && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
            && !"android.intent.action.QUICKBOOT_POWERON".equals(action)) return;

        SharedPreferences prefs = context.getSharedPreferences(PREFS, 0);
        boolean enabled = prefs.getBoolean("enabled", false);
        boolean paused = prefs.getBoolean("paused", true);
        if (!enabled || paused) return;

        Intent service = new Intent(context, AshWakeService.class);
        service.setAction(AshWakeService.ACTION_RESUME);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service);
        else context.startService(service);
    }
}
