// zhbtn.h —— 屏幕叠加按钮（GLES2 自绘）
// 被 zhfont.c 在 install_hook 之前 #include。
// 依赖：logf_ / patch_addr / p_gl* 指针 / g_s3e_base

#include <math.h>

// ---------------------------------------------------------------- 按钮几何
// 屏幕物理分辨率 2400x1080；「问号」按钮中心 (1042,248)，下一个按钮在 y=698。
// 新按钮放在两者之间的空档。
#define BTN_CX   1042
#define BTN_CY   400
#define BTN_R    78
#define BTN_TEX  128

// ---------------------------------------------------------------- 额外 GL 符号
typedef unsigned (*fn_createsh)(unsigned);
typedef void     (*fn_shadersrc)(unsigned, int, const char **, const int *);
typedef void     (*fn_shader1)(unsigned);
typedef void     (*fn_getiv)(unsigned, int, int *);
typedef unsigned (*fn_createprog)(void);
typedef void     (*fn_attach)(unsigned, unsigned);
typedef void     (*fn_link)(unsigned);
typedef void     (*fn_useprog)(unsigned);
typedef int      (*fn_getattr)(unsigned, const char *);
typedef void     (*fn_enableva)(unsigned);
typedef void     (*fn_vertexap)(unsigned, int, int, unsigned char, int, const void *);
typedef void     (*fn_genbuf)(int, unsigned *);
typedef void     (*fn_bindbuf)(int, unsigned);
typedef void     (*fn_bufdata)(int, long, const void *, int);
typedef void     (*fn_drawarr)(int, int, int);
typedef void     (*fn_viewport)(int, int, int, int);
typedef void     (*fn_void1)(int);
typedef unsigned char (*fn_isen)(int);
typedef void     (*fn_uni1i)(int, int);
typedef void     (*fn_uni2f)(int, float, float);
typedef int      (*fn_getuni)(unsigned, const char *);
typedef void     (*fn_blendfunc)(int, int);

static fn_createsh   p_glCreateShader;
static fn_shadersrc  p_glShaderSource;
static fn_shader1    p_glCompileShader;
static fn_getiv      p_glGetShaderiv;
static fn_createprog p_glCreateProgram;
static fn_attach     p_glAttachShader;
static fn_link       p_glLinkProgram;
static fn_getiv      p_glGetProgramiv;
static fn_useprog    p_glUseProgram;
static fn_getattr    p_glGetAttribLocation;
static fn_enableva   p_glEnableVertexAttribArray;
static fn_vertexap   p_glVertexAttribPointer;
static fn_genbuf     p_glGenBuffers;
static fn_gen        p_glGenTextures;
static fn_bindbuf    p_glBindBuffer;
static fn_bufdata    p_glBufferData;
static fn_drawarr    p_glDrawArrays;
static fn_viewport   p_glViewport;
static fn_void1      p_glEnable;
static fn_void1      p_glDisable;
static fn_isen       p_glIsEnabled;
static fn_void1      p_glActiveTexture;
static fn_uni1i      p_glUniform1i;
static fn_uni2f      p_glUniform2f;
static fn_getuni     p_glGetUniformLocation;
static fn_blendfunc  p_glBlendFunc;
static unsigned (*p_glGetError)(void);

#define GL_VSHADER      0x8B31
#define GL_FSHADER      0x8B30
#define GL_COMPILE_OK   0x8B81
#define GL_LINK_OK      0x8B82
#define GL_ARRAYBUF     0x8892
#define GL_STATICDRAW   0x88E4
#define GL_TRISTRIP     0x0005
#define GL_FLOAT_T      0x1406
#define GL_CURPROG      0x8B8D
#define GL_ACTIVETEX    0x84E0
#define GL_ARRAYBUFBIND 0x8894
#define GL_VIEWPORT     0x0BA2
#define GL_BLEND_E      0x0BE2
#define GL_DEPTH_E      0x0B71
#define GL_SCISSOR_E    0x0C11
#define GL_CULL_E       0x0B44
#define GL_SRCALPHA     0x0302
#define GL_1MSRCALPHA   0x0303
#define GL_TEX0         0x84C0

