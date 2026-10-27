// libzhfont.so —— 让 Majesty 引擎直接显示中文
//
// 原理：不改引擎绘制代码，只在 CIwGxFont::DrawText 入口挂一个跳转，
//      遇到码表里没有的码位就现场用 stb_truetype 光栅化，
//      glTexSubImage2D 传进引擎自己的字体图集，再往码表/记录表里插一条。
//
// 所有偏移都来自真机实测（见 .workbuddy-ai/memory/2026-07-09.md）。

#define _GNU_SOURCE
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <pthread.h>
#include <sys/mman.h>

#define STB_TRUETYPE_IMPLEMENTATION
#define STBTT_STATIC
#include "stb_truetype.h"
#include "cp_table.h"      // 翻译里用到的全部码位（自动生成）

// 由 ld -r -b binary 生成的符号
extern const unsigned char _binary_zhfont_subset_ttf_start[];
extern const unsigned char _binary_zhfont_subset_ttf_end[];

#define SIG_VA        0x45cd90u    // "9CIwGxFont"
// 诊断开关：0 = 正式版（不打日志、不开命令通道、不含内存扫描/存档探查代码）
//           1 = 诊断版（额外输出每次 DrawText 的文本、每个字形的度量、每个新字体对象的字段，
//               并开一个「命令文件 -> 结果文件」的内存读写通道，仅供开发排查）
#define ZF_DIAG       0
// 日志开关：0 = 静默（正式版）1 = 输出到 logcat
#define ZF_LOG        0
// 屏幕叠加按钮开关：0=关（正式版）1=开（实验）
#define ZF_BTN        0
// 老兵自测：1 = 启动后把场上第一个英雄推入升级队列，验证「投递 → 渲染线程升级」链路
#define ZF_VET_SELFTEST 0
// ★★ 作弊功能总开关（发行用）
//   1 = 完整版：中文翻译 + 全部作弊功能（+50 级、免费商店、英雄上限、建造上限、
//               关卡解锁、阵营切换、命令通道、存档备份……）
//   0 = 纯翻译版：只做中文显示。不含任何改游戏数值/解锁/免费购买的代码，
//               连作弊线程都不启动，等于「官方原版 + 汉化」。
//   两版共用同一份源码，靠这个宏切分；编译命令见 tools/build.sh。
//   （用 #ifndef 包住，命令行 -DZF_CHEAT=0 才能覆盖）
#ifndef ZF_CHEAT
#define ZF_CHEAT      1
#endif
#define DRAW_VA       0x110088u
#define DRAW_VA2      0x11076cu   // 同一个 DrawText 的第二个副本
#define FONT_COUNT    0x08
#define FONT_CODES    0x10
#define FONT_CAPCODES 0x1c
#define FONT_RECS     0x28
#define FONT_CAPRECS  0x34
#define FONT_PAGES    0x40
#define PAGE_W        0x1c
#define PAGE_H        0x20

#define MAXFONT 48
#define PAGE_VTBL 0x519110u   // CIw2DImageConcrete vtable，用来确认 page 对象是真的

// ---------------------------------------------------------------- 工具
#include <android/log.h>

// 老兵「玩家已购买」的捕获机制。
// 现象：在商店里点老兵，对号闪一下就没了 —— 我们自己每 300ms 的全量同步把它写回了 0
// （kAuto=0 的项要压住），而玩家点击那一帧的 1 我们轮询根本抓不到。
// 所以改成：渲染线程每次画字时顺手读一下那几个「默认关闭」的项，见到 1 就锁存，
// 之后作弊线程不再把它们压回 0，反而每轮把它们写回 1。
static volatile uintptr_t g_cht_arr;      // 作弊「已激活」数组（14 字节）
static volatile int g_vet_armed;          // 至少做过一次全量同步，可以开始捕获
static volatile unsigned g_keep_mask;     // bit i = 玩家买过第 i 项，本会话不再取消
static const int kOffIdx[4] = {1, 2, 6, 8};   // kAuto=0 的四个索引（快速建造/老兵/地图全开/快速雇佣）

// ---- 关键字段偏移（多处引用，统一放这里）----
#define CHT_N        14
#define CHT_COST_VA  0x443930u     // int32[14] 钻石商店价格表
#define CHT_SING_VA  0x542c80u     // 作弊单例：+0x08 数组指针，+0x10 已初始化
#define HERO_MAX_VA  0x53df88u     // 指针槽 -> int32 全局英雄上限
#define BLD_MAX_VA   0x53b300u     // 指针槽 -> int32 全局建筑数量上限
// ★ 别再犯的错：objdump 反汇编这个 bin 时，它把整个文件当 offset 0 的 .text，
//   所以 `adrp x0, 0x53f000` 里的 0x53f000 是「相对文件起点」的地址，
//   不是运行时偏移。换算（减去 0x4E01、再按页对齐）后，它其实就是
//   base+0x53B000 —— 和这里的 0x53b300 是同一个地方。
//   我曾经据此臆造出「0x53f300 / 0x540300 两组别名槽」，
//   结果 *(base+0x540300) 是个垃圾指针，往 0x79691c79b7 写 99 → 游戏黑屏。
//   结论：镜像里的数据地址只能用运行时日志验证过的值，不能从静态反汇编硬推。
static int zf_addr_ok(uintptr_t a, unsigned len);   // 定义在后面
#if ZF_CHEAT
static void zf_scan_levels(FILE *o, int all);        // 关卡解锁扫描，定义在后面
static void zf_unlock_levels(FILE *o, uintptr_t at, int n);  // 批量解锁，定义在后面
static void zf_list_buildings(FILE *o);             // 列建筑，定义在后面
static void zf_camp(FILE *o, int off, int auto_mode);  // 阵营切换，定义在后面
static void zf_camp_tick(void);                     // 永久模式维护，定义在后面
#endif

// ---------------------------------------------------------------- 即时作弊项队列
// 反汇编 0x1876c（applyCheat）得到的真相：
//   id 0..5   → 只把 arr[id] = 1 就 ret。效果由别处 isCheatActive(id) 实时读，
//               所以「填数组」就够，不需要额外动作。
//   id 6..12  → 写 arr[id] = 1 后，再走跳转表 0x443910 执行一次「即时动作」。
//   id 13     → 走 0x18928 分支：金币 += 10000。
// 结论：id 7（理想城堡）、id 13（金币宝箱）光填数组**不会动**，必须补一次动作。
// 这里用单生产者（作弊线程）/ 单消费者（渲染线程）的环形队列把 id 递过去，
// 由渲染线程执行 —— 和游戏自己调用 applyCheat 的上下文一致，避免跨线程碰分配器。
#define AQ_MAX 8
static volatile int g_aq[AQ_MAX];
static volatile int g_aq_h, g_aq_t;
static volatile unsigned g_aq_done;       // bit id = 已投递过（每进程一次）

static void zf_aq_push(int id) {
    int nt = (g_aq_t + 1) % AQ_MAX;
    if (nt == g_aq_h) return;             // 满了就丢
    g_aq[g_aq_t] = id;
    g_aq_t = nt;
}

static void zf_apply_pending(void);       // 定义在「作弊线程」一节

static void logf_(const char *fmt, ...) {
#if ZF_LOG
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    __android_log_print(ANDROID_LOG_INFO, "zhfont", "%s", buf);
#else
    (void)fmt;
#endif
}

static void *memmem_(const void *h, size_t hl, const void *n, size_t nl) {
    if (nl > hl) return NULL;
    const unsigned char *p = h, *e = p + hl - nl;
    for (; p <= e; p++) if (p[0] == ((const unsigned char *)n)[0] && !memcmp(p, n, nl)) return (void *)p;
    return NULL;
}

// ---------------------------------------------------------------- GL
typedef void (*fn_void_i)(int);
typedef void (*fn_void_ii)(int, int);
typedef void (*fn_void_iip)(int, int, void *);
typedef void (*fn_getint)(int, int *);
typedef void (*fn_bind)(int, unsigned);
typedef void (*fn_gen)(int, unsigned *);
typedef void (*fn_fbtex)(int, int, int, unsigned, int);
typedef unsigned (*fn_u_i)(int);
typedef void (*fn_readpx)(int, int, int, int, unsigned, unsigned, void *);
typedef void (*fn_teximg)(int, int, int, int, int, int, unsigned, unsigned, const void *);
typedef void (*fn_texlvl)(int, int, int, int *);

static fn_gen     p_glGenFramebuffers;
static fn_bind    p_glBindFramebuffer;
static fn_fbtex   p_glFramebufferTexture2D;
static fn_u_i     p_glCheckFramebufferStatus;
static fn_getint  p_glGetIntegerv;
static fn_bind    p_glBindTexture;
static fn_readpx  p_glReadPixels;
static fn_teximg  p_glTexImage2D;
static fn_teximg  p_glTexSubImage2D;
static fn_texlvl  p_glGetTexLevelParameteriv;
typedef void (*fn_void0)(void);
static fn_void0   p_glFinish;
typedef void (*fn_texparam)(int, int, int);
static fn_texparam p_glTexParameteri;

#define GL_TEX2D 0x0DE1
#define GL_FBO   0x8D40
#define GL_COLOR0 0x8CE0
#define GL_RGBA  0x1908
#define GL_UBYTE 0x1401
#define GL_FBO_BIND 0x8CA6
#define GL_TEX_BIND 0x8069
#define GL_TEX_W 0x1000
#define GL_TEX_H 0x1001
#define GL_TEX_IFMT 0x1003
#define GL_TEX_MIN_FILTER 0x2801
#define GL_TEX_MAG_FILTER 0x2800
#define GL_TEX_WRAP_S 0x2802
#define GL_TEX_WRAP_T 0x2803
#define GL_LINEAR     0x2601
#define GL_CLAMP_EDGE 0x812F
#define GL_COMPLETE 0x8CD5

static int gl_ready(void) {
    if (p_glBindTexture) return 1;
    void *h = dlopen("libGLESv2.so", RTLD_NOW);
    if (!h) h = dlopen("libGLESv2_angle.so", RTLD_NOW);
    if (!h) return 0;
#define L(n) p_##n = (void *)dlsym(h, #n)
    L(glGenFramebuffers); L(glBindFramebuffer); L(glFramebufferTexture2D);
    L(glCheckFramebufferStatus); L(glGetIntegerv); L(glBindTexture);
    L(glReadPixels); L(glTexImage2D); L(glTexSubImage2D); L(glGetTexLevelParameteriv);
    L(glFinish); L(glTexParameteri);
#undef L
    return p_glBindTexture != NULL;
}

static unsigned g_fbo;
static unsigned ensure_fbo(void) {
    if (!g_fbo) p_glGenFramebuffers(1, &g_fbo);
    return g_fbo;
}

static int tex_size(unsigned id, int *w, int *h) {
    p_glBindTexture(GL_TEX2D, id);
    p_glGetTexLevelParameteriv(GL_TEX2D, 0, GL_TEX_W, w);
    p_glGetTexLevelParameteriv(GL_TEX2D, 0, GL_TEX_H, h);
    return *w > 0 && *h > 0;
}

// 把纹理的一段读回内存（RGBA8）
static int read_rect(unsigned id, int x, int y, int w, int h, unsigned char *out) {
    int pf = 0, pt = 0;
    p_glGetIntegerv(GL_FBO_BIND, &pf);
    p_glGetIntegerv(GL_TEX_BIND, &pt);
    p_glBindFramebuffer(GL_FBO, ensure_fbo());
    p_glBindTexture(GL_TEX2D, id);
    p_glFramebufferTexture2D(GL_FBO, GL_COLOR0, GL_TEX2D, id, 0);
    int ok = 0;
    if (p_glCheckFramebufferStatus(GL_FBO) == GL_COMPLETE) {
        p_glReadPixels(x, y, w, h, GL_RGBA, GL_UBYTE, out);
        ok = 1;
    }
    p_glBindFramebuffer(GL_FBO, (unsigned)pf);
    p_glBindTexture(GL_TEX2D, (unsigned)pt);
    return ok;
}

// ---------------------------------------------------------------- 字体状态
// 引擎里可能存在多个 CIwGxFont 对象共享同一张图集纹理（各自独立 codes/recs）。
// 分配器必须按纹理共享，否则两套字体会往同一区域写字、互相覆盖 → 乱码。
typedef struct {
    unsigned texid;
    int      W, H;
    int      curX, curY, rowH;
} Atlas;

#define MAXATLAS 16

typedef struct {
    void    *font;
    void    *page;
    int      refH;        // 参考字高（拉丁字母高度）
    int      ready;
    int      tried;       // 已尝试初始化的次数（失败有限次重试，之后放弃，避免每帧重扫纹理）
    Atlas   *atlas;
} FontState;

static FontState g_fonts[MAXFONT];
static int g_nfont;
static Atlas g_atlases[MAXATLAS];
static int g_natlas;
static volatile int g_busy;
static volatile int g_traceparen;   // 诊断开关：0=关 1=只记含括号 2=全记
#define MAXDR 96
static uintptr_t g_dr_c[MAXDR];       // caller
static uint16_t  g_dr_t[MAXDR][20];   // 前 19 个字符
static int       g_dr_n[MAXDR];
static int       g_dr_len[MAXDR];
static volatile int g_dr_i, g_dr_total;
static volatile unsigned g_draw_calls;   // zh_on_draw 被调用总次数（含被 g_busy 拦掉的）
static int g_glyph_dbg;

static stbtt_fontinfo g_info;
static int g_font_ok;

static uint32_t rd32(void *p) { return *(uint32_t *)p; }
static void wr32(void *p, uint32_t v) { *(uint32_t *)p = v; }
static int16_t rd16(void *p) { return *(int16_t *)p; }
static void wr16(void *p, int16_t v) { *(int16_t *)p = v; }

static int code_find(void *codes, int count, uint16_t cp, int *ins) {
    int lo = 0, hi = count - 1, pos = count;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        uint16_t v = *(uint16_t *)((char *)codes + mid * 2);
        if (v == cp) { *ins = mid; return 1; }
        if (v < cp) lo = mid + 1; else { pos = mid; hi = mid - 1; }
    }
    *ins = pos;
    return 0;
}

// 找一个能放下 w x h 的位置（货架式）
static int alloc_slot(Atlas *at, int w, int h, int *ox, int *oy) {
    if (at->curX + w > at->W) { at->curY += at->rowH + 1; at->curX = 0; at->rowH = 0; }
    if (at->curY + h > at->H) return 0;
    *ox = at->curX;
    *oy = at->curY;
    at->curX += w + 1;
    if (h > at->rowH) at->rowH = h;
    return 1;
}

// 扩容图集。同步所有共享该纹理的 page 对象的尺寸浮点。
static int grow_atlas_to(Atlas *at, FontState *fs, int nw, int nh) {
    if (nw == at->W && nh == at->H) return 1;
    if (nw < at->W || nh < at->H) return 0;
    size_t oldsz = (size_t)at->W * at->H * 4, newsz = (size_t)nw * nh * 4;
    unsigned char *old = malloc(oldsz);
    unsigned char *nbig = calloc(1, newsz);
    if (!old || !nbig) { free(old); free(nbig); return 0; }
    if (!read_rect(at->texid, 0, 0, at->W, at->H, old)) { free(old); free(nbig); return 0; }
    for (int y = 0; y < at->H; y++)
        memcpy(nbig + (size_t)y * nw * 4, old + (size_t)y * at->W * 4, (size_t)at->W * 4);
    free(old);

    int pt = 0;
    p_glGetIntegerv(GL_TEX_BIND, &pt);
    p_glBindTexture(GL_TEX2D, at->texid);
    // 沿用原纹理的内部格式：强行改成 RGBA8888 会让引擎按旧格式的假设错位
    int ifmt = GL_RGBA;
    p_glGetTexLevelParameteriv(GL_TEX2D, 0, GL_TEX_IFMT, &ifmt);
    logf_("atlas %u 原内部格式 0x%x", at->texid, ifmt);
    // 一律用 RGBA8888 重建：字形靠 alpha 混合，若沿用 RGB565 之类会丢 alpha，
    // 文字会变成不透明色块。显存多花一点，换正确性。
    ifmt = GL_RGBA;
    p_glTexImage2D(GL_TEX2D, 0, ifmt, nw, nh, 0, GL_RGBA, GL_UBYTE, nbig);
    // 关键保护：重新分配之后 mipmap 链已经失效，且如果原纹理是 REPEAT，
    // 一旦 UV 略微越界就会把整张图集平铺出去 —— 屏幕上就是一大片白砖墙。
    // 这里强制 CLAMP_TO_EDGE + 线性过滤（不依赖 mipmap），从根上堵住这个表现。
    if (p_glTexParameteri) {
        p_glTexParameteri(GL_TEX2D, GL_TEX_MIN_FILTER, GL_LINEAR);
        p_glTexParameteri(GL_TEX2D, GL_TEX_MAG_FILTER, GL_LINEAR);
        p_glTexParameteri(GL_TEX2D, GL_TEX_WRAP_S, GL_CLAMP_EDGE);
        p_glTexParameteri(GL_TEX2D, GL_TEX_WRAP_T, GL_CLAMP_EDGE);
    }
    p_glBindTexture(GL_TEX2D, (unsigned)pt);
    free(nbig);

    // 所有共享此图集的字体页对象都要同步尺寸（UV 归一化用）
    for (int i = 0; i < g_nfont; i++) {
        if (g_fonts[i].atlas == at && g_fonts[i].page) {
            void *pg = g_fonts[i].page;
            *(float *)((char *)pg + PAGE_W)  = (float)nw;
            *(float *)((char *)pg + PAGE_H)  = (float)nh;
            *(float *)((char *)pg + 0x24)    = (float)nw;
            *(float *)((char *)pg + 0x28)    = (float)nh;
        }
    }
    (void)fs;
    int oldH = at->H;
    at->W = nw; at->H = nh;
    at->curX = 0; at->curY = oldH; at->rowH = 0;
    logf_("atlas %u grow -> %dx%d", at->texid, nw, nh);
    return 1;
}

// 翻倍扩容（add_glyph 的兜底路径）
static int grow_atlas(Atlas *at, FontState *fs) {
    int nw = at->W, nh = at->H;
    if (nh < 4096) nh *= 2;
    else if (nw < 4096) nw *= 2;
    else return 0;
    return grow_atlas_to(at, fs, nw, nh);
}

// 识别图集：拿若干条字形记录（位置+尺寸）去候选纹理上采样，看那里是不是真有墨迹。
//
// 两轮：先找尺寸完全一致的（快），再退一步接受"不小于页面尺寸"的纹理 ——
// 因为同一张纹理被多套字体共用时，我们扩容后其它字体对象的 page 尺寸还是旧值，
// 此时必须靠第二轮的宽容匹配把它认回来，并把 page 尺寸同步成真实纹理尺寸。
static unsigned identify_atlas(void *recs, int count, int W, int H, int *ow, int *oh) {
    int probe[40][4], np = 0;
    for (int i = 0; i < count && np < 40; i++) {
        void *rp = *(void **)((char *)recs + i * 8);
        if (!rp) continue;
        int16_t w = rd16((char *)rp + 0xc), h = rd16((char *)rp + 0xe);
        int16_t sx = rd16((char *)rp + 0x8), sy = rd16((char *)rp + 0xa);
        if (w > 2 && h > 5 && w <= 96 && h <= 96 && sx >= 0 && sy >= 0) {
            probe[np][0] = sx; probe[np][1] = sy; probe[np][2] = w; probe[np][3] = h;
            np++;
        }
    }
    if (np < 8) { logf_("atlas 探针不足 %d，放弃", np); return 0; }

    unsigned char *buf = malloc(96 * 96 * 4);
    if (!buf) return 0;

    // 第 0 轮：先认「我们自己扩容过的图集」。
    // 扩容后纹理的真实尺寸变了，而其它字体对象的 page 里还记着旧尺寸，
    // 按「尺寸完全一致」去找永远找不到 —— 提示文字那套字体就是这么整块丢掉的
    // （日志里表现为 `命中 0% (0x0)`，然后 init 失败，中文全缺、提示完全空白）。
    // 这里放宽成「纹理不小于 page」，但仍然要求探针 100% 命中，且只在已知图集里找，
    // 不会把字形写进别人的 UI 贴图。
    for (int i = 0; i < g_natlas; i++) {
        Atlas *at = &g_atlases[i];
        if (at->W < W || at->H < H) continue;
        int hits = 0, usable = 0;
        for (int k = 0; k < np; k++) {
            int sx = probe[k][0], sy = probe[k][1], pw = probe[k][2], ph = probe[k][3];
            if (sx + pw > at->W || sy + ph > at->H) continue;
            usable++;
            if (!read_rect(at->texid, sx, sy, pw, ph, buf)) continue;
            int ink = 0;
            for (int m = 0; m < pw * ph; m++) if (buf[m * 4 + 3] > 8) ink++;
            if (ink * 4 > pw * ph) hits++;
        }
        if (usable * 2 < np) continue;
        if (hits == np) {
            *ow = at->W; *oh = at->H;
            logf_("atlas 已知图集命中 tex=%u %dx%d（page 记的是 %dx%d）",
                  at->texid, at->W, at->H, W, H);
            free(buf);
            return at->texid;
        }
    }

    // 只认「尺寸完全一致 + 探针 100% 命中」的纹理。
    // 之前允许「不小于页面尺寸」的宽松匹配，会认成更大的 UI 贴图；
    // 字形写进去之后那张贴图会被铺满，屏幕上出现一整片白砖墙，且挡住点击。
    unsigned best = 0; int bestscore = -1, bw = 0, bh = 0;
    for (unsigned id = 1; id <= 256; id++) {
        int tw = 0, th = 0;
        if (!tex_size(id, &tw, &th)) continue;
        if (tw != W || th != H) continue;

        int hits = 0, usable = 0;
        for (int i = 0; i < np; i++) {
            int sx = probe[i][0], sy = probe[i][1], pw = probe[i][2], ph = probe[i][3];
            if (sx + pw > tw || sy + ph > th) continue;
            usable++;
            if (!read_rect(id, sx, sy, pw, ph, buf)) continue;
            int ink = 0;
            for (int k = 0; k < pw * ph; k++) if (buf[k * 4 + 3] > 8) ink++;
            if (ink * 4 > pw * ph) hits++;
        }
        if (usable * 2 < np) continue;            // 覆盖不到一半探针，不认
        int score = hits * 100 / np;
        if (score > bestscore) { bestscore = score; best = id; bw = tw; bh = th; }
    }
    free(buf);
    logf_("atlas id=%u 命中 %d%% (%dx%d) 探针 %d", best, bestscore < 0 ? 0 : bestscore, bw, bh, np);
    if (bestscore < 100) return 0;                // 必须全中：宁可放弃，也不写坏别人的纹理
    *ow = bw; *oh = bh;
    return best;
}

static int add_glyph(FontState *fs, uint16_t cp);
static void preload_all(FontState *fs);

// ---------------------------------------------------------------- 纹理定位
// page 对象里存的不是 GL 纹理 ID，而是指向 CIwTexture 的指针，所以要再解一层。
// 直接读 page 的指针字段、在它指向的对象里找「值在 1..1024 且宽高与 page 一致」
// 的整数，比"扫遍所有纹理猜哪张是图集"可靠得多 —— 后者认错一次就会把字形
// 写进 UI 贴图，屏幕上出现整片白砖墙。
typedef struct { uintptr_t a, b; } RdRange;
#define MAX_RD 192
static RdRange g_rd[MAX_RD];
static int g_nrd;

static void load_rd_ranges(void) {
    g_nrd = 0;
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return;
    char line[512];
    while (fgets(line, sizeof(line), f) && g_nrd < MAX_RD) {
        unsigned long a, b;
        char perm[8] = {0};
        if (sscanf(line, "%lx-%lx %7s", &a, &b, perm) < 3) continue;
        if (perm[0] != 'r') continue;
        g_rd[g_nrd].a = a;
        g_rd[g_nrd].b = b;
        g_nrd++;
    }
    fclose(f);
}

static int is_readable(uintptr_t p, size_t len) {
    if (!p) return 0;
    for (int i = 0; i < g_nrd; i++)
        if (p >= g_rd[i].a && p + len <= g_rd[i].b) return 1;
    return 0;
}

static unsigned find_texid_from_page(void *page, int W, int H) {
    if (!g_nrd) load_rd_ranges();
    if (!g_nrd) return 0;
    int pt = 0;
    p_glGetIntegerv(GL_TEX_BIND, &pt);
    unsigned found = 0;
    for (int off = 8; off < 0x40 && !found; off += 8) {
        uintptr_t p = *(uintptr_t *)((char *)page + off);
        if (p < 0x10000 || !is_readable(p, 0x80)) continue;
        for (int k = 0; k < 0x80; k += 4) {
            unsigned v = *(unsigned *)((char *)p + k);
            if (v == 0 || v > 1024) continue;
            int tw = 0, th = 0;
            if (!tex_size(v, &tw, &th)) continue;
            if (tw == W && th == H) {
                logf_("page+0x%x -> obj+0x%x 得到纹理 %u (%dx%d)", off, k, v, tw, th);
                found = v;
                break;
            }
        }
    }
    p_glBindTexture(GL_TEX2D, (unsigned)pt);
    return found;
}

static int font_init(FontState *fs) {
    void *font = fs->font;
    int count = (int)rd32((char *)font + FONT_COUNT);
    void *codes = *(void **)((char *)font + FONT_CODES);
    void *recs = *(void **)((char *)font + FONT_RECS);
    void *pages = *(void **)((char *)font + FONT_PAGES);
    if (!codes || !recs || !pages || count <= 0) { logf_("init失败 %p: codes=%p recs=%p pages=%p count=%d", font, codes, recs, pages, count); return 0; }
    void *page = *(void **)pages;
    if (!page) { logf_("init失败 %p: page=NULL", font); return 0; }
    fs->page = page;
    int W = (int)*(float *)((char *)page + PAGE_W);
    int H = (int)*(float *)((char *)page + PAGE_H);
    if (W < 64 || H < 64) { logf_("init失败 %p: page %dx%d 太小", font, W, H); return 0; }

    // 参考字高：取样本记录 h 的中位数
    int hs[40], nh = 0, maxY = 0;
    for (int i = 0; i < count && nh < 40; i++) {
        void *rp = *(void **)((char *)recs + i * 8);
        if (!rp) continue;
        int16_t h = rd16((char *)rp + 0xe), sy = rd16((char *)rp + 0xa);
        int16_t w = rd16((char *)rp + 0xc);
        if (h > 4 && w > 1) hs[nh++] = h;
    }
    for (int i = 0; i < count; i++) {
        void *rp = *(void **)((char *)recs + i * 8);
        if (!rp) continue;
        int y = rd16((char *)rp + 0xa) + rd16((char *)rp + 0xe);
        if (y > maxY) maxY = y;
    }
    if (!nh) { logf_("init失败 %p: 无有效字形记录", font); return 0; }
    for (int i = 1; i < nh; i++) { int v = hs[i], j = i - 1; while (j >= 0 && hs[j] > v) { hs[j + 1] = hs[j]; j--; } hs[j + 1] = v; }
    fs->refH = hs[nh / 2];
    if (fs->refH < 8) fs->refH = 8;
    if (fs->refH > 48) fs->refH = 48;

    if (!gl_ready()) { logf_("init失败 %p: GL 未就绪", font); return 0; }
    int tw = W, th = H;
    unsigned texid = find_texid_from_page(page, W, H);
    if (texid) {
        logf_("字体 %p 纹理自省成功 tex=%u", font, texid);
    } else {
        texid = identify_atlas(recs, count, W, H, &tw, &th);
        if (texid) logf_("字体 %p 自省失败，兜底识别 tex=%u", font, texid);
    }
    if (!texid) {
        logf_("init失败 %p: 找不到纹理 page=%dx%d count=%d", font, W, H, count);
        return 0;
    }

    // 纹理被我们扩容过：把本字体对象的 page 尺寸同步成真实尺寸，否则 UV 会算错
    if (tw != W || th != H) {
        *(float *)((char *)page + PAGE_W) = (float)tw;
        *(float *)((char *)page + PAGE_H) = (float)th;
        *(float *)((char *)page + 0x24)   = (float)tw;
        *(float *)((char *)page + 0x28)   = (float)th;
        logf_("page 尺寸同步 %dx%d -> %dx%d", W, H, tw, th);
        W = tw; H = th;
    }

    // 找/建共享 Atlas（同纹理的多套字体共用一套分配器）
    Atlas *at = NULL;
    for (int i = 0; i < g_natlas; i++) if (g_atlases[i].texid == texid) { at = &g_atlases[i]; break; }
    if (!at) {
        if (g_natlas >= MAXATLAS) { logf_("init失败 %p: atlas 槽满", font); return 0; }
        at = &g_atlases[g_natlas++];
        at->texid = texid;
        at->W = W; at->H = H;
        at->curX = 0;
        at->curY = maxY + 2;
        at->rowH = 0;
        logf_("新建 atlas %u %dx%d 起点y=%d", texid, W, H, at->curY);
    }
    fs->atlas = at;

    if (at->curY + fs->refH + 4 > at->H) {
        if (!grow_atlas(at, fs)) { logf_("init失败 %p: 扩容失败", font); return 0; }
        at->curY = maxY + 2;
    }
    fs->ready = 1;
    logf_("font %p page %dx%d refH=%d tex=%u count=%d atlas=%p", font, W, H, fs->refH, texid, count, at);
    preload_all(fs);
    return 1;
}

