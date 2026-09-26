package com.jakeharvey.ash;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;

import org.json.JSONObject;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AshWakePlugin.class);
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        }
        deliverWakeIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        deliverWakeIntent(intent);
    }

    private void deliverWakeIntent(Intent intent) {
        if (intent == null || !intent.hasExtra("ash_wake_command")) return;
        String command = intent.getStringExtra("ash_wake_command");
        if (command == null) command = "";
        final String safe = JSONObject.quote(command);
        getWindow().getDecorView().postDelayed(() -> {
            try {
                WebView webView = getBridge().getWebView();
                if (webView != null) {
                    String js = "window.dispatchEvent(new CustomEvent('ash-background-wake',{detail:{command:" + safe + "}}));";
                    webView.evaluateJavascript(js, null);
                }
            } catch (Exception ignored) {}
        }, 900L);
    }
}
