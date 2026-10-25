#include <jni.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <pthread.h>
#include <ucontext.h>
#include <stdint.h>
#include <unistd.h>
#include <android/log.h>
#include <sys/syscall.h>
#include <fcntl.h>

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/blip_buf.h>
#include <mgba-util/vfs.h>

#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, "gbaemu", __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, "gbaemu", __VA_ARGS__)

static struct mCore* g_core = NULL;
static color_t* g_video = NULL;
static unsigned g_w = 240, g_h = 160;
static short* g_audioL = NULL;
static short* g_audioR = NULL;
static size_t g_audioCap = 0;
static char g_stagePath[512];
static volatile int g_stage = 0;
static volatile int g_swapRB = 1;
static int g_stageFd = -1;

static void stage_open(void)
{
    if (g_stageFd < 0 && g_stagePath[0])
        g_stageFd = open(g_stagePath, O_WRONLY | O_CREAT | O_TRUNC, 0644);
}

static void stage_mark(int n)
{
    g_stage = n;
    if (g_stageFd < 0)
        return;
    char buf[32];
    int len = snprintf(buf, sizeof(buf), "stage=%d\n", n);
    if (len > 0)
        (void) pwrite(g_stageFd, buf, (size_t) len, 0);
}

static unsigned long find_lib_base(const char* needle)
{
    int fd = open("/proc/self/maps", O_RDONLY);
    if (fd < 0)
        return 0;
    char buf[4096];
    ssize_t n;
    unsigned long base = 0;
    char acc[8192];
    size_t used = 0;
    while ((n = read(fd, buf, sizeof(buf))) > 0) {
        for (ssize_t i = 0; i < n; i++) {
            if (used < sizeof(acc) - 1)
                acc[used++] = buf[i];
            if (buf[i] == '\n') {
                acc[used] = 0;
                if (used > 0 && strstr(acc, needle)) {
                    base = strtoul(acc, NULL, 16);
                    close(fd);
                    return base;
                }
                used = 0;
            }
        }
    }
    close(fd);
    return base;
}

static void crash_handler(int sig, siginfo_t* info, void* ucv)
{
    char tname[32] = "?";
    {
        char pbuf[64];
        long tid = syscall(__NR_gettid);
        int ln = snprintf(pbuf, sizeof(pbuf), "/proc/self/task/%ld/comm", tid);
        int tfd = open(pbuf, O_RDONLY);
        if (tfd >= 0) {
            ssize_t rn = read(tfd, tname, sizeof(tname) - 1);
            if (rn > 0) {
                tname[rn] = 0;
                for (int i = 0; i < rn; i++)
                    if (tname[i] == '\n') tname[i] = 0;
            } else {
                tname[0] = '?';
                tname[1] = 0;
            }
            close(tfd);
        }
    }

    unsigned long pc = 0;
    if (ucv) {
        ucontext_t* uc = (ucontext_t*) ucv;
        pc = (unsigned long) uc->uc_mcontext.pc;
    }
    unsigned long base = find_lib_base("libgbaemu.so");

    if (g_stagePath[0]) {
        char buf[256];
        int n = snprintf(buf, sizeof(buf),
                         "CRASH sig=%d stage=%d thread=%s pc=0x%lx addr=0x%lx libbase=0x%lx\n",
                         sig, (int) g_stage, tname, pc,
                         info ? (unsigned long) info->si_addr : 0UL, base);
        int fd = open(g_stagePath, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            ssize_t ignored = write(fd, buf, (size_t) n);
            (void) ignored;
            close(fd);
        }
    }
    signal(sig, SIG_DFL);
    raise(sig);
}

JNIEXPORT jint JNICALL
Java_com_stepx_pokeemerald_GameView_nativeWidth(JNIEnv* env, jobject thiz) { return (jint) g_w; }

JNIEXPORT jint JNICALL
Java_com_stepx_pokeemerald_GameView_nativeHeight(JNIEnv* env, jobject thiz) { return (jint) g_h; }

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeSetLogPath(JNIEnv* env, jobject thiz, jstring jpath)
{
    const char* p = (*env)->GetStringUTFChars(env, jpath, 0);
    if (p) {
        strncpy(g_stagePath, p, sizeof(g_stagePath) - 1);
        (*env)->ReleaseStringUTFChars(env, jpath, p);
    }
    stage_open();
}

