package cn.edu.suse.checkin;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.TimePickerDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.webkit.CookieManager;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;

import cn.edu.suse.checkin.data.ScheduleStore;
import cn.edu.suse.checkin.data.SecureSessionStore;
import cn.edu.suse.checkin.model.CheckinTask;
import cn.edu.suse.checkin.model.LocationPreset;
import cn.edu.suse.checkin.network.CheckinClient;
import cn.edu.suse.checkin.scheduling.CheckinScheduler;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int LOGIN_REQUEST = 652;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private SecureSessionStore store;
    private ScheduleStore scheduleStore;
    private CheckinClient client;
    private TextView accountText;
    private TextView statusText;
    private ProgressBar progressBar;
    private Spinner campusSpinner;
    private Button checkinButton;
    private Button refreshButton;
    private LinearLayout pendingContainer;
    private LinearLayout completedContainer;
    private Switch autoCheckinSwitch;
    private Button scheduleTimeButton;
    private TextView autoStatusText;
    private boolean busy;
    private boolean loginVisible;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        store = new SecureSessionStore(this);
        scheduleStore = new ScheduleStore(this);
        client = new CheckinClient();
        accountText = findViewById(R.id.accountText);
        statusText = findViewById(R.id.statusText);
        progressBar = findViewById(R.id.progressBar);
        campusSpinner = findViewById(R.id.campusSpinner);
        checkinButton = findViewById(R.id.checkinButton);
        refreshButton = findViewById(R.id.refreshButton);
        pendingContainer = findViewById(R.id.pendingContainer);
        completedContainer = findViewById(R.id.completedContainer);
        autoCheckinSwitch = findViewById(R.id.autoCheckinSwitch);
        scheduleTimeButton = findViewById(R.id.scheduleTimeButton);
        autoStatusText = findViewById(R.id.autoStatusText);
        Button logoutButton = findViewById(R.id.logoutButton);

        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_item,
                LocationPreset.campusNames()
        );
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        campusSpinner.setAdapter(adapter);
        int selectedCampus = LocationPreset.campusNames().indexOf(store.getCampus());
        campusSpinner.setSelection(Math.max(0, selectedCampus));

        checkinButton.setOnClickListener(view -> performCheckin());
        refreshButton.setOnClickListener(view -> refreshTasks());
        logoutButton.setOnClickListener(view -> confirmLogout());
        configureScheduleControls();

        if (store.hasSession()) {
            updateAccountText();
            refreshTasks();
        } else {
            openLogin();
        }
        if (scheduleStore.isEnabled()) {
            CheckinScheduler.schedule(this);
        }
    }

    private void configureScheduleControls() {
        autoCheckinSwitch.setChecked(scheduleStore.isEnabled());
        updateScheduleUi();
        autoCheckinSwitch.setOnCheckedChangeListener((button, checked) -> {
            if (checked && !store.hasSession()) {
                scheduleStore.setEnabled(false);
                button.setChecked(false);
                setStatus("请先登录再启用后台签到", true);
                openLogin();
                return;
            }
            scheduleStore.setEnabled(checked);
            if (checked) {
                requestNotificationPermissionIfNeeded();
                boolean scheduled = CheckinScheduler.schedule(this);
                if (!scheduled) {
                    scheduleStore.setLastResult("系统未能创建后台任务");
                }
            } else {
                CheckinScheduler.cancel(this);
                scheduleStore.setLastResult("");
            }
            updateScheduleUi();
        });
        scheduleTimeButton.setOnClickListener(view -> new TimePickerDialog(
                this,
                (picker, hour, minute) -> {
                    scheduleStore.setTime(hour, minute);
                    scheduleStore.setLastResult("");
                    if (scheduleStore.isEnabled()) {
                        CheckinScheduler.schedule(this);
                    }
                    updateScheduleUi();
                },
                scheduleStore.getHour(),
                scheduleStore.getMinute(),
                true
        ).show());
    }

    private void updateScheduleUi() {
        scheduleTimeButton.setText(getString(
                R.string.schedule_time_format,
                scheduleStore.getHour(),
                scheduleStore.getMinute()
        ));
        if (!scheduleStore.isEnabled()) {
            autoStatusText.setText(R.string.schedule_disabled);
            return;
        }
        String lastResult = scheduleStore.getLastResult();
        autoStatusText.setText(lastResult.trim().isEmpty() ? getString(R.string.schedule_waiting) : lastResult);
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 653);
        }
    }

    private void openLogin() {
        if (loginVisible) {
            return;
        }
        loginVisible = true;
        startActivityForResult(new Intent(this, LoginActivity.class), LOGIN_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != LOGIN_REQUEST) {
            return;
        }
        loginVisible = false;
        if (resultCode == RESULT_OK && store.hasSession()) {
            updateAccountText();
            setStatus("登录成功，正在刷新任务", false);
            refreshTasks();
            if (scheduleStore.isEnabled()) {
                CheckinScheduler.schedule(this);
            }
        } else if (!store.hasSession()) {
            setStatus("请先登录", true);
        }
    }

    private void refreshTasks() {
        if (busy) {
            return;
        }
        String cookies = store.getSession();
        if (cookies.trim().isEmpty()) {
            openLogin();
            return;
        }
        setBusy(true, "正在刷新任务…");
        executor.execute(() -> {
            CheckinClient.Operation<CheckinClient.TaskBundle> result = client.loadTasks(cookies);
            persistRefreshedSession(result.cookies);
            runOnUiThread(() -> {
                setBusy(false, result.message);
                if (result.success && result.data != null) {
                    renderTasks(pendingContainer, result.data.pending, false);
                    renderTasks(completedContainer, result.data.completed, true);
                    setStatus(
                            "待签到 " + result.data.pending.size()
                                    + " 项 · 已完成 " + result.data.completed.size() + " 项",
                            false
                    );
                } else if (result.authExpired) {
                    setStatus(result.message, true);
                    openLogin();
                } else {
                    setStatus(result.message, true);
                }
            });
        });
    }

    private void performCheckin() {
        if (busy) {
            return;
        }
        String cookies = store.getSession();
        if (cookies.trim().isEmpty()) {
            openLogin();
            return;
        }
        String campus = String.valueOf(campusSpinner.getSelectedItem());
        store.setCampus(campus);
        LocationPreset location = LocationPreset.forCampus(campus);
        setBusy(true, "正在签到：" + location.address);
        executor.execute(() -> {
            CheckinClient.Operation<CheckinTask> result = client.performCheckin(cookies, location);
            persistRefreshedSession(result.cookies);
            runOnUiThread(() -> {
                setBusy(false, result.message);
                setStatus(result.message, !result.success);
                if (result.authExpired) {
                    openLogin();
                } else if (result.success) {
                    refreshTasks();
                }
            });
        });
    }

    private void persistRefreshedSession(String cookies) {
        if (cookies == null || cookies.trim().isEmpty() || cookies.equals(store.getSession())) {
            return;
        }
        store.saveSession(cookies, store.getStudentId(), store.getDisplayName());
    }

    private void renderTasks(LinearLayout container, List<CheckinTask> tasks, boolean completed) {
        container.removeAllViews();
        if (tasks.isEmpty()) {
            TextView empty = new TextView(this);
            empty.setText(completed ? "暂无已完成任务" : "当前没有待签到任务");
            empty.setTextColor(getColor(R.color.text_secondary));
            empty.setPadding(dp(4), dp(10), dp(4), dp(10));
            container.addView(empty);
            return;
        }

        LayoutInflater inflater = LayoutInflater.from(this);
        int limit = completed ? Math.min(tasks.size(), 10) : tasks.size();
        for (int index = 0; index < limit; index++) {
            CheckinTask task = tasks.get(index);
            View row = inflater.inflate(R.layout.row_task, container, false);
            row.setBackgroundResource(completed ? R.drawable.bg_task_done : R.drawable.bg_task_pending);
            TextView title = row.findViewById(R.id.taskTitle);
            TextView meta = row.findViewById(R.id.taskMeta);
            title.setText(task.name);
            String time = completed && !task.checkinTime.isEmpty()
                    ? getString(R.string.task_checkin_time_format, task.checkinTime)
                    : getString(R.string.task_date_time_format, safeText(task.needTime), safeText(task.startTime));
            meta.setText(getString(R.string.task_meta_format, safeText(task.statusText), time));
            container.addView(row);
        }
    }

    private void updateAccountText() {
        String name = store.getDisplayName();
        String studentId = store.getStudentId();
        if (!name.trim().isEmpty() && !studentId.trim().isEmpty() && !name.equals(studentId)) {
            accountText.setText(getString(R.string.account_name_format, name, studentId));
        } else if (!studentId.trim().isEmpty()) {
            accountText.setText(getString(R.string.account_id_format, studentId));
        } else {
            accountText.setText("已安全登录");
        }
    }

    private void confirmLogout() {
        new AlertDialog.Builder(this)
                .setTitle("退出登录")
                .setMessage("将删除本机加密保存的登录态，确定继续吗？")
                .setNegativeButton("取消", null)
                .setPositiveButton("退出", (dialog, which) -> {
                    scheduleStore.setEnabled(false);
                    scheduleStore.setLastResult("");
                    CheckinScheduler.cancel(this);
                    autoCheckinSwitch.setChecked(false);
                    store.clearSession();
                    CookieManager.getInstance().removeAllCookies(null);
                    CookieManager.getInstance().flush();
                    pendingContainer.removeAllViews();
                    completedContainer.removeAllViews();
                    openLogin();
                })
                .show();
    }

    private void setBusy(boolean value, String message) {
        busy = value;
        progressBar.setVisibility(value ? View.VISIBLE : View.GONE);
        checkinButton.setEnabled(!value);
        refreshButton.setEnabled(!value);
        if (message != null && !message.trim().isEmpty()) {
            setStatus(message, false);
        }
    }

    private void setStatus(String message, boolean error) {
        statusText.setText(message);
        statusText.setTextColor(getColor(error ? R.color.error : R.color.text_secondary));
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static String safeText(String value) {
        return value == null || value.trim().isEmpty() ? "-" : value;
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (scheduleStore != null) {
            updateScheduleUi();
        }
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
