package cn.edu.suse.checkin.model;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public final class LocationPreset {
    public static final String CAMPUS_YIBIN = "宜宾";
    public static final String CAMPUS_LIBAIHE = "李白河";
    public static final String CAMPUS_HUIDONG = "汇东";

    private static final List<String> CAMPUS_NAMES = Collections.unmodifiableList(
            Arrays.asList(CAMPUS_YIBIN, CAMPUS_LIBAIHE, CAMPUS_HUIDONG)
    );

    public final String campus;
    public final String address;
    public final double longitude;
    public final double latitude;

    public LocationPreset(String campus, String address, double longitude, double latitude) {
        this.campus = campus;
        this.address = address;
        this.longitude = longitude;
        this.latitude = latitude;
    }

    public static List<String> campusNames() {
        return CAMPUS_NAMES;
    }

    public static LocationPreset forCampus(String campus) {
        if (CAMPUS_LIBAIHE.equals(campus)) {
            return new LocationPreset(
                    CAMPUS_LIBAIHE,
                    "四川省自贡市大安区大山铺镇四川轻化工大学李白河校区",
                    104.832512,
                    29.378790
            );
        }
        if (CAMPUS_HUIDONG.equals(campus)) {
            return new LocationPreset(
                    CAMPUS_HUIDONG,
                    "四川省自贡市自流井区学苑街道汇雅路15号四川轻化工大学汇东校区",
                    104.763952,
                    29.330347
            );
        }
        return new LocationPreset(
                CAMPUS_YIBIN,
                "四川省宜宾市翠屏区白沙湾街道大学路四川轻化工大学宜宾校区",
                104.674665,
                28.804867
        );
    }

    public String locationJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("point", new JSONArray().put(longitude).put(latitude));
        object.put("address", address);
        return object.toString();
    }
}
