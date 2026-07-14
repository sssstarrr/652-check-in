package cn.edu.suse.checkin.data;

import android.content.Context;
import android.content.SharedPreferences;

public final class ScheduleStore {
    private static final String PREFERENCES = "checkin_652_schedule";
    private final SharedPreferences preferences;

    public ScheduleStore(Context context) {
        preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    public boolean isEnabled() {
        return preferences.getBoolean("enabled", false);
    }

    public void setEnabled(boolean enabled) {
        preferences.edit().putBoolean("enabled", enabled).apply();
    }

    public int getHour() {
        return preferences.getInt("hour", 19);
    }

    public int getMinute() {
        return preferences.getInt("minute", 31);
    }

    public void setTime(int hour, int minute) {
        preferences.edit().putInt("hour", hour).putInt("minute", minute).apply();
    }

    public String getLastResult() {
        String value = preferences.getString("last_result", "");
        return value == null ? "" : value;
    }

    public void setLastResult(String value) {
        preferences.edit().putString("last_result", value == null ? "" : value).apply();
    }
}