static unsigned g_bprog, g_bvbo, g_btex;
static int g_ba_pos = -1, g_ba_uv = -1, g_bu_res = -1, g_bu_tex = -1;
static int g_bok, g_bfail;
static unsigned char g_bpx[BTN_TEX * BTN_TEX * 4];
static volatile unsigned g_bdraws;

static void zh_btn_gl(void) {
    if (p_glCreateShader) return;
    void *h = dlopen("libGLESv2.so", RTLD_NOW);
    if (!h) h = dlopen("libGLESv2_angle.so", RTLD_NOW);
    if (!h) { logf_("按钮: 无 libGLESv2"); return; }
#define BL(n) p_##n = (void *)dlsym(h, #n)
    BL(glCreateShader); BL(glShaderSource); BL(glCompileShader); BL(glGetShaderiv);
    BL(glCreateProgram); BL(glAttachShader); BL(glLinkProgram); BL(glGetProgramiv);
    BL(glUseProgram); BL(glGetAttribLocation); BL(glEnableVertexAttribArray);
    BL(glVertexAttribPointer); BL(glGenBuffers); BL(glGenTextures); BL(glBindBuffer); BL(glBufferData);
    BL(glDrawArrays); BL(glViewport); BL(glEnable); BL(glDisable); BL(glIsEnabled);
    BL(glActiveTexture); BL(glUniform1i); BL(glUniform2f); BL(glGetUniformLocation);
    BL(glBlendFunc); BL(glGetError);
#undef BL
}

// 程序化生成按钮贴图：金环 + 深蓝径向渐变 + 白色向上箭头
static void zh_btn_mktex(void) {
    const int C = BTN_TEX / 2;
    const float R = C - 2.0f;
    const float RIN = R - 9.0f;
    for (int y = 0; y < BTN_TEX; y++) {
        for (int x = 0; x < BTN_TEX; x++) {
            float dx = (float)x - (C - 0.5f);
            float dy = (float)y - (C - 0.5f);
            float r = sqrtf(dx * dx + dy * dy);
            unsigned char *p = g_bpx + ((size_t)y * BTN_TEX + x) * 4;
            int rr = 0, gg = 0, bb = 0, aa = 0;
            if (r <= R) {
                if (r > RIN) {
                    float k = 1.0f - (r - RIN) / (R - RIN);
                    rr = (int)(110 + 145 * k);
                    gg = (int)(82 + 138 * k);
                    bb = (int)(22 + 96 * k);
                } else {
                    float t = r / RIN;
                    rr = (int)(8 + 26 * (1 - t));
                    gg = (int)(24 + 74 * (1 - t));
                    bb = (int)(58 + 150 * (1 - t));
                }
                aa = 255;
                int in = 0;
                if (y >= 30 && y <= 60) {
                    float half = (y - 30) * (20.0f / 30.0f);
                    if (fabsf((float)x - (C - 0.5f)) <= half) in = 1;
                }
                if (y > 60 && y <= 92 && x >= C - 9 && x <= C + 8) in = 1;
                if (in) { rr = 244; gg = 250; bb = 255; }
            }
            p[0] = (unsigned char)rr;
            p[1] = (unsigned char)gg;
            p[2] = (unsigned char)bb;
            p[3] = (unsigned char)aa;
        }
    }
}

static unsigned zh_mkshader(unsigned type, const char *src) {
    unsigned s = p_glCreateShader(type);
    if (!s) return 0;
    p_glShaderSource(s, 1, &src, NULL);
    p_glCompileShader(s);
    int ok = 0;
    p_glGetShaderiv(s, GL_COMPILE_OK, &ok);
    if (!ok) logf_("按钮: shader 编译失败 type=%#x", type);
    return ok ? s : 0;
}

