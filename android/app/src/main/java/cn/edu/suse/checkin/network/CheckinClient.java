package cn.edu.suse.checkin.network;

import android.util.Base64;

import cn.edu.suse.checkin.model.CheckinTask;
import cn.edu.suse.checkin.model.LocationPreset;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

public final class CheckinClient {
    public static final String QFHY_BASE = "https://qfhy.suse.edu.cn";
    public static final String QDDK_ENTRY = QFHY_BASE + "/xg/app/qddk/admin/qddkdk";
    public static final String PASSWORD_LOGIN_URL = "https://uias.suse.edu.cn/sso/login?service=";
    public static final String LOGIN_SERVICE = QFHY_BASE
            + "/site/appware/system/sso/login?target=" + QDDK_ENTRY;
    public static final String WECHAT_LOGIN_URL = QFHY_BASE
            + "/edu/v1/wechat/qrcodelogin?appId=wx130c9f0196e29149"
            + "&ybAppId=yszbOwOyvwBVkjP3"
            + "&targetUrl=https%3A%2F%2Fqfhy.suse.edu.cn%2Fcallback%2Fedu%2F";

    private static final String TASK_LIST_URL = QFHY_BASE + "/site/qddk/qdrw/api/myList.rst?status=";
    private static final String TASK_DETAIL_URL = QFHY_BASE + "/site/qddk/qdrw/qdxx/api/detailList.rst?qdrwId=";
    private static final String CHECKIN_URL = QFHY_BASE + "/site/qddk/qdrw/api/checkSignLocationWithPhoto.rst";
    private static final int TIMEOUT_MS = 15_000;

    public static final class Operation<T> {
        public final boolean success;
        public final String message;
        public final T data;
        public final String cookies;
        public final boolean authExpired;

        private Operation(boolean success, String message, T data, String cookies, boolean authExpired) {
            this.success = success;
            this.message = message;
            this.data = data;
            this.cookies = cookies == null ? "" : cookies;
            this.authExpired = authExpired;
        }

        public static <T> Operation<T> success(String message, T data, String cookies) {
            return new Operation<>(true, message, data, cookies, false);
        }

        public static <T> Operation<T> failure(String message, String cookies, boolean authExpired) {
            return new Operation<>(false, message, null, cookies, authExpired);
        }
    }

    public static final class TaskBundle {
        public final List<CheckinTask> pending;
        public final List<CheckinTask> completed;
        public final List<CheckinTask> absent;

        public TaskBundle(List<CheckinTask> pending, List<CheckinTask> completed, List<CheckinTask> absent) {
            this.pending = Collections.unmodifiableList(pending);
            this.completed = Collections.unmodifiableList(completed);
            this.absent = Collections.unmodifiableList(absent);
        }
    }

    public static final class UserInfo {
        public final String studentId;
        public final String name;

        public UserInfo(String studentId, String name) {
            this.studentId = studentId == null ? "" : studentId;
            this.name = name == null ? "" : name;
        }
    }

    public String passwordLoginUrl() {
        try {
            return PASSWORD_LOGIN_URL + URLEncoder.encode(LOGIN_SERVICE, StandardCharsets.UTF_8.name());
        } catch (Exception exception) {
            return PASSWORD_LOGIN_URL;
        }
    }

