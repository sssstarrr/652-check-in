package cn.edu.suse.checkin.scheduling;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobParameters;
import android.app.job.JobService;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import cn.edu.suse.checkin.MainActivity;
import cn.edu.suse.checkin.R;
import cn.edu.suse.checkin.data.ScheduleStore;
import cn.edu.suse.checkin.data.SecureSessionStore;
import cn.edu.suse.checkin.model.CheckinTask;
import cn.edu.suse.checkin.model.LocationPreset;
import cn.edu.suse.checkin.network.CheckinClient;

import java.text.SimpleDateFormat;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public final class CheckinJobService extends JobService {
    private static final String CHANNEL_ID = "checkin_652_background";
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private Future<?> running;

    @Override
    public boolean onStartJob(JobParameters params) {
        running = executor.submit(() -> executeCheckin(params));
        return true;
    }

    private void executeCheckin(JobParameters params) {
        SecureSessionStore sessionStore = new SecureSessionStore(this);
        ScheduleStore scheduleStore = new ScheduleStore(this);
        String message;
        try {
            String cookies = sessionStore.getSession();
            if (cookies.trim().isEmpty()) {
                message = "未保存登录态，请打开 App 重新登录";
            } else {
                CheckinClient client = new CheckinClient();
                LocationPreset location = LocationPreset.forCampus(sessionStore.getCampus());
                CheckinClient.Operation<CheckinTask> result = client.performCheckin(cookies, location);
                message = result.message;
                if (result.cookies != null
                        && !result.cookies.trim().isEmpty()
                        && !result.cookies.equals(cookies)) {
                    sessionStore.saveSession(result.cookies, sessionStore.getStudentId(), sessionStore.getDisplayName());
                }
            }
        } catch (Exception exception) {
            message = "后台签到执行失败，请打开 App 查看";
        }

        String recorded = nowText() + "  " + message;
        scheduleStore.setLastResult(recorded);
        showNotification(message);
        jobFinished(params, false);
        CheckinScheduler.schedule(this);
    }

    private void showNotification(String message) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager == null) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT
        );
        manager.createNotificationChannel(channel);

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification notification = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_launcher)
                .setContentTitle(getString(R.string.notification_title))
                .setContentText(message)
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .build();
        manager.notify(CheckinScheduler.JOB_ID, notification);
    }

    private static String nowText() {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA);
        format.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        return format.format(System.currentTimeMillis());
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        if (running != null) {
            running.cancel(true);
        }
        return true;
    }

    @Override
    public void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
