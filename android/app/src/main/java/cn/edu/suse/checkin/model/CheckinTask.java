package cn.edu.suse.checkin.model;

import org.json.JSONObject;

public final class CheckinTask {
    public final int id;
    public final String name;
    public String statusText;
    public final String needTime;
    public final String startTime;
    public String checkinTime;
    public int checkinStatus;

    public CheckinTask(
            int id,
            String name,
            String statusText,
            String needTime,
            String startTime,
            String checkinTime,
            int checkinStatus
    ) {
        this.id = id;
        this.name = name;
        this.statusText = statusText;
        this.needTime = needTime;
        this.startTime = startTime;
        this.checkinTime = checkinTime;
        this.checkinStatus = checkinStatus;
    }

    public static CheckinTask fromJson(JSONObject data) {
        String needTime = data.optString("needTime", data.optString("qdksrq", ""));
        String startTime = data.optString("qdkssj", data.optString("start_date", ""));
        return new CheckinTask(
                data.optInt("id", 0),
                data.optString("rwmc", "未命名任务"),
                data.optString("rwzt", ""),
                needTime,
                startTime,
                data.optString("qdsj", ""),
                data.optInt("qdzt", 0)
        );
    }
}