    public Operation<String> refreshSession(String cookies) {
        if (cookies == null || cookies.trim().isEmpty()) {
            return Operation.failure("未找到登录信息", "", true);
        }
        String sop = CookieUtils.get(cookies, "_sop_session_");
        if (sop.isEmpty()) {
            if (CookieUtils.has(cookies, "SESSION")) {
                return Operation.success("已有登录信息", cookies, cookies);
            }
            return Operation.failure("登录信息不完整，请重新登录", cookies, true);
        }

        // Match the desktop fix: never let a stale SESSION short-circuit SOP
        // renewal. Only a SESSION issued by one of the requests below counts.
        String renewalCookies = CookieUtils.without(cookies, "SESSION");
        try {
            JSONObject payload = decodeSopPayload(sop);
            JSONObject extra = parseExtra(payload.opt("extra"));
            String openId = firstNonEmpty(extra.optString("openId"), extra.optString("open_id"));
            String ticket = payload.optString("ticket", "");

            String refreshed = "";
            if (!openId.isEmpty()) {
                refreshed = followForNewSession(
                        QFHY_BASE + "/xg/app/qddk/admin?open_id=" + encode(openId),
                        renewalCookies
                );
            }
            if (refreshed.isEmpty() && !ticket.isEmpty()) {
                refreshed = followForNewSession(
                        QFHY_BASE + "/site/appware/system/sso/login?ticket=" + encode(ticket)
                                + "&target=" + encode(QDDK_ENTRY),
                        renewalCookies
                );
            }
            if (refreshed.isEmpty() && !openId.isEmpty()) {
                HttpResult result = request(
                        "GET",
                        QFHY_BASE + "/site/app/base/common/api/user/current.rst",
                        renewalCookies,
                        null,
                        true
                );
                if (CookieUtils.has(result.cookies, "SESSION")) {
                    refreshed = result.cookies;
                }
            }
            if (!refreshed.isEmpty() && CookieUtils.has(refreshed, "SESSION")) {
                String merged = CookieUtils.merge(renewalCookies, refreshed);
                return Operation.success("登录态已续期", merged, merged);
            }
        } catch (Exception ignored) {
            // The caller will validate the existing SESSION once before asking
            // for interactive login. No secret material is included in errors.
        }
        return Operation.failure("登录态已过期，请重新登录", cookies, true);
    }

    public Operation<TaskBundle> loadTasks(String cookies) {
        Operation<String> renewal = refreshSession(cookies);
        String effectiveCookies = renewal.success ? renewal.data : cookies;
        try {
            List<CheckinTask> pending = fetchTasks(1, effectiveCookies);
            List<CheckinTask> completed = fetchTasks(2, effectiveCookies);
            List<CheckinTask> absent = fetchTasks(3, effectiveCookies);
            for (CheckinTask task : completed) {
                task.statusText = "已签到";
                if (task.checkinTime.isEmpty()) {
                    enrichCheckinTime(task, effectiveCookies);
                }
            }
            for (CheckinTask task : absent) {
                task.statusText = "缺勤";
            }
            return Operation.success(
                    "任务已刷新",
                    new TaskBundle(pending, completed, absent),
                    effectiveCookies
            );
        } catch (ApiException exception) {
            return Operation.failure(exception.getMessage(), effectiveCookies, exception.authExpired);
        } catch (Exception exception) {
            return Operation.failure("网络请求失败，请稍后重试", effectiveCookies, false);
        }
    }

    public Operation<CheckinTask> performCheckin(String cookies, LocationPreset location) {
        Operation<String> renewal = refreshSession(cookies);
        String effectiveCookies = renewal.success ? renewal.data : cookies;
        try {
            List<CheckinTask> pending = fetchTasks(1, effectiveCookies);
            if (pending.isEmpty()) {
                return Operation.success("当前没有待签到任务", null, effectiveCookies);
            }

            String today = formatDate("yyyy-MM-dd");
            CheckinTask selected = pending.get(0);
            for (CheckinTask task : pending) {
                if (today.equals(task.needTime) && "进行中".equals(task.statusText)) {
                    selected = task;
                    break;
                }
            }

            JSONObject detail = fetchDetail(selected.id, effectiveCookies);
            JSONObject dkxx = detail.optJSONObject("dkxx");
            if (dkxx != null && dkxx.optInt("qdzt", 0) == 1) {
                selected.checkinStatus = 1;
                selected.checkinTime = dkxx.optString("qdsj", selected.checkinTime);
                return Operation.success("今日已签到", selected, effectiveCookies);
            }

            String checkinTime = formatDate("yyyy-MM-dd HH:mm:ss");
            JSONObject body = new JSONObject();
            body.put("id", selected.id);
            body.put("qdzt", 1);
            body.put("qdsj", checkinTime);
            body.put("isOuted", 0);
            body.put("isLated", 0);
            body.put("dkddPhoto", "");
            body.put("qdddjtdz", location.address);
            body.put("location", location.locationJson());
            body.put("txxx", "{}");

            HttpResult response = request("POST", CHECKIN_URL, effectiveCookies, body.toString(), true);
            JSONObject payload = parsePayload(response);
            ensureApiSuccess(payload, "签到提交失败");
            selected.checkinStatus = 1;
            selected.checkinTime = checkinTime;
            return Operation.success("签到成功：" + checkinTime, selected, response.cookies);
        } catch (ApiException exception) {
            return Operation.failure(exception.getMessage(), effectiveCookies, exception.authExpired);
        } catch (Exception exception) {
            return Operation.failure("签到失败，请稍后重试", effectiveCookies, false);
        }
    }

