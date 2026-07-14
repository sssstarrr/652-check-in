package cn.edu.suse.checkin.network;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class CookieUtils {
    private CookieUtils() {
    }

    public static Map<String, String> parse(String cookieHeader) {
        Map<String, String> result = new LinkedHashMap<>();
        if (cookieHeader == null || cookieHeader.trim().isEmpty()) {
            return result;
        }
        for (String part : cookieHeader.split(";")) {
            String token = part.trim();
            int separator = token.indexOf('=');
            if (separator <= 0) {
                continue;
            }
            String name = token.substring(0, separator).trim();
            String value = token.substring(separator + 1).trim();
            if (!name.isEmpty()) {
                if (value.isEmpty()) {
                    result.remove(name);
                } else {
                    result.put(name, value);
                }
            }
        }
        return result;
    }

    public static String merge(String... cookieHeaders) {
        Map<String, String> merged = new LinkedHashMap<>();
        if (cookieHeaders != null) {
            for (String header : cookieHeaders) {
                for (Map.Entry<String, String> entry : parse(header).entrySet()) {
                    merged.put(entry.getKey(), entry.getValue());
                }
            }
        }
        return serialize(merged);
    }

    public static String mergeSetCookieHeaders(String baseCookies, List<String> setCookieHeaders) {
        Map<String, String> merged = parse(baseCookies);
        if (setCookieHeaders != null) {
            for (String header : setCookieHeaders) {
                if (header == null || header.trim().isEmpty()) {
                    continue;
                }
                String firstPart = header.split(";", 2)[0].trim();
                int separator = firstPart.indexOf('=');
                if (separator <= 0) {
                    continue;
                }
                String name = firstPart.substring(0, separator).trim();
                String value = firstPart.substring(separator + 1).trim();
                if (value.isEmpty()) {
                    merged.remove(name);
                } else {
                    merged.put(name, value);
                }
            }
        }
        return serialize(merged);
    }

    public static String without(String cookieHeader, String name) {
        Map<String, String> cookies = parse(cookieHeader);
        cookies.remove(name);
        return serialize(cookies);
    }

    public static String get(String cookieHeader, String name) {
        return parse(cookieHeader).getOrDefault(name, "");
    }

    public static boolean has(String cookieHeader, String name) {
        return !get(cookieHeader, name).isEmpty();
    }

    public static boolean isSensitiveCookieName(String name) {
        String lower = name == null ? "" : name.toLowerCase(Locale.ROOT);
        return lower.contains("session") || lower.contains("token") || lower.contains("ticket");
    }

    private static String serialize(Map<String, String> cookies) {
        StringBuilder builder = new StringBuilder();
        for (Map.Entry<String, String> entry : cookies.entrySet()) {
            if (builder.length() > 0) {
                builder.append("; ");
            }
            builder.append(entry.getKey()).append('=').append(entry.getValue());
        }
        return builder.toString();
    }
}
