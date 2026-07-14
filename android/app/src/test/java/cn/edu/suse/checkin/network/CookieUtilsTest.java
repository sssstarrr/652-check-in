package cn.edu.suse.checkin.network;

import org.junit.Test;

import java.util.Arrays;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class CookieUtilsTest {
    @Test
    public void staleSessionCanBeRemovedBeforeRenewal() {
        String old = "_sop_session_=jwt.value.sig; SESSION=stale";
        String renewal = CookieUtils.without(old, "SESSION");
        assertTrue(CookieUtils.has(renewal, "_sop_session_"));
        assertFalse(CookieUtils.has(renewal, "SESSION"));
    }

    @Test
    public void newSetCookieReplacesSessionWithoutAttributes() {
        String updated = CookieUtils.mergeSetCookieHeaders(
                "_sop_session_=jwt.value.sig",
                Arrays.asList("SESSION=fresh; Path=/; HttpOnly", "theme=blue; Path=/")
        );
        assertEquals("fresh", CookieUtils.get(updated, "SESSION"));
        assertEquals("blue", CookieUtils.get(updated, "theme"));
        assertFalse(CookieUtils.has(updated, "Path"));
        assertFalse(CookieUtils.has(updated, "HttpOnly"));
    }
}