    public UserInfo extractUserInfo(String cookies) {
        String sop = CookieUtils.get(cookies, "_sop_session_");
        if (sop.isEmpty()) {
            return new UserInfo("", "");
        }
        try {
            JSONObject payload = decodeSopPayload(sop);
            JSONObject extra = parseExtra(payload.opt("extra"));
            return new UserInfo(
                    String.valueOf(payload.opt("uid") == null ? "" : payload.opt("uid")),
                    firstNonEmpty(extra.optString("userName"), extra.optString("name"))
            );
        } catch (Exception ignored) {
            return new UserInfo("", "");
        }
    }

    private List<CheckinTask> fetchTasks(int status, String cookies) throws Exception {
        HttpResult response = request("GET", TASK_LIST_URL + status, cookies, null, true);
        JSONObject payload = parsePayload(response);
        ensureApiSuccess(payload, "获取任务列表失败");
        JSONObject result = payload.optJSONObject("result");
        JSONArray data = result == null ? null : result.optJSONArray("data");
        List<CheckinTask> tasks = new ArrayList<>();
        if (data != null) {
            for (int index = 0; index < data.length(); index++) {
                JSONObject item = data.optJSONObject(index);
                if (item != null) {
                    tasks.add(CheckinTask.fromJson(item));
                }
            }
        }
        return tasks;
    }

    private JSONObject fetchDetail(int taskId, String cookies) throws Exception {
        HttpResult response = request("GET", TASK_DETAIL_URL + taskId, cookies, null, true);
        JSONObject payload = parsePayload(response);
        ensureApiSuccess(payload, "获取任务详情失败");
        JSONObject result = payload.optJSONObject("result");
        JSONObject data = result == null ? null : result.optJSONObject("data");
        return data == null ? new JSONObject() : data;
    }

    private void enrichCheckinTime(CheckinTask task, String cookies) {
        try {
            JSONObject detail = fetchDetail(task.id, cookies);
            JSONObject dkxx = detail.optJSONObject("dkxx");
            if (dkxx != null) {
                task.checkinTime = dkxx.optString("qdsj", "");
                task.checkinStatus = dkxx.optInt("qdzt", task.checkinStatus);
            }
        } catch (Exception ignored) {
            // History remains useful even if one detail endpoint is unavailable.
        }
    }

    private String followForNewSession(String initialUrl, String renewalCookies) throws IOException {
        String currentUrl = initialUrl;
        String currentCookies = renewalCookies;
        for (int redirect = 0; redirect < 6; redirect++) {
            HttpResult result = request("GET", currentUrl, currentCookies, null, false);
            currentCookies = result.cookies;
            if (CookieUtils.has(currentCookies, "SESSION")) {
                return currentCookies;
            }
            if (result.statusCode < 300 || result.statusCode >= 400 || result.location.isEmpty()) {
                break;
            }
            currentUrl = new URL(new URL(currentUrl), result.location).toString();
        }
        return "";
    }