// 字形缓存：同一张纹理上、同一字号的同一个字只光栅化一次。
// 引擎里经常有多个字体对象共用同一张图集纹理，缓存能把预填的工作量砍掉一大截，
// 也让第二套字体不必把同样的字形再往图集里塞一遍。
typedef struct {
    uint16_t cp, refH;
    uint32_t texid;
    int16_t  dy, adv, sx, sy, w, h;
} GCache;
#define GCN 8192
static GCache g_gc[GCN];

static uint32_t gc_slot(uint16_t cp, uint16_t refH, uint32_t texid) {
    uint32_t h = (uint32_t)cp * 2654435761u ^ (uint32_t)refH * 40503u ^ texid * 2246822519u;
    return h & (GCN - 1);
}
static GCache *gc_find(uint16_t cp, uint16_t refH, uint32_t texid) {
    uint32_t i = gc_slot(cp, refH, texid);
    for (int k = 0; k < GCN; k++) {
        GCache *e = &g_gc[i];
        if (!e->w && !e->h) return NULL;
        if (e->cp == cp && e->refH == refH && e->texid == texid) return e;
        i = (i + 1) & (GCN - 1);
    }
    return NULL;
}
static void gc_store(uint16_t cp, uint16_t refH, uint32_t texid, const GCache *v) {
    uint32_t i = gc_slot(cp, refH, texid);
    for (int k = 0; k < GCN; k++) {
        GCache *e = &g_gc[i];
        if ((!e->w && !e->h) || (e->cp == cp && e->refH == refH && e->texid == texid)) {
            *e = *v; e->cp = cp; e->refH = refH; e->texid = texid; return;
        }
        i = (i + 1) & (GCN - 1);
    }
}

// 往字体里加一个码位
static int add_glyph(FontState *fs, uint16_t cp) {
    void *font = fs->font;
    Atlas *at = fs->atlas;
    if (!at) return 0;

    int count = (int)rd32((char *)font + FONT_COUNT);
    int cap = (int)rd32((char *)font + FONT_CAPCODES);
    void *codes = *(void **)((char *)font + FONT_CODES);
    void *recs = *(void **)((char *)font + FONT_RECS);
    int ins0 = 0;
    if (code_find(codes, count, cp, &ins0)) return 1;   // 已经有了

    int16_t dy, advpx, sx, sy, w, h;
    GCache *hit = gc_find(cp, (uint16_t)fs->refH, at->texid);
    if (hit) {
        dy = hit->dy; advpx = hit->adv;
        sx = hit->sx; sy = hit->sy; w = hit->w; h = hit->h;
    } else {
        float scale = stbtt_ScaleForPixelHeight(&g_info, (float)(fs->refH + 1));
        int adv = 0, lsb = 0;
        stbtt_GetCodepointHMetrics(&g_info, cp, &adv, &lsb);
        int x0, y0, x1, y1;
        stbtt_GetCodepointBitmapBox(&g_info, cp, scale, scale, &x0, &y0, &x1, &y1);
        int gw = x1 - x0, gh = y1 - y0;
        if (gw <= 0 || gh <= 0) return 0;
        if (gw > 96 || gh > 96) return 0;

        unsigned char *bmp = calloc(1, (size_t)gw * gh);
        if (!bmp) return 0;
        stbtt_MakeCodepointBitmap(&g_info, bmp, gw, gh, gw, scale, scale, cp);

        // 小字号下汉字笔画密集，直接光栅化会糊成一条灰线（建筑名、升级说明
        // 这类小标签就是这个问题）。做一次轻度加粗：alpha 提升 1.5 倍并截顶。
        if (fs->refH <= 18) {
            for (int i = 0; i < gw * gh; i++) {
                int a = bmp[i];
                a += a >> 1;
                bmp[i] = (unsigned char)(a > 255 ? 255 : a);
            }
        }

        int ox = 0, oy = 0;
        if (!alloc_slot(at, gw, gh, &ox, &oy)) {
            if (!grow_atlas(at, fs) || !alloc_slot(at, gw, gh, &ox, &oy)) { free(bmp); return 0; }
        }

        unsigned char *rgba = malloc((size_t)gw * gh * 4);
        if (!rgba) { free(bmp); return 0; }
        for (int i = 0; i < gw * gh; i++) {
            rgba[i * 4 + 0] = 255; rgba[i * 4 + 1] = 255; rgba[i * 4 + 2] = 255;
            rgba[i * 4 + 3] = bmp[i];
        }
        int pt = 0;
        p_glGetIntegerv(GL_TEX_BIND, &pt);
        p_glBindTexture(GL_TEX2D, at->texid);
        p_glTexSubImage2D(GL_TEX2D, 0, ox, oy, gw, gh, GL_RGBA, GL_UBYTE, rgba);
        p_glBindTexture(GL_TEX2D, (unsigned)pt);
        free(rgba);
        free(bmp);

        int d = 3 + (fs->refH - gh);
        if (d < 0) d = 0;
        int a = (int)(adv * scale + 0.5f);
        if (a < gw) a = gw;

        GCache e;
        memset(&e, 0, sizeof(e));
        e.dy = (int16_t)d; e.adv = (int16_t)a;
        e.sx = (int16_t)ox; e.sy = (int16_t)oy;
        e.w = (int16_t)gw; e.h = (int16_t)gh;
        gc_store(cp, (uint16_t)fs->refH, at->texid, &e);
        dy = e.dy; advpx = e.adv; sx = e.sx; sy = e.sy; w = e.w; h = e.h;
    }

    // 码表/记录表容量不够就翻倍
    if (count >= cap) {
        int ncap = cap * 2;
        void *nc = malloc((size_t)ncap * 2);
        void *nr = malloc((size_t)ncap * 8);
        if (!nc || !nr) { free(nc); free(nr); return 0; }
        memcpy(nc, codes, (size_t)count * 2);
        memcpy(nr, recs, (size_t)count * 8);
        for (int i = count; i < ncap; i++) { *(uint16_t *)((char *)nc + i * 2) = 0xffff; *(void **)((char *)nr + i * 8) = NULL; }
        *(void **)((char *)font + FONT_CODES) = nc;
        *(void **)((char *)font + FONT_RECS) = nr;
        wr32((char *)font + FONT_CAPCODES, (uint32_t)ncap);
        wr32((char *)font + FONT_CAPRECS, (uint32_t)ncap);
        codes = nc; recs = nr; cap = ncap;
    }

    int ins = 0;
    code_find(codes, count, cp, &ins);
    memmove((char *)codes + (ins + 1) * 2, (char *)codes + ins * 2, (size_t)(count - ins) * 2);
    memmove((char *)recs + (ins + 1) * 8, (char *)recs + ins * 8, (size_t)(count - ins) * 8);
    *(uint16_t *)((char *)codes + ins * 2) = cp;

    int16_t *rec = malloc(16);
    if (!rec) return 0;
#if ZF_DIAG
    if (g_glyph_dbg < 24) {
        g_glyph_dbg++;
        logf_("字形 %04x w=%d h=%d advpx=%d dy=%d sx=%d sy=%d refH=%d",
              cp, w, h, advpx, dy, sx, sy, fs->refH);
    }
#endif
    rec[0] = 0;        // dx
    rec[1] = dy;       // dy
    rec[2] = advpx;    // advance
    rec[3] = 0;        // 页号
    rec[4] = sx;
    rec[5] = sy;
    rec[6] = w;
    rec[7] = h;
    *(void **)((char *)recs + ins * 8) = rec;

    wr32((char *)font + FONT_COUNT, (uint32_t)(count + 1));
    wr32((char *)font + 0x18, (uint32_t)(count + 1));
    wr32((char *)font + 0x30, (uint32_t)(count + 1));
    return 1;
}

// 一次性把翻译用到的所有码位填进这个字体。
//
// 为什么要预填：引擎里不止一条文本绘制路径（主菜单卷轴标题、建筑面板等
// 都不走 img+0x110088），只 hook 一条必然漏。把字形直接写进字体自己的
// 码表后，任何路径查表都能命中，与 hook 无关。
static void preload_all(FontState *fs) {
    // 一次性扩到够用，而不是边填边扩。
    // 每扩一次都要 glTexImage2D 重新分配纹理，而预填是在引擎绘制回调里跑的；
    // 单帧内连续重分配 3 次会让 GPU 侧状态错乱，表现就是一整张图集被
    // REPEAT 铺满屏幕（白砖墙）且挡住点击。只分配一次，风险小得多。
    Atlas *at = fs->atlas;
    if (at && k_ncps > 0) {
        int cell = fs->refH + 4;
        long need = (long)k_ncps * cell * cell;
        int nw = at->W, nh = at->H;
        while ((long)nw * nh < need && nh < 4096) nh *= 2;
        while ((long)nw * nh < need && nw < 4096) nw *= 2;
        if (nw != at->W || nh != at->H) {
            if (p_glFinish) p_glFinish();
            int ok = grow_atlas_to(at, fs, nw, nh);
            if (p_glFinish) p_glFinish();
            logf_("预填前扩容 %s -> %dx%d（需要 %ld 像素）", ok ? "成功" : "失败", nw, nh, need);
        }
    }

    int added = 0;
    for (int i = 0; i < k_ncps; i++) {
        uint16_t cp = k_cps[i];
        void *codes = *(void **)((char *)fs->font + FONT_CODES);
        int count = (int)rd32((char *)fs->font + FONT_COUNT);
        int ins;
        if (code_find(codes, count, cp, &ins)) continue;
        if (add_glyph(fs, cp)) added++;
    }
    logf_("预填 %p: 新增 %d 个（表内 %d）", fs->font, added, k_ncps);
}

// ---------------------------------------------------------------- 诊断追踪

#if ZF_DIAG
static uint32_t g_th[8192];
static int g_tn;
static int trace_new(uint32_t h) {
    if (!h) h = 1;
    uint32_t i = h & 8191;
    for (int k = 0; k < 8192; k++) {
        if (!g_th[i]) { g_th[i] = h; return 1; }
        if (g_th[i] == h) return 0;
        i = (i + 1) & 8191;
    }
    return 0;
}
#endif

// ---------------------------------------------------------------- 钩子

// 「数字/数字」这种文本（比如面板上的 872/1000）几乎只出现在属性显示处，
// 把它的调用者记下来，就能直接定位英雄面板的绘制函数，
// 再从那个函数里读出经验的字段偏移 —— 比在内存里瞎扫稳得多。
#define MAXRT 48
static uintptr_t g_rt_c[MAXRT];
static char g_rt_t[MAXRT][24];
static int g_rt_i, g_rt_total;

void zh_on_draw(void *font, uint16_t *text, int len, int maxx, int site, uintptr_t caller) {
    g_draw_calls++;
#if ZF_CHEAT
    zf_apply_pending();       // 即时作弊项（理想城堡等）在这里执行，跑在渲染线程
    // 购买捕获：商店里点一下「对号」，那一帧 arr[i] 是 1，300ms 轮询抓不到，
    // 只能在这里顺手读。见到就锁存进 g_keep_mask，之后不再压回 0。
    if (g_vet_armed && g_keep_mask != 0xfu) {
        uintptr_t a = g_cht_arr;
        if (a && zf_addr_ok(a + 8, 1)) {
            const volatile unsigned char *p = (const volatile unsigned char *)a;
            for (int k = 0; k < 4; k++) {
                int i = kOffIdx[k];
                if ((g_keep_mask & (1u << i)) || !p[i]) continue;
                g_keep_mask |= (1u << i);
                logf_("★ 捕获到玩家购买第 %d 项，本会话保持开启（mask=%x）", i, g_keep_mask);
            }
        }
    }
#endif
    if (!font || !text || len <= 0 || len > 65536) return;
#if ZF_DIAG
    if (len >= 3 && len <= 23) {
        int nd = 0, sl = 0, ok = 1;
        for (int i = 0; i < len; i++) {
            uint16_t c = text[i];
            if (c == '/') sl++;
            else if (c >= '0' && c <= '9') nd++;
            else { ok = 0; break; }
        }
        if (ok && nd && sl) {
            int k = g_rt_i;
            g_rt_c[k] = caller;
            int cp = len < 23 ? len : 23;
            for (int i = 0; i < cp; i++) g_rt_t[k][i] = (char)text[i];
            g_rt_t[k][cp] = 0;
            g_rt_i = (k + 1) % MAXRT;
            g_rt_total++;
        }
    }
#endif
#if ZF_DIAG
    // 只把「含中文」的绘制记进环形缓冲，用 drawn 命令取。
    // 全量记录会被每帧重复绘制的纯 ASCII 文本（比如 ENGLISH）挤满。
    {
        int has_cjk = 0;
        for (int i = 0; i < len; i++) if (text[i] >= 0x80) { has_cjk = 1; break; }
        if (has_cjk) {
            int k = g_dr_i;
            g_dr_c[k] = caller;
            g_dr_n[k] = len;
            int cp = len < 19 ? len : 19;
            for (int i = 0; i < cp; i++) g_dr_t[k][i] = text[i];
            g_dr_t[k][cp] = 0;
            g_dr_len[k] = cp;
            g_dr_i = (k + 1) % MAXDR;
            g_dr_total++;
        }
    }
#endif
    if (g_busy) return;
    g_busy = 1;
    (void)caller;
#if ZF_DIAG
    if (len >= 4 && text[len - 1] == ')' ) {
        int has_open = 0, digit = 0;
        for (int i = 0; i < len - 1; i++) {
            if (text[i] == '(') has_open = 1;
            if (text[i] >= '0' && text[i] <= '9') digit = 1;
        }
        if (has_open && digit) {
            char bb[200]; int pp = 0;
            pp += snprintf(bb + pp, sizeof(bb) - pp, "HEROLABEL c=%p f=%p n=%d [", (void *)caller, font, len);
            for (int i = 0; i < len && pp < (int)sizeof(bb) - 10; i++) {
                uint16_t c = text[i];
                if (c >= 0x20 && c < 0x7f) bb[pp++] = (char)c;
                else pp += snprintf(bb + pp, sizeof(bb) - pp, "\\u%x", c);
            }
            bb[pp++] = ']'; bb[pp] = 0;
            logf_("%s", bb);
        }
    }
#endif

#if ZF_DIAG
    // 诊断：记录每个不同的 (font, len, maxX, 文本) 组合，用来判断某个界面到底
    // 走不走这条绘制路径、用的是哪个字体对象。
    {
        int has_nz = 0;
        for (int i = 0; i < len; i++) if (text[i] >= 0x80) { has_nz = 1; break; }
        (void)has_nz;
        uint32_t h = 2166136261u;
        uintptr_t fp = (uintptr_t)font;
        for (int i = 0; i < 8; i++) { h = (h ^ ((fp >> (i * 8)) & 0xff)) * 16777619u; }
        h = (h ^ (uint32_t)len) * 16777619u;
        h = (h ^ (uint32_t)maxx) * 16777619u;
        for (int i = 0; i < len; i++) {
            h = (h ^ (text[i] & 0xff)) * 16777619u;
            h = (h ^ ((text[i] >> 8) & 0xff)) * 16777619u;
        }
        if (trace_new(h)) {
            g_tn++;
            char b[320]; int p = 0;
            p += snprintf(b + p, sizeof(b) - p, "T%d s%d f=%p n=%d max=%d m8c=%d c=%p t=%p [",
                          g_tn, site, font, len, maxx,
                          (int)*(unsigned char *)((char *)font + 0x8c), (void *)caller, (void *)text);
            for (int i = 0; i < len && p < (int)sizeof(b) - 10; i++) {
                uint16_t c = text[i];
                if (c >= 0x20 && c < 0x7f) b[p++] = (char)c;
                else p += snprintf(b + p, sizeof(b) - p, "\\u%x", c);
            }
            b[p++] = ']'; b[p] = 0;
            logf_("%s", b);
        }
    }
#endif

    FontState *fs = NULL;
    void *fcodes = *(void **)((char *)font + FONT_CODES);
    // 先按 font 指针找
    for (int i = 0; i < g_nfont; i++) if (g_fonts[i].font == font) { fs = &g_fonts[i]; break; }
    // 再按 codes 数组指针找：不同 font 对象若共享同一码表，就是同一逻辑字体，复用状态
    int by_codes = 0;
    if (!fs && fcodes) {
        for (int i = 0; i < g_nfont; i++) {
            void *c2 = *(void **)((char *)g_fonts[i].font + FONT_CODES);
            if (c2 == fcodes) { fs = &g_fonts[i]; by_codes = 1; break; }
        }
    }
#if ZF_DIAG
    // 诊断：每个新出现的 font 对象都把内部字段打出来，用来判断「同一张图集的不同字体
    // 对象」到底共不共享 codes/recs —— 这决定了预填一次够不够。
    if (!fs) {
        void *rc = *(void **)((char *)font + FONT_RECS);
        void *pg = *(void **)((char *)font + FONT_PAGES);
        int pgw = 0, pgh = 0;
        if (pg) {
            void *p0 = *(void **)pg;
            if (p0) { pgw = (int)*(float *)((char *)p0 + PAGE_W); pgh = (int)*(float *)((char *)p0 + PAGE_H); }
        }
        logf_("新字体对象 %p count=%d cap=%d codes=%p recs=%p page=%p(%dx%d) b88=%d b8c=%d",
              font, (int)rd32((char *)font + FONT_COUNT), (int)rd32((char *)font + FONT_CAPCODES),
              fcodes, rc, pg, pgw, pgh,
              (int)*(unsigned char *)((char *)font + 0x88), (int)*(unsigned char *)((char *)font + 0x8c));
    } else if (by_codes) {
        logf_("字体 %p 复用 %p 的状态（codes 相同）", font, fs->font);
    }
#endif
    (void)by_codes;
    if (!fs && g_nfont < MAXFONT) { fs = &g_fonts[g_nfont++]; memset(fs, 0, sizeof(*fs)); fs->font = font; }
    if (!fs) { g_busy = 0; return; }

    if (!fs->ready) {
        // 失败不再一锤定音：纹理可能还没建好，给它几次机会（每次失败都记一笔，最多 5 次）
        if (fs->tried >= 5) { g_busy = 0; return; }
        fs->tried++;
        if (!font_init(fs)) { g_busy = 0; return; }
    }
    if (!fs->ready) { g_busy = 0; return; }

    for (int i = 0; i < len; i++) {
        uint16_t cp = text[i];
        if (cp < 0x80 || cp == 0xffff) continue;
        void *codes = *(void **)((char *)font + FONT_CODES);
        int count = (int)rd32((char *)font + FONT_COUNT);
        int ins;
        if (code_find(codes, count, cp, &ins)) continue;
        if (!g_font_ok) break;
        add_glyph(fs, cp);
    }
    g_busy = 0;
}

// 保存/恢复所有可能被破坏的寄存器，然后跳到各自的 trampoline。
// 引擎里有两个字节级完全相同的 DrawText 副本（0x110088 / 0x11076c），
// 每个副本都需要一个自己的桩，才能跳回正确的续点。
#define DEF_HANDLER(name, trampvar, siteid)                                          \
__attribute__((naked)) static void name(void) {                              \
    __asm__ volatile(                                                        \
        "sub  sp, sp, #0x200\n"                                             \
        "stp  x0, x1, [sp, #0x00]\n"                                        \
        "stp  x2, x3, [sp, #0x10]\n"                                        \
        "stp  x4, x5, [sp, #0x20]\n"                                        \
        "stp  x6, x7, [sp, #0x30]\n"                                        \
        "str  x8, [sp, #0x40]\n"                                            \
        "str  x30, [sp, #0x48]\n"                                           \
        "stp  q0, q1, [sp, #0x50]\n"                                        \
        "stp  q2, q3, [sp, #0x70]\n"                                        \
        "stp  q4, q5, [sp, #0x90]\n"                                        \
        "stp  q6, q7, [sp, #0xb0]\n"                                        \
        "mov  x1, x2\n"                                                     \
        "mov  w2, w3\n"                                                     \
        "mov  w3, w7\n"      /* 第 8 个参数 = maxX（绘制宽度上限） */        \
        "mov  w4, #" #siteid "\n"                                           \
        "ldr  x5, [sp, #0x48]\n"  /* 进入 DrawText 时的 x30 = 调用者返回地址 */ \
        "bl   zh_on_draw\n"                                                 \
        "ldp  q0, q1, [sp, #0x50]\n"                                        \
        "ldp  q2, q3, [sp, #0x70]\n"                                        \
        "ldp  q4, q5, [sp, #0x90]\n"                                        \
        "ldp  q6, q7, [sp, #0xb0]\n"                                        \
        "ldr  x8, [sp, #0x40]\n"                                            \
        "ldr  x30, [sp, #0x48]\n"                                           \
        "ldp  x6, x7, [sp, #0x30]\n"                                        \
        "ldp  x4, x5, [sp, #0x20]\n"                                        \
        "ldp  x2, x3, [sp, #0x10]\n"                                        \
        "ldp  x0, x1, [sp, #0x00]\n"                                        \
        "add  sp, sp, #0x200\n"                                             \
        "adrp x9, " #trampvar "\n"                                          \
        "add  x9, x9, :lo12:" #trampvar "\n"                                \
        "ldr  x9, [x9]\n"                                                   \
        "br   x9\n"                                                         \
    );                                                                       \
}

static unsigned char *g_tramp0, *g_tramp1;
DEF_HANDLER(zh_handler0, g_tramp0, 0)
DEF_HANDLER(zh_handler1, g_tramp1, 1)

#if ZF_CHEAT
// ------------------------------------------------- 单位标签函数 0x1db3c 的钩子
// 这个函数负责画「名字 (等级)」和经验条，第一个参数 x0 就是单位对象。
// 直接 hook 入口，把 x0 抓下来 —— 这是拿到英雄对象最稳的办法（静态推偏移太脆）。
#define LABEL_VA 0x1db3cu

static unsigned char *g_tramp2;
static unsigned char *g_img;        // 定义在后面「启动」一节，这里先声明

#define MAXHO 96
static uintptr_t g_ho[MAXHO];
static int g_nho;
static volatile uintptr_t g_lbl_obj;    // 最近一次「名字(等级)」标签绘制的对象

// 老兵升级的「投递」机制：
//   作弊线程只负责发现「新出现的英雄」，把对象指针塞进队列；
//   真正的升级动作由渲染线程（本文件里的 zh_on_hero）执行。
//   原因：升级要调游戏自己的升级函数，它会重算属性、可能触发特效，
//         跨线程调有并发风险（以前就吃过闪退的亏）。
//   队列是单生产者（作弊线程）/ 单消费者（渲染线程），不用加锁。
#define VQ_MAX 128
static volatile uintptr_t g_vq[VQ_MAX];
static volatile int g_vq_h, g_vq_t;
static void zf_level_to(uintptr_t obj, int target);   // 定义在后面

// 只在下面的内联汇编里被引用，必须标 used，否则编译器会把它当未使用删掉，
// 结果 .so 里留下一个 UND 的 zh_on_hero —— dlopen 直接失败，整个钩子都装不上。
__attribute__((used)) static void zh_on_hero(uintptr_t p, uintptr_t lr) {
    if (!p || (p & 7)) return;
    // 队列里有活就取一个升掉（这里跑在渲染线程，安全）
    int h = g_vq_h;
    if (h != g_vq_t) {
        uintptr_t vo = g_vq[h];
        g_vq_h = (h + 1) % VQ_MAX;
        if (vo) zf_level_to(vo, 99);
    }
    g_lbl_obj = p;
    for (int i = 0; i < g_nho; i++) if (g_ho[i] == p) return;
    if (g_nho < MAXHO) {
        g_ho[g_nho] = p;
        logf_("HO %d = %p lr=%#lx", g_nho, (void *)p,
             (unsigned long)(lr - (uintptr_t)g_img));
        g_nho++;
    }
}

