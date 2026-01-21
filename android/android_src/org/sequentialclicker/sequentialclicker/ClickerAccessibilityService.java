package org.sequentialclicker.sequentialclicker;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Path;
import android.os.Build;
import android.view.accessibility.AccessibilityEvent;

public class ClickerAccessibilityService extends AccessibilityService {
    public static final String ACTION_CLICK = "org.sequentialclicker.ACTION_CLICK";
    public static final String EXTRA_X = "x";
    public static final String EXTRA_Y = "y";

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (!ACTION_CLICK.equals(intent.getAction())) return;
            int x = intent.getIntExtra(EXTRA_X, -1);
            int y = intent.getIntExtra(EXTRA_Y, -1);
            if (x < 0 || y < 0) return;
            performClick(x, y);
        }
    };

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        IntentFilter filter = new IntentFilter();
        filter.addAction(ACTION_CLICK);
        registerReceiver(receiver, filter);
    }

    @Override
    public void onDestroy() {
        try {
            unregisterReceiver(receiver);
        } catch (Exception ignored) {
        }
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    private void performClick(int x, int y) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return;
        Path path = new Path();
        path.moveTo(x, y);
        GestureDescription.StrokeDescription stroke = new GestureDescription.StrokeDescription(path, 0, 50);
        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);
        dispatchGesture(builder.build(), null, null);
    }
}