    private HttpResult request(String method, String url, String cookies, String body, boolean apiHeaders) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setConnectTimeout(TIMEOUT_MS);
        connection.setReadTimeout(TIMEOUT_MS);
        connection.setRequestMethod(method);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/125 Mobile Safari/537.36");
        connection.setRequestProperty("Accept-Language", "zh-CN,zh;q=0.9");
        connection.setRequestProperty("Accept", apiHeaders ? "application/json, text/plain, */*" : "text/html,application/xhtml+xml,*/*;q=0.8");
        connection.setRequestProperty("Referer", apiHeaders ? QDDK_ENTRY : QFHY_BASE + "/edu/");
        if (apiHeaders) {
            connection.setRequestProperty("appcode", "qddk");
        }
        if (cookies != null && !cookies.trim().isEmpty() && QFHY_BASE.equals(urlOrigin(url))) {
            connection.setRequestProperty("Cookie", cookies);
        }
        if (body != null) {
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(bytes);
            }
        }

        int statusCode = connection.getResponseCode();
        String responseBody = readBody(connection, statusCode);
        List<String> setCookieHeaders = new ArrayList<>();
        for (Map.Entry<String, List<String>> header : connection.getHeaderFields().entrySet()) {
            if (header.getKey() != null && "set-cookie".equalsIgnoreCase(header.getKey()) && header.getValue() != null) {
                setCookieHeaders.addAll(header.getValue());
            }
        }
        String mergedCookies = CookieUtils.mergeSetCookieHeaders(cookies, setCookieHeaders);
        String location = connection.getHeaderField("Location");
        connection.disconnect();
        return new HttpResult(statusCode, responseBody, mergedCookies, location == null ? "" : location);
    }

    private static String readBody(HttpURLConnection connection, int statusCode) throws IOException {
        InputStream stream = statusCode >= 400 ? connection.getErrorStream() : connection.getInputStream();
        if (stream == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private static JSONObject parsePayload(HttpResult response) throws ApiException {
        if (response.statusCode != 200) {
            throw new ApiException("服务器请求失败 (" + response.statusCode + ")", false);
        }
        try {
            return new JSONObject(response.body);
        } catch (JSONException exception) {
            throw new ApiException("服务器返回了无效数据", false);
        }
    }

    private static void ensureApiSuccess(JSONObject payload, String fallback) throws ApiException {
        boolean success = payload.optBoolean("success", false) && payload.optInt("resultCode", -1) == 0;
        if (success) {
            return;
        }
        String message = firstNonEmpty(payload.optString("errorMsg"), payload.optString("message"), fallback);
        boolean authExpired = message.contains("身份信息")
                || message.contains("登录已过期")
                || message.contains("重新登录");
        throw new ApiException(authExpired ? message + "，请重新登录" : message, authExpired);
    }

    private static JSONObject decodeSopPayload(String token) throws JSONException {
        String[] parts = token.split("\\.");
        if (parts.length != 3) {
            throw new JSONException("Invalid SOP token");
        }
        byte[] decoded = Base64.decode(parts[1], Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
        return new JSONObject(new String(decoded, StandardCharsets.UTF_8));
    }

    private static JSONObject parseExtra(Object value) {
        if (value instanceof JSONObject) {
            return (JSONObject) value;
        }
        if (value instanceof String) {
            try {
                return new JSONObject((String) value);
            } catch (JSONException ignored) {
                return new JSONObject();
            }
        }
        return new JSONObject();
    }

    private static String encode(String value) {
        try {
            return URLEncoder.encode(value, StandardCharsets.UTF_8.name());
        } catch (Exception exception) {
            return value;
        }
    }

    private static String formatDate(String pattern) {
        SimpleDateFormat formatter = new SimpleDateFormat(pattern, Locale.CHINA);
        formatter.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        return formatter.format(System.currentTimeMillis());
    }

    private static String firstNonEmpty(String... values) {
        if (values != null) {
            for (String value : values) {
                if (value != null && !value.trim().isEmpty()) {
                    return value;
                }
            }
        }
        return "";
    }

    private static String urlOrigin(String value) {
        try {
            URL url = new URL(value);
            return url.getProtocol() + "://" + url.getHost();
        } catch (Exception exception) {
            return "";
        }
    }

    private static final class HttpResult {
        final int statusCode;
        final String body;
        final String cookies;
        final String location;

        HttpResult(int statusCode, String body, String cookies, String location) {
            this.statusCode = statusCode;
            this.body = body;
            this.cookies = cookies;
            this.location = location;
        }
    }

    private static final class ApiException extends Exception {
        final boolean authExpired;

        ApiException(String message, boolean authExpired) {
            super(message);
            this.authExpired = authExpired;
        }
    }
}