static const char *BTN_VS =
    "attribute vec2 aPos;\n"
    "attribute vec2 aUV;\n"
    "uniform vec2 uRes;\n"
    "varying vec2 vUV;\n"
    "void main(){\n"
    "  vec2 p = aPos / uRes * 2.0 - 1.0;\n"
    "  gl_Position = vec4(p.x, -p.y, 0.0, 1.0);\n"
    "  vUV = aUV;\n"
    "}\n";

static const char *BTN_FS =
    "precision mediump float;\n"
    "varying vec2 vUV;\n"
    "uniform sampler2D uTex;\n"
    "void main(){ gl_FragColor = vec4(1.0,0.0,0.0,1.0); }\n";

static int zh_btn_init(void) {
    if (g_bok) return 1;
    if (g_bfail) return 0;
    zh_btn_gl();
    if (!p_glCreateShader || !p_glCreateProgram) { g_bfail = 1; logf_("按钮: 无 shader API（可能是 GLES1）"); return 0; }
    unsigned vs = zh_mkshader(GL_VSHADER, BTN_VS);
    unsigned fs = zh_mkshader(GL_FSHADER, BTN_FS);
    if (!vs || !fs) { g_bfail = 1; return 0; }
    unsigned pr = p_glCreateProgram();
    p_glAttachShader(pr, vs);
    p_glAttachShader(pr, fs);
    p_glLinkProgram(pr);
    int ok = 0;
    p_glGetProgramiv(pr, GL_LINK_OK, &ok);
    if (!ok) { g_bfail = 1; logf_("按钮: link 失败"); return 0; }
    g_bprog = pr;
    g_ba_pos = p_glGetAttribLocation(pr, "aPos");
    g_ba_uv  = p_glGetAttribLocation(pr, "aUV");
    g_bu_res = p_glGetUniformLocation(pr, "uRes");
    g_bu_tex = p_glGetUniformLocation(pr, "uTex");

    zh_btn_mktex();
    p_glGenTextures(1, &g_btex);
    p_glBindTexture(GL_TEX2D, g_btex);
    p_glTexImage2D(GL_TEX2D, 0, GL_RGBA, BTN_TEX, BTN_TEX, 0,
                   GL_RGBA, GL_UBYTE, g_bpx);
    p_glTexParameteri(GL_TEX2D, GL_TEX_MIN_FILTER, GL_LINEAR);
    p_glTexParameteri(GL_TEX2D, GL_TEX_MAG_FILTER, GL_LINEAR);
    p_glTexParameteri(GL_TEX2D, GL_TEX_WRAP_S, GL_CLAMP_EDGE);
    p_glTexParameteri(GL_TEX2D, GL_TEX_WRAP_T, GL_CLAMP_EDGE);

    p_glGenBuffers(1, &g_bvbo);
    g_bok = 1;
    logf_("按钮: 初始化完成 prog=%u tex=%u aPos=%d aUV=%d", g_bprog, g_btex, g_ba_pos, g_ba_uv);
    return 1;
}