JNIEXPORT jboolean JNICALL
Java_com_stepx_pokeemerald_GameView_nativeInit(JNIEnv* env, jobject thiz, jstring jrom, jstring jsave)
{
    stage_mark(1);
    {
        struct sigaction sa;
        memset(&sa, 0, sizeof(sa));
        sa.sa_sigaction = crash_handler;
        sa.sa_flags = SA_SIGINFO | SA_ONSTACK;
        sigaction(SIGSEGV, &sa, NULL);
        sigaction(SIGBUS, &sa, NULL);
        sigaction(SIGABRT, &sa, NULL);
        sigaction(SIGILL, &sa, NULL);
    }

    const char* rom = (*env)->GetStringUTFChars(env, jrom, 0);
    const char* save = jsave ? (*env)->GetStringUTFChars(env, jsave, 0) : NULL;

    stage_mark(2);
    g_core = mCoreFind(rom);
    if (!g_core) {
        LOGE("no core for %s", rom);
        return JNI_FALSE;
    }

    stage_mark(3);
    mCoreInitConfig(g_core, NULL);
    // StepClaw: 关闭核心侧音视频同步，改由 Java 侧独立音频线程 + 环形缓冲控制节奏，
    // 避免核心在等音频缓冲时阻塞（表现为音乐卡住、整体顿卡）
    g_core->opts.audioSync = false;
    g_core->opts.videoSync = false;
    g_core->init(g_core);

    stage_mark(4);
    g_core->desiredVideoDimensions(g_core, &g_w, &g_h);
    g_video = (color_t*) calloc((size_t) g_w * g_h, sizeof(color_t));
    if (!g_video)
        return JNI_FALSE;
    g_core->setVideoBuffer(g_core, g_video, g_w);
    g_core->setAudioBufferSize(g_core, 0x2000);

    stage_mark(5);
    if (!mCoreLoadFile(g_core, rom)) {
        LOGE("failed to load rom");
        return JNI_FALSE;
    }
    if (save && save[0])
        mCoreLoadSaveFile(g_core, save, false);

    stage_mark(6);
    blip_t* l = g_core->getAudioChannel(g_core, 0);
    blip_t* r = g_core->getAudioChannel(g_core, 1);
    blip_set_rates(l, g_core->frequency(g_core), 44100);
    blip_set_rates(r, g_core->frequency(g_core), 44100);
    blip_clear(l);
    blip_clear(r);

    g_audioCap = 0x2000;
    g_audioL = (short*) malloc(g_audioCap * sizeof(short));
    g_audioR = (short*) malloc(g_audioCap * sizeof(short));

    stage_mark(7);
    g_core->reset(g_core);
    stage_mark(8);
    LOGI("core ready %ux%u bytesperpixel=%d", g_w, g_h, BYTES_PER_PIXEL);
    return JNI_TRUE;
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeSetAudioRate(JNIEnv* env, jobject thiz, jint rate)
{
    if (!g_core || rate <= 0) return;
    blip_t* l = g_core->getAudioChannel(g_core, 0);
    blip_t* r = g_core->getAudioChannel(g_core, 1);
    if (!l || !r) return;
    blip_set_rates(l, g_core->frequency(g_core), (double) rate);
    blip_set_rates(r, g_core->frequency(g_core), (double) rate);
    blip_clear(l);
    blip_clear(r);
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeRunFrame(JNIEnv* env, jobject thiz)
{
    if (!g_core || !g_video) return;
    stage_mark(20);
    g_core->runFrame(g_core);
    stage_mark(21);
    // 视频缓冲保持 mGBA 原样，转换在 nativeCopyFrame 里做
}

JNIEXPORT jint JNICALL
Java_com_stepx_pokeemerald_GameView_nativeReadAudio(JNIEnv* env, jobject thiz, jshortArray out)
{
    if (!g_core || !g_audioL || !g_audioR || !out) return 0;

    jsize outLen = (*env)->GetArrayLength(env, out);
    if (outLen < 2) return 0;

    blip_t* l = g_core->getAudioChannel(g_core, 0);
    blip_t* r = g_core->getAudioChannel(g_core, 1);
    if (!l || !r) return 0;

    size_t avail = (size_t) blip_samples_avail(l);
    size_t limit = g_audioCap;
    size_t outLimit = (size_t) outLen / 2;
    if (limit > outLimit) limit = outLimit;
    if (avail > limit) avail = limit;
    if (avail == 0) return 0;

    blip_read_samples(l, g_audioL, (int) avail, 0);
    blip_read_samples(r, g_audioR, (int) avail, 0);

    stage_mark(23);
    if (avail > 0) stage_mark(24);
    jshort* buf = (*env)->GetShortArrayElements(env, out, NULL);
    if (!buf) return 0;
    for (size_t i = 0; i < avail; i++) {
        buf[i * 2] = g_audioL[i];
        buf[i * 2 + 1] = g_audioR[i];
    }
    (*env)->ReleaseShortArrayElements(env, out, buf, 0);
    return (jint) avail;
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeCopyFrame(JNIEnv* env, jobject thiz, jintArray out)
{
    if (!g_core || !g_video) return;
    stage_mark(22);
    jint* buf = (*env)->GetIntArrayElements(env, out, NULL);
    if (buf) {
        if (BYTES_PER_PIXEL == 4) {
            size_t n = (size_t) g_w * g_h;
            if (g_swapRB) {
                for (size_t i = 0; i < n; i++) {
                    color_t v = g_video[i];
                    buf[i] = (jint) (0xFF000000u | ((v & 0xFFu) << 16) | (v & 0xFF00u) | ((v >> 16) & 0xFFu));
                }
            } else {
                for (size_t i = 0; i < n; i++)
                    buf[i] = (jint) (g_video[i] | 0xFF000000u);
            }
        }
        else {
            const uint16_t* src = (const uint16_t*) g_video;
            for (size_t i = 0; i < (size_t) g_w * g_h; i++) {
                unsigned c = src[i];
                unsigned r = (c & 0x1F) << 3;
                unsigned g = ((c >> 5) & 0x1F) << 3;
                unsigned b = ((c >> 10) & 0x1F) << 3;
                buf[i] = (jint) (0xFF000000u | (b << 16) | (g << 8) | r);
            }
        }
        (*env)->ReleaseIntArrayElements(env, out, buf, 0);
    }
    stage_mark(25);
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeSetKeys(JNIEnv* env, jobject thiz, jint mask)
{
    if (g_core) g_core->setKeys(g_core, (uint32_t) mask);
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeReset(JNIEnv* env, jobject thiz)
{
    if (g_core) g_core->reset(g_core);
}

JNIEXPORT jboolean JNICALL
Java_com_stepx_pokeemerald_GameView_nativeSaveSRAM(JNIEnv* env, jobject thiz, jstring jpath)
{
    if (!g_core) return JNI_FALSE;
    void* sram = NULL;
    size_t size = g_core->savedataClone(g_core, &sram);
    if (!sram || !size) return JNI_FALSE;
    const char* path = (*env)->GetStringUTFChars(env, jpath, 0);
    FILE* f = fopen(path, "wb");
    if (!f) { free(sram); return JNI_FALSE; }
    fwrite(sram, 1, size, f);
    fclose(f);
    free(sram);
    return JNI_TRUE;
}

JNIEXPORT jboolean JNICALL
Java_com_stepx_pokeemerald_GameView_nativeSaveState(JNIEnv* env, jobject thiz, jstring jpath)
{
    if (!g_core) return JNI_FALSE;
    size_t size = g_core->stateSize(g_core);
    void* state = malloc(size);
    if (!state) return JNI_FALSE;
    if (!g_core->saveState(g_core, state)) { free(state); return JNI_FALSE; }
    const char* path = (*env)->GetStringUTFChars(env, jpath, 0);
    FILE* f = fopen(path, "wb");
    if (!f) { free(state); return JNI_FALSE; }
    fwrite(state, 1, size, f);
    fclose(f);
    free(state);
    return JNI_TRUE;
}

JNIEXPORT jboolean JNICALL
Java_com_stepx_pokeemerald_GameView_nativeLoadState(JNIEnv* env, jobject thiz, jstring jpath)
{
    if (!g_core) return JNI_FALSE;
    const char* path = (*env)->GetStringUTFChars(env, jpath, 0);
    FILE* f = fopen(path, "rb");
    if (!f) return JNI_FALSE;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    size_t stateSize = g_core->stateSize(g_core);
    if (size <= 0 || (size_t) size != stateSize) { fclose(f); return JNI_FALSE; }
    void* state = malloc((size_t) size);
    if (!state) { fclose(f); return JNI_FALSE; }
    size_t rd = fread(state, 1, (size_t) size, f);
    fclose(f);
    if (rd != (size_t) size) { free(state); return JNI_FALSE; }
    bool ok = g_core->loadState(g_core, state);
    free(state);
    return ok ? JNI_TRUE : JNI_FALSE;
}

/* ---- 种族值覆盖表的读写（App 侧持久化） ---- */
JNIEXPORT jboolean JNICALL
Java_com_stepx_pokeemerald_GameView_nativeWriteMemory(JNIEnv* env, jobject thiz, jint addr, jbyteArray data)
{
    if (!g_core) return JNI_FALSE;
    jsize len = (*env)->GetArrayLength(env, data);
    jbyte* buf = (*env)->GetByteArrayElements(env, data, NULL);
    if (!buf) return JNI_FALSE;
    for (jsize i = 0; i < len; i++)
        g_core->busWrite8(g_core, (uint32_t) (addr + i), (uint8_t) buf[i]);
    (*env)->ReleaseByteArrayElements(env, data, buf, JNI_ABORT);
    return JNI_TRUE;
}

JNIEXPORT jbyteArray JNICALL
Java_com_stepx_pokeemerald_GameView_nativeReadMemory(JNIEnv* env, jobject thiz, jint addr, jint len)
{
    jbyteArray out = (*env)->NewByteArray(env, len);
    if (!out) return NULL;
    if (!g_core) return out;
    jbyte* buf = (*env)->GetByteArrayElements(env, out, NULL);
    if (!buf) return out;
    for (jint i = 0; i < len; i++)
        buf[i] = (jbyte) g_core->busRead8(g_core, (uint32_t) (addr + i));
    (*env)->ReleaseByteArrayElements(env, out, buf, 0);
    return out;
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeStage(JNIEnv* env, jobject thiz, jint n)
{
    stage_open();
    stage_mark((int) n);
}

JNIEXPORT void JNICALL
Java_com_stepx_pokeemerald_GameView_nativeSetSwapRB(JNIEnv* env, jobject thiz, jint on)
{
    g_swapRB = (int) on;
}

JNIEXPORT jboolean JNICALL
Java_com_stepx_pokeemerald_GameView_nativeCoreReady(JNIEnv* env, jobject thiz)
{
    return g_core ? JNI_TRUE : JNI_FALSE;
}
