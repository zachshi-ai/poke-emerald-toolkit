package com.stepx.pokeemerald;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.Build;
import android.view.MotionEvent;
import android.view.SurfaceHolder;
import android.view.SurfaceView;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class GameView extends SurfaceView implements SurfaceHolder.Callback, Runnable {

    static { System.loadLibrary("gbaemu"); }

    native boolean nativeInit(String rom, String save);
    native void nativeRunFrame();
    native void nativeSetAudioRate(int rate);
    native void nativeCopyFrame(int[] out);
    native int nativeReadAudio(short[] out);
    native void nativeSetKeys(int mask);
    native void nativeReset();
    native boolean nativeSaveSRAM(String path);
    native boolean nativeSaveState(String path);
    native boolean nativeLoadState(String path);
    native int nativeWidth();
    native int nativeHeight();
    native void nativeSetLogPath(String path);
    native boolean nativeCoreReady();
    native void nativeStage(int n);
    native byte[] nativeReadMemory(int addr, int len);
    native boolean nativeWriteMemory(int addr, byte[] data);
    native void nativeSetSwapRB(int on);

    static final int KEY_A = 1, KEY_B = 2, KEY_SELECT = 4, KEY_START = 8,
            KEY_RIGHT = 16, KEY_LEFT = 32, KEY_UP = 64, KEY_DOWN = 128,
            KEY_R = 256, KEY_L = 512;

    static final long FRAME_NS = 16742000L;   // 59.7 fps
    static final long MIN_HOLD_MS = 70;       // 最短按压时间，避免快速连按被吞

    final String romPath, savePath, statePath;
    final File filesDir;
    Thread thread;
    volatile boolean running;
    volatile int speed = 1;
    volatile boolean showControls = true;
    volatile boolean coreReady;
    volatile boolean coreInited;
    volatile boolean initFailed;
    volatile boolean audioEnabled = true;   // 默认开启声音
    volatile boolean swapRB = true;
    volatile int injectMask = 0;
    volatile int injectFrames = 0;
    volatile String initMsg = "";

    int gw = 240, gh = 160;
    Bitmap frame;
    int[] pixels;
    final Paint paint = new Paint();
    final Paint ctrlPaint = new Paint();
    final Paint ctrlText = new Paint();

    AudioTrack audio;
    int audioRate = 44100;
    short[] audioBuf = new short[16384];

    // 音频：独立播放线程 + 环形缓冲（主循环只投递，绝不阻塞）
    final Object audioLock = new Object();
    final short[] ringBuf = new short[44100 * 2];   // 约 1 秒立体声
    int ringHead = 0, ringCount = 0;
    volatile boolean audioThreadRunning = false;
    Thread audioThread;

    int activeMask = 0;
    final int[] holdUntil = new int[10];
    final Map<Integer, Integer> pointerKeys = new HashMap<>();

    static class Btn {
        float cx, cy, w, h;
        int key;
        String label;
        Btn(float cx, float cy, float w, float h, int key, String label) {
            this.cx = cx; this.cy = cy; this.w = w; this.h = h; this.key = key; this.label = label;
        }
        RectF asRect(int W, int H) {
            float bw = w * W * 1.12f, bh = h * H * 1.12f;
            return new RectF(cx * W - bw / 2, cy * H - bh / 2, cx * W + bw / 2, cy * H + bh / 2);
        }
        void draw(Canvas c, int W, int H, Paint p) {
            RectF r = asRect(W, H);
            c.drawRoundRect(r, 14, 14, p);
        }
    }

    final List<Btn> buttons = new ArrayList<>();
    final RectF menuRect = new RectF();

    float dpadCx, dpadCy, dpadR;
    // 方向键（上下左右四个独立按钮，替代原来的圆形摇杆，避免误触）
    final RectF[] dpadRects = new RectF[]{ new RectF(), new RectF(), new RectF(), new RectF() };
    static final int[] DPAD_KEYS = new int[]{ KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT };
    static final String[] DPAD_LABELS = new String[]{ "▲", "▶", "▼", "◀" };

    public GameView(Context ctx, String rom, String save, String state, File files) {
        super(ctx);
        romPath = rom; savePath = save; statePath = state;
        filesDir = files;
        getHolder().addCallback(this);
        setFocusable(true);
        setKeepScreenOn(true);

        buttons.add(new Btn(0.885f, 0.70f, 0.125f, 0.30f, KEY_A, "A"));
        buttons.add(new Btn(0.760f, 0.87f, 0.125f, 0.30f, KEY_B, "B"));
        buttons.add(new Btn(0.44f, 0.10f, 0.15f, 0.15f, KEY_START, "START"));
        buttons.add(new Btn(0.57f, 0.10f, 0.15f, 0.15f, KEY_SELECT, "SELECT"));
        buttons.add(new Btn(0.035f, 0.12f, 0.10f, 0.20f, KEY_L, "L"));
        buttons.add(new Btn(0.965f, 0.12f, 0.10f, 0.20f, KEY_R, "R"));
    }

    @Override public void surfaceCreated(SurfaceHolder h) {
        running = true;
        thread = new Thread(this, "emu");
        thread.start();
    }

    @Override public void surfaceChanged(SurfaceHolder h, int f, int w, int ht) { }

    @Override public void surfaceDestroyed(SurfaceHolder h) {
        running = false;
        try { if (thread != null) thread.join(2000); } catch (InterruptedException ignored) { }
    }

    void pauseGame() {
        running = false;
        try { if (thread != null) thread.join(2000); } catch (InterruptedException ignored) { }
        if (coreReady) {
            try { nativeSaveSRAM(savePath); } catch (Throwable ignored) { }
        }
        // 不销毁模拟器核心，回到前台继续原进度
        releaseAudio();
    }

    void resumeGame() {
        if (getHolder().getSurface() != null && (thread == null || !thread.isAlive())) {
            running = true;
            thread = new Thread(this, "emu");
            thread.start();
        }
    }

    public boolean saveSram() { return coreReady && nativeSaveSRAM(savePath); }
    public boolean saveStateNow() { return coreReady && nativeSaveState(statePath); }
    public boolean loadStateNow() { return coreReady && nativeLoadState(statePath); }

    public byte[] readMem(int addr, int len) {
        try { return nativeReadMemory(addr, len); } catch (Throwable t) { return null; }
    }

    public boolean writeMem(int addr, byte[] data) {
        try { return nativeWriteMemory(addr, data); } catch (Throwable t) { return false; }
    }

    void injectCombo(int mask, int frames) {
        injectMask = mask;
        injectFrames = frames;
    }

    void setAudio(boolean on) {
        audioEnabled = on;
        if (on) startAudioThread();
        else releaseAudio();
    }

    public void resetGame() {
        if (!coreReady) return;
        nativeReset();
    }

    private void startAudioThread() {
        if (audioThreadRunning) return;
        audioThreadRunning = true;
        audioThread = new Thread(new Runnable() {
            @Override public void run() {
                // 关键：AudioTrack 的创建/播放也放在这个线程里，
                // 万一设备音频栈卡住，卡的是音频线程，渲染线程不受影响（不会黑屏）
                if (audio == null) createTrackInternal();
                if (audio == null) {
                    audioThreadRunning = false;
                    audioEnabled = false;
                }
                short[] chunk = new short[2048];
                while (audioThreadRunning) {
                    int cnt = 0;
                    synchronized (audioLock) {
                        if (ringCount == 0) {
                            try { audioLock.wait(20); } catch (InterruptedException ignored) { }
                            continue;
                        }
                        cnt = Math.min(ringCount, chunk.length);
                        for (int i = 0; i < cnt; i++)
                            chunk[i] = ringBuf[(ringHead + i) % ringBuf.length];
                        ringHead = (ringHead + cnt) % ringBuf.length;
                        ringCount -= cnt;
                    }
                    AudioTrack t = audio;
                    if (t == null || cnt <= 0) continue;
                    try {
                        if (t.getPlayState() != AudioTrack.PLAYSTATE_PLAYING) t.play();
                        t.write(chunk, 0, cnt);   // 阻塞只发生在这个线程
                    } catch (Throwable ignored) { }
                }
            }
        }, "audio");
        audioThread.start();
    }

    private void pushAudio(short[] src, int samples) {
        if (audio == null || samples <= 0) return;
        int cnt = Math.min(samples * 2, src.length);
        synchronized (audioLock) {
            int space = ringBuf.length - ringCount;
            if (cnt > space) {
                int drop = cnt - space;
                ringHead = (ringHead + drop) % ringBuf.length;
                ringCount -= drop;
            }
            for (int i = 0; i < cnt; i++)
                ringBuf[(ringHead + ringCount + i) % ringBuf.length] = src[i];
            ringCount += cnt;
            audioLock.notifyAll();
        }
    }

    private synchronized void createTrackInternal() {
        if (audio != null) return;
        int[] rates = new int[]{44100, 32768};
        for (int rate : rates) {
            try {
                int minBuf = AudioTrack.getMinBufferSize(rate,
                        AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT);
                if (minBuf <= 0) continue;
                int bufSize = Math.max(minBuf * 2, 32768);
                AudioTrack t = new AudioTrack(AudioManager.STREAM_MUSIC, rate,
                        AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT,
                        bufSize, AudioTrack.MODE_STREAM);
                if (t.getState() != AudioTrack.STATE_INITIALIZED) {
                    try { t.release(); } catch (Throwable ignored) { }
                    continue;
                }
                t.setVolume(1.0f);
                t.play();
                audio = t;
                audioRate = rate;
                try { nativeSetAudioRate(rate); } catch (Throwable ignored) { }
                return;
            } catch (Throwable ignored) {
                // 换下一个采样率重试
            }
        }
        audio = null;
    }

    private void releaseAudio() {
        audioThreadRunning = false;
        Thread t = audioThread;
        audioThread = null;
        if (t != null) {
            synchronized (audioLock) { audioLock.notifyAll(); }
            try { t.join(200); } catch (InterruptedException ignored) { }
        }
        synchronized (audioLock) { ringHead = 0; ringCount = 0; }
        if (audio != null) {
            try { audio.stop(); } catch (Throwable ignored) { }
            try { audio.release(); } catch (Throwable ignored) { }
            audio = null;
        }
    }

    private int buildMask() {
        int now = (int) (android.os.SystemClock.uptimeMillis() & 0x7fffffff);
        int m = activeMask;
        int[] bits = {KEY_A, KEY_B, KEY_SELECT, KEY_START, KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN, KEY_R, KEY_L};
        for (int i = 0; i < bits.length; i++) {
            if ((int) (holdUntil[i] - now) > 0) m |= bits[i];
        }
        return m;
    }

    private static int bitIndex(int bit) {
        switch (bit) {
            case KEY_A: return 0;
            case KEY_B: return 1;
            case KEY_SELECT: return 2;
            case KEY_START: return 3;
            case KEY_RIGHT: return 4;
            case KEY_LEFT: return 5;
            case KEY_UP: return 6;
            case KEY_DOWN: return 7;
            case KEY_R: return 8;
            default: return 9;
        }
    }

    private void applyMask() {
        int m = buildMask();
        if (coreReady) {
            try { nativeSetKeys(m); } catch (Throwable ignored) { }
        }
    }

    @Override public void run() {
        try {
            nativeSetLogPath(new File(filesDir, "stage.txt").getAbsolutePath());
            if (!coreInited) {
                coreReady = nativeInit(romPath, savePath);
                coreInited = coreReady;
            } else {
                coreReady = true;
            }
            if (!coreReady) {
                initFailed = true;
                initMsg = "核心初始化失败";
                while (running) {
                    drawFail();
                    try { Thread.sleep(400); } catch (InterruptedException ignored) { }
                }
                return;
            }
            gw = nativeWidth();
            gh = nativeHeight();
            if (frame == null) {
                frame = Bitmap.createBitmap(gw, gh, Bitmap.Config.ARGB_8888);
                pixels = new int[gw * gh];
            }
            if (audioEnabled) startAudioThread();

            long next = System.nanoTime();
            while (running) {
                int frames = speed < 1 ? 1 : speed;
                for (int i = 0; i < frames; i++) nativeRunFrame();

                nativeCopyFrame(pixels);
                frame.setPixels(pixels, 0, gw, 0, 0, gw, gh);

                // 音频放到画面之后处理，并且只做非阻塞写入：任何情况下都不能卡住主循环
                int n = 0;
                try { n = nativeReadAudio(audioBuf); } catch (Throwable ignored) { n = 0; }

                if (injectFrames > 0) {
                    try { nativeSetKeys(injectMask); } catch (Throwable ignored) { }
                    injectFrames--;
                } else {
                    applyMask();
                }
                drawSurface();

                if (speed <= 1 && audio != null && n > 0) {
                    try { pushAudio(audioBuf, n); } catch (Throwable ignored) { }
                }

                // 倍速：每显示帧推进 speed 个游戏帧，但时间基准仍是一帧，从而实现真正的加速
                next += FRAME_NS;
                long now = System.nanoTime();
                long sleepNs = next - now;
                if (sleepNs > 0) {
                    try { Thread.sleep(sleepNs / 1000000L, (int) (sleepNs % 1000000L)); } catch (InterruptedException ignored) { }
                } else if (-sleepNs > 200L * 1000000L) {
                    next = now;
                }
            }
        } catch (Throwable t) {
            MainActivity.logCrash(getContext(), "emu-thread", t);
            initFailed = true;
            initMsg = "运行异常：" + t.getClass().getSimpleName();
            while (running) {
                drawFail();
                try { Thread.sleep(400); } catch (InterruptedException ignored) { }
            }
        }
        releaseAudio();
    }

    private void drawFail() {
        SurfaceHolder h = getHolder();
        Canvas c = null;
        try {
            c = h.lockCanvas();
            if (c == null) return;
            c.drawColor(Color.BLACK);
            Paint p = new Paint();
            p.setColor(Color.WHITE);
            p.setTextSize(Math.min(c.getWidth(), c.getHeight()) * 0.055f);
            p.setTextAlign(Paint.Align.CENTER);
            c.drawText(initMsg, c.getWidth() / 2f, c.getHeight() * 0.45f, p);
            p.setTextSize(p.getTextSize() * 0.6f);
            c.drawText("日志：下载/pokeemerald_log.txt", c.getWidth() / 2f, c.getHeight() * 0.58f, p);
        } catch (Throwable ignored) {
        } finally {
            if (c != null) {
                try { h.unlockCanvasAndPost(c); } catch (Throwable ignored) { }
            }
        }
    }

    private void drawSurface() {
        SurfaceHolder h = getHolder();
        Canvas c = null;
        try {
            c = h.lockCanvas();
            if (c == null) return;
            c.drawColor(Color.BLACK);
            int W = c.getWidth(), H = c.getHeight();
            float scale = Math.min(W / (float) gw, H / (float) gh);
            float dw = gw * scale, dh = gh * scale;
            float dx = (W - dw) / 2f, dy = (H - dh) / 2f;
            c.drawBitmap(frame, null, new android.graphics.Rect((int) dx, (int) dy, (int) (dx + dw), (int) (dy + dh)), paint);
            if (showControls) drawControls(c, W, H);
        } catch (Throwable ignored) {
        } finally {
            if (c != null) {
                try { h.unlockCanvasAndPost(c); } catch (Throwable ignored) { }
            }
        }
    }

    private void drawControls(Canvas c, int W, int H) {
        int tint = Color.argb(60, 255, 255, 255);
        ctrlPaint.setColor(tint);
        ctrlPaint.setStyle(Paint.Style.FILL);
        ctrlText.setColor(Color.argb(190, 0, 0, 0));
        ctrlText.setTextSize(Math.min(W, H) * 0.048f);

        layoutDpad(W, H);

        int cur = buildMask();

        // 四个方向键：带箭头、按下高亮
        ctrlText.setTextAlign(Paint.Align.CENTER);
        for (int i = 0; i < 4; i++) {
            boolean down = (cur & DPAD_KEYS[i]) != 0;
            ctrlPaint.setColor(down ? Color.argb(150, 255, 255, 255) : Color.argb(60, 255, 255, 255));
            c.drawRoundRect(dpadRects[i], 16, 16, ctrlPaint);
            c.drawText(DPAD_LABELS[i], dpadRects[i].centerX(),
                    dpadRects[i].centerY() + ctrlText.getTextSize() * 0.35f, ctrlText);
        }

        for (Btn b : buttons) {
            ctrlText.setTextAlign(Paint.Align.CENTER);
            boolean down = (cur & b.key) != 0;
            ctrlPaint.setColor(down ? Color.argb(140, 255, 255, 255) : Color.argb(60, 255, 255, 255));
            b.draw(c, W, H, ctrlPaint);
            c.drawText(b.label, b.cx * W, b.cy * H + ctrlText.getTextSize() * 0.35f, ctrlText);
        }

        menuRect.set(W - 0.09f * W, 0.02f * H, W - 0.01f * W, 0.10f * H);
        c.drawRoundRect(menuRect, 10, 10, ctrlPaint);
        ctrlText.setTextSize(Math.min(W, H) * 0.032f);
        c.drawText("MENU", menuRect.centerX(), menuRect.centerY() + ctrlText.getTextSize() * 0.35f, ctrlText);
    }

    private int hitButtons(float x, float y, int W, int H) {
        for (Btn b : buttons) {
            if (b.asRect(W, H).contains(x, y)) return b.key;
        }
        return 0;
    }

    private void layoutDpad(int W, int H) {
        dpadCx = 0.17f * W;
        dpadCy = 0.76f * H;
        dpadR = 0.17f * H;

        float size = dpadR * 0.92f;      // 单个方向键边长
        float gap = size * 0.10f;
        float cx = dpadCx, cy = dpadCy;

        // 上
        dpadRects[0].set(cx - size / 2, cy - size - gap, cx + size / 2, cy - gap);
        // 右
        dpadRects[1].set(cx + gap, cy - size / 2, cx + size + gap, cy + size / 2);
        // 下
        dpadRects[2].set(cx - size / 2, cy + gap, cx + size / 2, cy + size + gap);
        // 左
        dpadRects[3].set(cx - size - gap, cy - size / 2, cx - gap, cy + size / 2);
    }

    private int hitDpad(float x, float y) {
        for (int i = 0; i < 4; i++) {
            if (dpadRects[i].contains(x, y)) {
                // 稍微放宽命中范围，避免边缘漏按
                return DPAD_KEYS[i];
            }
        }
        // 兜底：扩大 8px 容差
        for (int i = 0; i < 4; i++) {
            RectF r = dpadRects[i];
            if (x >= r.left - 8 && x <= r.right + 8 && y >= r.top - 8 && y <= r.bottom + 8)
                return DPAD_KEYS[i];
        }
        return 0;
    }

    private void updatePointers(MotionEvent e) {
        int W = getWidth(), H = getHeight();
        int action = e.getActionMasked();
        int idx = e.getActionIndex();

        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
            int pid = e.getPointerId(idx);
            int k = hitDpad(e.getX(idx), e.getY(idx)) | hitButtons(e.getX(idx), e.getY(idx), W, H);
            pointerKeys.put(pid, k);
        } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP) {
            Integer old = pointerKeys.remove(e.getPointerId(idx));
            if (old != null) latchRelease(old);
        } else if (action == MotionEvent.ACTION_MOVE) {
            for (int i = 0; i < e.getPointerCount(); i++) {
                int pid = e.getPointerId(i);
                if (!pointerKeys.containsKey(pid)) continue;
                int k = hitDpad(e.getX(i), e.getY(i)) | hitButtons(e.getX(i), e.getY(i), W, H);
                Integer old = pointerKeys.get(pid);
                if (old != null && old != k) latchRelease(old);
                pointerKeys.put(pid, k);
            }
        } else if (action == MotionEvent.ACTION_CANCEL) {
            for (Integer k : pointerKeys.values()) latchRelease(k);
            pointerKeys.clear();
        }

        int m = 0;
        for (Integer k : pointerKeys.values()) m |= k;
        activeMask = m;
        applyMask();
    }

    private void latchRelease(int mask) {
        int now = (int) (android.os.SystemClock.uptimeMillis() & 0x7fffffff);
        int[] bits = {KEY_A, KEY_B, KEY_SELECT, KEY_START, KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN, KEY_R, KEY_L};
        for (int bit : bits) {
            if ((mask & bit) != 0) {
                int i = bitIndex(bit);
                holdUntil[i] = Math.max(holdUntil[i], now + (int) MIN_HOLD_MS);
            }
        }
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        int W = getWidth(), H = getHeight();
        int action = e.getActionMasked();
        if (action == MotionEvent.ACTION_UP) {
            float x = e.getX(), y = e.getY();
            if (menuRect.contains(x, y)) {
                try { ((MainActivity) getContext()).showMenu(); } catch (Throwable ignored) { }
                return true;
            }
        }
        updatePointers(e);
        return true;
    }
}
