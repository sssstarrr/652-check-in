package cn.edu.suse.checkin.data;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class SecureSessionStore {
    private static final String PREFERENCES = "checkin_652_secure";
    private static final String KEY_ALIAS = "checkin_652_session_key_v1";
    private static final String KEY_SESSION = "session_encrypted";
    private static final String KEY_STUDENT_ID = "student_id";
    private static final String KEY_NAME = "display_name";
    private static final String KEY_CAMPUS = "campus";

    private final SharedPreferences preferences;

    public SecureSessionStore(Context context) {
        preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    public synchronized boolean saveSession(String cookies, String studentId, String name) {
        if (cookies == null || cookies.trim().isEmpty()) {
            return false;
        }
        try {
            String encrypted = encrypt(cookies);
            preferences.edit()
                    .putString(KEY_SESSION, encrypted)
                    .putString(KEY_STUDENT_ID, safe(studentId))
                    .putString(KEY_NAME, safe(name))
                    .apply();
            return true;
        } catch (Exception exception) {
            preferences.edit().remove(KEY_SESSION).apply();
            return false;
        }
    }

    public synchronized String getSession() {
        String encrypted = preferences.getString(KEY_SESSION, "");
        if (encrypted == null || encrypted.trim().isEmpty()) {
            return "";
        }
        try {
            return decrypt(encrypted);
        } catch (Exception exception) {
            preferences.edit().remove(KEY_SESSION).apply();
            return "";
        }
    }

    public boolean hasSession() {
        return !getSession().trim().isEmpty();
    }

    public String getStudentId() {
        return preferences.getString(KEY_STUDENT_ID, "") == null
                ? ""
                : preferences.getString(KEY_STUDENT_ID, "");
    }

    public String getDisplayName() {
        return preferences.getString(KEY_NAME, "") == null
                ? ""
                : preferences.getString(KEY_NAME, "");
    }

    public String getCampus() {
        String campus = preferences.getString(KEY_CAMPUS, "宜宾");
        return campus == null || campus.trim().isEmpty() ? "宜宾" : campus;
    }

    public void setCampus(String campus) {
        preferences.edit().putString(KEY_CAMPUS, safe(campus)).apply();
    }

    public void clearSession() {
        preferences.edit()
                .remove(KEY_SESSION)
                .remove(KEY_STUDENT_ID)
                .remove(KEY_NAME)
                .apply();
    }

    private SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    private String encrypt(String value) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        byte[] iv = cipher.getIV();
        ByteBuffer buffer = ByteBuffer.allocate(4 + iv.length + encrypted.length);
        buffer.putInt(iv.length);
        buffer.put(iv);
        buffer.put(encrypted);
        return Base64.encodeToString(buffer.array(), Base64.NO_WRAP);
    }

    private String decrypt(String encoded) throws Exception {
        ByteBuffer buffer = ByteBuffer.wrap(Base64.decode(encoded, Base64.NO_WRAP));
        int ivLength = buffer.getInt();
        if (ivLength < 12 || ivLength > 16 || buffer.remaining() <= ivLength) {
            throw new IllegalArgumentException("Invalid encrypted session");
        }
        byte[] iv = new byte[ivLength];
        buffer.get(iv);
        byte[] encrypted = new byte[buffer.remaining()];
        buffer.get(encrypted);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }
}
