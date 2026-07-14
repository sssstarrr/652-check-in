package cn.edu.suse.checkin;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;

import cn.edu.suse.checkin.data.SecureSessionStore;
import cn.edu.suse.checkin.network.CheckinClient;
import cn.edu.suse.checkin.network.CookieUtils;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class LoginActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean completing = new AtomicBoolean(false);

    private CheckinClient client;
    private SecureSessionStore store;
    private CookieManager cookieManager;
    private WebView webView;
    private TextView statusText;
    private ProgressBar progressBar;
    private boolean qrMode;
    private boolean freshLoginSignal;

    @Override
    @SuppressLint("SetJavaScriptEnabled")
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        client = new CheckinClient();
        store = new SecureSessionStore(this);
        cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);

        statusText = findViewById(R.id.loginStatusText);
        progressBar = findViewById(R.id.loginProgress);
        webView = findViewById(R.id.loginWebView);
        Button passwordButton = findViewById(R.id.passwordLoginButton);
        Button qrButton = findViewById(R.id.qrLoginButton);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setUserAgentString(
                "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                        + "(KHTML, like Gecko) Chrome/125 Mobile Safari/537.36"
        );
        cookieManager.setAcceptThirdPartyCookies(webView, true);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
                updateFreshSignal(url);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                updateFreshSignal(url);
                probeLogin(url);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return false;
            }
        });

        passwordButton.setOnClickListener(view -> startLogin(false));
        qrButton.setOnClickListener(view -> startLogin(true));
        startLogin(false);
    }

    private void startLogin(boolean useQr) {
        qrMode = useQr;
        freshLoginSignal = false;
        completing.set(false);
        statusText.setText(useQr
                ? "请使用微信扫描页面中的二维码"
                : "请在学校官方页面完成认证");
        progressBar.setVisibility(View.VISIBLE);
        cookieManager.removeAllCookies(removed -> {
            cookieManager.flush();
            runOnUiThread(() -> webView.loadUrl(useQr ? CheckinClient.WECHAT_LOGIN_URL : client.passwordLoginUrl()));
        });
    }

    private void updateFreshSignal(String url) {
        if (url == null) {
            return;
        }
        if (url.contains("/callback/edu/")
                || url.contains("ybClientId=")
                || url.contains("/xg/app/qddk")) {
            freshLoginSignal = true;
        }
    }

    private void probeLogin(String currentUrl) {
        if (completing.get()) {
            return;
        }
        String cookies = cookieManager.getCookie(CheckinClient.QFHY_BASE);
        if (cookies == null || cookies.trim().isEmpty()) {
            return;
        }
        boolean hasSession = CookieUtils.has(cookies, "SESSION");
        boolean hasSop = CookieUtils.has(cookies, "_sop_session_");
        boolean qfhyPage = currentUrl != null
                && currentUrl.startsWith(CheckinClient.QFHY_BASE)
                && !currentUrl.contains("qrcodelogin");

        if (qrMode) {
            if (!freshLoginSignal || (!hasSop && !hasSession)) {
                return;
            }
        } else if (!qfhyPage || (!hasSession && !hasSop)) {
            return;
        }
        completeLogin(cookies, hasSession);
    }

    private void completeLogin(String webCookies, boolean alreadyHasSession) {
        if (!completing.compareAndSet(false, true)) {
            return;
        }
        progressBar.setVisibility(View.VISIBLE);
        statusText.setText(R.string.completing_sso);
        executor.execute(() -> {
            CheckinClient.Operation<String> renewal = client.refreshSession(webCookies);
            String finalCookies = renewal.success ? renewal.data : (alreadyHasSession ? webCookies : "");
            if (finalCookies.trim().isEmpty() || !CookieUtils.has(finalCookies, "SESSION")) {
                runOnUiThread(() -> {
                    completing.set(false);
                    progressBar.setVisibility(View.GONE);
                    statusText.setText(R.string.session_acquire_failed);
                });
                return;
            }

            CheckinClient.UserInfo user = client.extractUserInfo(finalCookies);
            boolean saved = store.saveSession(finalCookies, user.studentId, user.name);
            runOnUiThread(() -> {
                progressBar.setVisibility(View.GONE);
                if (!saved) {
                    completing.set(false);
                    statusText.setText("系统安全存储不可用，请重试");
                    return;
                }
                statusText.setText("登录成功");
                setResult(RESULT_OK);
                finish();
            });
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (qrMode && webView != null) {
            webView.onResume();
            webView.resumeTimers();
            webView.postDelayed(() -> probeLogin(webView.getUrl()), 400);
            webView.postDelayed(() -> probeLogin(webView.getUrl()), 1_200);
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
            webView.pauseTimers();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }
}
