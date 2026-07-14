package cn.edu.suse.checkin.scheduling;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;

import cn.edu.suse.checkin.data.ScheduleStore;

import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;

public final class CheckinScheduler {
    public static final int JOB_ID = 65201;
    private static final ZoneId CHINA = ZoneId.of("Asia/Shanghai");

    private CheckinScheduler() {
    }

    public static boolean schedule(Context context) {
        ScheduleStore store = new ScheduleStore(context);
        if (!store.isEnabled()) {
            cancel(context);
            return false;
        }
        long delay = delayUntilNext(store.getHour(), store.getMinute(), System.currentTimeMillis(), CHINA);
        JobInfo job = new JobInfo.Builder(JOB_ID, new ComponentName(context, CheckinJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setMinimumLatency(delay)
                .setOverrideDeadline(delay + 15 * 60_000L)
                .setBackoffCriteria(5 * 60_000L, JobInfo.BACKOFF_POLICY_LINEAR)
                .setPersisted(true)
                .build();
        JobScheduler scheduler = context.getSystemService(JobScheduler.class);
        return scheduler != null && scheduler.schedule(job) == JobScheduler.RESULT_SUCCESS;
    }

    public static void cancel(Context context) {
        JobScheduler scheduler = context.getSystemService(JobScheduler.class);
        if (scheduler != null) {
            scheduler.cancel(JOB_ID);
        }
    }

    public static long delayUntilNext(int hour, int minute, long nowMillis, ZoneId zone) {
        ZonedDateTime now = Instant.ofEpochMilli(nowMillis).atZone(zone);
        ZonedDateTime target = now.withHour(hour).withMinute(minute).withSecond(0).withNano(0);
        if (!target.isAfter(now)) {
            target = target.plusDays(1);
        }
        return Math.max(1_000L, Duration.between(now, target).toMillis());
    }
}