__attribute__((used, noinline)) static void zh_btn_draw(void) {
    if (g_bfail) return;
    if (!zh_btn_init()) return;

    int vp[4] = { 0, 0, 2400, 1080 };
    p_glGetIntegerv(GL_VIEWPORT, vp);
    float W = (float)vp[2], H = (float)vp[3];
    static unsigned dbg;
    if ((++dbg % 120) == 1) logf_("btn draw #%u vp=%d,%d,%d,%d", dbg, vp[0], vp[1], vp[2], vp[3]);
    if (W < 100 || H < 100) return;

    int prevProg = 0, prevTex = 0, prevAct = 0, prevBuf = 0;
    p_glGetIntegerv(GL_CURPROG, &prevProg);
    p_glGetIntegerv(GL_TEX_BIND, &prevTex);
    p_glGetIntegerv(GL_ACTIVETEX, &prevAct);
    p_glGetIntegerv(GL_ARRAYBUFBIND, &prevBuf);
    int bl = p_glIsEnabled(GL_BLEND_E);
    int dt = p_glIsEnabled(GL_DEPTH_E);
    int sc = p_glIsEnabled(GL_SCISSOR_E);
    int cu = p_glIsEnabled(GL_CULL_E);

    float x0 = 0, y0 = 0;
    float x1 = W, y1 = H;
    float q[16] = {
        x0, y0, 0.0f, 0.0f,
        x1, y0, 1.0f, 0.0f,
        x0, y1, 0.0f, 1.0f,
        x1, y1, 1.0f, 1.0f,
    };

    p_glViewport(0, 0, (int)W, (int)H);
    if (dt) p_glDisable(GL_DEPTH_E);
    if (sc) p_glDisable(GL_SCISSOR_E);
    if (cu) p_glDisable(GL_CULL_E);
    if (!bl) p_glEnable(GL_BLEND_E);
    p_glBlendFunc(GL_SRCALPHA, GL_1MSRCALPHA);

    p_glUseProgram(g_bprog);
    p_glActiveTexture(GL_TEX0);
    p_glBindTexture(GL_TEX2D, g_btex);
    if (g_bu_tex >= 0) p_glUniform1i(g_bu_tex, 0);
    if (g_bu_res >= 0) p_glUniform2f(g_bu_res, W, H);

    p_glBindBuffer(GL_ARRAYBUF, g_bvbo);
    p_glBufferData(GL_ARRAYBUF, (long)sizeof(q), q, GL_STATICDRAW);
    if (g_ba_pos >= 0) {
        p_glEnableVertexAttribArray((unsigned)g_ba_pos);
        p_glVertexAttribPointer((unsigned)g_ba_pos, 2, GL_FLOAT_T, 0, 16, (const void *)0);
    }
    if (g_ba_uv >= 0) {
        p_glEnableVertexAttribArray((unsigned)g_ba_uv);
        p_glVertexAttribPointer((unsigned)g_ba_uv, 2, GL_FLOAT_T, 0, 16, (const void *)8);
    }
    p_glDrawArrays(GL_TRISTRIP, 0, 4);
    g_bdraws++;
    if (p_glGetError) {
        unsigned e = p_glGetError();
        static unsigned last_e;
        if (e != last_e) { last_e = e; logf_("btn glError=%#x (draws=%u)", e, g_bdraws); }
    }

    // 恢复
    p_glBindBuffer(GL_ARRAYBUF, (unsigned)prevBuf);
    p_glUseProgram((unsigned)prevProg);
    p_glActiveTexture((unsigned)(prevAct ? prevAct : GL_TEX0));
    p_glBindTexture(GL_TEX2D, (unsigned)prevTex);
    if (!bl) p_glDisable(GL_BLEND_E);
    if (dt) p_glEnable(GL_DEPTH_E);
    if (sc) p_glEnable(GL_SCISSOR_E);
    if (cu) p_glEnable(GL_CULL_E);
    p_glViewport(vp[0], vp[1], vp[2], vp[3]);
}

// ---------------------------------------------------------------- eglSwapBuffers 指针替换
// libEGL.so 带 BTI+PAC，inline hook 必崩（实测闪退）。
// libs3e 用 dlsym("eglSwapBuffers") 拿到地址后存进自己的变量再 blr 调用，
// 所以直接把内存里所有等于该地址的指针替换成 wrapper 即可，完全不碰代码页。
typedef void *(*swap_t)(void *, void *);
static void *g_real_swap;
static int g_swap_ptr_done;
static volatile unsigned g_swap_wrap_calls;

__attribute__((used, noinline)) static void *zh_swap_wrap(void *a, void *b) {
    g_swap_wrap_calls++;
    zh_btn_draw();
    return ((swap_t)g_real_swap)(a, b);
}

