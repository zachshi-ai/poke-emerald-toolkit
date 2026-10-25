package com.stepx.pokeemerald;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Context;
import android.content.DialogInterface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.view.WindowManager;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;

public class MainActivity extends Activity {
    static final String ROM_ASSET = "pokeemerald.gba";
    static final String ROM_NAME = "pokeemerald.gba";
    static final String LOG_NAME = "pokeemerald_log.txt";
    GameView view;
    static File logDir;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        AppCtx.set(this);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        hideSystemUi();

        logDir = getFilesDir();
        publishLog();  // 先把手上一轮的日志投放到 Download，方便排查

        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
            @Override
            public void uncaughtException(Thread t, Throwable e) {
                logCrash(MainActivity.this, "ui-thread", e);
                publishLog();
                if (prev != null) prev.uncaughtException(t, e);
            }
        });

        // ROM 更新逻辑：资产长度或版本标记变化时重新释放，避免旧内核一直复用
        File rom = new File(getFilesDir(), ROM_NAME);
        File mark = new File(getFilesDir(), "rom_version.txt");
        int versionCode = 0;
        try {
            versionCode = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
        } catch (Throwable ignored) {
        }
        long assetLen = 0;
        try {
            assetLen = getAssets().openFd(ROM_ASSET).getLength();
        } catch (Throwable t) {
            try {
                java.io.InputStream in = getAssets().open(ROM_ASSET);
                assetLen = in.available();
                in.close();
            } catch (Throwable ignored) {
            }
        }
        String last = logDir != null && mark.exists() ? readAll(mark).trim() : "";
        boolean needCopy = !rom.exists() || (assetLen > 0 && rom.length() != assetLen) || !String.valueOf(versionCode).equals(last);
        if (needCopy) {
            try {
                copyAsset(ROM_ASSET, rom);
                java.io.FileOutputStream fo = new java.io.FileOutputStream(mark, false);
                fo.write(String.valueOf(versionCode).getBytes("UTF-8"));
                fo.close();
            } catch (IOException e) {
                Toast.makeText(this, "ROM 释放失败: " + e.getMessage(), Toast.LENGTH_LONG).show();
            }
        }

        try {
            try {
            java.io.InputStream in = getAssets().open("mem.cfg");
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[512];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            PokemonBox.loadConfig(bo.toString("UTF-8"));
        } catch (Throwable ignored) {
        }

        view = new GameView(this, rom.getAbsolutePath(),
                    new File(getFilesDir(), "save.sav").getAbsolutePath(),
                    new File(getFilesDir(), "state.sav").getAbsolutePath(),
                    getFilesDir());
            setContentView(view);
        } catch (Throwable t) {
            logCrash(this, "create-view", t);
            publishLog();
            showError(t);
        }

        Thread publisher = new Thread(new Runnable() {
            @Override
            public void run() {
                while (true) {
                    try { Thread.sleep(1500); } catch (InterruptedException ignored) { return; }
                    publishLog();
                }
            }
        });
        publisher.setDaemon(true);
        publisher.start();
    }

    private void showError(Throwable t) {
        StringWriter sw = new StringWriter();
        t.printStackTrace(new PrintWriter(sw));
        ScrollView sv = new ScrollView(this);
        TextView tv = new TextView(this);
        tv.setText("启动异常，请把这段内容发给我：\n\n" + sw.toString());
        tv.setTextSize(11f);
        tv.setPadding(24, 24, 24, 24);
        sv.addView(tv);
        setContentView(sv);
    }

    static String readAll(File f) {
        if (f == null || !f.exists()) return "";
        try {
            FileInputStream in = new FileInputStream(f);
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] b = new byte[4096];
            int n;
            while ((n = in.read(b)) > 0) bo.write(b, 0, n);
            in.close();
            return bo.toString("UTF-8");
        } catch (Throwable t) {
            return "";
        }
    }

    static void publishLog() {
        try {
            StringBuilder sb = new StringBuilder();
            String stage = readAll(new File(logDir, "stage.txt"));
            if (stage.length() > 0) sb.append("[stage]\n").append(stage).append("\n");
            String crash = readAll(new File(logDir, "crash.txt"));
            if (crash.length() > 0) {
                sb.append("[crash]\n");
                int from = Math.max(0, crash.length() - 6000);
                sb.append(crash.substring(from)).append("\n");
            }
            if (sb.length() == 0) sb.append("no-log\n");
            writeDownload(LOG_NAME, sb.toString());
        } catch (Throwable ignored) {
        }
    }

    static void writeDownload(String name, String content) {
        try {
            Context ctx = AppCtx.get();
            if (ctx == null) return;
            if (Build.VERSION.SDK_INT >= 29) {
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                cv.put(MediaStore.MediaColumns.MIME_TYPE, "text/plain");
                cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                try {
                    ctx.getContentResolver().delete(MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                            MediaStore.MediaColumns.DISPLAY_NAME + "=?", new String[]{name});
                } catch (Throwable ignored) { }
                Uri uri = ctx.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) return;
                OutputStream os = ctx.getContentResolver().openOutputStream(uri);
                if (os != null) {
                    os.write(content.getBytes("UTF-8"));
                    os.close();
                }
            } else {
                File f = new File(Environment.getExternalStorageDirectory(), "Download/" + name);
                FileOutputStream fos = new FileOutputStream(f, false);
                fos.write(content.getBytes("UTF-8"));
                fos.close();
            }
        } catch (Throwable ignored) {
        }
    }

    static void logCrash(Context ctx, String where, Throwable t) {
        try {
            File dir = logDir != null ? logDir : ctx.getFilesDir();
            File f = new File(dir, "crash.txt");
            FileOutputStream fos = new FileOutputStream(f, true);
            StringWriter sw = new StringWriter();
            PrintWriter pw = new PrintWriter(sw);
            pw.println("=== " + where + " " + System.currentTimeMillis());
            t.printStackTrace(pw);
            pw.flush();
            fos.write(sw.toString().getBytes("UTF-8"));
            fos.close();
        } catch (Throwable ignored) {
        }
    }

    void hideSystemUi() {
        View decor = getWindow().getDecorView();
        decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }

    private void copyAsset(String name, File out) throws IOException {
        InputStream in = getAssets().open(name);
        FileOutputStream fos = new FileOutputStream(out);
        byte[] buf = new byte[1 << 20];
        int n;
        while ((n = in.read(buf)) > 0) fos.write(buf, 0, n);
        fos.close();
        in.close();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (view != null) view.pauseGame();
    }

    @Override
    protected void onResume() {
        super.onResume();
        hideSystemUi();
        if (view != null) view.resumeGame();
    }

    private String versionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Throwable t) {
            return "?";
        }
    }

    private void showPokemonBox() {
        final PokemonBox box = new PokemonBox(view);
        final String[] actions = new String[]{
                "查看队伍与箱子", "箱子 → 队伍（换人）", "队伍 → 箱子（存起来）", "队伍内部互换",
                "箱子占用情况", "导出箱子到文件（腾空）", "从文件导入到箱子（装回来）"
        };
        new AlertDialog.Builder(this)
                .setTitle("宝可梦仓库")
                .setItems(actions, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        switch (which) {
                            case 0: {
                                StringBuilder sb = new StringBuilder(box.partySummary()).append('\n');
                                for (int i = 0; i < PokemonBox.BOX_COUNT; i++) {
                                    sb.append(box.boxSummary(i)).append('\n');
                                }
                                new AlertDialog.Builder(MainActivity.this).setTitle("当前状况").setMessage(sb.toString()).setPositiveButton("好", null).show();
                                break;
                            }
                            case 1:
                                promptBoxSwap(box);
                                break;
                            case 2:
                                promptPartyToBox(box);
                                break;
                            case 3:
                                promptPartySwap(box);
                                break;
                            case 4: {
                                StringBuilder sb = new StringBuilder();
                                for (int i = 0; i < PokemonBox.BOX_COUNT; i++) sb.append(box.boxSummary(i)).append('\n');
                                new AlertDialog.Builder(MainActivity.this).setTitle("箱子占用").setMessage(sb.toString()).setPositiveButton("好", null).show();
                                break;
                            }
                            case 5:
                                promptBoxFile(box, true);
                                break;
                            case 6:
                                promptBoxFile(box, false);
                                break;
                        }
                    }
                })
                .show();
    }

    private void promptBoxSwap(final PokemonBox box) {
        final android.widget.EditText input = new android.widget.EditText(this);
        input.setHint("箱号,位号,队伍槽位 例如 3,5,2");
        new AlertDialog.Builder(this)
                .setTitle("箱子 → 队伍")
                .setView(input)
                .setPositiveButton("确定", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int w) {
                        try {
                            String[] p = input.getText().toString().split("[,，\\s]+");
                            int b = Integer.parseInt(p[0]) - 1;
                            int pos = Integer.parseInt(p[1]) - 1;
                            int slot = Integer.parseInt(p[2]) - 1;
                            boolean ok = box.swapPartyBox(slot, b, pos);
                            Toast.makeText(MainActivity.this, ok ? "已互换，回到游戏查看队伍" : "失败：槽位为空或索引越界", Toast.LENGTH_LONG).show();
                            if (ok) view.saveSram();
                        } catch (Throwable t) {
                            Toast.makeText(MainActivity.this, "格式不对，应为 3,5,2", Toast.LENGTH_SHORT).show();
                        }
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void promptPartyToBox(final PokemonBox box) {
        final android.widget.EditText input = new android.widget.EditText(this);
        input.setHint("队伍槽位,箱号,位号 例如 2,3,5");
        new AlertDialog.Builder(this)
                .setTitle("队伍 → 箱子")
                .setView(input)
                .setPositiveButton("确定", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int w) {
                        try {
                            String[] p = input.getText().toString().split("[,，\\s]+");
                            int slot = Integer.parseInt(p[0]) - 1;
                            int b = Integer.parseInt(p[1]) - 1;
                            int pos = Integer.parseInt(p[2]) - 1;
                            boolean ok = box.partyToBox(slot, b, pos);
                            Toast.makeText(MainActivity.this, ok ? "已存入箱子" : "失败", Toast.LENGTH_SHORT).show();
                            if (ok) view.saveSram();
                        } catch (Throwable t) {
                            Toast.makeText(MainActivity.this, "格式不对，应为 2,3,5", Toast.LENGTH_SHORT).show();
                        }
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void promptBoxFile(final PokemonBox box, final boolean export) {
        final android.widget.EditText input = new android.widget.EditText(this);
        input.setHint(export ? "要导出第几号箱子（1-22）" : "要导入到第几号箱子（1-22）");
        new AlertDialog.Builder(this)
                .setTitle(export ? "导出箱子" : "导入箱子")
                .setView(input)
                .setPositiveButton("确定", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int w) {
                        try {
                            int idx = Integer.parseInt(input.getText().toString().trim()) - 1;
                            if (idx < 0 || idx >= PokemonBox.BOX_COUNT) {
                                Toast.makeText(MainActivity.this, "箱号超出范围", Toast.LENGTH_SHORT).show();
                                return;
                            }
                            java.io.File dir = new java.io.File(getFilesDir(), "boxes");
                            if (!dir.exists()) dir.mkdirs();
                            java.io.File f = new java.io.File(dir, "box_" + (idx + 1) + ".bin");
                            boolean ok;
                            if (export) {
                                ok = box.exportBox(idx, f);
                                if (ok) {
                                    // 导出后清空该箱，腾出空间
                                    box.importBox(idx, emptyBoxFile(dir));
                                }
                                Toast.makeText(MainActivity.this, ok ? "已导出到文件并清空该箱" : "导出失败", Toast.LENGTH_LONG).show();
                            } else {
                                ok = box.importBox(idx, f);
                                Toast.makeText(MainActivity.this, ok ? "已从文件装回该箱" : "导入失败：文件不存在或读取错误", Toast.LENGTH_LONG).show();
                            }
                            if (ok) view.saveSram();
                        } catch (Throwable t) {
                            Toast.makeText(MainActivity.this, "请输入数字箱号", Toast.LENGTH_SHORT).show();
                        }
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private java.io.File emptyBoxFile(java.io.File dir) {
        java.io.File f = new java.io.File(dir, "_empty.bin");
        try {
            if (!f.exists()) {
                java.io.FileOutputStream fos = new java.io.FileOutputStream(f);
                fos.write(new byte[PokemonBox.IN_BOX_COUNT * PokemonBox.BOXMON_SIZE]);
                fos.close();
            }
        } catch (Throwable ignored) {
        }
        return f;
    }

    private void promptPartySwap(final PokemonBox box) {
        final android.widget.EditText input = new android.widget.EditText(this);
        input.setHint("两个队伍槽位 例如 1,4");
        new AlertDialog.Builder(this)
                .setTitle("队伍内部互换")
                .setView(input)
                .setPositiveButton("确定", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int w) {
                        try {
                            String[] p = input.getText().toString().split("[,，\\s]+");
                            boolean ok = box.swapParty(Integer.parseInt(p[0]) - 1, Integer.parseInt(p[1]) - 1);
                            Toast.makeText(MainActivity.this, ok ? "已互换" : "失败", Toast.LENGTH_SHORT).show();
                            if (ok) view.saveSram();
                        } catch (Throwable t) {
                            Toast.makeText(MainActivity.this, "格式不对，应为 1,4", Toast.LENGTH_SHORT).show();
                        }
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    public void showMenu() {
        final String[] items = new String[]{
                "打开修改器（L+R）", "宝可梦仓库…", "保存游戏进度（存档）", "即时存档", "读取即时存档", "速度：1x/2x/3x/5x/10x",
                "声音：开/关", "颜色：正常/红蓝对调", "重置游戏", "隐藏/显示虚拟按键"
        };
        new AlertDialog.Builder(this)
                .setTitle("游戏菜单 v" + versionName())
                .setItems(items, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        switch (which) {
                            case 0:
                                view.injectCombo(GameView.KEY_L | GameView.KEY_R, 40);
                                Toast.makeText(MainActivity.this, "已发送 L+R，稍等片刻", Toast.LENGTH_SHORT).show();
                                break;
                            case 1:
                                showPokemonBox();
                                break;
                            case 2:
                                Toast.makeText(MainActivity.this, view.saveSram() ? "已保存到存档文件" : "保存失败", Toast.LENGTH_SHORT).show();
                                break;
                            case 3:
                                Toast.makeText(MainActivity.this, view.saveStateNow() ? "即时存档完成" : "即时存档失败", Toast.LENGTH_SHORT).show();
                                break;
                            case 4:
                                Toast.makeText(MainActivity.this, view.loadStateNow() ? "已读取即时存档" : "读取失败", Toast.LENGTH_SHORT).show();
                                break;
                            case 5: {
                                int[] steps = {1, 2, 3, 5, 10};
                                int cur = view.speed;
                                int next = 1;
                                for (int i = 0; i < steps.length; i++) {
                                    if (steps[i] == cur) {
                                        next = steps[(i + 1) % steps.length];
                                        break;
                                    }
                                }
                                view.speed = next;
                                Toast.makeText(MainActivity.this, "游戏速度 " + next + "x", Toast.LENGTH_SHORT).show();
                                break;
                            }
                            case 6:
                                view.setAudio(!view.audioEnabled);
                                Toast.makeText(MainActivity.this, view.audioEnabled ? "声音开启" : "声音关闭", Toast.LENGTH_SHORT).show();
                                break;
                            case 7:
                                view.swapRB = !view.swapRB;
                                view.nativeSetSwapRB(view.swapRB ? 1 : 0);
                                Toast.makeText(MainActivity.this, view.swapRB ? "已切换为红蓝对调" : "已恢复默认颜色", Toast.LENGTH_SHORT).show();
                                break;
                            case 8:
                                view.resetGame();
                                break;
                            case 9:
                                view.showControls = !view.showControls;
                                break;
                        }
                    }
                })
                .show();
    }
}