__attribute__((naked)) static void zh_handler2(void) {
    __asm__ volatile(
        "sub  sp, sp, #0x60\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "stp  x2, x3, [sp, #0x10]\n"
        "stp  x4, x5, [sp, #0x20]\n"
        "stp  x6, x7, [sp, #0x30]\n"
        "str  x30, [sp, #0x40]\n"
        "ldr  x1, [sp, #0x40]\n"
        "bl   zh_on_hero\n"
        "ldr  x30, [sp, #0x40]\n"
        "ldp  x6, x7, [sp, #0x30]\n"
        "ldp  x4, x5, [sp, #0x20]\n"
        "ldp  x2, x3, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0x60\n"
        "adrp x9, g_tramp2\n"
        "add  x9, x9, :lo12:g_tramp2\n"
        "ldr  x9, [x9]\n"
        "br   x9\n"
    );
}

// ------------------------------------------------- 单位对象钩子（0xe92b8）
// 属性重算函数 0xe8d3c 里这段是「等级加成」：
//   0xe92b4  ldr x2, [x1, w20, sxtw #3]   ; x1[w20] = 单位对象
//   0xe92b8  ldr w2, [x2, #0x4c]          ; +0x4c = 等级
//   0xe92bc  add w2, w2, w2               ; 等级 * 2
//   0xe92c0  add w2, w2, w4
//   0xe92c4  str w2, [x0, #0xd4]          ; 最大生命 = 基础 + 等级*2
// 从 0xe92b8 挂进去，x2 正好是单位对象 —— 这是目前唯一能稳定拿到对象指针的地方。
// 选这里还有一个原因：这 4 条指令全是 PC 无关的，能整体搬进 trampoline。
// （0xe8d3c 入口第 3 条是 adrp，PC 相关，搬不了，所以只能在中间找落点。）
// 换成血条绘制函数 0x1057b0 的入口。调用方 0x8d4f8 是 `mov x0,x20; bl 0x1057b0`，
// 所以 x0 就是单位对象。入口前 4 条：
//   stp x19,x20,[sp,#-0xd0]!  /  stp d10,d11,[sp,#0x68]  /  fmov d11,x0  /  str x30,[sp,#0x50]
// 全是 PC 无关的，能整体搬进 trampoline。
// （0xe8d3c 里 0xe92b8 那段只在某个 type 分支里走，实测一次都没触发，所以换这里。）
#define UNIT_VA 0x1057b0u

static int zf_ld32(uintptr_t a);        // 定义在后面，这里先声明
static unsigned char *g_tramp_u;
static volatile unsigned g_u_calls;

#define MAXU 64
static uintptr_t g_up[MAXU];
static int g_ulv[MAXU];
static int g_nu;

__attribute__((used)) static void zh_on_unit(uintptr_t obj) {
    g_u_calls++;
    if (!obj) return;
    for (int i = 0; i < g_nu; i++) if (g_up[i] == obj) { g_ulv[i]++; return; }
    if (g_nu < MAXU) {
        g_up[g_nu] = obj;
        g_ulv[g_nu] = 1;
        g_nu++;
    }
}

__attribute__((naked)) static void zh_h_unit(void) {
    __asm__ volatile(
        "sub  sp, sp, #0x30\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "stp  x2, x3, [sp, #0x10]\n"
        "str  x30, [sp, #0x20]\n"
        // x0 就是单位对象（调用方 `mov x0,x20; bl 0x1057b0`）。
        // 之前这里错写成 `mov x0, x2`，抓到的全是垃圾指针（g_ho 里躺着一个路径字符串），
        // 所以「单位对象数组」一直是空的。
        "bl   zh_on_unit\n"
        "ldr  x30, [sp, #0x20]\n"
        "ldp  x2, x3, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0x30\n"
        "adrp x9, g_tramp_u\n"
        "add  x9, x9, :lo12:g_tramp_u\n"
        "ldr  x9, [x9]\n"
        "br   x9\n"
    );
}


// ------------------------------------------------- 平台层输入探针
// 注意：这一组探针（s3ePointerUpdate / GetState / TouchState 覆盖）是早期排查
// 「触摸事件进不来」时写的，正式版从未调用过（install_hook 里已注释掉）。
// 它们依赖的 zf_modbase 只在诊断版里有定义，所以整段跟着 ZF_DIAG 走，
// 免得正式版编译时冒出「internal linkage but is not defined」警告。
#if ZF_DIAG
// libs3e_android.so 里 s3ePointerUpdate（文件偏移 0xaf3d4）每帧被调用，
// 它负责把 Android 的 AInputEvent 转成引擎的指针状态。如果它压根没被调用，
// 说明主循环没跑；被调用了但状态数组还是全 0，说明事件没进引擎。
// 前 4 条指令是 sub sp / mov w0,#0x10 / stp x19,x20 / stp x21,x22，全是 PC 无关的，
// 可以安全搬到 trampoline。
#define PU_VA 0xaf3d4u
static int patch_site(uintptr_t base, unsigned va, void (*handler)(void), unsigned char **tramp_out);
static uintptr_t zf_modbase(const char *name);
static unsigned char *g_tramp_pu;
static volatile unsigned g_pu_calls;
static int g_pu_done;

// 注入：直接往引擎的指针状态块里写「按下/抬起」+ 坐标，
// 绕过 Android 输入栈（实测事件根本进不来：状态数组恒 0）。
// 布局：0x174af0 = 按钮状态 byte[6]，0x174afc = X，0x174b00 = Y。
static volatile int g_inj_frames;
static volatile int g_inj_down;
static volatile int g_inj_x, g_inj_y;
static volatile unsigned g_inj_hits;
static uintptr_t g_s3e_base;

__attribute__((used)) static void zh_on_pu(void) {
    g_pu_calls++;
}

__attribute__((naked)) static void zh_h_pu(void) {
    __asm__ volatile(
        "sub  sp, sp, #0x30\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "stp  x2, x3, [sp, #0x10]\n"
        "str  x30, [sp, #0x20]\n"
        "bl   zh_on_pu\n"
        "ldr  x30, [sp, #0x20]\n"
        "ldp  x2, x3, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0x30\n"
        "adrp x9, g_tramp_pu\n"
        "add  x9, x9, :lo12:g_tramp_pu\n"
        "ldr  x9, [x9]\n"
        "br   x9\n"
    );
}

static int install_pu_hook(void) {
    if (g_pu_done) return 1;
    uintptr_t b = zf_modbase("libs3e_android.so");
    if (!b) return 0;
    if (patch_site(b, PU_VA, zh_h_pu, &g_tramp_pu)) {
        g_pu_done = 1;
        g_s3e_base = b;
        logf_("s3ePointerUpdate 已挂钩 base=%p", (void *)b);
        return 1;
    }
    return 0;
}

// s3ePointerGetState(button) 直接返回 *(0x174af0 + button)。
// 前 4 条是 sub sp / stp x19,x30 / mov w19,w0 / mov w0,#0x10 —— 全 PC 无关，可安全搬。
// 计数能区分两种故障：
//   计数不涨 → 游戏根本没在轮询输入（逻辑卡在别的状态）
//   计数在涨但值恒 0 → 引擎收到了轮询但事件没进状态数组
#define GS_VA 0xacf40u
static unsigned char *g_tramp_gs;
static volatile unsigned g_gs_calls;
static volatile int g_gs_lastbtn;
static volatile int g_gs_lastret;
static int g_gs_done;

__attribute__((used)) static void zh_on_gs(unsigned btn) {
    g_gs_calls++;
    g_gs_lastbtn = (int)btn;
}

__attribute__((naked)) static void zh_h_gs(void) {
    __asm__ volatile(
        "sub  sp, sp, #0x20\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "str  x30, [sp, #0x10]\n"
        "bl   zh_on_gs\n"
        "ldr  x30, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0x20\n"
        "adrp x9, g_tramp_gs\n"
        "add  x9, x9, :lo12:g_tramp_gs\n"
        "ldr  x9, [x9]\n"
        "br   x9\n"
    );
}

static int install_gs_hook(void) {
    if (g_gs_done) return 1;
    uintptr_t b = zf_modbase("libs3e_android.so");
    if (!b) return 0;
    if (patch_site(b, GS_VA, zh_h_gs, &g_tramp_gs)) {
        g_gs_done = 1;
        logf_("s3ePointerGetState 已挂钩 base=%p", (void *)b);
        return 1;
    }
    return 0;
}

// 多点触控版本 s3ePointerGetTouchState(index)。现代 Marmalade UI 多半走这条。
// 实测游戏每帧调它一次（index=0），但内部状态块被 s3ePointerUpdate 重算覆盖，
// 光写内存改不动。所以改成「直接伪造返回值」：注入期间这三个函数不执行原逻辑。
// 约定：覆盖函数返回 -1 表示放行走原函数，否则该值就是函数返回值。
#define GTS_VA 0xacf90u
#define TX_VA  0xad2b4u
#define TY_VA  0xad380u

static volatile int g_ovr_mode;      // 0=关 1=按下 2=抬起
static volatile int g_ovr_x, g_ovr_y;
static volatile unsigned g_ovr_calls;

static unsigned char *g_tramp_gts, *g_tramp_tx, *g_tramp_ty;
static volatile unsigned g_gts_calls;
static volatile int g_gts_lastidx;
static int g_gts_done, g_tx_done, g_ty_done;

// 这三个函数只在内联汇编写死名字被调用，编译器看不到引用，-O2 会把它们删掉，
// 结果 .so 里留下 UND 符号 → dlopen 直接失败 → 整个钩子都装不上（踩过两次）。
__attribute__((used)) static int zh_gts_ovr(unsigned idx) {
    g_gts_calls++;
    g_gts_lastidx = (int)idx;
    if (!g_ovr_mode || idx != 0) return -1;
    g_ovr_calls++;
    return g_ovr_mode == 1 ? 2 : 3;   // S3E_POINTER_STATE_PRESSED / RELEASED
}
__attribute__((used)) static int zh_tx_ovr(unsigned idx) {
    if (!g_ovr_mode || idx != 0) return -1;
    return g_ovr_x;
}
__attribute__((used)) static int zh_ty_ovr(unsigned idx) {
    if (!g_ovr_mode || idx != 0) return -1;
    return g_ovr_y;
}

#define DEF_OVR_HANDLER(fn, ovr, tramp)                                       \
__attribute__((naked)) static void fn(void) {                                 \
    __asm__ volatile(                                                         \
        "sub  sp, sp, #0x20\n"                                                \
        "stp  x0, x1, [sp, #0x00]\n"                                          \
        "str  x30, [sp, #0x10]\n"                                             \
        "bl   " #ovr "\n"                                                     \
        "ldr  x30, [sp, #0x10]\n"                                             \
        "cmn  w0, #1\n"                                                       \
        "b.eq 2f\n"                                                           \
        "ldr  x1, [sp, #0x08]\n"                                              \
        "add  sp, sp, #0x20\n"                                                \
        "ret\n"                                                               \
        "2:\n"                                                                \
        "ldp  x0, x1, [sp, #0x00]\n"                                          \
        "add  sp, sp, #0x20\n"                                                \
        "adrp x9, " #tramp "\n"                                               \
        "add  x9, x9, :lo12:" #tramp "\n"                                     \
        "ldr  x9, [x9]\n"                                                     \
        "br   x9\n"                                                           \
    );                                                                        \
}
DEF_OVR_HANDLER(zh_h_gts, zh_gts_ovr, g_tramp_gts)
DEF_OVR_HANDLER(zh_h_tx,  zh_tx_ovr,  g_tramp_tx)
DEF_OVR_HANDLER(zh_h_ty,  zh_ty_ovr,  g_tramp_ty)

static int install_gts_hook(void) {
    if (g_gts_done) return 1;
    uintptr_t b = zf_modbase("libs3e_android.so");
    if (!b) return 0;
    if (!patch_site(b, GTS_VA, zh_h_gts, &g_tramp_gts)) return 0;
    if (!patch_site(b, TX_VA, zh_h_tx, &g_tramp_tx)) return 0;
    if (!patch_site(b, TY_VA, zh_h_ty, &g_tramp_ty)) return 0;
    g_gts_done = g_tx_done = g_ty_done = 1;
    logf_("TouchState/TouchX/TouchY 已挂钩 base=%p", (void *)b);
    return 1;
}

#endif  // ZF_DIAG（输入探针结束）
#endif  // ZF_CHEAT：标签钩子 + 单位对象钩子 + 输入探针（全部只服务作弊）

// ---------------------------------------------------------------- 启动
static unsigned char *g_img;

// ---------------------------------------------------------------- 安全读（正式版）
// 诊断版那套 zf_ld/zf_ld32 靠 sigsetjmp 兜底，配一张全量扫描表。
// 正式版先试过「/proc/self/maps 收区间 + 二分查」，结果点问号完全没反应：
// 游戏映射数超过表容量（512），截断后目标区间不在表里；重读也还是截断。
// 换成信号兜底：读之前置位，SIGSEGV/SIGBUS 里 longjmp 回来返回 0。
// 这个方案在诊断版跑了很久，没有副作用，也不依赖任何表。
#include <signal.h>
#include <setjmp.h>

static sigjmp_buf g_jb;
static volatile int g_guard;

static void zf_fault(int sig) {
    if (g_guard) { g_guard = 0; siglongjmp(g_jb, 1); }
    // 不是我们自己的读触发的，恢复默认处理再抛回去，不掩盖真实崩溃
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = SIG_DFL;
    sigemptyset(&sa.sa_mask);
    sigaction(sig, &sa, NULL);
    raise(sig);
}

static void zf_guard_install(void) {
    static int done;
    if (done) return;
    done = 1;
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = zf_fault;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_NODEFER;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
}

static uintptr_t zf_ld(uintptr_t a) {
    uintptr_t v;
    if (!a) return 0;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    v = *(volatile uintptr_t *)a;
    g_guard = 0;
    return v;
}

static int zf_ld32(uintptr_t a) {
    int v;
    if (!a) return 0;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    v = *(volatile int32_t *)a;
    g_guard = 0;
    return v;
}

// 保留给 zf_hero_ok 做粗筛：读靠信号兜底，这里只排除明显不可能的空地址。
static int zf_inreg(uintptr_t a) {
    return a >= 0x1000 && (a >> 48) == 0;
}

static uintptr_t find_image(void) {
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[512];
    static const char sig[] = "9CIwGxFont";
    unsigned char *buf = malloc(256 * 1024);
    if (!buf) { fclose(f); return 0; }
    uintptr_t found = 0;
    while (fgets(line, sizeof(line), f)) {
        unsigned long a, b;
        char perm[8] = {0}, path[256] = {0};
        int nf = sscanf(line, "%lx-%lx %7s %*s %*s %*s %255s", &a, &b, perm, path);
        if (nf < 3) continue;
        // 只扫可执行段：引擎镜像是 rwxs 匿名段，映射后内容稳定，读取安全。
        // 这样既排除海量 rw-p 堆段（并发变化会导致读越界崩溃），
        // 也排除 libzhfont.so 自身的 r--p 只读段（.dynstr 里有同名字符串，会误命中）。
        if (perm[2] != 'x') continue;
        if (nf >= 4 && strstr(path, "libzhfont")) continue;
        unsigned long size = b - a;
        if (size < 0x100000 || size > 0x8000000) continue;
        unsigned long off = 0;
        while (off < size) {
            size_t chunk = size - off;
            if (chunk > 256 * 1024) chunk = 256 * 1024;
            memcpy(buf, (void *)(a + off), chunk);
            void *hit = memmem_(buf, chunk, sig, sizeof(sig) - 1);
            if (hit) {
                uintptr_t addr = (uintptr_t)(a + off) + (uintptr_t)((unsigned char *)hit - buf);
                uintptr_t base = addr - SIG_VA;
                // 引擎镜像来自 mmap，基址必页对齐；非对齐说明命中了别处的同名串
                if ((base & 0xfff) == 0) { found = base; break; }
            }
            off += chunk;
        }
        if (found) break;
    }
    free(buf);
    fclose(f);
    return found;
}

// 在 base+va 处打一个 16 字节跳转：ldr x16,#8 ; br x16 ; .quad handler
// 原前 4 条指令复制到 trampoline，桩执行完再从 trampoline 跳回 va+16 继续。
static int patch_site(uintptr_t base, unsigned va, void (*handler)(void), unsigned char **tramp_out) {
    unsigned char *tr = mmap(NULL, 4096, PROT_READ | PROT_WRITE | PROT_EXEC,
                             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (tr == MAP_FAILED) { logf_("mmap 失败"); return 0; }
    memcpy(tr, (void *)(base + va), 16);
    uint32_t *t = (uint32_t *)(tr + 16);
    t[0] = 0x58000050u;
    t[1] = 0xD61F0200u;
    uint64_t resume = (uint64_t)(base + va + 16);
    memcpy(tr + 24, &resume, 8);
    __builtin___clear_cache((char *)tr, (char *)tr + 32);

    uint32_t *site = (uint32_t *)(base + va);
    if (mprotect((void *)((uintptr_t)site & ~0xfff), 8192,
                 PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
        logf_("mprotect 失败 %#x（跳过）", va);
        munmap(tr, 4096);
        return 0;
    }
    uint64_t hv = (uint64_t)(void *)handler;
    site[0] = 0x58000050u;
    site[1] = 0xD61F0200u;
    memcpy((void *)(base + va + 8), &hv, 8);      // va 不一定是 8 字节对齐，用 memcpy
    __builtin___clear_cache((char *)site, (char *)site + 16);
    *tramp_out = tr;
    logf_("钩子 %#x -> %p", va, site);
    return 1;
}

// 同上，但对任意绝对地址打补丁（用于 libEGL.so / libGLESv2.so 里的导出函数）
static int patch_addr(uintptr_t addr, void (*handler)(void), unsigned char **tramp_out) {
    if (!addr) return 0;
    unsigned char *tr = mmap(NULL, 4096, PROT_READ | PROT_WRITE | PROT_EXEC,
                             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (tr == MAP_FAILED) { logf_("patch_addr: mmap 失败"); return 0; }
    memcpy(tr, (void *)addr, 16);
    uint32_t *t = (uint32_t *)(tr + 16);
    t[0] = 0x58000050u;
    t[1] = 0xD61F0200u;
    uint64_t resume = (uint64_t)(addr + 16);
    memcpy(tr + 24, &resume, 8);
    __builtin___clear_cache((char *)tr, (char *)tr + 32);

    uint32_t *site = (uint32_t *)addr;
    if (mprotect((void *)(addr & ~(uintptr_t)0xfff), 8192,
                 PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
        logf_("patch_addr: mprotect 失败 %p", (void *)addr);
        munmap(tr, 4096);
        return 0;
    }
    uint64_t hv = (uint64_t)(void *)handler;
    site[0] = 0x58000050u;
    site[1] = 0xD61F0200u;
    memcpy((void *)(addr + 8), &hv, 8);
    __builtin___clear_cache((char *)site, (char *)site + 16);
    *tramp_out = tr;
    return 1;
}

// ================================================================
// 以下整段（升级 / 商店 / 英雄上限 / 建造上限 / 关卡解锁 / 阵营 /
// 命令通道 / 存档备份 / 作弊线程）全部属于作弊功能。
// ZF_CHEAT=0 时整段不参与编译 —— 纯翻译版连一个写入游戏内存的
// 符号都不存在，做到「只加中文字形，不碰游戏逻辑」。
// ================================================================
#if ZF_CHEAT
// ---------------------------------------------------------------- 升级功能常量
// 必须放在 ZF_DIAG 之外：这些是正式功能，不是诊断代码。
static int zf_hero_ok(uintptr_t p);        // 定义在后面，这里先声明
static uintptr_t zf_pick_hero(void);
static uintptr_t zf_sel_at(unsigned off);
static void zf_do_up(uintptr_t obj, FILE *o);

// 面板英雄指针所在的全局槽（镜像内偏移）。实测：点谁，这里就是谁。
//   0x543408 / 0x543458 / 0x544330 三个槽同时指向当前选中单位（带 top-byte tag）。
// 这三个值是用 pfind 反查出来的：先 qfind 用面板数字（等级/生命上限/升级门槛）
// 在内存里唯一命中英雄对象，再搜「哪些 8 字节槽等于这个地址」，落在镜像的这几个偏移上。
#define SEL_OFF_A  0x543408u
#define SEL_OFF_B  0x543458u
#define SEL_OFF_C  0x544330u

#define UP_WANT 50             // 一次点击升几级（会撞到等级上限就停在满级）
#define UP_FINAL_TH 200        // 升完后门槛留在这个值

// ---------------------------------------------------------------- 内存探测（实验）
// 目标：在进程内存里定位「英雄对象」。
// 锚点选英雄名：绘制时 DrawText 收到的是 UTF-16，说明名字在内存里就是 UTF-16 字符串。
// 找到名字所在地址后，再反向找「谁指向它」，持有者极可能就是英雄对象。
#if ZF_DIAG
static int u16_encode(const char *utf8, uint16_t *out, int cap) {
    int n = 0;
    const unsigned char *p = (const unsigned char *)utf8;
    while (*p && n < cap) {
        if (p[0] < 0x80) { out[n++] = p[0]; p += 1; }
        else if ((p[0] & 0xe0) == 0xc0) { out[n++] = (uint16_t)(((p[0] & 0x1f) << 6) | (p[1] & 0x3f)); p += 2; }
        else if ((p[0] & 0xf0) == 0xe0) { out[n++] = (uint16_t)(((p[0] & 0x0f) << 12) | ((p[1] & 0x3f) << 6) | (p[2] & 0x3f)); p += 3; }
        else { out[n++] = '?'; p += 1; }
    }
    return n;
}

// 在给定内存区间里找 u16 序列
static uintptr_t memmem16(uintptr_t start, uintptr_t end, const uint16_t *pat, int plen) {
    uintptr_t n = (uintptr_t)plen * 2;
    if (end < start + n) return 0;
    unsigned char *p = (unsigned char *)start;
    unsigned char *last = (unsigned char *)(end - n);
    uint16_t first = pat[0];
    while (p <= last) {
        unsigned char *hit = memchr(p, (unsigned char)(first & 0xff), (size_t)(last - p) + 1);
        if (!hit) return 0;
        if (((uintptr_t)hit & 1) == 0 && memcmp(hit, pat, n) == 0) return (uintptr_t)hit;
        p = hit + 2;
    }
    return 0;
}

static void hexdump_ctx(const char *tag, uintptr_t addr, int before, int after) {
    char b[512]; int p = 0;
    p += snprintf(b + p, sizeof(b) - p, "%s @%p:", tag, (void *)addr);
    for (int i = -before; i < after && p < (int)sizeof(b) - 6; i++)
        p += snprintf(b + p, sizeof(b) - p, " %02x", *(unsigned char *)(addr + i));
    logf_("%s", b);
}

// ---------------------------------------------------------------- 内存工具（诊断）
// 无 root、APK 非 debuggable，adb 无法 attach；但代码本身跑在游戏进程里，
// 所以用一个「命令文件 -> 结果文件」的通道来做交互式探查：
//   /storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files/zhcmd.txt
//   /storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files/zhout.txt
//
// 命令（一行一条，# 开头为注释）：
//   regions                       列出可扫描区间
//   find <v>[,<v>...] [win]       找 32 位整数；要求同一窗口内全部命中
//   find16 <v>[,<v>...] [win]     同上，16 位
//   u16 <文本>                    找 UTF-16LE 文本
//   dump <hexaddr> <len>          十六进制转储（addr 为运行时绝对地址）
//   poke <hexaddr> <v>            写 32 位
//   poke16 <hexaddr> <v>          写 16 位
//   where <hexaddr>               该地址属于哪个区间

#if ZF_DIAG
#include <signal.h>
#include <setjmp.h>
#include <sys/stat.h>

#define ZF_DIR  "/storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files"
#define ZF_CMD  ZF_DIR "/zhcmd.txt"
#define ZF_OUT  ZF_DIR "/zhout.txt"

static sigjmp_buf g_jb;
static volatile int g_guard;

// 升级用的门槛阶梯（诊断期用过的多档试探方案，正式版已改用单次调用）
static const int kUpTh[] = {200, 100, 50, 25, 12, 6, 3};
#define UP_TH_N (int)(sizeof(kUpTh) / sizeof(kUpTh[0]))

static void zf_fault(int sig) {
    if (g_guard) { g_guard = 0; siglongjmp(g_jb, 1); }
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = SIG_DFL;
    sigemptyset(&sa.sa_mask);
    sigaction(sig, &sa, NULL);
    raise(sig);
}

static void zf_guard_install(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = zf_fault;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_NODEFER;
    sigaction(SIGBUS, &sa, NULL);
    sigaction(SIGSEGV, &sa, NULL);
}

typedef struct { uintptr_t a, b; } Reg;
static Reg g_reg[8192];
static Reg g_regA[8192];    // 按起始地址排序的副本，供 zf_inreg 二分
static int g_nreg;

static int zf_regcmp(const void *x, const void *y) {
    const Reg *p = (const Reg *)x, *q = (const Reg *)y;
    if (p->a < q->a) return -1;
    if (p->a > q->a) return 1;
    return 0;
}

#define MAXSNAP 40000
static uintptr_t g_snapA[MAXSNAP];
static int32_t   g_snapV[MAXSNAP];
static int       g_nsnap;

// 扫描线程栈里的一个地址：该区间要整个跳过。
// 否则命令文本、strtol 结果、/proc/self/maps 行缓冲都会被当成命中（固定的假阳性）。
static uintptr_t g_excl_stack;

// 收「全部可读」区间。
// 早期版本只收匿名段，结果把引擎镜像的 .data/.bss 整块漏掉了 —— 游戏的对象池、
// 全局单例都在那儿，英雄结构体因此永远搜不到。文件映射越界读会 SIGBUS，
// 但 zf_find/zf_find64/zf_u16 的 memcpy 都在 sigsetjmp 守卫里，能被安全捕获。
static int zf_regions(void) {
    g_nreg = 0;
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[512];
    while (fgets(line, sizeof(line), f) && g_nreg < 8192) {
        unsigned long a, b; char perm[8] = {0}, path[320] = {0};
        int nf = sscanf(line, "%lx-%lx %7s %*s %*s %*s %319s", &a, &b, perm, path);
        if (nf < 3) continue;
        if (perm[0] != 'r') continue;
        if (b <= a) continue;
        // 早先这里限制 512MB，本意是跳过巨大的空保留区，结果把 Android 的
        // jemalloc 堆整块过滤掉了（它常以 0xb4000079xxxxxxxx 形式出现、保留区能到 2GB）。
        // 英雄对象就分配在那块堆里，于是 find/snap/units 一直在漏 —— 这是长期搜不到
        // 对象指针的真正原因。放宽到 3GB。
        if (b - a > 3072ul * 1024 * 1024) continue;
        // 自身数据段：libzhfont 的 .data/.bss 里有 g_reg/g_snap 等，必须排除
        if (nf >= 4 && path[0] && strstr(path, "libzhfont")) continue;
        // 扫描线程自己的栈
        if (g_excl_stack && (uintptr_t)a <= g_excl_stack && g_excl_stack < (uintptr_t)b) continue;
        g_reg[g_nreg].a = (uintptr_t)a;
        g_reg[g_nreg].b = (uintptr_t)b;
        g_nreg++;
    }
    fclose(f);
    // 按区间大小升序：小的（真实堆、栈）先扫，几百 MB 的空保留区放最后，
    // 免得它们把「命中上限」和输出篇幅吃光。
    for (int i = 1; i < g_nreg; i++) {
        Reg k = g_reg[i];
        int j = i - 1;
        while (j >= 0 && (g_reg[j].b - g_reg[j].a) > (k.b - k.a)) { g_reg[j + 1] = g_reg[j]; j--; }
        g_reg[j + 1] = k;
    }
    // 再建一份「按起始地址排序」的副本，供 zf_inreg 二分查找。
    // 指针扫描要对每个 8 字节槽判一次「这个地址在不在可读区间内」，
    // 线性遍历几千个区间会把扫描拖到不可接受。
    if (g_nreg > 0) {
        memcpy(g_regA, g_reg, sizeof(Reg) * (size_t)g_nreg);
        qsort(g_regA, (size_t)g_nreg, sizeof(Reg), zf_regcmp);
    }
    return g_nreg;
}

static const char *zf_where(uintptr_t addr) {
    static char b[96];
    for (int i = 0; i < g_nreg; i++) {
        if (addr >= g_reg[i].a && addr < g_reg[i].b) {
            snprintf(b, sizeof(b), "reg[%d] %p-%p +%#lx", i, (void *)g_reg[i].a, (void *)g_reg[i].b,
                     (unsigned long)(addr - g_reg[i].a));
            return b;
        }
    }
    return "out-of-region";
}

// 快速判定「地址是否落在某个可读区间内」——二分，供指针扫描高频调用
static int zf_inreg(uintptr_t addr) {
    int lo = 0, hi = g_nreg - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        if (addr < g_regA[mid].a) hi = mid - 1;
        else if (addr >= g_regA[mid].b) lo = mid + 1;
        else return 1;
    }
    return 0;
}

// 指针归一化：ARM64 上部分指针带 top-byte tag（如 0xb40000796bcdf878），
// 最高字节是标签，真实地址是低 7 字节。实测 0x796bcdf878 可读、0xb4... 读不到。
static inline uintptr_t zf_pt(uintptr_t v) {
    return v & 0x00FFFFFFFFFFFFFFull;
}

static int zf_self(uintptr_t lo, uintptr_t hi, unsigned char *buf, size_t n);

// ---------------------------------------------------------------- 指针扫描
// 思路：不顺着任何偏移链找数组，而是反过来 —— 在内存里找「看起来像单位对象指针」
// 的 8 字节值，再用对象自身的结构特征（+0x4c 是个合理等级）反查对象。
// 这比按值扫描（find 12 这种小整数有几万个命中）选择性高两个数量级。
#define MAXPS 16384
static uintptr_t g_ps[MAXPS];
static int g_nps;

static int uptr_cmp(const void *x, const void *y) {
    uintptr_t p = *(const uintptr_t *)x, q = *(const uintptr_t *)y;
    return (p < q) ? -1 : (p > q) ? 1 : 0;
}

// 判定一个值 v 是否是「合法单位对象指针」；命中则把对象地址写入 *out
// 只看 +0x4c（等级）噪声太大 —— 16 这种小整数全内存到处都是。
// 再加一条 +0xd4（疑似最大生命）落在 [hpmin,hpmax]，选择性立刻提高两个数量级。
static int zf_isobj(uintptr_t v, int lvmin, int lvmax, int hpmin, int hpmax, uintptr_t *out) {
    if (v < 0x10000000ull) return 0;
    uintptr_t p = zf_pt(v);
    if (p & 7) return 0;
    if (!zf_inreg(p)) return 0;
    int lv = zf_ld32(p + 0x4c);
    if (lv < lvmin || lv > lvmax) return 0;
    if (hpmin || hpmax) {
        int hp = zf_ld32(p + 0xd4);
        if (hp < hpmin || hp > hpmax) return 0;
    }
    *out = p;
    return 1;
}

static int zf_pscan(FILE *o, int lvmin, int lvmax, int hpmin, int hpmax, int arr_only) {
    const size_t CH = 1u << 20;
    unsigned char *buf = malloc(CH + 16);
    if (!buf) return 0;
    g_nps = 0;
    int nblk = 0, narr = 0;
    for (int r = 0; r < g_nreg && g_nps < MAXPS; r++) {
        uintptr_t a = g_reg[r].a, b = g_reg[r].b;
        for (uintptr_t off = a; off < b; off += CH) {
            size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
            if (zf_self(off, off + want, buf, CH + 16)) continue;
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
            memcpy(buf, (void *)off, want);
            g_guard = 0;
            nblk++;
            int run = 0;
            uintptr_t run_start = 0;
            for (size_t k = 0; k + 8 <= want; k += 8) {
                uintptr_t obj = 0;
                if (zf_isobj(*(uintptr_t *)(buf + k), lvmin, lvmax, hpmin, hpmax, &obj)) {
                    if (run == 0) run_start = off + k;
                    run++;
                    if (g_nps < MAXPS) g_ps[g_nps++] = obj;
                } else {
                    // 连续 >= 4 个槽都指向合法对象 —— 这就是「对象数组」的特征
                    if (run >= 4) {
                        fprintf(o, "ARR %p len=%d\n", (void *)run_start, run);
                        narr++;
                    }
                    run = 0;
                }
            }
            if (run >= 4) {
                fprintf(o, "ARR %p len=%d\n", (void *)run_start, run);
                narr++;
            }
        }
    }
    free(buf);
    // 排序去重
    int raw = g_nps;
    if (g_nps > 1) {
        qsort(g_ps, (size_t)g_nps, sizeof(uintptr_t), uptr_cmp);
        int m = 0;
        for (int i = 0; i < g_nps; i++)
            if (i == 0 || g_ps[i] != g_ps[i - 1]) g_ps[m++] = g_ps[i];
        g_nps = m;
    }
    fprintf(o, "扫描 %d 块，指针槽命中 %d 个，去重后对象 %d 个，连续数组段 %d 个\n",
            nblk, raw, g_nps, narr);
    if (!arr_only) {
        for (int i = 0; i < g_nps && i < 120; i++) {
            uintptr_t p = g_ps[i];
            fprintf(o, "OBJ %p lv=%d hp=%d/%d f20=%d f6c=%d f240=%d f254=%d\n",
                    (void *)p, zf_ld32(p + 0x4c), zf_ld32(p + 0xd4), zf_ld32(p + 0xd8),
                    zf_ld32(p + 0x20), zf_ld32(p + 0x6c), zf_ld32(p + 0x240), zf_ld32(p + 0x254));
        }
    }
    return g_nps;
}

static void zf_hexdump(FILE *o, uintptr_t addr, int len) {
    unsigned char buf[16];
    for (int i = 0; i < len; i += 16) {
        g_guard = 1;
        if (sigsetjmp(g_jb, 1)) { g_guard = 0; fprintf(o, "%p  <不可读>\n", (void *)(addr + i)); return; }
        memcpy(buf, (void *)(addr + i), 16);
        g_guard = 0;
        fprintf(o, "%p ", (void *)(addr + i));
        for (int k = 0; k < 16; k++) fprintf(o, "%02x", buf[k]);
        fprintf(o, "  ");
        for (int k = 0; k < 16; k++) fputc((buf[k] >= 0x20 && buf[k] < 0x7f) ? buf[k] : '.', o);
        fprintf(o, "\n");
    }
}

// ---- 安全读：不可读地址返回 0，不炸进程 -------------------------------
static uintptr_t zf_ld(uintptr_t a) {
    uintptr_t v;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    v = *(uintptr_t *)a;
    g_guard = 0;
    return v;
}

static int zf_ld32(uintptr_t a) {
    int v;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    v = *(int *)a;
    g_guard = 0;
    return v;
}

// 安全写：不可写返回 0，不炸进程
static int zf_wr32(uintptr_t a, int v) {
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    *(int32_t *)a = v;
    g_guard = 0;
    return 1;
}

// 从 /proc/self/maps 找某个 .so 的加载基址（第一个 offset==0 的段起始）
static uintptr_t zf_modbase(const char *name) {
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[512];
    uintptr_t best = 0;
    while (fgets(line, sizeof line, f)) {
        if (!strstr(line, name)) continue;
        unsigned long a = 0, b = 0, off = 0;
        char perm[8] = {0};
        if (sscanf(line, "%lx-%lx %7s %lx", &a, &b, perm, &off) < 4) continue;
        if (off == 0) { best = (uintptr_t)a; break; }
        if (!best) best = (uintptr_t)a;
    }
    fclose(f);
    return best;
}

// 在全部区间里找 32 位值；要求 vals[0..n-1] 全部落在同一个 win 字节窗口内
static int g_finddump;      // >0 时每个命中点顺便转储这么多字节
// 扫描缓冲本身就在堆里，若不排除会「扫到自己刚写进去的数据」，产生固定假命中
static int zf_self(uintptr_t lo, uintptr_t hi, unsigned char *buf, size_t n) {
    uintptr_t bl = (uintptr_t)buf, bh = bl + n;
    return (lo < bh) && (hi > bl);
}

static int zf_find64(FILE *o, uint64_t v, int dump) {
    const size_t CH = 1u << 20;
    unsigned char *buf = malloc(CH + 8);
    if (!buf) return 0;
    int total = 0;
    for (int r = 0; r < g_nreg && total < 200; r++) {
        uintptr_t a = g_reg[r].a, b = g_reg[r].b;
        for (uintptr_t off = a; off < b; off += CH) {
            size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
            if (zf_self(off, off + want, buf, CH + 8)) continue;
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
            memcpy(buf, (void *)off, want);
            g_guard = 0;
            for (size_t k = 0; k + 8 <= want; k += 8) {
                if (*(uint64_t *)(buf + k) != v) continue;
                uintptr_t at = off + k;
                fprintf(o, "HIT64 %p (%s)\n", (void *)at, zf_where(at));
                if (dump > 0) zf_hexdump(o, at > 0x40 ? at - 0x40 : at, dump);
                total++;
                if (total >= 200) break;
            }
        }
    }
    free(buf);
    return total;
}

static int zf_find(FILE *o, const int *vals, int nv, uintptr_t win, int wide) {
    const size_t CH = 1u << 20;
    size_t bufsz = CH + 8 + 2 * win;
    unsigned char *buf = malloc(bufsz);
    if (!buf) return 0;
    int total = 0;
    for (int r = 0; r < g_nreg && total < 300; r++) {
        uintptr_t a = g_reg[r].a, b = g_reg[r].b;
        for (uintptr_t off = a; off < b; off += CH) {
            size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
            // 关键：把「窗口」一起拷进缓冲，之后所有判断都只在缓冲里做。
            // 直接解引用活内存会撞上游戏并发 munmap，触发 SIGSEGV 把进程带走。
            uintptr_t lo = (off > a + win) ? off - win : a;
            uintptr_t hi = off + want + win;
            if (hi > b) hi = b;
            size_t span = (size_t)(hi - lo);
            if (zf_self(lo, hi, buf, bufsz)) continue;
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
            memcpy(buf, (void *)lo, span);
            g_guard = 0;
            int step = wide ? 4 : 2;
            for (size_t k = 0; k + (size_t)step <= want; k += step) {
                size_t idx = (size_t)(off - lo) + k;
                if (wide) { if (*(int32_t *)(buf + idx) != vals[0]) continue; }
                else { if (*(int16_t *)(buf + idx) != (int16_t)vals[0]) continue; }
                uintptr_t at = off + k;
                int all = 1;
                for (int q = 1; q < nv && all; q++) {
                    // 只在 [at-win, at+win] 里找，别把整块 1MB 当窗口
                    size_t wlo = (idx > win) ? idx - win : 0;
                    size_t whi = idx + win;
                    if (whi > span) whi = span;
                    int hit = 0;
                    for (size_t t = wlo; t + (size_t)step <= whi; t += step) {
                        if (t == idx) continue;     // 别把锚点自己当成「另一个值」
                        if (wide) { if (*(int32_t *)(buf + t) == vals[q]) { hit = 1; break; } }
                        else { if (*(int16_t *)(buf + t) == (int16_t)vals[q]) { hit = 1; break; } }
                    }
                    if (!hit) all = 0;
                }
                if (!all) continue;
                fprintf(o, "HIT %p (%s) win=%#lx\n", (void *)at, zf_where(at), (unsigned long)win);
                if (g_finddump > 0) {
                    uintptr_t d0 = (at > 0x40) ? at - 0x40 : at;
                    zf_hexdump(o, d0, g_finddump);
                }
                total++;
                if (total >= 300) break;
            }
        }
    }
    free(buf);
    return total;
}

// 以「已知锚点对」反推对象基址，再在同结构里找目标值。
// 已知：单位对象 +0xd4 = 当前生命，+0xd8 = 最大生命（0xe92c0 附近 str w2,[x0,#0xd4]/#0xd8 证实）。
// 所以扫到 (hp,hpmax) 相邻对，就能算出 base = at - 0xd4，再在 base+[0,span) 里找经验值和升级上限。
// 比盲目 poke 二分靠谱得多：一次就把「哪个偏移是经验」直接打出来。
static int zf_hscan(FILE *o, int hp, int hpmax, int v1, int v2, uintptr_t span) {
    const size_t CH = 1u << 20;
    const uintptr_t ANCHOR = 0xd4;
    size_t bufsz = CH + 8 + 2 * span + ANCHOR;
    unsigned char *buf = malloc(bufsz);
    if (!buf) return 0;
    int cand = 0, good = 0;
    for (int r = 0; r < g_nreg && good < 40; r++) {
        uintptr_t a = g_reg[r].a, b = g_reg[r].b;
        for (uintptr_t off = a; off < b; off += CH) {
            size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
            uintptr_t lo = (off > span + ANCHOR) ? off - span - ANCHOR : a;
            uintptr_t hi = off + want + span;
            if (hi > b) hi = b;
            size_t s = (size_t)(hi - lo);
            if (s > bufsz) continue;
            if (zf_self(lo, hi, buf, bufsz)) continue;
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
            memcpy(buf, (void *)lo, s);
            g_guard = 0;
            for (size_t k = 0; k + 8 <= want; k += 4) {
                size_t idx = (size_t)(off - lo) + k;
                // 生命值每帧都在回血，扫描时早就不是截图那个数了 —— 所以锚点给容差。
                // 最大生命（+0xd8）是稳定的，用它做硬约束。
                int32_t cur = *(int32_t *)(buf + idx);
                if (cur < hp - 8 || cur > hp + 8) continue;
                if (*(int32_t *)(buf + idx + 4) != hpmax) continue;
                if (idx < ANCHOR) continue;
                size_t ib = idx - ANCHOR;
                if (ib + span > s) continue;
                cand++;
                uintptr_t base = off + k - ANCHOR;
                int o1[8], n1 = 0, o2[8], n2 = 0;
                for (uintptr_t t = 0; t + 4 <= span; t += 4) {
                    int32_t v = *(int32_t *)(buf + ib + t);
                    if (v >= v1 - 16 && v <= v1 + 16 && n1 < 8) o1[n1++] = (int)t;
                    if (v2 >= 0 && v == v2 && n2 < 8) o2[n2++] = (int)t;
                }
                if (!n1 || (v2 >= 0 && !n2)) {
                    fprintf(o, "CAND %p (%s)", (void *)base, zf_where(base));
                    if (n1) { fprintf(o, "  ~%d@", v1); for (int i = 0; i < n1; i++) fprintf(o, "+%#x=%d ", (unsigned)o1[i], *(int32_t *)(buf + ib + o1[i])); }
                    if (n2) { fprintf(o, "  %d@", v2); for (int i = 0; i < n2; i++) fprintf(o, "+%#x ", (unsigned)o2[i]); }
                    fprintf(o, "\n");
                    continue;
                }
                good++;
                fprintf(o, "BASE %p (%s)", (void *)base, zf_where(base));
                fprintf(o, "  ~%d@", v1);
                for (int i = 0; i < n1; i++) fprintf(o, "+%#x=%d ", (unsigned)o1[i], *(int32_t *)(buf + ib + o1[i]));
                fprintf(o, " %d@", v2);
                for (int i = 0; i < n2; i++) fprintf(o, "+%#x ", (unsigned)o2[i]);
                fprintf(o, "\n");
                if (good >= 40) break;
            }
        }
    }
    fprintf(o, "候选 %d，同时含 %d 和 %d 的 %d 个\n", cand, v1, v2, good);
    free(buf);
    return good;
}

// near <v> <lo> <hi> [win]：找所有等于 v 的 int32，且它 ±win 内存在落在 [lo,hi] 的 int32。
// 用途：经验上限 1000 是稳定常量，经验值却每帧都在涨（截图到命令送达之间就漂了十几点）。
// 用 1000 当锚、经验区间当约束，一次就能把「经验字段」和「上限字段」一起打出来。
static int zf_near(FILE *o, int32_t v, int32_t lo, int32_t hi, uintptr_t win) {
    const size_t CH = 1u << 20;
    size_t bufsz = CH + 8 + 2 * win;
    unsigned char *buf = malloc(bufsz);
    if (!buf) return 0;
    int total = 0;
    for (int r = 0; r < g_nreg && total < 200; r++) {
        uintptr_t a = g_reg[r].a, b = g_reg[r].b;
        for (uintptr_t off = a; off < b; off += CH) {
            size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
            uintptr_t l0 = (off > win) ? off - win : a;
            uintptr_t h0 = off + want + win;
            if (h0 > b) h0 = b;
            size_t s = (size_t)(h0 - l0);
            if (s > bufsz) continue;
            if (zf_self(l0, h0, buf, bufsz)) continue;
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
            memcpy(buf, (void *)l0, s);
            g_guard = 0;
            for (size_t k = 0; k + 4 <= want; k += 4) {
                size_t idx = (size_t)(off - l0) + k;
                if (*(int32_t *)(buf + idx) != v) continue;
                size_t wlo = (idx > win) ? idx - win : 0;
                size_t whi = idx + win + 4;
                if (whi > s) whi = s;
                int found = 0;
                for (size_t t = wlo; t + 4 <= whi; t += 4) {
                    if (t == idx) continue;
                    int32_t q = *(int32_t *)(buf + t);
                    if (q < lo || q > hi) continue;
                    fprintf(o, "NEAR %p  %d @%+ld\n", (void *)(off + k), q, (long)(t - idx));
                    found = 1;
                }
                if (found) total++;
                if (total >= 200) break;
            }
        }
    }
    free(buf);
    return total;
}

static int zf_u16(FILE *o, const char *txt, uintptr_t win) {
    uint16_t pat[128];
    int pl = u16_encode(txt, pat, 128);
    if (pl < 1) return 0;
    size_t n = (size_t)pl * 2;
    const size_t CH = 1u << 20;
    unsigned char *buf = malloc(CH + 8);
    if (!buf) return 0;
    int total = 0;
    for (int r = 0; r < g_nreg && total < 120; r++) {
        uintptr_t a = g_reg[r].a, b = g_reg[r].b;
        for (uintptr_t off = a; off < b; off += CH) {
            size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
            if (zf_self(off, off + want, buf, CH + 8)) continue;
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
            memcpy(buf, (void *)off, want);
            g_guard = 0;
            if (want < n) break;
            for (size_t k = 0; k + n <= want; k += 2) {
                if (buf[k] != (unsigned char)(pat[0] & 0xff)) continue;
                if (memcmp(buf + k, pat, n) != 0) continue;
                uintptr_t at = off + k;
                fprintf(o, "STR %p (%s)\n", (void *)at, zf_where(at));
                // 前后各 win 字节的转储，方便看结构
                uintptr_t lo = (at > win) ? at - win : a;
                zf_hexdump(o, lo, (int)(win * 2 + n));
                total++;
                if (total >= 120) break;
            }
        }
    }
    free(buf);
    return total;
}

static void dump_tree(const char *dir, const char *out, int depth);   // 定义在下面

static void zf_run(FILE *o) {
    FILE *f = fopen(ZF_CMD, "r");
    if (!f) { fprintf(o, "打不开命令文件\n"); return; }
    char line[512];
    zf_guard_install();
    g_excl_stack = (uintptr_t)&f;          // 本帧所在栈区间整个跳过
    int nr = zf_regions();
    fprintf(o, "=== 区间 %d 个 ===\n", nr);
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        size_t L = strlen(p);
        while (L && (p[L - 1] == '\n' || p[L - 1] == '\r' || p[L - 1] == ' ')) p[--L] = 0;
        if (!L || *p == '#') continue;
        fprintf(o, "\n>>> %s\n", p);

        char cmd[32] = {0};
        sscanf(p, "%31s", cmd);
        char *arg = p + strlen(cmd);
        while (*arg == ' ') arg++;

        if (!strcmp(cmd, "regions")) {
            for (int i = 0; i < nr; i++)
                fprintf(o, "  [%d] %p-%p  %#lx\n", i, (void *)g_reg[i].a, (void *)g_reg[i].b,
                        (unsigned long)(g_reg[i].b - g_reg[i].a));
        } else if (!strcmp(cmd, "find") || !strcmp(cmd, "find16")) {
            int vals[16]; int nv = 0;
            char *s = arg;
            while (*s && nv < 16) {
                vals[nv++] = (int)strtol(s, &s, 10);
                if (*s == ',') s++;
                else break;
            }
            uintptr_t win = 0x400;
            if (*s) win = (uintptr_t)strtoul(s, &s, 0);
            g_finddump = 0;
            if (*s) g_finddump = (int)strtol(s, NULL, 0);
            int wide = !strcmp(cmd, "find");
            int n = zf_find(o, vals, nv, win, wide);
            fprintf(o, "命中 %d 处\n", n);
        } else if (!strcmp(cmd, "hscan")) {
            // hscan <hp> <hpmax> <v1> <v2> [span]
            // 用 +0xd4/+0xd8 的生命对反推单位对象基址，再打印 v1/v2 在结构内的偏移
            char *s = arg;
            int hp = (int)strtol(s, &s, 0);
            int hm = (int)strtol(s, &s, 0);
            int v1 = (int)strtol(s, &s, 0);
            int v2 = (int)strtol(s, &s, 0);
            uintptr_t sp = 0x400;
            if (*s) sp = (uintptr_t)strtoul(s, &s, 0);
            if (sp < 0x200) sp = 0x200;
            if (sp > 0x2000) sp = 0x2000;
            zf_hscan(o, hp, hm, v1, v2, sp);
        } else if (!strcmp(cmd, "near")) {
            // near <v> <lo> <hi> [win]
            char *s = arg;
            int32_t v = (int32_t)strtol(s, &s, 0);
            int32_t lo = (int32_t)strtol(s, &s, 0);
            int32_t hi = (int32_t)strtol(s, &s, 0);
            uintptr_t win = 0x40;
            if (*s) win = (uintptr_t)strtoul(s, &s, 0);
            if (win > 0x400) win = 0x400;
            int n = zf_near(o, v, lo, hi, win);
            fprintf(o, "命中 %d 处\n", n);
        } else if (!strcmp(cmd, "find64")) {
            char *s = arg;
            uint64_t v = (uint64_t)strtoull(s, &s, 16);
            int dump = 0;
            if (*s) dump = (int)strtol(s, NULL, 0);
            int n = zf_find64(o, v, dump);
            fprintf(o, "命中 %d 处\n", n);
        } else if (!strcmp(cmd, "u16")) {
            uintptr_t win = 0x100;
            char *sp = strchr(arg, ' ');
            if (sp) { *sp = 0; win = (uintptr_t)strtoul(sp + 1, NULL, 0); }
            int n = zf_u16(o, arg, win);
            fprintf(o, "命中 %d 处\n", n);
        } else if (!strcmp(cmd, "dump")) {
            char *s = arg;
            uintptr_t at = (uintptr_t)strtoul(s, &s, 16);
            int len = (int)strtol(s, NULL, 0);
            if (len <= 0 || len > 65536) len = 256;
            fprintf(o, "%s\n", zf_where(at));
            zf_hexdump(o, at, len);
        } else if (!strcmp(cmd, "copysave")) {
            // 把游戏私有目录整树搬到外部存储，供离线分析
            const char *out = ZF_DIR "/_dump";
            mkdir(out, 0777);
            dump_tree("/data/data/com.herocraft.game.majesty_ne", out, 2);
            dump_tree("/data/user/0/com.herocraft.game.majesty_ne", out, 2);
            fprintf(o, "存档已复制到 %s\n", out);
        } else if (!strcmp(cmd, "wait")) {
            int sec = (int)strtol(arg, NULL, 0);
            if (sec < 0) sec = 0;
            if (sec > 120) sec = 120;
            fprintf(o, "等待 %d 秒\n", sec);
            fflush(o);
            sleep(sec);
        } else if (!strcmp(cmd, "where")) {
            uintptr_t at = (uintptr_t)strtoul(arg, NULL, 16);
            fprintf(o, "%s\n", zf_where(at));
        } else if (!strcmp(cmd, "snap") || !strcmp(cmd, "snapr")) {
            // 快照：把全部持有该值的位置记下来，供 diffchg 之后对比。
            // snapr <lo> <hi>：按区间快照。经验/生命这种每帧都在涨的值，
            // 从截图到命令送达之间早就漂了十几点，必须给容差才抓得住。
            char *s = arg;
            int32_t v = (int32_t)strtol(s, &s, 10);
            int32_t vhi = v;
            int wide = 1;
            if (!strcmp(cmd, "snapr")) {
                vhi = (int32_t)strtol(s, &s, 10);
                if (vhi < v) { int32_t t = v; v = vhi; vhi = t; }
            } else if (*s) { while (*s == ' ') s++; if (*s) wide = (int)strtol(s, NULL, 0); }
            g_nsnap = 0;
            const size_t CH = 1u << 20;
            unsigned char *buf = malloc(CH + 8);
            if (buf) {
                for (int r = 0; r < g_nreg && g_nsnap < MAXSNAP; r++) {
                    uintptr_t a = g_reg[r].a, b = g_reg[r].b;
                    for (uintptr_t off = a; off < b; off += CH) {
                        size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
                        if (zf_self(off, off + want, buf, CH + 8)) continue;
                        g_guard = 1;
                        if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
                        memcpy(buf, (void *)off, want);
                        g_guard = 0;
                        int step = wide ? 4 : 2;
                        for (size_t k = 0; k + (size_t)step <= want && g_nsnap < MAXSNAP; k += step) {
                            int32_t got = wide ? *(int32_t *)(buf + k) : (int32_t)*(int16_t *)(buf + k);
                            if (got < v || got > vhi) continue;
                            g_snapA[g_nsnap] = off + k;
                            g_snapV[g_nsnap] = got;
                            g_nsnap++;
                        }
                    }
                }
                free(buf);
            }
            if (vhi == v) fprintf(o, "快照 %d 处（值 %d，%d 位）\n", g_nsnap, v, wide ? 32 : 16);
            else fprintf(o, "快照 %d 处（区间 %d..%d）\n", g_nsnap, v, vhi);
        } else if (!strcmp(cmd, "diffchg")) {
            // 把快照里「值已经变了」的位置列出来 —— 正在战斗的英雄，生命/经验就在这些位置里
            // diffchg [lo [hi]]：只要新值落在 [lo,hi] 的
            int32_t lo = -0x7fffffff, hi = 0x7fffffff;
            char *s = arg;
            if (*s) {
                lo = (int32_t)strtol(s, &s, 10);
                hi = lo;
                if (*s) hi = (int32_t)strtol(s, NULL, 10);
            }
            int shown = 0;
            for (int i = 0; i < g_nsnap; i++) {
                int32_t now;
                g_guard = 1;
                if (sigsetjmp(g_jb, 1)) { g_guard = 0; continue; }
                now = *(int32_t *)g_snapA[i];
                g_guard = 0;
                if (now == g_snapV[i]) continue;
                if (now < lo || now > hi) continue;
                fprintf(o, "CHG %p  %d -> %d\n", (void *)g_snapA[i], g_snapV[i], now);
                shown++;
                if (shown >= 400) break;
            }
            fprintf(o, "变化 %d 处（快照共 %d）\n", shown, g_nsnap);
        } else if (!strcmp(cmd, "heroes")) {
            // 0x1db3c 钩子抓到的单位对象（x0）。arg 给长度，默认 0x180
            int lim = (int)strtol(arg, NULL, 0);
            if (lim <= 0 || lim > 0x1000) lim = 0x180;
            fprintf(o, "已抓 %d 个单位对象\n", g_nho);
            for (int i = 0; i < g_nho; i++) {
                fprintf(o, "\n--- HO[%d] @%p ---\n", i, (void *)g_ho[i]);
                zf_hexdump(o, g_ho[i], lim);
            }
        } else if (!strcmp(cmd, "setlv")) {
            // setlv <对象地址(hex)> <等级>：直接改 +0x4c
            char *s = arg;
            uintptr_t p = (uintptr_t)strtoul(s, &s, 16);
            int lv = (int)strtol(s, &s, 0);
            int old = zf_ld32(p + 0x4c);
            int r = zf_wr32(p + 0x4c, lv);
            fprintf(o, "写 %p+0x4c: %d -> %d  %s\n", (void *)p, old, lv, r ? "成功" : "失败");
            fprintf(o, "回读 +0x4c=%d +0xd4=%d +0xd8=%d\n",
                    zf_ld32(p + 0x4c), zf_ld32(p + 0xd4), zf_ld32(p + 0xd8));
        } else if (!strcmp(cmd, "ulist")) {
            // 0x1057b0 钩子抓到的 x0
            fprintf(o, "钩子 %u 次，不同值 %d 个\n", g_u_calls, g_nu);
            for (int i = 0; i < g_nu && i < 24; i++) {
                uintptr_t p = g_up[i];
                fprintf(o, "U[%d] %#lx  cnt=%d", i, (unsigned long)p, g_ulv[i]);
                if (!(p & 7) && p > 0x1000) {
                    fprintf(o, "  [+0x00]=%d [+0x4c]=%d [+0xd4]=%d [+0xd8]=%d",
                            zf_ld32(p), zf_ld32(p + 0x4c), zf_ld32(p + 0xd4), zf_ld32(p + 0xd8));
                }
                fprintf(o, "\n");
            }
        } else if (!strcmp(cmd, "ratios")) {
            fprintf(o, "累计 %d 条\n", g_rt_total);
            int start = (g_rt_total <= MAXRT) ? 0 : g_rt_i;
            int cnt = g_rt_total < MAXRT ? g_rt_total : MAXRT;
            for (int j = 0; j < cnt; j++) {
                int k = (start + j) % MAXRT;
                fprintf(o, "c=%#lx [%s]\n",
                        (unsigned long)(g_rt_c[k] - (uintptr_t)g_img), g_rt_t[k]);
            }
        } else if (!strcmp(cmd, "drawn")) {
            fprintf(o, "累计 %d 条，环内 %d 条，钩子调用 %u 次，trace=%d\n",
                    g_dr_total, g_dr_total < MAXDR ? g_dr_total : MAXDR,
                    g_draw_calls, g_traceparen);
            int start = (g_dr_total <= MAXDR) ? 0 : g_dr_i;
            int cnt = g_dr_total < MAXDR ? g_dr_total : MAXDR;
            for (int j = 0; j < cnt; j++) {
                int k = (start + j) % MAXDR;
                char bb[128]; int pp = 0;
                for (int i = 0; i < g_dr_len[k]; i++) {
                    uint16_t c = g_dr_t[k][i];
                    if (c >= 0x20 && c < 0x7f) bb[pp++] = (char)c;
                    else pp += snprintf(bb + pp, sizeof(bb) - pp, "\\u%x", c);
                }
                bb[pp] = 0;
                fprintf(o, "c=%#lx n=%d [%s]\n",
                        (unsigned long)(g_dr_c[k] - (uintptr_t)g_img), g_dr_n[k], bb);
            }
        } else if (!strcmp(cmd, "trace")) {
            g_traceparen = (int)strtol(arg, NULL, 0);
            fprintf(o, "含括号文本追踪 = %d\n", g_traceparen);
        } else if (!strcmp(cmd, "diag")) {
            uintptr_t g = (uintptr_t)g_img + 0x542ce0;
            fprintf(o, "img = %p   state = %p\n", (void *)g_img, (void *)g);
            fprintf(o, "guard[768] = %d   770 = %p   780 = %p   788 = %d\n",
                    zf_ld32(g + 0x768) & 0xff, (void *)zf_ld(g + 0x770),
                    (void *)zf_ld(g + 0x780), zf_ld32(g + 0x788));
            fprintf(o, "已抓单位对象 %d 个\n", g_nho);
            zf_hexdump(o, g + 0x760, 0x40);
        } else if (!strcmp(cmd, "sl")) {
            zf_scan_levels(o, 0);
        } else if (!strcmp(cmd, "ulk")) {
            // ulk <hex地址> [长度]  把从该地址开始的 n 个 int32 全写成 1
            uintptr_t at = (uintptr_t)strtoull(arg, NULL, 16);
            int n = 17;
            const char *sp = arg;
            while (*sp && *sp != ' ') sp++;
            while (*sp == ' ') sp++;
            if (*sp) n = (int)strtol(sp, NULL, 10);
            zf_unlock_levels(o, at, n);
        } else if (!strcmp(cmd, "cst")) {
            // 作弊状态总览：数组、价格、城堡等级、金币、各项上限
            uintptr_t b = (uintptr_t)g_img;
            fprintf(o, "base = %p\n", (void *)b);
            uintptr_t s = b + CHT_SING_VA;
            int inited = zf_ld8(s + 0x10);
            uintptr_t arr = inited ? zf_ld(s + 8) : 0;
            fprintf(o, "单例=%p 已初始化=%d 数组=%p\n", (void *)s, inited, (void *)arr);
            if (arr) {
                char hx[32];
                int p = 0;
                for (int i = 0; i < CHT_N && p < 24; i++)
                    p += snprintf(hx + p, sizeof(hx) - p, "%d", zf_ld8(arr + i) ? 1 : 0);
                fprintf(o, "arr = %s\n", hx);
                for (int i = 0; i < CHT_N; i++)
                    fprintf(o, "  [%2d] on=%d price=%d\n", i, zf_ld8(arr + i) ? 1 : 0,
                            zf_ld32(b + CHT_COST_VA + i * 4));
            }
            uintptr_t cp = zf_ld(b + 0x53c030u);
            uintptr_t castle = cp ? zf_ld(cp) : 0;
            fprintf(o, "城堡=%p 等级=%d 类型=%d 血上限=%d 血=%d\n", (void *)castle,
                    castle ? zf_ld32(castle + 0x4c) : -1,
                    castle ? zf_ld32(castle + 0x40) : -1,
                    castle ? zf_ld32(castle + 0xd8) : -1,
                    castle ? zf_ld32(castle + 0xd4) : -1);
            uintptr_t gp = zf_ld(b + 0x53c040u);
            fprintf(o, "金币槽=%p 金币=%d\n", (void *)gp, gp ? zf_ld32(gp) : -1);
            uintptr_t hm = zf_ld(b + HERO_MAX_VA);
            fprintf(o, "英雄上限槽=%p 上限=%d\n", (void *)hm, hm ? zf_ld32(hm) : -1);
            uintptr_t bm = zf_ld(b + BLD_MAX_VA);
            fprintf(o, "建筑上限槽=%p 上限=%d\n", (void *)bm, bm ? zf_ld32(bm) : -1);
        } else if (!strcmp(cmd, "click")) {
            // click <x> <y>：注入一次点击。不写内存，直接伪造引擎的查询结果，
            // 因为状态块每帧都被 s3ePointerUpdate 重算覆盖。
            char *s = arg;
            int x = (int)strtol(s, &s, 0);
            int y = (int)strtol(s, &s, 0);
            if (!g_gts_done) install_gts_hook();
            if (!g_gts_done) fprintf(o, "TouchState 钩子没装上，无法注入\n");
            else {
                unsigned c0 = g_gts_calls;
                fprintf(o, "注入点击 (%d,%d)\n", x, y);
                g_ovr_x = x; g_ovr_y = y;
                g_ovr_mode = 1; usleep(120 * 1000);
                g_ovr_mode = 2; usleep(120 * 1000);
                g_ovr_mode = 0;
                fprintf(o, "完成：覆盖 %u 次，期间查询 %u 次\n",
                        g_ovr_calls, g_gts_calls - c0);
            }
        } else if (!strcmp(cmd, "s3e")) {
            // Marmalade 平台层 libs3e_android.so：
            //   s3ePointerUpdate 开头 mov w0,#0x10; bl s3eDeviceGetInt
            //   实际是 tst w0, *(0x16f178) —— bit4 没置就直接返回，指针状态永不更新。
            // 这里读出来看看，顺便可以强制置位。
            uintptr_t b = zf_modbase("libs3e_android.so");
            fprintf(o, "libs3e_android base = %p\n", (void *)b);
            if (!b) { fprintf(o, "没找到模块\n"); }
            else {
                uintptr_t p = b + 0x16f178;
                int v = zf_ld32(p);
                fprintf(o, "flags @%#lx = %#x  bit4=%d\n", (unsigned long)p, v, (v >> 4) & 1);
                fprintf(o, "PointerUpdate 调用 %u 次  钩子=%s\n",
                        g_pu_calls, g_pu_done ? "on" : "off");
                fprintf(o, "PointerGetState 调用 %u 次  lastBtn=%d 钩子=%s\n",
                        g_gs_calls, g_gs_lastbtn, g_gs_done ? "on" : "off");
                fprintf(o, "PointerGetTouchState 调用 %u 次  lastIdx=%d 钩子=%s\n",
                        g_gts_calls, g_gts_lastidx, g_gts_done ? "on" : "off");
                if (!g_pu_done) install_pu_hook();
                if (!g_gs_done) install_gs_hook();
                if (!g_gts_done) install_gts_hook();
                // 状态数组 *(0x174af0 + button)，0..5 分别是左/右/中/back/forward/...
                fprintf(o, "状态数组 @%#lx:", (unsigned long)(b + 0x174af0));
                {
                    int wa = zf_ld32(b + 0x174af0);
                    int wb = zf_ld32(b + 0x174af4);
                    for (int i = 0; i < 4; i++) fprintf(o, " %02x", (unsigned)((wa >> (8 * i)) & 0xff));
                    for (int i = 0; i < 4; i++) fprintf(o, " %02x", (unsigned)((wb >> (8 * i)) & 0xff));
                }
                fprintf(o, "\n");
                if (arg && *arg && (*arg == '1' || *arg == 's')) {
                    g_guard = 1;
                    if (sigsetjmp(g_jb, 1)) { g_guard = 0; fprintf(o, "写入失败\n"); }
                    else {
                        *(int *)p = v | 0x10;
                        g_guard = 0;
                        fprintf(o, "已置 bit4 -> %#x\n", zf_ld32(p));
                    }
                }
            }
        } else if (!strcmp(cmd, "maps")) {
            // 打印高地址（0xb4 堆等）的 maps 行，用来确认 zf_regions 到底漏了什么
            FILE *f = fopen("/proc/self/maps", "r");
            char line[512];
            int n = 0, tot = 0;
            while (f && fgets(line, sizeof line, f)) {
                unsigned long a = 0, b = 0;
                if (sscanf(line, "%lx-%lx", &a, &b) != 2) continue;
                tot++;
                if (a < 0x1000000000000ul) continue;
                fprintf(o, "%s", line);
                if (++n >= 60) break;
            }
            if (f) fclose(f);
            fprintf(o, "高地址 %d 行 / maps 共 %d 行\n", n, tot);
        } else if (!strcmp(cmd, "pscan")) {
            // pscan [arr] [lvmin lvmax]
            //   默认列出所有「+0x4c 落在 [lvmin,lvmax] 的合法对象指针」候选
            //   arr  只输出「连续 >=4 个槽都指向合法对象」的数组段
            int lvmin = 1, lvmax = 50, hpmin = 0, hpmax = 0, arr_only = 0;
            char *s = arg;
            while (*s == ' ') s++;
            if (!strncmp(s, "arr", 3)) { arr_only = 1; s += 3; }
            while (*s == ' ') s++;
            if (*s) {
                lvmin = (int)strtol(s, &s, 0);
                lvmax = (int)strtol(s, &s, 0);
                if (lvmax < lvmin) { int t = lvmin; lvmin = lvmax; lvmax = t; }
            }
            while (*s == ' ') s++;
            if (*s) {
                hpmin = (int)strtol(s, &s, 0);
                hpmax = (int)strtol(s, &s, 0);
                if (hpmax < hpmin) { int t = hpmin; hpmin = hpmax; hpmax = t; }
            }
            zf_pscan(o, lvmin, lvmax, hpmin, hpmax, arr_only);
        } else if (!strcmp(cmd, "hfind")) {
            // 扫描所有「像英雄」的对象：+0x4c 等级 / +0xd4 当前生命 / +0xd8 生命上限 /
            // +0x28c 升级门槛，四者同时合法才算命中（比 pscan 严得多）。
            const size_t CH = 1u << 20;
            unsigned char *buf = malloc(CH + 16);
            int nblk = 0, found = 0;
            for (int r = 0; r < g_nreg; r++) {
                uintptr_t a = g_reg[r].a, b = g_reg[r].b;
                for (uintptr_t off = a; off < b; off += CH) {
                    size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
                    if (zf_self(off, off + want, buf, CH + 16)) continue;
                    g_guard = 1;
                    if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
                    memcpy(buf, (void *)off, want);
                    g_guard = 0;
                    nblk++;
                    for (size_t k = 0; k + 8 <= want; k += 8) {
                        uintptr_t v = *(uintptr_t *)(buf + k);
                        if (v < 0x10000000ull) continue;
                        uintptr_t p = v & 0x00FFFFFFFFFFFFFFull;
                        if (p & 7) continue;
                        if (!zf_inreg(p) || !zf_inreg(p + 0x28c)) continue;
                        if (!zf_hero_ok(p)) continue;
                        found++;
                        if (found <= 200)
                            fprintf(o, "HERO %p lv=%d hp=%d/%d 门槛=%d f0=%#lx f20=%d f6c=%d slot=%p\n",
                                    (void *)p, zf_ld32(p + 0x4c), zf_ld32(p + 0xd4),
                                    zf_ld32(p + 0xd8), zf_ld32(p + 0x28c),
                                    (unsigned long)zf_ld(p), zf_ld32(p + 0x20),
                                    zf_ld32(p + 0x6c), (void *)(off + k));
                    }
                }
            }
            free(buf);
            fprintf(o, "扫描 %d 块，英雄候选 %d 个\n", nblk, found);
        } else if (!strcmp(cmd, "qfind")) {
            // qfind <lv> <hp> <hpmax> <门槛>：原始内存四字段特征匹配（0 = 通配）。
            // 不要求对象被指针槽引用 —— 面板上读到的数字直接拿来当指纹。
            char *s = arg;
            int w0 = (int)strtol(s, &s, 0);
            int w1 = (int)strtol(s, &s, 0);
            int w2 = (int)strtol(s, &s, 0);
            int w3 = (int)strtol(s, &s, 0);
            fprintf(o, "指纹 lv=%d hp=%d max=%d 门槛=%d\n", w0, w1, w2, w3);
            const size_t CH = 1u << 20;
            unsigned char *buf = malloc(CH + 16);
            int nblk = 0, found = 0;
            for (int r = 0; r < g_nreg; r++) {
                uintptr_t a = g_reg[r].a, b = g_reg[r].b;
                for (uintptr_t off = a; off < b; off += CH) {
                    size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
                    if (want < 0x2a0) continue;
                    if (zf_self(off, off + want, buf, CH + 16)) continue;
                    g_guard = 1;
                    if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
                    memcpy(buf, (void *)off, want);
                    g_guard = 0;
                    nblk++;
                    for (size_t k = 0; k + 0x2a0 <= want; k += 8) {
                        int32_t *q = (int32_t *)(buf + k);
                        if (w0 && q[0x4c / 4] != w0) continue;
                        if (w1 && q[0xd4 / 4] != w1) continue;
                        if (w2 && q[0xd8 / 4] != w2) continue;
                        if (w3 && q[0x28c / 4] != w3) continue;
                        found++;
                        if (found <= 40)
                            fprintf(o, "QF %p f0=%#lx f20=%d f6c=%d\n",
                                    (void *)(off + k), (unsigned long)zf_ld(off + k),
                                    q[0x20 / 4], q[0x6c / 4]);
                    }
                }
            }
            free(buf);
            fprintf(o, "扫描 %d 块，命中 %d 个\n", nblk, found);
        } else if (!strcmp(cmd, "pfind")) {
            // pfind <hex64>：找 8 字节槽等于该值的所有位置（自动兼容 top-byte tag 0xb4）
            uintptr_t want = (uintptr_t)strtoull(arg, NULL, 16);
            uintptr_t wt = want | 0xb400000000000000ull;
            fprintf(o, "pfind %#lx (tag %#lx)\n", (unsigned long)want, (unsigned long)wt);
            const size_t CH = 1u << 20;
            unsigned char *buf = malloc(CH + 16);
            int nblk = 0, found = 0;
            for (int r = 0; r < g_nreg; r++) {
                uintptr_t a = g_reg[r].a, b = g_reg[r].b;
                for (uintptr_t off = a; off < b; off += CH) {
                    size_t want_n = (size_t)((b - off) < CH ? (b - off) : CH);
                    if (zf_self(off, off + want_n, buf, CH + 16)) continue;
                    g_guard = 1;
                    if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
                    memcpy(buf, (void *)off, want_n);
                    g_guard = 0;
                    nblk++;
                    for (size_t k = 0; k + 8 <= want_n; k += 8) {
                        uintptr_t v = *(uintptr_t *)(buf + k);
                        if (v != want && v != wt) continue;
                        found++;
                        if (found <= 60)
                            fprintf(o, "PSLOT %p%s  %s\n", (void *)(off + k),
                                    v == wt ? " (tag)" : "", zf_where(off + k));
                    }
                }
            }
            free(buf);
            fprintf(o, "扫描 %d 块，指针槽 %d 个\n", nblk, found);
        } else if (!strcmp(cmd, "hq")) {
            // hq：结构化扫描「英雄对象」。
            //   原始内存每 8 字节当一次对象基址，四字段全合法 + 首 8 字节是有效指针才要。
            const size_t CH = 1u << 20;
            unsigned char *buf = malloc(CH + 16);
            int nblk = 0, found = 0;
            for (int r = 0; r < g_nreg; r++) {
                uintptr_t a = g_reg[r].a, b = g_reg[r].b;
                for (uintptr_t off = a; off < b; off += CH) {
                    size_t want = (size_t)((b - off) < CH ? (b - off) : CH);
                    if (want < 0x2a0) continue;
                    if (zf_self(off, off + want, buf, CH + 16)) continue;
                    g_guard = 1;
                    if (sigsetjmp(g_jb, 1)) { g_guard = 0; break; }
                    memcpy(buf, (void *)off, want);
                    g_guard = 0;
                    nblk++;
                    for (size_t k = 0; k + 0x2a0 <= want; k += 8) {
                        int32_t *q = (int32_t *)(buf + k);
                        int lv = q[0x4c / 4], hp = q[0xd4 / 4], hm = q[0xd8 / 4], th = q[0x28c / 4];
                        if (lv < 1 || lv > 80) continue;
                        if (hm < 5 || hm > 20000) continue;
                        if (hp < 1 || hp > hm) continue;
                        if (th < 1 || th > 1000000) continue;
                        uintptr_t f0 = *(uintptr_t *)(buf + k) & 0x00FFFFFFFFFFFFFFull;
                        if (f0 < 0x1000 || !zf_inreg(f0)) continue;
                        found++;
                        if (found <= 60)
                            fprintf(o, "HQ %p lv=%d hp=%d/%d 门槛=%d f0=%p f6c=%d\n",
                                    (void *)(off + k), lv, hp, hm, th, (void *)f0, q[0x6c / 4]);
                    }
                }
            }
            free(buf);
            fprintf(o, "扫描 %d 块，HQ 命中 %d 个\n", nblk, found);
        } else if (!strcmp(cmd, "sel")) {
            // sel：打印「面板英雄」三个候选槽，以及各自指向对象的字段
            unsigned offs[3] = { SEL_OFF_A, SEL_OFF_B, SEL_OFF_C };
            for (int i = 0; i < 3; i++) {
                uintptr_t v = zf_ld((uintptr_t)g_img + offs[i]);
                uintptr_t p = v & 0x00FFFFFFFFFFFFFFull;
                fprintf(o, "槽 +%#x  raw=%#lx  obj=%p  %s  lv=%d/%d hp=%d/%d 经验=%d 已消耗=%d 可用=%d 门槛=%d 类型=%d\n",
                        offs[i], (unsigned long)v, (void *)p,
                        zf_hero_ok(p) ? "OK" : "reject",
                        zf_ld32(p + 0x4c), zf_ld32(p + 0x290),
                        zf_ld32(p + 0xd4), zf_ld32(p + 0xd8),
                        zf_ld32(p + 0x268), zf_ld32(p + 0x270),
                        zf_ld32(p + 0x268) - zf_ld32(p + 0x270),
                        zf_ld32(p + 0x28c), zf_ld32(p + 0x40));
            }
            fprintf(o, "zf_pick_hero -> %p\n", (void *)zf_pick_hero());
        } else if (!strcmp(cmd, "up")) {
            // up：给「面板英雄」升到 +5 级，并把门槛留在 200（与问号按钮同一套逻辑）
            uintptr_t p = zf_pick_hero();
            if (!p) fprintf(o, "没找到面板英雄\n");
            else zf_do_up(p, o);
        } else if (!strcmp(cmd, "units")) {
            // units [n]：枚举「单位对象指针数组」。
            // 数组基址 = *(img+0x544058)：0xe8d3c 里 0xe8e64 `add x19,x19,#0xfe0`
            // 之后 0xe8e70 `ldr x2,[x19,#0x78]`，即 img+0x543fe0+0x78。
            int n = (arg && *arg) ? atoi(arg) : 24;
            if (n > 96) n = 96;
            uintptr_t raw = zf_ld((uintptr_t)g_img + 0x544058);
            // 实测这个槽读出来是 0xb40000796bcdf878 —— 高字节 0xb4 是 ARM64 的
            // top-byte pointer tag（MTE 风格打标），真实地址是低 7 字节 0x796bcdf878，
            // 实测落在 reg[4908] 0x796b2a7000-0x796e257000 内、可读。
            // 所以判断不能看「读出非 0」，要看「地址是否落在已知区间内」。
            uintptr_t arr = raw;
            if (!strcmp(zf_where(arr), "out-of-region")) {
                uintptr_t m = raw & 0x00FFFFFFFFFFFFFFull;
                if (strcmp(zf_where(m), "out-of-region")) arr = m;
            }
            fprintf(o, "img=%p  raw=%#lx  arr=%p  %s\n", (void *)g_img,
                    (unsigned long)raw, (void *)arr, zf_where(arr));
            zf_hexdump(o, (uintptr_t)g_img + 0x544040, 0x30);
            if (arr) {
                int live = 0;
                for (int i = 0; i < n; i++) {
                    uintptr_t p = zf_ld(arr + (uintptr_t)i * 8);
                    if (!p) continue;
                    live++;
                    fprintf(o, "[%2d] %p  +0x4c=%d +0xf0=%d +0x6c=%d +0x70=%d +0xd4=%d +0xd8=%d +0x240=%d +0x254=%d\n",
                            i, (void *)p,
                            zf_ld32(p + 0x4c), zf_ld32(p + 0xf0), zf_ld32(p + 0x6c),
                            zf_ld32(p + 0x70), zf_ld32(p + 0xd4), zf_ld32(p + 0xd8),
                            zf_ld32(p + 0x240), zf_ld32(p + 0x254));
                }
                fprintf(o, "非空 %d / %d\n", live, n);
            }
        } else if (!strcmp(cmd, "pokeall")) {
            // pokeall <新值> <起始序号> <结束序号>：把快照里这一段地址全写成新值。
            // 用来二分定位「某个显示值到底存在哪」：改了之后界面跟着变就说明命中了。
            char *s = arg;
            long v = strtol(s, &s, 10);
            int from = (int)strtol(s, &s, 0);
            int to = (int)strtol(s, &s, 0);
            if (to <= from || from < 0) { fprintf(o, "参数范围无效\n"); }
            else {
                if (to > g_nsnap) to = g_nsnap;
                int done = 0;
                for (int i = from; i < to; i++) {
                    uintptr_t at = g_snapA[i];
                    g_guard = 1;
                    if (sigsetjmp(g_jb, 1)) { g_guard = 0; continue; }
                    *(int32_t *)at = (int32_t)v;
                    g_guard = 0;
                    fprintf(o, "  [%d] %#lx\n", i, (unsigned long)at);
                    done++;
                }
                fprintf(o, "已写 %d 处（%d..%d，共 %d）\n", done, from, to, g_nsnap);
            }
        } else if (!strcmp(cmd, "poke") || !strcmp(cmd, "poke16")) {
            char *s = arg;
            uintptr_t at = (uintptr_t)strtoul(s, &s, 16);
            long v = strtol(s, NULL, 10);
            g_guard = 1;
            if (sigsetjmp(g_jb, 1)) { g_guard = 0; fprintf(o, "写入失败（不可写）\n"); }
            else {
                if (!strcmp(cmd, "poke")) *(int32_t *)at = (int32_t)v;
                else *(int16_t *)at = (int16_t)v;
                g_guard = 0;
                fprintf(o, "已写 %p = %ld\n", (void *)at, v);
            }
        } else {
            fprintf(o, "未知命令 %s\n", cmd);
        }
    }
    fclose(f);
}

static void *zh_cmd(void *arg) {
    (void)arg;
    sleep(12);                                  // 等游戏进入主界面
    unsigned long last = 0;
    int lastsz = -1;
    for (;;) {
        struct stat st;
        if (stat(ZF_CMD, &st) == 0) {
            if ((unsigned long)st.st_mtime != last || (int)st.st_size != lastsz) {
                last = (unsigned long)st.st_mtime;
                lastsz = (int)st.st_size;
                FILE *o = fopen(ZF_OUT, "w");
                if (o) { zf_run(o); fclose(o); logf_("命令已执行，见 zhout.txt"); }
            }
        }
        sleep(1);
    }
    return NULL;
}
#endif
#endif

// ---------------------------------------------------------------- 存档探查（实验）
// 应用私有目录只有进程自己有权限读，而我们就跑在这个进程里 —— 正好能把它搬出来。
#if ZF_DIAG
#include <dirent.h>
#include <sys/stat.h>

static long copy_file(const char *src, const char *dst, long maxsz) {
    FILE *f = fopen(src, "rb");
    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 0 || sz > maxsz) { fclose(f); return sz; }
    FILE *o = fopen(dst, "wb");
    if (!o) { fclose(f); return -2; }
    char buf[65536]; long total = 0; size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) { fwrite(buf, 1, n, o); total += (long)n; }
    fclose(o); fclose(f);
    return total;
}

static void dump_tree(const char *dir, const char *out, int depth) {
    DIR *d = opendir(dir);
    if (!d) { logf_("存档探查: 打不开 %s", dir); return; }
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        char p[512], o[512];
        snprintf(p, sizeof(p), "%s/%s", dir, e->d_name);
        snprintf(o, sizeof(o), "%s/%s", out, e->d_name);
        struct stat st;
        if (stat(p, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            logf_("存档探查: [D] %s", p);
            if (depth > 0) { mkdir(o, 0777); dump_tree(p, o, depth - 1); }
        } else {
            long got = copy_file(p, o, 8L * 1024 * 1024);
            logf_("存档探查: [F] %s  %ld 字节 -> %s", p, (long)st.st_size, got >= 0 ? o : "跳过");
        }
    }
    closedir(d);
}

static void *zh_dumpsave(void *arg) {
    (void)arg;
    sleep(25);                    // 等游戏把存档写出来
    const char *roots[] = {
        "/data/data/com.herocraft.game.majesty_ne",
        "/data/user/0/com.herocraft.game.majesty_ne",
    };
    const char *out = "/storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files/_dump";
    mkdir(out, 0777);
    for (int i = 0; i < 2; i++) {
        logf_("存档探查: 根目录 %s", roots[i]);
        dump_tree(roots[i], out, 2);
    }
    logf_("存档探查: 完成");
    return NULL;
}
#endif

// ---------------------------------------------------------------- 指针读取入口探测
// 实测 s3ePointerGetState / GetTouchState 调用 0 次，状态数组恒 0，
// 但游戏能响应触摸 → 走的是 GetInt / GetX / GetY 这些老接口。
#define GINT_VA 0xaced0u
#define GX_VA   0xad1e0u
#define GY_VA   0xad244u
static unsigned char *g_tramp_gint, *g_tramp_gx, *g_tramp_gy;
static volatile unsigned g_gint_calls, g_gx_calls, g_gy_calls;
static volatile int g_gint_lastw0;
static unsigned char g_gint_seen[256];
static int g_gint_done, g_gx_done, g_gy_done;

__attribute__((used)) static void zh_on_gint(int w0) {
    g_gint_calls++;
    g_gint_lastw0 = w0;
    if (w0 >= 0 && w0 < 256 && !g_gint_seen[w0]) {
        g_gint_seen[w0] = 1;
        logf_("GetInt 首次请求 w0=%d", w0);
    }
}
__attribute__((used)) static void zh_on_gx(void) { g_gx_calls++; }
__attribute__((used)) static void zh_on_gy(void) { g_gy_calls++; }

#define DEF_PTRH(fn, cb, tramp)                                               \
__attribute__((naked)) static void fn(void) {                                 \
    __asm__ volatile(                                                         \
        "sub  sp, sp, #0x20\n"                                                \
        "stp  x0, x1, [sp, #0x00]\n"                                          \
        "str  x30, [sp, #0x10]\n"                                             \
        "bl   " #cb "\n"                                                      \
        "ldr  x30, [sp, #0x10]\n"                                             \
        "ldp  x0, x1, [sp, #0x00]\n"                                          \
        "add  sp, sp, #0x20\n"                                                \
        "adrp x9, " #tramp "\n"                                               \
        "add  x9, x9, :lo12:" #tramp "\n"                                     \
        "ldr  x9, [x9]\n"                                                     \
        "br   x9\n"                                                           \
    );                                                                        \
}
DEF_PTRH(zh_h_gint, zh_on_gint, g_tramp_gint)
DEF_PTRH(zh_h_gx,   zh_on_gx,   g_tramp_gx)
DEF_PTRH(zh_h_gy,   zh_on_gy,   g_tramp_gy)

static void install_ptr_probe(uintptr_t base) {
    if (!g_gint_done && patch_site(base, GINT_VA, zh_h_gint, &g_tramp_gint)) g_gint_done = 1;
    if (!g_gx_done   && patch_site(base, GX_VA,   zh_h_gx,   &g_tramp_gx))   g_gx_done = 1;
    if (!g_gy_done   && patch_site(base, GY_VA,   zh_h_gy,   &g_tramp_gy))   g_gy_done = 1;
}

// ---------------------------------------------------------------- 指针回调注册探测
// 镜像导入表里有 s3ePointerRegister / GetX / GetTouchState，但轮询接口调用 0 次，
// 说明游戏走的是「注册回调」模式：事件来了直接调回调，参数里带坐标。
// s3ePointerRegister(0xacdec) 只是个跳板，真实实现是 0x8832c(6, 5, type, cb, data)。
#define REG_VA 0x8832cu
static unsigned char *g_tramp_reg;
static volatile unsigned g_reg_calls;
static int g_reg_done;

__attribute__((used)) static void zh_on_reg(int a0, int a1, int type, uintptr_t cb, uintptr_t data) {
    g_reg_calls++;
    logf_("Register a0=%d a1=%d type=%d cb=%p data=%p",
          a0, a1, type, (void *)cb, (void *)data);
}

__attribute__((naked)) static void zh_h_reg(void) {
    __asm__ volatile(
        "sub  sp, sp, #0x40\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "stp  x2, x3, [sp, #0x10]\n"
        "str  x4, [sp, #0x20]\n"
        "str  x30, [sp, #0x30]\n"
        "bl   zh_on_reg\n"
        "ldr  x30, [sp, #0x30]\n"
        "ldr  x4, [sp, #0x20]\n"
        "ldp  x2, x3, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0x40\n"
        "adrp x9, g_tramp_reg\n"
        "add  x9, x9, :lo12:g_tramp_reg\n"
        "ldr  x9, [x9]\n"
        "br   x9\n"
    );
}

static void install_reg_probe(uintptr_t base) {
    if (!g_reg_done && patch_site(base, REG_VA, zh_h_reg, &g_tramp_reg)) g_reg_done = 1;
}

// ---------------------------------------------------------------- 触摸事件回调（真正的输入入口）
// 游戏通过 s3ePointerRegister 注册回调，运行时地址落在镜像偏移 0x122f30。
// 结构：x0 -> { +4: state, +8: X, +0xc: Y }，坐标是物理像素，回调内部再缩放成逻辑坐标。
//
// 原函数前 6 条：
//   122f30  adrp x1, #0x53c000
//   122f34  stp  x19, x20, [sp, #-0x20]!
//   122f38  ldr  x1, [x1, #0xbe0]
//   122f3c  str  x30, [sp, #0x10]
//   122f40  ldrb w1, [x1]          <-- 输入总开关
//   122f44  cbnz w1, #0x122fa8     <-- 开关非 0 直接 return
//
// ★ 教训（两次踩坑都在这 6 条指令上）：
//   ① 不能直接把入口交给 patch_site 的 trampoline —— 第 1 条 adrp 是 PC 相对寻址，
//      搬到 trampoline（0x7d79cf5000 之类）后算出的地址完全不对，第一次触摸就 SIGSEGV。
//   ② 手工重建时必须从 0x122f40 续（含 ldrb w1,[x1]），
//      若从 0x122f44 续，cbnz w1 拿到的是 x1 指针的低 32 位（永远非 0），
//      每个触摸都被送去 ret —— 游戏收不到任何点击（PLAY 界面点对号进不去）。
//   所以：手工重建 4 条（adrp 换成绝对地址加载），然后跳 0x122f40。
#define EVT_VA      0x122f30u
#define EVT_G_OFF   0x53cbe0u      // adrp x1,#0x53c000 + ldr x1,[x1,#0xbe0] 的全局槽
#define EVT_RESUME  0x122f40u      // ldrb w1,[x1] —— 必须从这里续

// 问号按钮：物理像素 2400x1080 横屏。
// 按蓝色圆环实测（截图坐标）：X 按钮 (1038,78)、? 按钮 (1037,234)，圆直径 118（半径 59）。
//
// ★★ 关键：触摸上报坐标 ≠ 截图坐标，横向差 108px
//   实测（adb input tap 注入后读触摸回调）：
//     物理 (1380, 92) -> 上报 (1272, 92)   Δx=108
//     物理 ( 600,500) -> 上报 ( 492,500)   Δx=108
//     物理 (2000,900) -> 上报 (1892,900)   Δx=108
//     物理 ( 100,100) -> 无事件（x<108 落在左黑边里，被丢弃）
//   原因：游戏逻辑 1280x603 按 1.791 倍放大成 2292x1080，左边被裁掉/偏移 108px，
//   触摸系统上报的是「视口内坐标」。y 方向没有偏移（高度正好铺满）。
//   所以问号按钮在上报空间里的圆心是 1037-108 = 929。
#define QB_CX  929
#define QB_CY  234
#define QB_R2  (90 * 90)

static unsigned char *g_tramp_evt;
// 只被 naked 汇编里 adrp/add 引用，C 代码不读 —— 必须标 used，
// 否则 -O2 会把它优化掉，链接时报 "relocation ... cannot be used against symbol"。
__attribute__((used)) static uintptr_t g_evt_g;
__attribute__((used)) static uintptr_t g_evt_resume;
static volatile unsigned g_evt_calls;
static volatile int g_evt_lastx, g_evt_lasty, g_evt_lastst;
static int g_evt_done;
static volatile int g_up_busy;

// --------------------------------------------------------------- 升级动作
// 思路（已实测）：不改等级、不碰经验，只把「升级门槛 +0x28c」压到 1，
// 游戏自己的每帧检查就会完成升级 —— 属性重算 / UI 刷新 / 特效 / 存档标记全部原生。
static int zf_hero_ok(uintptr_t p) {
    if (!p || (p & 7)) return 0;
    if (!zf_inreg(p) || !zf_inreg(p + 0x28c)) return 0;
    int lv = zf_ld32(p + 0x4c);
    int hp = zf_ld32(p + 0xd4);
    int hm = zf_ld32(p + 0xd8);
    int th = zf_ld32(p + 0x28c);
    if (lv < 1 || lv > 80) return 0;
    if (hm < 5 || hm > 20000) return 0;
    if (hp < 1 || hp > hm) return 0;
    if (th < 1 || th > 1000000) return 0;
    // 真对象的首 8 字节是类型/vtable 指针，必须落在已知可读区间里
    uintptr_t f0 = zf_ld(p) & 0x00FFFFFFFFFFFFFFull;
    if (f0 < 0x1000 || !zf_inreg(f0)) return 0;
    return 1;
}

static void zf_dump_cand(void) {
    uintptr_t a = zf_sel_at(SEL_OFF_A);
    uintptr_t b = zf_sel_at(SEL_OFF_B);
    uintptr_t c = zf_sel_at(SEL_OFF_C);
    logf_("选中槽 A=%p%s B=%p%s C=%p%s", (void *)a, zf_hero_ok(a) ? "*" : "",
         (void *)b, zf_hero_ok(b) ? "*" : "", (void *)c, zf_hero_ok(c) ? "*" : "");
    for (int i = 0; i < g_nu && i < 12; i++) {
        uintptr_t p = g_up[i];
        logf_("  U[%d]%s %p 绘制=%d lv=%d/%d hp=%d/%d 经验=%d 已消耗=%d 门槛=%d 类型=%d",
              i, zf_hero_ok(p) ? "*" : " ", (void *)p, g_ulv[i],
              zf_ld32(p + 0x4c), zf_ld32(p + 0x290),
              zf_ld32(p + 0xd4), zf_ld32(p + 0xd8),
              zf_ld32(p + 0x268), zf_ld32(p + 0x270),
              zf_ld32(p + 0x28c), zf_ld32(p + 0x40));
    }
}

// 面板英雄指针槽见文件上方的 SEL_OFF_A/B/C

static uintptr_t zf_sel_at(unsigned off) {
    if (!g_img) return 0;
    uintptr_t v = zf_ld((uintptr_t)g_img + off);
    return v & 0x00FFFFFFFFFFFFFFull;
}

static uintptr_t zf_sel(void) {
    uintptr_t p = zf_sel_at(SEL_OFF_A);
    if (zf_hero_ok(p)) return p;
    p = zf_sel_at(SEL_OFF_B);
    if (zf_hero_ok(p)) return p;
    p = zf_sel_at(SEL_OFF_C);
    if (zf_hero_ok(p)) return p;
    return 0;
}

static uintptr_t zf_pick_hero(void) {
    uintptr_t p = zf_sel();          // 首选：面板上正在显示的那个英雄
    if (p) return p;
    // 兜底：血条绘制钩子抓到的屏上单位里，绘制次数最多的合法英雄
    uintptr_t best = 0;
    int bestn = -1;
    for (int i = 0; i < g_nu; i++) {
        if (!zf_hero_ok(g_up[i])) continue;
        if (g_ulv[i] > bestn) { bestn = g_ulv[i]; best = g_up[i]; }
    }
    return best;
}

// 1 = 真的写门槛；0 = 只打日志（采集阶段）
#define ZF_UP_WRITE 1

// ---------------------------------------------------------------- 升级函数
// 反汇编定位（镜像偏移 0x13C654），就是游戏自己「获得经验」的入口：
//
//   13c654  prologue
//   13c664  w3 = [x0+0x4c]        ; 等级
//   13c668  w2 = [x0+0x290]       ; 等级上限
//   13c670  b.ge -> return        ; 满级直接返回
//   13c678  w2 = [x0+0x268]       ; 当前经验
//   13c67c  w0 = w1 / w3          ; 参数 w1 = 获得的经验，按等级折算
//   13c688  w0 = w0 + w2          ; 经验 += ...
//   13c68c  w2 = [x19+0x270]      ; 已消耗经验
//   13c690  w1 = [x19+0x28c]      ; 升级门槛
//   13c698  w0 = 经验 - 已消耗
//   13c69c  cmp 门槛, w0
//   13c6a0  b.gt -> return        ; 不够一级，返回
//   13c6a4  ...  已消耗 += 门槛
//   13c6b8  b.le -> 13c754        ; 单位类型符合 -> 升级
//   13c754  [x19+0x4c] = 等级+1
//   13c760  bl 0xcce14            ; ★ 游戏自己重算属性
//   13c714  b.le -> 13c6a4        ; ★ 循环：余量还够就继续升
//
// 调用者证实参数约定：`mov x0,x20; mov w1,#0xaf; bl 0x13c654`（0x59EB8）。
//
// ★ 这就是之前「门槛改成 200 但等级不动」的根因：
//   这个函数**只在获得经验时被调用**，英雄站在城里不打怪就永远不会进来，
//   所以压门槛没有任何效果。现在改成我们直接调用它，传 w1=0（不加经验），
//   循环条件只看「经验 - 已消耗」，照样会把攒下的经验兑换成等级，并原地重算属性。
#define LVFN_OFF   0x13c654u
#define LV_LEVEL   0x4cu
#define LV_CAP     0x290u     // 等级上限
#define LV_XP      0x268u     // 当前经验
#define LV_SPENT   0x270u     // 已消耗经验
#define LV_TH      0x28cu     // 升级门槛
#define LV_TYPE    0x40u      // 单位类型（决定能不能升级）

typedef void (*fn_lvup)(void *obj, int addxp);

// 升级实现：把门槛设成「可用经验 / 5」，调一次游戏函数 → 正好升 5 级。
// 循环里门槛不重算（已实测），所以 floor(可用经验 / 门槛) 就是升级数，可精确控制。
static void zf_do_up(uintptr_t obj, FILE *o) {
    int lv0 = zf_ld32(obj + LV_LEVEL);
    int hp0 = zf_ld32(obj + 0xd4);
    int hm0 = zf_ld32(obj + 0xd8);
    int cap = zf_ld32(obj + LV_CAP);
    int xp  = zf_ld32(obj + LV_XP);
    int sp  = zf_ld32(obj + LV_SPENT);
    int avail = xp - sp;
    int ty  = zf_ld32(obj + LV_TYPE);
    logf_("★ 升级 %p lv=%d/%d hp=%d/%d 类型=%d 经验=%d 已消耗=%d 可用=%d 门槛=%d",
          (void *)obj, lv0, cap, hp0, hm0, ty, xp, sp, avail, zf_ld32(obj + LV_TH));
    if (o) fprintf(o, "升级 %p lv=%d/%d hp=%d/%d 类型=%d 经验=%d 已消耗=%d 可用=%d\n",
                   (void *)obj, lv0, cap, hp0, hm0, ty, xp, sp, avail);
#if ZF_UP_WRITE
    if (!g_img || !zf_inreg(obj + LV_TH)) { logf_("对象无效"); return; }
    if (cap < 1 || cap > 200) { logf_("等级上限字段异常 (%d)，不敢动", cap); return; }
    // 自愈：早期版本因为循环内没有上限判断，把英雄顶到了 127 / 101 级。
    // 再点一次就把等级拉回上限，避免带着超界等级存档。
    if (lv0 > cap) {
        *(volatile int32_t *)(obj + LV_LEVEL) = cap;
        logf_("等级 %d 超过上限 %d，已修正为 %d", lv0, cap, cap);
        return;
    }
    if (lv0 >= cap) { logf_("已经满级 (%d/%d)，不动", lv0, cap); return; }
    // ★ 护栏：13c6b0 处是 `tbnz w0,#0x1f` + `cmp w0,#9` / `cmp w0,#0x141`。
    //   类型符合才走「等级++ → bl 0xcce14 重算属性」；
    //   不符合会走 13c6c4 那条路径，里面 `ldr x0,[x0,#0x478]; ldr w0,[x0]` 直接解引用全局，
    //   那个全局在某些时机是空的 —— 从我们的调用点进去会 SIGSEGV。
    //   所以类型不合格就干脆不调，只把类型打出来。
    if (!((ty >= 0 && ty <= 9) || ty == 0x141)) {
        logf_("单位类型 %d 不在可升级集合 {0..9, 0x141} 内，放弃（避免走解引用路径）", ty);
        return;
    }

    // 目标：每次点击升 UP_WANT 级，可无限重复；撞到等级上限就停在满级。
    //   门槛 T 取 max(200, 可用经验/want)，这样 floor(可用经验/T) 一定 ≤ want。
    //   若可用经验不够 want*T，就把差额「补」进去：
    //   函数内部是 `经验 += w1 / 等级`，所以传 w1 = 差额 * 等级 就能精确补上差额。
    //   → 补完可用经验正好等于 want*T，循环升 want 级后余数 0，门槛收尾回 200。
    //   注意 w1 必须用【进入函数前的等级】折算，因为 13c67c 用的就是入口时的等级。
    //
    // ★ 上限必须自己算：13c654 只在【入口】检查一次 `等级 >= 上限`，
    //   循环内部没有任何上限判断。want 直接给 50 的话，77 级会一路升到 127 级，
    //   冲出 99 的上限（实测踩过）。所以 want 要按剩余空间夹一次。
    int want = UP_WANT;
    if (want > cap - lv0) want = cap - lv0;
    if (want < 1) { logf_("已经满级 (%d/%d)，不动", lv0, cap); return; }

    int T = avail / want;
    if (T < UP_FINAL_TH) T = UP_FINAL_TH;
    if (T > 100000) T = 100000;
    // 兜底：确保 floor(可用经验 / T) 不会超过 want（整数除法有取整误差）
    while (T > UP_FINAL_TH && avail / T > want) T++;
    int need = want * T;
    int w1 = 0;
    if (avail < need) {
        int d = need - avail;
        int lv = lv0 > 0 ? lv0 : 1;
        w1 = d * lv;
        logf_("  可用经验 %d < %d，补 %d 点（w1=%d）", avail, need, d, w1);
    }
    logf_("  计划升 %d 级（lv%d -> %d，上限 %d）门槛=%d need=%d w1=%d",
          want, lv0, lv0 + want, cap, T, need, w1);
    *(volatile int32_t *)(obj + LV_TH) = T;
    ((fn_lvup)(g_img + LVFN_OFF))((void *)obj, w1);
    // 收尾：门槛落回 200
    if (zf_inreg(obj + LV_TH)) *(volatile int32_t *)(obj + LV_TH) = UP_FINAL_TH;
#endif
    logf_("★ 完成 lv=%d->%d hp=%d/%d->%d/%d 门槛=%d", lv0, zf_ld32(obj + LV_LEVEL),
         hp0, hm0, zf_ld32(obj + 0xd4), zf_ld32(obj + 0xd8), zf_ld32(obj + LV_TH));
    if (o) fprintf(o, "结果 lv=%d->%d hp=%d/%d->%d/%d 门槛=%d\n", lv0,
                   zf_ld32(obj + LV_LEVEL), hp0, hm0, zf_ld32(obj + 0xd4),
                   zf_ld32(obj + 0xd8), zf_ld32(obj + LV_TH));
}

__attribute__((used)) static void zh_on_evt(uintptr_t ev) {
    if (!ev) return;
    int st = zf_ld32(ev + 4);
    if (st != 1) return;                  // 只在「按下」时触发
    int x  = zf_ld32(ev + 8);
    int y  = zf_ld32(ev + 0xc);
    int dx = x - QB_CX, dy = y - QB_CY;
    int d2 = dx * dx + dy * dy;
    if (d2 > QB_R2) return;
    logf_("命中问号按钮 (%d,%d) 距圆心²=%d", x, y, d2);
    if (g_up_busy) { logf_("上一次还没跑完，忽略"); return; }
    uintptr_t t = zf_pick_hero();
    logf_("zf_pick_hero -> %p", (void *)t);
    if (!t) return;
    g_up_busy = 1;
    // ★ 直接在游戏自己的线程里调升级函数（这里就是游戏输入回调的上下文），
    //   不再开新线程：跨线程调游戏代码会碰 UI / 分配器，容易炸。
    zf_do_up(t, NULL);
    g_up_busy = 0;
}

// 保存 x0..x18 + x30（C 函数会破坏 x0..x18），然后手工重建被覆盖的 4 条原指令：
//   adrp x1, #0x53c000        -> ldr x1, [g_evt_g]   （绝对地址，等价且不受 PC 影响）
//   stp  x19, x20, [sp, #-0x20]!
//   ldr  x1, [x1, #0xbe0]     -> 合并进上面那条
//   str  x30, [sp, #0x10]
// 最后跳 0x122f40（ldrb w1,[x1]），让原函数自己判断输入总开关。
// 只用 x16/x17（IP0/IP1，架构规定的过程内临时寄存器），不碰任何活寄存器。
__attribute__((naked)) static void zh_h_evt(void) {
    __asm__ volatile(
        "sub  sp, sp, #0xa0\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "stp  x2, x3, [sp, #0x10]\n"
        "stp  x4, x5, [sp, #0x20]\n"
        "stp  x6, x7, [sp, #0x30]\n"
        "stp  x8, x9, [sp, #0x40]\n"
        "stp  x10, x11, [sp, #0x50]\n"
        "stp  x12, x13, [sp, #0x60]\n"
        "stp  x14, x15, [sp, #0x70]\n"
        "stp  x16, x17, [sp, #0x80]\n"
        "str  x18, [sp, #0x90]\n"
        "str  x30, [sp, #0x98]\n"
        "bl   zh_on_evt\n"
        "ldr  x30, [sp, #0x98]\n"
        "ldr  x18, [sp, #0x90]\n"
        "ldp  x16, x17, [sp, #0x80]\n"
        "ldp  x14, x15, [sp, #0x70]\n"
        "ldp  x12, x13, [sp, #0x60]\n"
        "ldp  x10, x11, [sp, #0x50]\n"
        "ldp  x8, x9, [sp, #0x40]\n"
        "ldp  x6, x7, [sp, #0x30]\n"
        "ldp  x4, x5, [sp, #0x20]\n"
        "ldp  x2, x3, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0xa0\n"
        // --- 重建原指令 ---
        "adrp x16, g_evt_g\n"
        "add  x16, x16, :lo12:g_evt_g\n"
        "ldr  x16, [x16]\n"          // x16 = &(base+0x53cbe0)
        "stp  x19, x20, [sp, #-0x20]!\n"
        "ldr  x1, [x16]\n"           // x1 = *(base+0x53cbe0)
        "str  x30, [sp, #0x10]\n"
        "adrp x17, g_evt_resume\n"
        "add  x17, x17, :lo12:g_evt_resume\n"
        "ldr  x17, [x17]\n"
        "br   x17\n"
    );
}

static void install_evt_hook(uintptr_t base) {
    if (g_evt_done) return;
    g_evt_g      = base + EVT_G_OFF;
    g_evt_resume = base + EVT_RESUME;
    // patch_site 只是往入口写 16 字节跳转；它顺带建的 trampoline 这里不用（adrp 搬不动）。
    if (patch_site(base, EVT_VA, zh_h_evt, &g_tramp_evt)) {
        g_evt_done = 1;
        logf_("触摸回调已挂钩 g=%p resume=%p", (void *)g_evt_g, (void *)g_evt_resume);
    }
}

// ---------------------------------------------------------------- 钻石商店（作弊商店）免费
// 结构由反汇编确认（0x18498 初始化 / 0x18544 isCheatActive / 0x186dc getCheatCost）：
//   单例 base+0x542c80：+0x00 已加载字节，+0x08 → 14 字节「已购买」数组，+0x10 已初始化字节
//   价格表 base+0x443930：int32[14] = {30,20,30,30,20,20,10,20,10,0,30,30,20,12}
// 目标：① 14 项价格全部清零（UI 显示 0，购买不扣钻）
//       ② 14 项全部置为已购买（商店里显示橙色对勾，效果立刻生效）
// 用 300ms 轮询而不是一次性写入：游戏重新初始化单例或重开一局后能自动补回。
static volatile unsigned g_cht_fill;      // 自动勾选执行次数（诊断用）
static void zh_hero_apply(uintptr_t base); // 定义在后面

// ★ 线程安全铁律：作弊线程里只能用下面这套「maps 快照 + 区间判断」的读，
//   绝对不能用 zf_ld/z_ld32/zf_ld8（sigsetjmp 兜底）。那套的 g_guard/g_jb 是全局的，
//   两个线程同时进出会让 siglongjmp 跳到别人的栈上 → SIGSEGV。
static void zf_snap_regions(void);
static int g_nregs;                        // 定义在后面（试探性定义，C 允许重复）
static int  zf_addr_ok(uintptr_t a, unsigned len);
static uintptr_t zf_rd(uintptr_t a);
static int  zf_rd32(uintptr_t a);
static int  zf_rd8(uintptr_t a);
static void zf_wr32(uintptr_t a, int v);
static void zf_wr8(uintptr_t a, int v);
static volatile int g_level_loaded;   // 关卡载入完成（见过读档 + 之后数量稳定 3 轮）
static volatile int g_seen_load;      // 见过一次「批量冒出英雄」= 读档事件

static int zf_ld8(uintptr_t a) {
    int v;
    if (!a) return 0;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    v = *(volatile unsigned char *)a;
    g_guard = 0;
    return v;
}

static int zf_st32(uintptr_t a, int v) {
    if (!a) return 0;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    *(volatile int32_t *)a = v;
    g_guard = 0;
    return 1;
}

static int zf_st8(uintptr_t a, int v) {
    if (!a) return 0;
    g_guard = 1;
    if (sigsetjmp(g_jb, 1)) { g_guard = 0; return 0; }
    *(volatile unsigned char *)a = (unsigned char)v;
    g_guard = 0;
    return 1;
}

// 14 项的价格与自动勾选策略（索引 = 作弊 id）
//   id 0  不朽税吏     0  自动勾选
//   id 1  快速建造     1  不勾选（留 1 钻石让玩家自己买）
//   id 2  老兵         1  不勾选（买了以后，新招募的英雄直接 99 级）
//   id 3  易得经验     0  自动勾选
//   id 4  牢固城墙     0  自动勾选
//   id 5  哨塔强化     0  自动勾选
//   id 6  地图全开     1  不勾选
//   id 7  理想城堡     0  自动勾选
//   id 8  快速雇佣     1  不勾选
//   id 9  （空位）     0  自动勾选（无害）
//   id 10 强大亡灵法师 0  自动勾选
//   id 11 更多英雄     0  自动勾选
//   id 12 扩建公会     0  自动勾选
//   id 13 金币宝箱     0  自动勾选
static const int kPrice[CHT_N] = {0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0};
static const unsigned char kAuto[CHT_N] = {1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1};

// 渲染线程：把作弊线程递过来的「即时动作」id 执行掉。
// 只处理 id 6..12（跳转表覆盖的范围），并且要求游戏已经初始化。
#define APPLY_OFF 0x1876cu
typedef void (*fn_apply)(int id);

// 理想城堡的目标等级。
// ★ 只能到 2！游戏自己给城堡按「初始等级」定长分配了税吏槽位等结构，
//   直接写 3 级会越界访问 → 首次进新关卡闪退（已实测踩过）。
//   游戏原作弊也是写死 2 级（0x188c4 `mov w1,#2`），这是安全上限。
//   想要 3 级必须走游戏自己的升级流程（12 个英雄 + 钱），不能硬写字段。
#define CASTLE_LV_WANT 2

static void zf_apply_pending(void) {
    int h = g_aq_h;
    if (h == g_aq_t) return;
    int id = g_aq[h];
    g_aq_h = (h + 1) % AQ_MAX;
    if (id < 6 || id > 12) return;         // 只有跳转表范围内的才走 applyCheat
    if (!g_img) return;

    // 执行前后各读一次城堡，确认到底改成了几级
    uintptr_t base = (uintptr_t)g_img;
    uintptr_t cp = zf_ld(base + 0x53c030u);
    uintptr_t castle = cp ? zf_ld(cp) : 0;
    int lv0 = castle ? zf_ld32(castle + 0x4c) : -1;
    int hp0 = castle ? zf_ld32(castle + 0xd8) : -1;

    ((fn_apply)(base + APPLY_OFF))(id);

    int lv1 = castle ? zf_ld32(castle + 0x4c) : -1;
    int hp1 = castle ? zf_ld32(castle + 0xd8) : -1;
    logf_("即时作弊项 %d 已执行：城堡 %p 等级 %d -> %d，血上限 %d -> %d",
          id, (void *)castle, lv0, lv1, hp0, hp1);
}

static void zh_cheat_tick(uintptr_t base) {
    if (g_nregs <= 0) zf_snap_regions();     // 区间表还没建就先用不了安全读写

    // ⓪ 阵营互斥「永久模式」的后台维护（未开启时立即返回，几乎零开销）
    zf_camp_tick();

    // ① 价格表。表可能落在只读段，先把所在页放开写权限（只做一次）。
    uintptr_t tab = base + CHT_COST_VA;
    static int prot_done;
    if (!prot_done) {
        uintptr_t pg = tab & ~(uintptr_t)0xfff;
        if (mprotect((void *)pg, 0x2000, PROT_READ | PROT_WRITE | PROT_EXEC) == 0)
            prot_done = 1;
        else
            logf_("价格表 mprotect 失败（价格可能改不动）");
    }
    int dirty = 0;
    for (int i = 0; i < CHT_N; i++) if (zf_rd32(tab + i * 4) != kPrice[i]) { dirty = 1; break; }
    if (dirty) {
        for (int i = 0; i < CHT_N; i++) zf_wr32(tab + i * 4, kPrice[i]);
        logf_("钻石商店：价格已写入（%d 项）", CHT_N);
    }

    // ② 按 kAuto 设置勾选状态（1 = 已购买生效，0 = 取消勾选）。
    //    ★ 只在启动阶段（前 ~8 秒）做全量同步：游戏初始化会重建数组，
    //      需要压住；之后 kAuto=0 的项就交给玩家，买了不会再被改回去。
    uintptr_t s = base + CHT_SING_VA;
    uintptr_t arr = 0;
    if (zf_rd8(s + 0x10)) arr = zf_rd(s + 8);
    g_cht_arr = arr;                       // 给渲染线程做「对号亮一帧」捕获
    if (arr) {
        static int dumped;
        if (!dumped) {
            dumped = 1;
            char b[CHT_N + 1];
            for (int i = 0; i < CHT_N; i++) b[i] = '0' + (zf_rd8(arr + i) ? 1 : 0);
            b[CHT_N] = 0;
            logf_("商店数组初始状态（存档）: %s", b);
        }
    }
    if (arr) {
        static int sync_n;
        // ★ 全量同步窗口：从启动一直持续到「关卡载入完成」（见过读档 + 数量稳定 3 轮）。
        //   原因：读档发生在进关卡时，游戏会从存档把「已激活」数组重建一遍，
        //   如果窗口提前关了，kAuto=0 的老兵会被存档里的 1 覆盖回去。
        //   兜底：最多 200 轮，避免一直卡在全量同步。
        int full = (!g_level_loaded && sync_n < 200);

        // 玩家买过的项：游戏/我们的同步都可能把它写回 0，这里每轮压回 1
        for (int k = 0; k < 4; k++) {
            int i = kOffIdx[k];
            if (!(g_keep_mask & (1u << i))) continue;
            if (zf_rd8(arr + i) != 1) {
                zf_wr8(arr + i, 1);
                logf_("第 %d 项被改回 0，重新写回 1", i);
            }
        }

        int need = 0;
        for (int i = 0; i < CHT_N; i++) {
            int want = kAuto[i];
            if (!full && !want) continue;          // 窗口结束后不再强行取消
            if (!kAuto[i] && (g_keep_mask & (1u << i))) continue;   // 玩家买过，不动
            if (zf_rd8(arr + i) != want) { need = 1; break; }
        }
        if (need) {
            for (int i = 0; i < CHT_N; i++) {
                int want = kAuto[i];
                if (!full && !want) continue;
                if (!kAuto[i] && (g_keep_mask & (1u << i))) continue;
                zf_wr8(arr + i, want);
            }
            // 至少做过一次全量同步后，才允许捕获「玩家购买」
            // （此时默认关闭的项已被压成 0，之后再变 1 只可能是玩家买的）
            if (full) g_vet_armed = 1;
            g_cht_fill++;
            logf_("钻石商店：勾选状态已同步（第 %u 次%s）", g_cht_fill,
                  full ? "，启动阶段" : "，仅保证默认项");
        }
        if (sync_n < 1000) sync_n++;
    }

    // ④ 即时生效项：只填数组不够，得补一次动作。
    //    ★ 反汇编证据：applyCheat 里 id 0..5 直接 ret（效果靠 isCheatActive 实时读），
    //      id 6..12 才走跳转表做即时动作，id 13 单独一个分支给金币 +10000。
    //      所以我们之前只填数组时，理想城堡和金币宝箱根本不会动。
    //    ★ 时序坑：这两项都必须等「城堡对象出现」才能做。启动时游戏还在主菜单，
    //      *(base+0x53c030) 是 0，applyCheat(7) 会直接空指针返回，白跑一趟；
    //      金币也可能还没从存档读出来，加了会被覆盖。所以做成就置位，没做成下轮再来。
    if (arr) {
        uintptr_t cp = zf_rd(base + 0x53c030u);      // 城堡容器
        uintptr_t castle = cp ? zf_rd(cp) : 0;       // 城堡对象
        int cty = castle ? zf_rd32(castle + 0x40) : 0;
        int ready = castle && zf_addr_ok(castle + 0x4c, 4) && cty > 0 && cty < 0x40;

        // ★ 新关卡检测：城堡对象换了就重置一次性标记。
        //   否则「理想城堡 / 金币宝箱」只在本次进程的第一局生效，
        //   玩家重开一局（或读别的存档）就什么都没有了。
        static uintptr_t last_castle;
        if (castle != last_castle) {
            if (last_castle && ready)
                logf_("检测到新关卡（城堡 %p -> %p），重置一次性作弊项",
                      (void *)last_castle, (void *)castle);
            if (last_castle) g_aq_done &= ~((1u << 7) | (1u << 13));
            last_castle = castle;
        }

        if (ready) {
            // id 13 金币宝箱：+10000。这里自己写，因为 applyCheat 那个分支
            // （0x18928）没有空指针检查，指针没初始化时会直接崩。
            if (!(g_aq_done & (1u << 13)) && zf_rd8(arr + 13)) {
                uintptr_t gp = zf_rd(base + 0x53c040u);
                if (gp && zf_addr_ok(gp, 4)) {
                    int g0 = zf_rd32(gp);
                    zf_wr32(gp, g0 + 10000);
                    g_aq_done |= 1u << 13;
                    logf_("金币宝箱：%d -> %d（槽 %p，城堡类型 %d）", g0, g0 + 10000,
                          (void *)gp, cty);
                }
            }
            // id 7 理想城堡：递到渲染线程走游戏自己的 applyCheat，
            // 它会同时写等级、重算血量上限、改状态字段，比自己写安全。
            // 只在城堡等级不足目标值时执行，避免每帧重复投递。
            if (!(g_aq_done & (1u << 7)) && zf_rd8(arr + 7) &&
                zf_rd32(castle + 0x4c) < CASTLE_LV_WANT) {
                zf_aq_push(7);
                g_aq_done |= 1u << 7;
                logf_("理想城堡：城堡 %p 类型 %d 等级 %d，投递升级到 %d",
                      (void *)castle, cty, zf_rd32(castle + 0x4c), CASTLE_LV_WANT);
            }
        }
    }

    // ⑤ 建造上限诊断：每 10 轮（约 3 秒）打一次真实数值。
    //    反汇编确认建造检查长这样（0x69168 和 0xafe9c 两处一模一样）：
    //      w1 = *(*(base+0x53bce8))   ; 当前建筑数
    //      w0 = *(*(base+0x53b300))   ; 建筑数量上限
    //      cmp w1, w0 / b.lt 允许 / 否则提示 shortTxtMaxBuildings
    //    所以「提示已达上限」只有两种可能：上限被写回 30，或者当前数比想象的大。
    {
        static int dn;
        if (++dn >= 10) {
            dn = 0;
            uintptr_t mp = zf_rd(base + 0x53b300u);
            uintptr_t np = zf_rd(base + 0x53bce8u);
            uintptr_t x8 = zf_rd(base + 0x53b308u);
            logf_("建造检查: 上限=%d 当前=%d b308=%d", mp ? zf_rd32(mp) : -1,
                  np ? zf_rd32(np) : -1, x8 ? zf_rd32(x8) : -1);
        }
    }

    // ⑥ 英雄上限（放在最后，每轮都要跑，不能被上面的提前 return 跳过）
    zh_hero_apply(base);
}

// ---------------------------------------------------------------- 英雄上限探测
// 反汇编确认（0x18884 = 作弊 id 11「更多英雄」的分支，0x68258 = 雇佣时的检查）：
//   base+0x53df88  指针槽 → int32 全局英雄上限（作弊直接写成 40）
//   base+0x53add8  指针槽 → int32 当前英雄总数
//   obj+0x1f4      某建筑已雇英雄数
//   obj+0x1fc      某建筑容量（初始 2 或 4，「扩建公会」×2 后最多 8）
//   base+0x53d980  单位链表容器；容器→a→sentinel→first，节点 +0x10 = 单位对象
// ★ 64 位 ldr 的立即数是 imm12*8：`ldr x0,[x0,#0xf88]` 的 imm12 是 0x1f1，
//   实际偏移 0x1f1*8 = 0xf88。之前按 *4 算成 0x7c4，读到的是垃圾。
#define HERO_CNT_VA   0x53add8u
#define HERO_LIST_VA  0x53d980u

static volatile int g_hero_probe_done;

// 信号兜底（zf_ld）在多线程下会互相踩 g_guard/g_jb：一个线程崩溃后 siglongjmp 到
// 另一个线程的栈，直接 SIGSEGV。探测线程读的是不确定地址，必须避开这套机制。
// 这里单独用 /proc/self/maps 快照 + 区间判断，完全不依赖信号。
typedef struct { uintptr_t lo, hi; int wr; } zf_reg_t;
#define ZF_REG_MAX 4096
static zf_reg_t g_regs[ZF_REG_MAX];
static int g_nregs;

static void zf_snap_regions(void) {
    g_nregs = 0;
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return;
    char line[512];
    while (fgets(line, sizeof(line), f) && g_nregs < ZF_REG_MAX) {
        unsigned long lo, hi;
        char perm[8] = {0};
        if (sscanf(line, "%lx-%lx %7s", &lo, &hi, perm) != 3) continue;
        if (perm[0] != 'r') continue;
        if (hi <= lo) continue;
        g_regs[g_nregs].lo = (uintptr_t)lo;
        g_regs[g_nregs].hi = (uintptr_t)hi;
        g_regs[g_nregs].wr = (perm[1] == 'w');
        g_nregs++;
    }
    fclose(f);
}

static int zf_addr_ok(uintptr_t a, unsigned len) {
    if (!a) return 0;
    int lo = 0, hi = g_nregs - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        if (a < g_regs[mid].lo) hi = mid - 1;
        else if (a >= g_regs[mid].hi) lo = mid + 1;
        else return a + len <= g_regs[mid].hi;
    }
    return 0;
}

// 写入前的可写性校验。
// ★ 教训：曾经把一个垃圾指针（0x79691c79b7）当上限槽去写，游戏直接黑屏。
//   凡是从「指针槽解引用」拿到的地址，写之前都必须过这一关。
static int zf_writable(uintptr_t a, unsigned len) {
    if (!a) return 0;
    int lo = 0, hi = g_nregs - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        if (a < g_regs[mid].lo) hi = mid - 1;
        else if (a >= g_regs[mid].hi) lo = mid + 1;
        else return g_regs[mid].wr && a + len <= g_regs[mid].hi;
    }
    return 0;
}

// ---------------------------------------------------------------- 关卡解锁
// 需求：把战役地图上锁着的关卡全部打开（至少 1~7 关）。
// 关卡名 key 是 sL0..sL16（17 关，见 analysis/zh_entities.py），
// 这些 key 只存在于外部 translate.dat，镜像里查不到，所以没法从字符串反推。
//
// 思路：当前存档只有第 1 关解锁，解锁状态大概率长这样（int32 数组）：
//       1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
//   在镜像的 .data/.bss 里扫「首元素为 1、其余 16 个为 0」的连续 17 个 int32。
//   候选可能不止一个，用 `ulk <地址>` 逐个试，改完直接看地图有没有开锁。
//
// 扫描范围只取 base..base+8MB（镜像 5.5MB，留余量），不碰堆 ——
// 全盘扫堆太慢，而且先确认它是全局静态变量更省事。
#define LVL_N 17
#define LVL_SCAN_SPAN 0x800000u

static void zf_scan_levels(FILE *o, int all) {
    if (!g_img) { fprintf(o, "no img\n"); return; }
    zf_snap_regions();
    uintptr_t base = (uintptr_t)g_img;
    uintptr_t lo = base, hi = base + LVL_SCAN_SPAN;
    fprintf(o, "img=%p 模式=%s\n", (void *)base, all ? "全部 rw 段" : "镜像区");

    int found = 0;
    unsigned long long scanned = 0;
    for (int r = 0; r < g_nregs && found < 120; r++) {
        if (!g_regs[r].wr) continue;
        uintptr_t s = g_regs[r].lo, e = g_regs[r].hi;
        if (!all) {
            if (s < lo) s = lo;
            if (e > hi) e = hi;
            if (s >= e) continue;
        } else {
            // 单段最多扫 48MB，避免超大堆把时间拖爆
            if (e - s > 48ull * 1024 * 1024) e = s + 48ull * 1024 * 1024;
        }
        scanned += (e - s);
        uintptr_t a = (s + 3) & ~(uintptr_t)3;
        for (; a + LVL_N * 4 <= e && found < 120; a += 4) {
            int v0 = *(volatile int32_t *)a;
            if (v0 != 1) continue;
            int nz = 0, bad = 0;
            for (int i = 0; i < LVL_N; i++) {
                int v = *(volatile int32_t *)(a + i * 4);
                if (v < 0 || v > 3) { bad = 1; break; }
                if (v) nz++;
            }
            if (bad || nz > 2) continue;
            for (int i = LVL_N; i < LVL_N + 8; i++) {
                int v = *(volatile int32_t *)(a + i * 4);
                if (v != 0) { bad = 1; break; }
            }
            if (bad) continue;
            fprintf(o, "  [%02d] %p:", found, (void *)a);
            for (int i = 0; i < LVL_N; i++)
                fprintf(o, "%d", *(volatile int32_t *)(a + i * 4));
            fprintf(o, "  off=+%#lx\n", (unsigned long)(a - base));
            found++;
        }
    }
    fprintf(o, "共 %d 个候选，扫了 %llu MB。用 ulk <地址> 逐个试。\n",
            found, scanned >> 20);
}

// 把 at 开始的 n 个 int32 全写成 1（解锁）。写前逐个校验可写。
static void zf_unlock_levels(FILE *o, uintptr_t at, int n) {
    if (!g_img) { fprintf(o, "no img\n"); return; }
    if (n <= 0 || n > 64) n = LVL_N;
    if (!at || (at & 3u)) { fprintf(o, "地址非法 %p\n", (void *)at); return; }
    zf_snap_regions();
    if (!zf_writable(at, (unsigned)n * 4)) {
        fprintf(o, "不可写：%p +%d\n", (void *)at, n * 4);
        return;
    }
    fprintf(o, "写入前:");
    for (int i = 0; i < n; i++) fprintf(o, "%d", *(volatile int32_t *)(at + i * 4));
    fprintf(o, "\n");
    for (int i = 0; i < n; i++) *(volatile int32_t *)(at + i * 4) = 1;
    fprintf(o, "写入后:");
    for (int i = 0; i < n; i++) fprintf(o, "%d", *(volatile int32_t *)(at + i * 4));
    fprintf(o, "\n（回战役地图看是否解锁）\n");
}

// 列出当前关卡里所有建筑对象。
// 用途：确认「侏儒屋 / 精灵小屋 / 矮人堡垒 / 神庙」分别是哪个类型 ID，
// 以及它们之间是不是靠某个字段互斥的。
// 链表结构（见 HERO_LIST_VA 注释）：
//   容器 -> a -> sentinel -> first
//   节点 +0x10 = 单位对象；对象 +0x40 = 类型，+0x44 = 子类型/变体
static void zf_list_buildings(FILE *o) {
    if (!g_img) { fprintf(o, "no img\n"); return; }
    zf_snap_regions();
    uintptr_t b = (uintptr_t)g_img;
    uintptr_t cp = zf_rd(b + HERO_LIST_VA);
    uintptr_t aa = cp ? zf_rd(cp) : 0;
    uintptr_t sn = aa ? zf_rd(aa) : 0;
    uintptr_t nn = sn ? zf_rd(sn) : 0;
    if (!nn || nn == sn) { fprintf(o, "未进关卡（链表空）\n"); return; }
    int nodes = 0, nb = 0;
    while (nn && nn != sn && nodes < 4000) {
        uintptr_t obj = zf_rd(nn + 0x10);
        if (obj) {
            int t = zf_rd32(obj + 0x40);
            if (t >= 0x20 && t < 0x40) {
                nb++;
                if (nb <= 150)
                    fprintf(o, "  [%3d] obj=%p type=%#x sub=%#x xy=(%d,%d)\n",
                            nb, (void *)obj, t, zf_rd32(obj + 0x44),
                            zf_rd32(obj + 0x18), zf_rd32(obj + 0x1c));
            }
        }
        nn = zf_rd(nn);
        nodes++;
    }
    fprintf(o, "建筑 %d 个（链表节点 %d）\n", nb, nodes);
}

// ============================== 阵营互斥的绕过 ==============================
// 互斥到底在哪：
//   6 条提示 key 是镜像内嵌的（不是 translate.dat），镜像偏移：
//     0x44f7e8 shortCryptaAlreadyBuilt   0x44f800 shortAgrellaAlreadyBuilt
//     0x44f820 shortKrolmaAlreadyBuilt   0x44f838 shortDwarfWndAlreadyBuilt
//     0x44f858 shortElfBngAlreadyBuilt   0x44f870 shortHovelAlreadyBuilt
//   这些 key 只在 0x176e60 一处被 adrp+add 引用，而那是个「本地化字典初始化」
//   函数（bl 0x3c171 = std::string::assign，bl 0x42d0e5 = 字典 set），
//   代码里根本不再出现这些字符串 —— 判断走的是字典 handle / 数字 ID。
//   建筑类型大分派在镜像 0x46000 起，每种建筑自己的 handler 里走虚函数
//   （ldr x1,[x1,#8]; blr x1），**没有一个统一的 if (互斥) 可以 patch**。
// 所以这里不用 patch，用「改类型」：
//   把矮人阵营建筑（0x21 矮人要塞 / 0x22 侏儒屋）的类型临时写成民居 0x32，
//   游戏就认为场上没有矮人阵营 → 精灵小屋随便建；建完再恢复。
// ★ 记录的是对象地址，重启后地址会变，所以记录只在同一局内有效。
// ★ 副作用：类型被改期间，这些建筑按「民居」行事，矮人/侏儒相关加成失效。
//   想恢复就 camp on。
#define CAMP_MAX 32
static uintptr_t g_camp_obj[CAMP_MAX];
static int g_camp_orig[CAMP_MAX];
static int g_camp_n;
static int g_camp_auto;            // 1 = 永久模式：后台常驻维护，新造的自
                                   //     动纳入，不再需要手动 on/off

// ★★ 已停用（2026-10-26 事故）
//
// 原来的假设「0x21 = 矮人要塞、0x22 = 侏儒屋」是错的。
// 实测证据：玩家建了游侠公会和战士公会，永久模式把它们的类型改成 0x32 之后，
// 建筑面板标题变成了「英雄之家」（hHouse = 民居）。也就是说：
//     0x21 = 游侠公会  0x22 = 战士公会（或反之）
// 而 0x32 = hHouse = 民居。
// 当时 `bld` 复核也印证了：开启永久模式后场上 0x21/0x22 全部消失，0x32 多出两栋。
//
// 结论：自动改类型这条路从根上就是错的，它不会解除阵营互斥，
// 只会把玩家的英雄公会建筑变成普通民居。这里直接停用，永不再命中。
// 若还有历史误伤需要还原，仍可用 `camp on`（靠 g_camp_obj 里记的原值）。
#define CAMP_IS_EXCL(t) ((void)(t), 0)

// 永久模式的开关文件：存在 = 每次启动自动开启。
// 放在外部 files 目录，卸载重装会丢，但正常重启游戏不会。
#define ZF_CAMPFLAG \
    "/storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files/camp_auto.flag"

// 走一遍建筑链表，把 CAMP_IS_EXCL 命中的对象换成 0x32。
// 返回本次新改的栋数；already 返回累计记录数。
static int zf_camp_apply(int *already) {
    int fresh = 0;
    uintptr_t b = (uintptr_t)g_img;
    uintptr_t cp = zf_rd(b + HERO_LIST_VA);
    uintptr_t aa = cp ? zf_rd(cp) : 0;
    uintptr_t sn = aa ? zf_rd(aa) : 0;
    uintptr_t nn = sn ? zf_rd(sn) : 0;
    if (!nn || nn == sn) return 0;
    int nodes = 0;
    while (nn && nn != sn && nodes < 4000) {
        uintptr_t obj = zf_rd(nn + 0x10);
        if (obj) {
            int t = zf_rd32(obj + 0x40);
            if (CAMP_IS_EXCL(t)) {
                int seen = 0;
                for (int i = 0; i < g_camp_n; i++)
                    if (g_camp_obj[i] == obj) { seen = 1; break; }
                if (!seen && g_camp_n < CAMP_MAX && zf_writable(obj + 0x40, 4)) {
                    g_camp_obj[g_camp_n] = obj;
                    g_camp_orig[g_camp_n] = t;
                    *(volatile int32_t *)(obj + 0x40) = 0x32;
                    g_camp_n++;
                    fresh++;
                }
            }
        }
        nn = zf_rd(nn);
        nodes++;
    }
    if (already) *already = g_camp_n;
    return fresh;
}

// 永久模式的维护钩子，由 zh_cheat_tick 定期调用。
// ★ 已停用：CAMP_IS_EXCL 恒为假，这里保留空实现避免调用点改动。
static void zf_camp_tick(void) {
    (void)g_camp_auto;
}

// off=1 临时解除；off=0 恢复；auto=1 永久模式
// 永久模式的开关落在文件里，重启后自动恢复 —— 见 ZF_CAMPFLAG。
static void zf_camp(FILE *o, int off, int auto_mode) {
    if (!g_img) { fprintf(o, "no img\n"); return; }
    zf_snap_regions();
    if (auto_mode) {
        g_camp_auto = 0;
        remove(ZF_CAMPFLAG);
        fprintf(o, "永久模式已停用：类型认定错误，会把游侠公会/战士公会改成民居。\n"
                   "（0x21/0x22 是英雄公会，不是矮人阵营建筑）\n"
                   "已顺手删除开关文件，重启后不会再自动改。\n"
                   "若还有被误伤的建筑，执行 camp on 按记录还原。\n");
    } else if (off) {
        g_camp_auto = 0;
        remove(ZF_CAMPFLAG);
        g_camp_n = 0;
        int already = 0;
        int fresh = zf_camp_apply(&already);
        fprintf(o, "阵营限制已临时解除：改了 %d 栋\n"
                   "（现在可以建精灵小屋，建完记得执行 camp on）\n", fresh);
    } else {
        g_camp_auto = 0;
        remove(ZF_CAMPFLAG);
        int k = 0;
        for (int i = 0; i < g_camp_n; i++) {
            if (zf_writable(g_camp_obj[i] + 0x40, 4)) {
                *(volatile int32_t *)(g_camp_obj[i] + 0x40) = g_camp_orig[i];
                k++;
            }
        }
        fprintf(o, "已恢复 %d 栋，永久模式已关闭\n", k);
        g_camp_n = 0;
    }
}

// 扫「按建筑类型索引的计数表」。
// 思路：游戏判断「某类建筑是否已存在」最可能是查一张 by-type 的表。
// 先用当前关卡的建筑列表算出每种类型的真实数量 cnt[0x20..0x3f]，
// 再拿这个指纹去内存里找 —— 18 栋建筑的类型分布是很强的签名，
// 命中通常只有 0~2 个。
// 同时试 int32 计数表 和 byte 计数表 两种布局。
static void zf_scan_bflags(FILE *o) {
    if (!g_img) { fprintf(o, "no img\n"); return; }
    zf_snap_regions();

    int cnt[0x40];
    for (int i = 0; i < 0x40; i++) cnt[i] = 0;
    uintptr_t b = (uintptr_t)g_img;
    uintptr_t cp = zf_rd(b + HERO_LIST_VA);
    uintptr_t aa = cp ? zf_rd(cp) : 0;
    uintptr_t sn = aa ? zf_rd(aa) : 0;
    uintptr_t nn = sn ? zf_rd(sn) : 0;
    if (!nn || nn == sn) { fprintf(o, "未进关卡（链表空）\n"); return; }
    int nodes = 0, nb = 0;
    while (nn && nn != sn && nodes < 4000) {
        uintptr_t obj = zf_rd(nn + 0x10);
        if (obj) {
            int t = zf_rd32(obj + 0x40);
            if (t >= 0x20 && t < 0x40) { cnt[t]++; nb++; }
        }
        nn = zf_rd(nn);
        nodes++;
    }
    fprintf(o, "本关 %d 栋，类型分布:", nb);
    for (int t = 0x20; t < 0x40; t++) if (cnt[t]) fprintf(o, " %x=%d", t, cnt[t]);
    fprintf(o, "\n");

    // 挑两个探针下标做快速过滤：数量最多的那个 + 一个数量为 0 的
    int hi_t = 0x32, zero_t = -1;
    for (int t = 0x20; t < 0x40; t++) if (cnt[t] > cnt[hi_t]) hi_t = t;
    for (int t = 0x20; t < 0x40; t++) if (!cnt[t]) { zero_t = t; break; }
    if (zero_t < 0) zero_t = 0x20;
    fprintf(o, "探针: 最多=%#x(%d) 为零=%#x\n", hi_t, cnt[hi_t], zero_t);

    int found = 0;
    unsigned long long scanned = 0;
    const unsigned long long CAP = 48ull << 20;

    // ---- int32 布局 ----
    for (int r = 0; r < g_nregs && found < 24 && scanned < CAP; r++) {
        if (!g_regs[r].wr) continue;
        uintptr_t lo = g_regs[r].lo, hi = g_regs[r].hi;
        if (hi - lo > 48ull << 20) hi = lo + (48ull << 20);
        for (uintptr_t p = (lo + 3) & ~(uintptr_t)3; p + 0x100 < hi; p += 4) {
            scanned += 4;
            if (scanned > CAP) break;
            if (*(volatile int32_t *)(p + 4 * hi_t) != cnt[hi_t]) continue;
            if (*(volatile int32_t *)(p + 4 * zero_t) != 0) continue;
            int ok = 1;
            for (int t = 0x20; t < 0x40 && ok; t++)
                if (*(volatile int32_t *)(p + 4 * t) != cnt[t]) ok = 0;
            if (!ok) continue;
            found++;
            fprintf(o, "[i32 %d] %p 完全匹配\n", found, (void *)p);
        }
    }
    // ---- byte 布局 ----
    scanned = 0;
    for (int r = 0; r < g_nregs && found < 24 && scanned < CAP; r++) {
        if (!g_regs[r].wr) continue;
        if (cnt[hi_t] > 255) break;
        uintptr_t lo = g_regs[r].lo, hi = g_regs[r].hi;
        if (hi - lo > 48ull << 20) hi = lo + (48ull << 20);
        for (uintptr_t p = lo; p + 0x80 < hi; p += 1) {
            scanned += 1;
            if (scanned > CAP) break;
            if (*(volatile unsigned char *)(p + hi_t) != (unsigned char)cnt[hi_t]) continue;
            if (*(volatile unsigned char *)(p + zero_t) != 0) continue;
            int ok = 1;
            for (int t = 0x20; t < 0x40 && ok; t++)
                if (*(volatile unsigned char *)(p + t) != (unsigned char)cnt[t]) ok = 0;
            if (!ok) continue;
            found++;
            fprintf(o, "[u8  %d] %p 完全匹配\n", found, (void *)p);
        }
    }
    fprintf(o, "候选 %d 个，扫了 %llu MB\n", found, scanned >> 20);
}

// ---------------------------------------------------------------- 轻量命令通道
// 旧的 zf_run/zh_cmd 整段包在 #if ZF_DIAG 里，而那套 sigsetjmp 诊断实现
// 和后来基于 /proc/self/maps 的新实现重复定义，一开 ZF_DIAG 就编译不过。
// 这里另起一个精简通道，只用新的一套（zf_rd / zf_wr32 / zf_snap_regions）。
//   zhcmd.txt 写命令，结果看 zhout.txt
//     sl              扫描关卡解锁候选
//     ulk <hex> [n]   把 addr 起 n 个 int32 写成 1（默认 17）
#include <sys/stat.h>
#define ZF_DIR2 "/storage/emulated/0/Android/data/com.herocraft.game.majesty_ne/files"
#define ZF_CMD2 ZF_DIR2 "/zhcmd.txt"
#define ZF_OUT2 ZF_DIR2 "/zhout.txt"

// ---------------------------------------------------------------- 存档备份
// Android 11+ 之后 `adb backup` 基本废了，`/data/user/0/<pkg>` 没 root 也读不到。
// 但我们的 .so 就跑在 App 进程里（同一个 uid），读自己的私有目录完全没问题。
// 所以备份只能在进程内做：把私有目录递归拷到外部 files 下。
//   savedump          备份到 files/savebk/<时间戳>/
//   savedump <名字>    备份到 files/savebk/<名字>/
#include <dirent.h>
#include <time.h>

static int zf_copy_file(const char *src, const char *dst) {
    int fi = open(src, O_RDONLY);
    if (fi < 0) return -1;
    int fo = open(dst, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fo < 0) { close(fi); return -1; }
    char buf[16384];
    ssize_t r;
    int bad = 0;
    while (!bad && (r = read(fi, buf, sizeof(buf))) > 0) {
        ssize_t off = 0;
        while (off < r) {
            ssize_t w = write(fo, buf + off, (size_t)(r - off));
            if (w <= 0) { bad = 1; break; }
            off += w;
        }
    }
    close(fi);
    close(fo);
    return bad ? -1 : 0;
}

// 这些目录没必要备：缓存和 native 库都能重新生成
static int zf_skip_name(const char *n) {
    return !strcmp(n, "cache") || !strcmp(n, "code_cache") || !strcmp(n, "lib");
}

static void zf_dump_tree(const char *src, const char *dst, FILE *o,
                         int *files, long long *bytes, int depth) {
    if (depth > 12) return;
    DIR *d = opendir(src);
    if (!d) { fprintf(o, "  打不开 %s\n", src); return; }
    mkdir(dst, 0700);
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        if (zf_skip_name(e->d_name)) continue;
        char sp[512], dp[512];
        snprintf(sp, sizeof(sp), "%s/%s", src, e->d_name);
        snprintf(dp, sizeof(dp), "%s/%s", dst, e->d_name);
        struct stat st;
        if (stat(sp, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            zf_dump_tree(sp, dp, o, files, bytes, depth + 1);
        } else if (S_ISREG(st.st_mode)) {
            if (zf_copy_file(sp, dp) == 0) {
                (*files)++;
                *bytes += (long long)st.st_size;
                if (depth <= 1) fprintf(o, "  %s (%lld)\n", sp, (long long)st.st_size);
            } else {
                fprintf(o, "  拷贝失败 %s\n", sp);
            }
        }
    }
    closedir(d);
}

static void zf_save_dump(FILE *o, const char *name) {
    const char *pkg = "com.herocraft.game.majesty_ne";
    char src[256], dst[256], parent[256], stamp[64];
    snprintf(src, sizeof(src), "/data/user/0/%s", pkg);
    if (name && name[0]) {
        snprintf(stamp, sizeof(stamp), "%s", name);
    } else {
        time_t now = time(NULL);
        struct tm tmv;
        localtime_r(&now, &tmv);
        strftime(stamp, sizeof(stamp), "%Y%m%d_%H%M%S", &tmv);
    }
    snprintf(parent, sizeof(parent), "%s/savebk", ZF_DIR2);
    mkdir(parent, 0700);
    snprintf(dst, sizeof(dst), "%s/%s", parent, stamp);
    if (mkdir(dst, 0700) != 0) {
        fprintf(o, "建目录失败 %s\n", dst);
        return;
    }
    int files = 0;
    long long bytes = 0;
    zf_dump_tree(src, dst, o, &files, &bytes, 0);
    fprintf(o, "备份完成：%d 个文件，%lld 字节\n目标：%s\n", files, bytes, dst);
}

static void *zh_cmd2(void *arg) {
    (void)arg;
    sleep(10);
    unsigned long last = 0;
    int lastsz = -1;
    for (;;) {
        struct stat st;
        if (stat(ZF_CMD2, &st) == 0) {
            if ((unsigned long)st.st_mtime != last || (int)st.st_size != lastsz) {
                last = (unsigned long)st.st_mtime;
                lastsz = (int)st.st_size;
                char cmd[64] = {0};
                char arg[128] = {0};
                FILE *f = fopen(ZF_CMD2, "r");
                if (f) {
                    if (fgets(cmd, sizeof(cmd), f)) {
                        char *p = cmd;
                        while (*p && *p != ' ' && *p != '\n' && *p != '\r') p++;
                        if (*p == ' ') {
                            *p++ = 0;
                            strncpy(arg, p, sizeof(arg) - 1);
                            char *q = arg + strlen(arg);
                            while (q > arg && (q[-1] == '\n' || q[-1] == '\r')) *--q = 0;
                        } else {
                            *p = 0;
                        }
                    }
                    fclose(f);
                }
                FILE *o = fopen(ZF_OUT2, "w");
                if (o) {
                    if (!strcmp(cmd, "sl")) {
                        zf_scan_levels(o, arg[0] != 0);
                    } else if (!strcmp(cmd, "ulk")) {
                        uintptr_t at = (uintptr_t)strtoull(arg, NULL, 16);
                        int n = LVL_N;
                        const char *sp = strchr(arg, ' ');
                        if (sp && sp[1]) n = atoi(sp + 1);
                        zf_unlock_levels(o, at, n);
                    } else if (!strcmp(cmd, "ver")) {
                        fprintf(o, "libzhfont 关卡探查版\n");
                    } else if (!strcmp(cmd, "info")) {
                        fprintf(o, "base = %p\n", (void *)g_img);
                        if (g_img) {
                            uintptr_t b = (uintptr_t)g_img;
                            uintptr_t cp = zf_rd(b + HERO_LIST_VA);
                            uintptr_t aa = cp ? zf_rd(cp) : 0;
                            uintptr_t sn = aa ? zf_rd(aa) : 0;
                            uintptr_t nn = sn ? zf_rd(sn) : 0;
                            fprintf(o, "链表 容器=%p a=%p sentinel=%p first=%p\n",
                                    (void *)cp, (void *)aa, (void *)sn, (void *)nn);
                        }
                    } else if (!strcmp(cmd, "camp")) {
                        if (!strcmp(arg, "auto")) zf_camp(o, 0, 1);
                        else zf_camp(o, !strcmp(arg, "off"), 0);
                    } else if (!strcmp(cmd, "bscan")) {
                        zf_scan_bflags(o);
                    } else if (!strcmp(cmd, "bld")) {
                        zf_list_buildings(o);
                    } else if (!strcmp(cmd, "rd")) {
                        uintptr_t at = (uintptr_t)strtoull(arg, NULL, 16);
                        int n = 16;
                        const char *sp = strchr(arg, ' ');
                        if (sp && sp[1]) n = atoi(sp + 1);
                        if (n <= 0) n = 16;
                        if (n > 64) n = 64;
                        zf_snap_regions();
                        if (!zf_addr_ok(at, (unsigned)n * 4)) {
                            fprintf(o, "不可读 %p\n", (void *)at);
                        } else {
                            fprintf(o, "%p:\n", (void *)at);
                            for (int i = 0; i < n; i++) {
                                int v = *(volatile int32_t *)(at + i * 4);
                                fprintf(o, "  +%#04x = %d (%#x)\n", i * 4, v, v);
                            }
                        }
                    } else if (!strcmp(cmd, "w32")) {
                        uintptr_t at = (uintptr_t)strtoull(arg, NULL, 16);
                        const char *sp = strchr(arg, ' ');
                        int v = sp ? (int)strtol(sp + 1, NULL, 0) : 0;
                        zf_snap_regions();
                        if (!zf_writable(at, 4)) {
                            fprintf(o, "不可写 %p\n", (void *)at);
                        } else {
                            int old = *(volatile int32_t *)at;
                            *(volatile int32_t *)at = v;
                            fprintf(o, "%p: %d -> %d\n", (void *)at, old, v);
                        }
                    } else if (!strcmp(cmd, "settype")) {
                        // settype <x> <y> <type> [sub]
                        // 按格子坐标定位建筑再改类型，避免 bld 输出的对象地址
                        // 在几秒内失效（游戏会重排/重建对象）。
                        // ★ 改类型时务必同时给对 sub：只改 type 不动 sub，
                        //   游戏会按 (type, sub) 组合去查表，很容易越界闪退。
                        int x = 0, y = 0, t = 0, sub = -1;
                        if (sscanf(arg, "%d %d %d %d", &x, &y, &t, &sub) < 3) {
                            fprintf(o, "用法: settype <x> <y> <type> [sub]\n");
                        } else if (!g_img) {
                            fprintf(o, "no img\n");
                        } else {
                            zf_snap_regions();
                            uintptr_t b = (uintptr_t)g_img;
                            uintptr_t cp = zf_rd(b + HERO_LIST_VA);
                            uintptr_t aa = cp ? zf_rd(cp) : 0;
                            uintptr_t sn = aa ? zf_rd(aa) : 0;
                            uintptr_t nn = sn ? zf_rd(sn) : 0;
                            int hit = 0, nodes = 0;
                            while (nn && nn != sn && nodes < 4000) {
                                uintptr_t obj = zf_rd(nn + 0x10);
                                if (obj && zf_rd32(obj + 0x18) == x &&
                                    zf_rd32(obj + 0x1c) == y) {
                                    int ot = zf_rd32(obj + 0x40);
                                    int os = zf_rd32(obj + 0x44);
                                    if (zf_writable(obj + 0x40, 4)) {
                                        *(volatile int32_t *)(obj + 0x40) = t;
                                        if (sub >= 0 && zf_writable(obj + 0x44, 4))
                                            *(volatile int32_t *)(obj + 0x44) = sub;
                                        fprintf(o, "obj=%p (%d,%d) type %#x -> %#x",
                                                (void *)obj, x, y, ot, t);
                                        if (sub >= 0) fprintf(o, " sub %#x -> %#x", os, sub);
                                        fprintf(o, "\n");
                                        hit++;
                                    }
                                }
                                nn = zf_rd(nn);
                                nodes++;
                            }
                            if (!hit) fprintf(o, "没找到坐标 (%d,%d)\n", x, y);
                        }
                    } else {
                        fprintf(o, "未知命令 [%s] arg=[%s]\n", cmd, arg);
                    }
                    fclose(o);
                    logf_("命令 [%s] 已执行", cmd);
                }
            }
        }
        sleep(1);
    }
    return NULL;
}

static uintptr_t zf_rd(uintptr_t a) {
    // ARM64 top-byte tag：0xb4000079xxxxxxxx，硬件读时会忽略高字节，
    // 但区间表比对必须先去 tag，否则永远判定「不可读」。
    a &= 0x00FFFFFFFFFFFFFFull;
    if (!zf_addr_ok(a, 8)) return 0;
    return *(volatile uintptr_t *)a & 0x00FFFFFFFFFFFFFFull;
}

static int zf_rd32(uintptr_t a) {
    return zf_addr_ok(a, 4) ? *(volatile int32_t *)a : 0;
}

static int zf_rd8(uintptr_t a) {
    return zf_addr_ok(a, 1) ? *(volatile unsigned char *)a : 0;
}

static void zf_wr32(uintptr_t a, int v) {
    if (zf_addr_ok(a, 4)) *(volatile int32_t *)a = v;
}

static void zf_wr8(uintptr_t a, int v) {
    if (zf_addr_ok(a, 1)) *(volatile unsigned char *)a = (unsigned char)v;
}

// 目标值。想调整只改这几个数字。
#define HERO_MAX_WANT  99      // 全局英雄上限（原版 20，作弊「更多英雄」= 40）
// ★ 建筑容量不能乱放大：游戏内部按初始容量定长分配英雄槽位数组，
//   容量字段只是「允许多少」，不会扩数组，超了就是越界写 → 闪退。
//   游戏自己的「扩建公会」也只给到 8，这里取同一个上限。
#define HERO_CAP_WANT  8       // 每栋建筑可容纳英雄数（原版 2~4）
#define CRYSTAL_WANT   999     // 水晶（钻石）固定值
#define BLD_MAX_WANT   99      // 全局建筑数量上限（顶栏 20/30 的那个 30）
// 0x53b300 是指针槽，指向的 int32 正好是「英雄上限指针 + 4」，
// 也就是同一个 limits 结构体里的第二项 —— 建筑数量上限。

static volatile int g_hero_tick;
static volatile int g_hero_log_n;
static volatile int g_bld_log_n;
static volatile int g_vet_log_n;
static volatile int g_new_log_n;
static volatile int g_dbg_dump;
static volatile int g_dia_probe;
static volatile int g_dia_log_n;

// 老兵升级队列：单生产者（作弊线程）/ 单消费者（渲染线程）。
// 用队列而不是单个变量，是因为进新关卡时可能同时冒出一批「新英雄」，
// 单槽会被后来者覆盖，只有一个能升。
// （g_vq / g_vq_h / g_vq_t 已在 zh_on_hero 之前定义）
static void zf_vq_push(uintptr_t o) {
    int nt = (g_vq_t + 1) % VQ_MAX;
    if (nt == g_vq_h) return;              // 满了就丢，下一轮扫描还会补
    g_vq[g_vq_t] = o;
    g_vq_t = nt;
}

// 把一个单位直接升到 target 级（复用游戏自己的升级函数，属性由它重算）
// ★ 只在渲染线程调用（zh_on_hero 里消费队列），和「点问号升级」同一条线程。
static void zf_level_to(uintptr_t obj, int target) {
    if (!g_img) return;
    int lv = zf_ld32(obj + LV_LEVEL);
    int cap = zf_ld32(obj + LV_CAP);
    if (cap < 1 || cap > 200) return;
    if (target > cap) {
        // 新兵的等级上限可能只有 10，不抬上去就升不到 99。
        // 0x13c654 开头就是 `w2=[x0+0x290]; b.ge -> return`，写这个字段就能放开。
        *(volatile int32_t *)(obj + LV_CAP) = target;
    }
    int want = target - lv;
    if (want < 1) return;
    int xp = zf_ld32(obj + 0x268);
    int sp = zf_ld32(obj + 0x270);
    int avail = xp - sp;
    if (avail < 0) avail = 0;
    int T = avail / want;
    if (T < UP_FINAL_TH) T = UP_FINAL_TH;
    if (T > 100000) T = 100000;
    while (T > UP_FINAL_TH && avail / T > want) T++;
    int need = want * T;
    int w1 = 0;
    if (avail < need) w1 = (need - avail) * (lv > 0 ? lv : 1);
    *(volatile int32_t *)(obj + LV_TH) = T;
    ((fn_lvup)(g_img + LVFN_OFF))((void *)obj, w1);
    if (zf_inreg(obj + LV_TH)) *(volatile int32_t *)(obj + LV_TH) = UP_FINAL_TH;
    if (g_vet_log_n < 30) {
        g_vet_log_n++;
        logf_("老兵生效：%p %d -> %d 级（血上限 %d）", (void *)obj, lv,
              zf_ld32(obj + LV_LEVEL), zf_ld32(obj + 0xd8));
    }
}

// 英雄判定：类型在可升级集合内 + 生命/等级上限/升级门槛都合理
// ★ 这个函数会被作弊线程调用，只能读 zf_rd32（maps 快照），不能读 zf_ld32。
static int zf_is_hero(uintptr_t obj) {
    int ty = zf_rd32(obj + 0x40);
    if (!((ty >= 1 && ty <= 9) || ty == 0x141)) return 0;
    int hm = zf_rd32(obj + 0xd8);
    if (hm < 5 || hm > 20000) return 0;
    int hp = zf_rd32(obj + 0xd4);
    if (hp < 1 || hp > hm) return 0;              // 血量为 0 = 已死/不是活单位
    int cap = zf_rd32(obj + LV_CAP);
    if (cap < 1 || cap > 200) return 0;
    int th = zf_rd32(obj + LV_TH);
    if (th < 1 || th > 1000000) return 0;         // 怪物一般没有升级门槛
    if (zf_rd(obj) < 0x1000) return 0;            // 首 8 字节应是有效指针
    return 1;
}

// 临时诊断：找「建筑数量上限」所在的字段。
// 顶栏显示 20/30 —— 当前 20 栋、上限 30。扫描全局数据区里值为 30 的 int32
// 每约 2 秒复查一次：上限被游戏重置、或者新建了公会建筑，都能自动补上。
static void zh_hero_apply(uintptr_t base) {
    if (++g_hero_tick < 7) return;          // 300ms × 7 ≈ 2s
    g_hero_tick = 0;
    zf_snap_regions();

    // ① 全局上限：base+0x53df88 是指针槽，指向真正的 int32
    uintptr_t pmax = zf_rd(base + HERO_MAX_VA);
    if (pmax && zf_addr_ok(pmax, 4)) {
        int cur = zf_rd32(pmax);
        if (cur != HERO_MAX_WANT) {
            *(volatile int32_t *)pmax = HERO_MAX_WANT;
            if (g_hero_log_n < 30) {
                g_hero_log_n++;
                logf_("英雄上限 %d -> %d（槽 %p）", cur, HERO_MAX_WANT, (void *)pmax);
            }
        }
    }

    // ①b 全局建筑数量上限（顶栏 20/30 的那个 30）
    // ★★ 血泪教训：不要拿 objdump 反汇编出来的 adrp 目标当运行时偏移用！
    //   objdump 把整个 bin 当成 offset 0 的 .text，它显示的 `adrp x0, 0x53f000`
    //   是「相对文件/段起点」的地址，而运行时 = base + 镜像偏移，
    //   两者差 0x4E01 且 adrp 还做了页对齐，换算后：
    //       ELF 0x53f000  ->  运行时 base+0x53B000
    //       ELF 0x540000  ->  运行时 base+0x53B000
    //   也就是说 0x69168 和 0xafe9c 读的**就是** base+0x53bce8 / base+0x53b300，
    //   和 zf 一直用的地址完全一致。我一度以为有「三组别名槽」，
    //   照着 ELF 数字去写 0x53f300 / 0x540300，结果
    //   `*(base+0x540300)` 是个垃圾指针，往 0x79691c79b7 写了 99 → 游戏黑屏。
    //   这里只保留唯一经过运行时验证的那组，并且写入前做严格校验。
    {
        uintptr_t pbl = zf_rd(base + BLD_MAX_VA);
        if (pbl && (pbl & 3u) == 0 && zf_addr_ok(pbl, 4) && zf_writable(pbl, 4)) {
            int cur = zf_rd32(pbl);
            if (cur != BLD_MAX_WANT && cur >= 0 && cur < 100000) {
                *(volatile int32_t *)pbl = BLD_MAX_WANT;
                if (g_bld_log_n < 30) {
                    g_bld_log_n++;
                    logf_("建筑上限 %d -> %d（%p）", cur, BLD_MAX_WANT, (void *)pbl);
                }
            }
        }
    }

    // ② 老兵：勾选时，新雇的英雄直接升到 99 级
    uintptr_t sing = base + CHT_SING_VA;
    uintptr_t carr = zf_rd8(sing + 0x10) ? zf_rd(sing + 8) : 0;
    int vet = (g_keep_mask & 4u) || (carr ? zf_rd8(carr + 2) : 0);

    // ③ 建筑容量 + 老兵升级，都要遍历单位链表
    // 老兵基线（跨轮保持）
    static uintptr_t base_h[512];
    static int base_hn, hs_init, hs_last_n, hs_stable;
    uintptr_t c = zf_rd(base + HERO_LIST_VA);
    uintptr_t a = c ? zf_rd(c) : 0;
    uintptr_t sent = a ? zf_rd(a) : 0;
    uintptr_t n = sent ? zf_rd(sent) : 0;
    if (!n || n == sent) {                  // 还没进关卡 / 已经离开关卡
        hs_init = 0;                        // 基线作废，下次进关卡重新取
        return;
    }
    int seen = 0, bld = 0, changed = 0, vetup = 0;
    int hist[64];                    // 建筑类型直方图，用来确认「集市/精灵小屋」是哪个 id
    memset(hist, 0, sizeof(hist));

    // 本轮的英雄集合
    static uintptr_t hs[192];
    int hs_n = 0;

    // 节点上限给足：一关里英雄 + 建筑 + 怪物 + 掉落物很容易上千，
    // 原来 600 会在链表尾部截断，导致「刚雇的英雄」永远扫不到。
    while (n && n != sent && seen < 4000) {
        uintptr_t obj = zf_rd(n + 0x10);
        if (obj) {
            int t = zf_rd32(obj + 0x40);
            if (t >= 0x20 && t < 0x40) hist[t]++;      // 只统计建筑类型
            if ((t >= 0x21 && t <= 0x26) || t == 0x2b || t == 0x2c) {
                int cap = zf_rd32(obj + 0x1fc);
                bld++;
                if (cap > 0 && cap < 200 && cap != HERO_CAP_WANT) {
                    *(volatile int32_t *)(obj + 0x1fc) = HERO_CAP_WANT;
                    changed++;
                }
            }
            if (zf_is_hero(obj)) {
                if (hs_n < 192) hs[hs_n++] = obj;
            }
        }
        n = zf_rd(n);
        seen++;
    }

    // 收入探针：每约 40 秒打一次「建筑类型分布 + 金币」，
    // 建第二座集市/精灵小屋前后对比这两行就能判断到底叠不叠加。
    {
        static int prn;
        if (++prn >= 20 && bld > 0) {
            prn = 0;
            uintptr_t gp = zf_rd(base + 0x53c040u);
            int g = gp ? zf_rd32(gp) : -1;
            char buf[320];
            int p = 0;
            for (int i = 1; i < 64 && p < 260; i++)
                if (hist[i]) p += snprintf(buf + p, sizeof(buf) - p, "%#x×%d ", i, hist[i]);
            logf_("建筑分布: %s| 金币 %d | 节点 %d", buf, g, seen);
        }
    }

    // 老兵：把「本进程内第一次见到的英雄」排队升级。
    //   ★ 不能再用「等级 == 1」判定 —— 游戏自己的老兵效果会让新兵一开始就是 5 级。
    //   ★ 读档时英雄是分批冒出来的（实测基线 34 个，之后 20 秒内又冒出 1+6 个），
    //     所以不能「第一次扫到就定基线」。改成：数量连续稳定 3 轮才锁定基线，
    //     这之前每一轮都把基线重建成当前列表（谁都不升）。
    //   ★ 离开关卡（列表清空）后把基线作废，下次进关卡重新取。
    {
        if (hs_n == hs_last_n) { if (hs_stable < 100) hs_stable++; } else hs_stable = 0;
        hs_last_n = hs_n;
        if (hs_stable >= 3 && g_seen_load) g_level_loaded = 1;

        if (hs_n == 0) {
            hs_init = 0;                       // 场上一时没英雄，基线作废重来
        } else if (!hs_init) {
            // 载入中：每轮把基线重建成当前列表，顺便等它稳定
            base_hn = 0;
            for (int i = 0; i < hs_n && base_hn < 512; i++) base_h[base_hn++] = hs[i];
            if (hs_stable >= 3) {
                hs_init = 1;
                g_seen_load = 1;
                logf_("老兵：基线锁定 %d 个英雄（已有英雄不升级）", hs_n);
            }
        } else {
            uintptr_t fresh[8];
            int fresh_n = 0, newn = 0;
            for (int i = 0; i < hs_n; i++) {
                uintptr_t h = hs[i];
                int f = 0;
                for (int j = 0; j < base_hn; j++) if (base_h[j] == h) { f = 1; break; }
                if (f) continue;
                if (base_hn < 512) base_h[base_hn++] = h;
                if (fresh_n < 8) fresh[fresh_n++] = h;
                newn++;
            }
            if (newn > 0) {
                if (!vet) {
                    if (g_new_log_n < 20) {
                        g_new_log_n++;
                        logf_("新英雄 %p（lv=%d）：老兵未勾选，跳过", (void *)fresh[0],
                              zf_rd32(fresh[0] + LV_LEVEL));
                    }
                } else {
                    for (int i = 0; i < fresh_n; i++) {
                        zf_vq_push(fresh[i]);
                        vetup++;
                        if (g_vet_log_n < 40) {
                            g_vet_log_n++;
                            logf_("老兵投递：新英雄 %p（lv=%d）待升 99", (void *)fresh[i],
                                  zf_rd32(fresh[i] + LV_LEVEL));
                        }
                    }
                }
            }
        }
    }

#if ZF_VET_SELFTEST
    // 自测：拿场上第一个英雄走一遍「投递 → 渲染线程升级」，验证链路通不通
    {
        static int st_done;
        if (!st_done && hs_n > 0) {
            st_done = 1;
            zf_vq_push(hs[0]);
            logf_("★ 自测：把 %p（lv=%d）推入升级队列", (void *)hs[0],
                  zf_rd32(hs[0] + LV_LEVEL));
        }
    }
#endif
    if (changed && g_hero_log_n < 30) {
        g_hero_log_n++;
        logf_("建筑容量：扫到 %d 个建筑，改写 %d 个（共 %d 个节点）", bld, changed, seen);
    }
    (void)vetup;

    // ④ 水晶（钻石）固定 999
    // 扣费函数 0x11f6b4 里 `ldr w3,[x0,#0xf8]` 就是当前水晶数，
    // x0 = *(*(base+0x53d678)) —— 玩家/资源对象。
    // 注意这是【有符号】比较（b.le），所以价格 -1 也能过校验并倒贴，
    // 但直接补满更省事，不需要手动点购买。
    uintptr_t pmgr = zf_rd(base + 0x53d678u);
    uintptr_t player = pmgr ? zf_rd(pmgr) : 0;
    if (player && zf_addr_ok(player + 0xf8, 4)) {
        int cv = zf_rd32(player + 0xf8);
        if (cv < CRYSTAL_WANT) {
            *(volatile int32_t *)(player + 0xf8) = CRYSTAL_WANT;
            if (g_dia_log_n < 20) {
                g_dia_log_n++;
                logf_("水晶 %d -> %d（%p+0xf8）", cv, CRYSTAL_WANT, (void *)player);
            }
        }
    }
}

// 常驻线程：等镜像映射出来，然后每 300ms 复查一次
static void *zh_cheat(void *arg) {
    (void)arg;
    uintptr_t base = 0;
    while (!base) {
        base = find_image();
        if (!base) usleep(100 * 1000);
    }
    for (;;) {
        zh_cheat_tick(base);
        usleep(300 * 1000);
    }
    return NULL;
}
#endif  // ZF_CHEAT（作弊功能整段结束）

// 装钩子（引擎镜像映射之后才能做）
//
#if ZF_CHEAT
// ===== 建造数量上限硬绕过 =====
// 镜像里只有两处代码读「建筑数量上限」字段（xref2.py 全量扫过，见下），
// 两处逻辑完全一样：
//
//   (A) 0x69168                          (B) 0xafe9c
//   adrp x1, #0x53b000                   adrp x3, #0x53b000
//   ldr  x1, [x1, #0xce8]  ; 当前数       adrp x2, #0x53b000
//   ldr  x0, [x0, #0x300]  ; 上限         ldr  x3, [x3, #0xce8]  ; 当前数
//   ldr  w1, [x1]                        ldr  x2, [x2, #0x300]  ; 上限
//   ldr  w0, [x0]                        ldr  w3, [x3]
//   cmp  w1, w0                          ldr  w2, [x2]
//   b.lt 0x67e1c   ← 允许               cmp  w3, w2
//   否则弹 shortTxtMaxBuildings          b.lt 0xafe88   ← 允许（返回 1）
//                                        否则走类型范围判断 + 跳转表
//
// ★ 实测教训：一开始只 patch 了 (A)，日志确实打出「已绕过」，但玩家点「新建」
//   依旧弹「已达游戏内建筑数量上限」。建筑数从 33 涨到 34 是游戏自己造的英雄
//   小屋，不是玩家建的。说明 UI 建造面板走的是 (B)，(A) 是 AI/自动建造用的。
//
// 两处都把条件跳转改成无条件跳转。为什么不担心越界：
//   英雄槽位（obj+0x208）是定长分配，写超会 SIGSEGV（踩过，上限只能 8）；
//   但建筑列表是动态链表（头在 base+0x53d980），节点 malloc 出来的，
//   数量本身不构成越界。
// 上限字段仍然由 zf 维持在 99，只是检查本身不再拦人。
//
// 另外确认过：全镜像里没有任何 `str w?, [x?, #0x300]` 指令，
// 说明「上限被写回 30」不是某条指令干的，而是配置对象被整块重建/覆盖，
// 所以靠 300ms 轮询永远存在窗口，必须从检查侧下手。
typedef struct {
    uint32_t off;    // 镜像偏移
    uint32_t want;   // 原始指令
    uint32_t repl;   // 替换指令
    const char *tag;
} bldpatch_t;

static const bldpatch_t kBldPatches[] = {
    // b.lt 0x6cc1d  ->  b 0x6cc1d        永远走「允许」路径
    {0x69184u, 0x54ff64cbu, 0x17fffb26u, "0x69184 (自动建造)"},
    // b.ge 0xb4c89  ->  b 0xb4c99        「当前 >= 上限」不再直接拒绝，
    //                                    而是继续走后面的类型判断（保留原语义，
    //                                    等价于「上限 = 无穷大」，不会误放开）
    {0xafebcu, 0x54fffe6au, 0x17fffff7u, "0xafebc (UI 建造面板)"},
};

static void zh_patch_bldcheck(uintptr_t base) {
    int n = (int)(sizeof(kBldPatches) / sizeof(kBldPatches[0]));
    for (int i = 0; i < n; i++) {
        uintptr_t at = base + kBldPatches[i].off;
        uintptr_t pg = at & ~(uintptr_t)0xfff;
        if (mprotect((void *)pg, 0x2000, PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
            logf_("建造检查 patch %s：mprotect 失败", kBldPatches[i].tag);
            continue;
        }
        uint32_t old = *(volatile uint32_t *)at;
        if (old == kBldPatches[i].want) {
            *(volatile uint32_t *)at = kBldPatches[i].repl;
            __builtin___clear_cache((char *)at, (char *)at + 4);
            logf_("建造上限检查已绕过 %s", kBldPatches[i].tag);
        } else {
            logf_("建造检查 patch %s：原指令不匹配 %08x（跳过）",
                  kBldPatches[i].tag, old);
        }
    }
}
#endif  // ZF_CHEAT（建造上限 patch 结束）

static int install_hook(uintptr_t base) {    g_img = (unsigned char *)base;
    logf_("img base = %p", g_img);
    int ok = 0;
    // 这两个是翻译的核心：引擎的 DrawText 有两个副本，都得挂。
    ok += patch_site(base, DRAW_VA, zh_handler0, &g_tramp0);
    ok += patch_site(base, DRAW_VA2, zh_handler1, &g_tramp1);
#if ZF_CHEAT
    ok += patch_site(base, LABEL_VA, zh_handler2, &g_tramp2);
    ok += patch_site(base, UNIT_VA, zh_h_unit, &g_tramp_u);
    zh_patch_bldcheck(base);
    // 实验钩子（GetInt/GetX/GetY）会干扰输入导致游戏退出，正式版不启用
    // { uintptr_t sb = zf_modbase("libs3e_android.so"); if (sb) install_ptr_probe(sb); }
    install_evt_hook(base);
#endif
    return ok > 0;
}

// 后台线程：等引擎镜像映射出来再装钩子
// （DT_INIT 在进程启动时执行，此时 s3e 镜像还没解压映射）
static void *zh_poll(void *arg) {
    (void)arg;
    for (int i = 0; i < 1200; i++) {          // 最多等 60 秒
        uintptr_t base = find_image();
        if (base) {
            if (install_hook(base)) return NULL;
        }
        usleep(50 * 1000);                     // 50ms
    }
    logf_("等待镜像超时");
    return NULL;
}

__attribute__((constructor)) static void zh_start(void) {
    logf_("=== libzhfont start ===");
    zf_guard_install();         // 安全读需要先装好 SIGSEGV/SIGBUS 兜底

    const unsigned char *b = _binary_zhfont_subset_ttf_start;
    size_t n = (size_t)(_binary_zhfont_subset_ttf_end - _binary_zhfont_subset_ttf_start);
    if (stbtt_InitFont(&g_info, b, stbtt_GetFontOffsetForIndex(b, 0))) {
        g_font_ok = 1;
        logf_("TTF ok, %zu bytes", n);
    } else {
        logf_("TTF 解析失败 (%zu bytes)", n);
    }

    pthread_t th;
#if ZF_CHEAT
    if (pthread_create(&th, NULL, zh_cheat, NULL) == 0) pthread_detach(th);
#endif
    if (pthread_create(&th, NULL, zh_poll, NULL) == 0) {
        pthread_detach(th);
    } else {
        logf_("线程创建失败，同步尝试");
        uintptr_t base = find_image();
        if (base) install_hook(base);
    }
#if ZF_CHEAT
    // 阵营互斥「永久模式」已停用（类型认定错误，会破坏游侠公会/战士公会）。
    // 即使上次留下了开关文件，也不再自动开启；这里顺手把它删掉。
    {
        FILE *cf = fopen(ZF_CAMPFLAG, "r");
        if (cf) {
            fclose(cf);
            remove(ZF_CAMPFLAG);
            logf_("检测到旧的阵营永久模式开关，已删除并停用");
        }
    }
    if (pthread_create(&th, NULL, zh_cmd2, NULL) == 0) pthread_detach(th);
#if ZF_DIAG
    if (pthread_create(&th, NULL, zh_cmd, NULL) == 0) pthread_detach(th);
#endif
#endif  // ZF_CHEAT
}