static void patch_swap_ptr(void) {
    if (g_swap_ptr_done) return;
    void *h = dlopen("libEGL.so", RTLD_NOW);
    if (!h) return;
    void *P = dlsym(h, "eglSwapBuffers");
    if (!P) return;
    g_real_swap = P;

    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return;
    char line[512];
    int hits = 0, regions = 0;
    uint64_t oldv = (uint64_t)(uintptr_t)P;
    uint64_t newv = (uint64_t)(uintptr_t)zh_swap_wrap;
    while (fgets(line, sizeof line, f)) {
        unsigned long a = 0, b = 0;
        char perms[8] = { 0 };
        if (sscanf(line, "%lx-%lx %7s", &a, &b, perms) != 3) continue;
        if (perms[0] != 'r' || perms[1] != 'w') continue;      // 只扫可写段
        if (strstr(line, "libzhfont")) continue;               // 绝不碰自己
        regions++;
        for (uintptr_t p = (a + 7) & ~(uintptr_t)7; p + 8 <= b; p += 8) {
            if (*(volatile uint64_t *)p == oldv) {
                *(volatile uint64_t *)p = newv;
                hits++;
            }
        }
    }
    fclose(f);
    logf_("eglSwapBuffers 指针替换 P=%p 扫描%d段 命中%d处", P, regions, hits);
    g_swap_ptr_done = 1;
}

// ---------------------------------------------------------------- s3eSurfaceShow 钩子
// libEGL.so 带 BTI+PAC，inline hook 会崩（实测闪退）。
// libs3e_android.so 没有 BTI，且 s3eSurfaceShow(0xbc590) 就是每帧的 swap，
// 所以改挂它。入口前 4 条含 adrp（PC 相对），不能直接搬，handler 里重建。
#define SURF_VA     0xbc590u
#define SURF_ADRP   0x177000u      // adrp x19, 0x177000
#define SURF_ADD    0x9c8u         // add x0, x19, #0x9c8
#define SURF_RESUME 0xbc5a0u       // 第 5 条指令

static unsigned char *g_tramp_surf;
static uintptr_t g_surf_p177;
static uintptr_t g_surf_resume;
static volatile unsigned g_surf_calls;
static int g_surf_done;

__attribute__((used)) static void zh_on_surf(void) {
    unsigned n = ++g_surf_calls;
    if (n == 1 || (n % 600) == 0) logf_("SurfaceShow 调用 %u 次", n);
}

__attribute__((naked)) static void zh_h_surf(void) {
    __asm__ volatile(
        "sub  sp, sp, #0x40\n"
        "stp  x0, x1, [sp, #0x00]\n"
        "stp  x2, x3, [sp, #0x10]\n"
        "stp  x19, x20, [sp, #0x20]\n"
        "str  x30, [sp, #0x30]\n"
        "bl   zh_on_surf\n"
        "bl   zh_btn_draw\n"
        "ldr  x30, [sp, #0x30]\n"
        "ldp  x19, x20, [sp, #0x20]\n"
        "ldp  x2, x3, [sp, #0x10]\n"
        "ldp  x0, x1, [sp, #0x00]\n"
        "add  sp, sp, #0x40\n"
        // 重建被覆盖的原指令
        "sub  sp, sp, #0xa0\n"
        "stp  x19, x20, [sp]\n"
        "adrp x9, g_surf_p177\n"
        "add  x9, x9, :lo12:g_surf_p177\n"
        "ldr  x19, [x9]\n"
        "add  x0, x19, #0x9c8\n"
        "adrp x9, g_surf_resume\n"
        "add  x9, x9, :lo12:g_surf_resume\n"
        "ldr  x9, [x9]\n"
        "br   x9\n"
    );
}

static int install_surf_hook(void) {
    if (g_surf_done) return 1;
    uintptr_t b = zf_modbase("libs3e_android.so");
    if (!b) return 0;
    g_surf_p177 = b + SURF_ADRP;
    g_surf_resume = b + SURF_RESUME;
    if (patch_site(b, SURF_VA, zh_h_surf, &g_tramp_surf)) {
        g_surf_done = 1;
        logf_("s3eSurfaceShow 已挂钩 base=%p p177=%p resume=%p", (void *)b, (void *)g_surf_p177, (void *)g_surf_resume);
        return 1;
    }
    return 0;
}
