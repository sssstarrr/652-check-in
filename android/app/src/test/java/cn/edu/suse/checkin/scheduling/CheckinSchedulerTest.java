package cn.edu.suse.checkin.scheduling;

import org.junit.Test;

import java.time.ZoneId;
import java.time.ZonedDateTime;

import static org.junit.Assert.assertEquals;

public class CheckinSchedulerTest {
    private static final ZoneId CHINA = ZoneId.of("Asia/Shanghai");

    @Test
    public void schedulesLaterTodayBeforeTarget() {
        long now = ZonedDateTime.of(2026, 7, 14, 19, 30, 0, 0, CHINA).toInstant().toEpochMilli();
        assertEquals(60_000L, CheckinScheduler.delayUntilNext(19, 31, now, CHINA));
    }

    @Test
    public void schedulesTomorrowAtOrAfterTarget() {
        long now = ZonedDateTime.of(2026, 7, 14, 19, 31, 0, 0, CHINA).toInstant().toEpochMilli();
        assertEquals(24 * 60 * 60_000L, CheckinScheduler.delayUntilNext(19, 31, now, CHINA));
    }
}
