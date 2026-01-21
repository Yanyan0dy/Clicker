package org.sequentialclicker.sequentialclicker;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import androidx.core.app.NotificationCompat;

public class ClickerForegroundService extends Service {
    public static final String CHANNEL_ID = "sequential_clicker";

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        startForeground(1, buildNotification("准备"));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(1, buildNotification("运行中"));
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "Sequential Clicker",
                NotificationManager.IMPORTANCE_LOW
        );
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.createNotificationChannel(channel);
    }

    private Notification buildNotification(String text) {
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                getPackageManager().getLaunchIntentForPackage(getPackageName()),
                Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_IMMUTABLE : 0
        );
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("顺序连点器")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_media_play)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build();
    }
}

