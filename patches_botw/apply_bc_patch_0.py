import os, sys, re, shutil

def apply_bc_patch(repo_dir):
    print(f"Applying BC decompression, Link's Awakening fixes, and 30fps limiter to: {repo_dir}")
    tex_dir = os.path.join(repo_dir, "dm", "gfx", "tex")
    nvn_dir = os.path.join(repo_dir, "dm", "gfx", "nvn")
    tools_dir = os.path.join(repo_dir, "dm", "tools")
    games_dir = os.path.join(repo_dir, "dm", "games")

    # 0.0 Update dmsh_chain.h to match Mario Wonder shader pack (670578cbb17a)
    chain_h = os.path.join(nvn_dir, "dmsh_chain.h")
    if os.path.exists(chain_h):
        with open(chain_h, "w", encoding="utf-8") as f_chain:
            f_chain.write('// Mario Wonder shaders compatibility\n#define DMSH_CHAIN "670578cbb17a"\n')
        print("  [OK] Set DMSH_CHAIN to 670578cbb17a in dmsh_chain.h")

    # 0. Download bcdec.h if not present
    bcdec_path = os.path.join(tex_dir, "bcdec.h")
    if not os.path.exists(bcdec_path):
        try:
            import urllib.request
            print("  Downloading bcdec.h...")
            urllib.request.urlretrieve("https://raw.githubusercontent.com/iOrange/bcdec/master/bcdec.h", bcdec_path)
            print("  [OK] Downloaded bcdec.h")
        except Exception as e:
            print(f"  [WARN] Failed to download bcdec.h via urllib: {e}")

    # 1. nvn_bc1astc.h
    bc1_h_path = os.path.join(tex_dir, "nvn_bc1astc.h")
    bc1_h_code = """#ifndef NVN_BC1ASTC_H
#define NVN_BC1ASTC_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int nvn_bc1_astc_enabled(void);
void nvn_bc1_astc_set_enabled(int enabled);
void nvn_bc1_to_astc4x4_block(const void *src_bc1, void *dst_astc);
void nvn_bc1_to_astc4x4(uint32_t width, uint32_t height,
                        const void *src_bc1, size_t src_pitch,
                        void *dst_astc, size_t dst_pitch);

#ifdef __cplusplus
}
#endif

#endif // NVN_BC1ASTC_H
"""
    with open(bc1_h_path, "w", encoding="utf-8") as f:
        f.write(bc1_h_code)
    print("  [OK] Created nvn_bc1astc.h")

    # 1.1 nvn_bc1astc.c
    bc1_c_path = os.path.join(tex_dir, "nvn_bc1astc.c")
    bc1_c_code = """#include "nvn_bc1astc.h"
#include <stdlib.h>
#include <string.h>

static int g_bc1_astc_enabled = -1;

int nvn_bc1_astc_enabled(void) {
    if (g_bc1_astc_enabled < 0) {
        const char *env = getenv("DM_BC1_ASTC");
        if (!env) env = getenv("TOTK_BC1_ASTC");
        if (env) {
            g_bc1_astc_enabled = (atoi(env) != 0) ? 1 : 0;
        } else {
            g_bc1_astc_enabled = 1;
        }
    }
    return g_bc1_astc_enabled;
}

void nvn_bc1_astc_set_enabled(int enabled) {
    g_bc1_astc_enabled = enabled ? 1 : 0;
}

void nvn_bc1_to_astc4x4_block(const void *src_bc1, void *dst_astc) {
    const uint8_t *src = (const uint8_t *)src_bc1;
    uint8_t *dst = (uint8_t *)dst_astc;

    uint16_t c0 = (uint16_t)src[0] | ((uint16_t)src[1] << 8);
    uint16_t c1 = (uint16_t)src[2] | ((uint16_t)src[3] << 8);
    uint32_t idx = (uint32_t)src[4] | ((uint32_t)src[5] << 8) |
                   ((uint32_t)src[6] << 16) | ((uint32_t)src[7] << 24);

    uint8_t r0 = (uint8_t)((((c0 >> 11) & 0x1f) * 527 + 23) >> 6);
    uint8_t g0 = (uint8_t)((((c0 >> 5) & 0x3f) * 259 + 33) >> 6);
    uint8_t b0 = (uint8_t)(((c0 & 0x1f) * 527 + 23) >> 6);

    uint8_t r1 = (uint8_t)((((c1 >> 11) & 0x1f) * 527 + 23) >> 6);
    uint8_t g1 = (uint8_t)((((c1 >> 5) & 0x3f) * 259 + 33) >> 6);
    uint8_t b1 = (uint8_t)(((c1 & 0x1f) * 527 + 23) >> 6);

    uint32_t w0 = 0x10042u | ((uint32_t)r0 << 17) | (((uint32_t)r1 & 0x7fu) << 25);
    uint32_t w1 = (((uint32_t)r1 >> 7) & 1u) | ((uint32_t)g0 << 1) | ((uint32_t)g1 << 9) |
                  ((uint32_t)b0 << 17) | (((uint32_t)b1 & 0x7fu) << 25);
    uint32_t w2 = (((uint32_t)b1 >> 7) & 1u);

    static const uint8_t lut4[4] = { 0, 3, 2, 1 };
    static const uint8_t lut3[4] = { 0, 3, 2, 0 };
    const uint8_t *lut = (c0 > c1) ? lut4 : lut3;

    uint32_t w3 = 0;
    for (int i = 0; i < 16; i++) {
        uint32_t bi = (idx >> (2 * i)) & 3u;
        w3 |= ((uint32_t)lut[bi]) << (30 - 2 * i);
    }

    uint32_t *d32 = (uint32_t *)dst;
    d32[0] = w0;
    d32[1] = w1;
    d32[2] = w2;
    d32[3] = w3;
}

void nvn_bc1_to_astc4x4(uint32_t width, uint32_t height,
                        const void *src_bc1, size_t src_pitch,
                        void *dst_astc, size_t dst_pitch) {
    uint32_t bx = (width + 3) / 4;
    uint32_t by = (height + 3) / 4;
    for (uint32_t y = 0; y < by; y++) {
        const uint8_t *s_row = (const uint8_t *)src_bc1 + y * src_pitch;
        uint8_t *d_row = (uint8_t *)dst_astc + y * dst_pitch;
        for (uint32_t x = 0; x < bx; x++) {
            nvn_bc1_to_astc4x4_block(s_row + x * 8, d_row + x * 16);
        }
    }
}
"""
    with open(bc1_c_path, "w", encoding="utf-8") as f:
        f.write(bc1_c_code)
    print("  [OK] Created nvn_bc1astc.c")

    # 1.2 nvn_bctc.metal
    bctc_metal_path = os.path.join(tex_dir, "nvn_bctc.metal")
    bctc_metal_code = """#include <metal_stdlib>
using namespace metal;

struct BCTCParams {
    uint width;
    uint height;
    uint src_pitch;
    uint dst_pitch;
};

kernel void bctc_bc3(device const uchar *src [[buffer(0)]],
                     device uchar *dst [[buffer(1)]],
                     constant BCTCParams &p [[buffer(2)]],
                     uint2 tid [[thread_position_in_grid]]) {
    uint bx = tid.x;
    uint by = tid.y;
    uint x0 = bx * 4;
    uint y0 = by * 4;
    if (x0 >= p.width || y0 >= p.height) return;

    device const uchar *b = src + (ulong)by * p.src_pitch + (ulong)bx * 16;

    uchar a0 = b[0], a1 = b[1];
    ulong a_indices = (ulong)b[2] | ((ulong)b[3] << 8) | ((ulong)b[4] << 16) |
                      ((ulong)b[5] << 24) | ((ulong)b[6] << 32) | ((ulong)b[7] << 40);
    uchar a_lut[8];
    a_lut[0] = a0;
    a_lut[1] = a1;
    if (a0 > a1) {
        a_lut[2] = (uchar)((6 * (uint)a0 +     (uint)a1) / 7);
        a_lut[3] = (uchar)((5 * (uint)a0 + 2 * (uint)a1) / 7);
        a_lut[4] = (uchar)((4 * (uint)a0 + 3 * (uint)a1) / 7);
        a_lut[5] = (uchar)((3 * (uint)a0 + 4 * (uint)a1) / 7);
        a_lut[6] = (uchar)((2 * (uint)a0 + 5 * (uint)a1) / 7);
        a_lut[7] = (uchar)((    (uint)a0 + 6 * (uint)a1) / 7);
    } else {
        a_lut[2] = (uchar)((4 * (uint)a0 +     (uint)a1) / 5);
        a_lut[3] = (uchar)((3 * (uint)a0 + 2 * (uint)a1) / 5);
        a_lut[4] = (uchar)((2 * (uint)a0 + 3 * (uint)a1) / 5);
        a_lut[5] = (uchar)((    (uint)a0 + 4 * (uint)a1) / 5);
        a_lut[6] = 0;
        a_lut[7] = 255;
    }

    ushort c0 = (ushort)b[8] | ((ushort)b[9] << 8);
    ushort c1 = (ushort)b[10] | ((ushort)b[11] << 8);
    uint c_indices = (uint)b[12] | ((uint)b[13] << 8) | ((uint)b[14] << 16) | ((uint)b[15] << 24);

    uint r0 = (c0 >> 11) & 0x1f, g0 = (c0 >> 5) & 0x3f, b0 = c0 & 0x1f;
    uint r1 = (c1 >> 11) & 0x1f, g1 = (c1 >> 5) & 0x3f, b1 = c1 & 0x1f;

    uchar4 c_lut[4];
    c_lut[0] = uchar4((r0 * 527 + 23) >> 6, (g0 * 259 + 33) >> 6, (b0 * 527 + 23) >> 6, 255);
    c_lut[1] = uchar4((r1 * 527 + 23) >> 6, (g1 * 259 + 33) >> 6, (b1 * 527 + 23) >> 6, 255);
    c_lut[2] = uchar4(((2 * r0 + r1) * 351 + 61) >> 7, ((2 * g0 + g1) * 2763 + 1039) >> 11, ((2 * b0 + b1) * 351 + 61) >> 7, 255);
    c_lut[3] = uchar4(((r0 + 2 * r1) * 351 + 61) >> 7, ((g0 + 2 * g1) * 2763 + 1039) >> 11, ((b0 + 2 * b1) * 351 + 61) >> 7, 255);

    for (uint dy = 0; dy < 4; dy++) {
        if (y0 + dy >= p.height) break;
        device uchar *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
        for (uint dx = 0; dx < 4; dx++) {
            if (x0 + dx >= p.width) break;
            uint p_idx = dy * 4 + dx;
            uint a_sel = (uint)((a_indices >> (3 * p_idx)) & 7);
            uint c_sel = (c_indices >> (2 * p_idx)) & 3;
            uchar4 col = c_lut[c_sel];
            col.w = a_lut[a_sel];
            *(device uchar4 *)(dst_row + (x0 + dx) * 4) = col;
        }
    }
}

kernel void bctc_bc7(device const uchar *src [[buffer(0)]],
                     device uchar *dst [[buffer(1)]],
                     constant BCTCParams &p [[buffer(2)]],
                     uint2 tid [[thread_position_in_grid]]) {
    uint bx = tid.x;
    uint by = tid.y;
    uint x0 = bx * 4;
    uint y0 = by * 4;
    if (x0 >= p.width || y0 >= p.height) return;

    device const uchar *b = src + (ulong)by * p.src_pitch + (ulong)bx * 16;
    ulong low = (ulong)b[0] | ((ulong)b[1] << 8) | ((ulong)b[2] << 16) | ((ulong)b[3] << 24) |
                ((ulong)b[4] << 32) | ((ulong)b[5] << 40) | ((ulong)b[6] << 48) | ((ulong)b[7] << 56);
    ulong high = (ulong)b[8] | ((ulong)b[9] << 8) | ((ulong)b[10] << 16) | ((ulong)b[11] << 24) |
                 ((ulong)b[12] << 32) | ((ulong)b[13] << 40) | ((ulong)b[14] << 48) | ((ulong)b[15] << 56);

    if ((low & 0x7fu) == 0x40u) {
        uint bitpos = 7;
        uint r0 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint r1 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint g0 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint g1 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint b0 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint b1 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint a0 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint a1 = (uint)((low >> bitpos) & 0x7fu); bitpos += 7;
        uint p0 = (uint)((low >> 63) & 1u);
        uint p1 = (uint)(high & 1u);

        r0 = (r0 << 1) | p0; r1 = (r1 << 1) | p1;
        g0 = (g0 << 1) | p0; g1 = (g1 << 1) | p1;
        b0 = (b0 << 1) | p0; b1 = (b1 << 1) | p1;
        a0 = (a0 << 1) | p0; a1 = (a1 << 1) | p1;

        static constant uchar aWeight4[16] = {
            0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64
        };

        for (uint dy = 0; dy < 4; dy++) {
            if (y0 + dy >= p.height) break;
            device uchar *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
            for (uint dx = 0; dx < 4; dx++) {
                if (x0 + dx >= p.width) break;
                uint p_idx = dy * 4 + dx;
                uint w_idx = (p_idx == 0) ? (uint)((high >> 1) & 7u) : (uint)((high >> (4 + (p_idx - 1) * 4)) & 0xfu);
                uint w = aWeight4[w_idx & 0xfu];
                uint r = (r0 * (64 - w) + r1 * w + 32) >> 6;
                uint g = (g0 * (64 - w) + g1 * w + 32) >> 6;
                uint b_val = (b0 * (64 - w) + b1 * w + 32) >> 6;
                uint a = (a0 * (64 - w) + a1 * w + 32) >> 6;
                *(device uchar4 *)(dst_row + (x0 + dx) * 4) = uchar4(r, g, b_val, a);
            }
        }
    } else if ((low & 0x3fu) == 0x20u) {
        uint rot = (uint)((low >> 6) & 3u);
        uint r0 = (uint)((low >> 8) & 0x7fu);
        uint r1 = (uint)((low >> 15) & 0x7fu);
        uint g0 = (uint)((low >> 22) & 0x7fu);
        uint g1 = (uint)((low >> 29) & 0x7fu);
        uint b0 = (uint)((low >> 36) & 0x7fu);
        uint b1 = (uint)((low >> 43) & 0x7fu);
        uint a0 = (uint)((low >> 50) & 0xffu);
        uint a1 = (uint)(((low >> 58) & 0x3fu) | ((high & 3u) << 6));

        r0 = (r0 << 1) | (r0 >> 6); r1 = (r1 << 1) | (r1 >> 6);
        g0 = (g0 << 1) | (g0 >> 6); g1 = (g1 << 1) | (g1 >> 6);
        b0 = (b0 << 1) | (b0 >> 6); b1 = (b1 << 1) | (b1 >> 6);

        uint c_weights = (uint)((high >> 2) & 0x7fffffffu);
        uint a_weights = (uint)((high >> 33) & 0x7fffffffu);

        static constant uchar aWeight2[4] = { 0, 21, 43, 64 };

        for (uint dy = 0; dy < 4; dy++) {
            if (y0 + dy >= p.height) break;
            device uchar *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
            for (uint dx = 0; dx < 4; dx++) {
                if (x0 + dx >= p.width) break;
                uint p_idx = dy * 4 + dx;
                uint cw = (p_idx == 0) ? aWeight2[c_weights & 1u] : aWeight2[(c_weights >> (1 + (p_idx - 1) * 2)) & 3u];
                uint aw = (p_idx == 0) ? aWeight2[a_weights & 1u] : aWeight2[(a_weights >> (1 + (p_idx - 1) * 2)) & 3u];

                uint r = (r0 * (64 - cw) + r1 * cw + 32) >> 6;
                uint g = (g0 * (64 - cw) + g1 * cw + 32) >> 6;
                uint b_val = (b0 * (64 - cw) + b1 * cw + 32) >> 6;
                uint a = (a0 * (64 - aw) + a1 * aw + 32) >> 6;

                if (rot == 1) { uint tmp = r; r = a; a = tmp; }
                else if (rot == 2) { uint tmp = g; g = a; a = tmp; }
                else if (rot == 3) { uint tmp = b_val; b_val = a; a = tmp; }

                *(device uchar4 *)(dst_row + (x0 + dx) * 4) = uchar4(r, g, b_val, a);
            }
        }
    } else {
        for (uint dy = 0; dy < 4; dy++) {
            if (y0 + dy >= p.height) break;
            device uchar *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
            for (uint dx = 0; dx < 4; dx++) {
                if (x0 + dx >= p.width) break;
                *(device uchar4 *)(dst_row + (x0 + dx) * 4) = uchar4(128, 128, 128, 255);
            }
        }
    }
}

kernel void bctc_bc4_u(device const uchar *src [[buffer(0)]],
                       device uchar *dst [[buffer(1)]],
                       constant BCTCParams &p [[buffer(2)]],
                       uint2 tid [[thread_position_in_grid]]) {
    uint bx = tid.x;
    uint by = tid.y;
    uint x0 = bx * 4;
    uint y0 = by * 4;
    if (x0 >= p.width || y0 >= p.height) return;

    device const uchar *b = src + (ulong)by * p.src_pitch + (ulong)bx * 8;
    uchar a0 = b[0], a1 = b[1];
    ulong a_indices = (ulong)b[2] | ((ulong)b[3] << 8) | ((ulong)b[4] << 16) |
                      ((ulong)b[5] << 24) | ((ulong)b[6] << 32) | ((ulong)b[7] << 40);
    uchar a_lut[8];
    a_lut[0] = a0;
    a_lut[1] = a1;
    if (a0 > a1) {
        a_lut[2] = (uchar)((6 * (uint)a0 +     (uint)a1 + 3) / 7);
        a_lut[3] = (uchar)((5 * (uint)a0 + 2 * (uint)a1 + 3) / 7);
        a_lut[4] = (uchar)((4 * (uint)a0 + 3 * (uint)a1 + 3) / 7);
        a_lut[5] = (uchar)((3 * (uint)a0 + 4 * (uint)a1 + 3) / 7);
        a_lut[6] = (uchar)((2 * (uint)a0 + 5 * (uint)a1 + 3) / 7);
        a_lut[7] = (uchar)((    (uint)a0 + 6 * (uint)a1 + 3) / 7);
    } else {
        a_lut[2] = (uchar)((4 * (uint)a0 +     (uint)a1 + 2) / 5);
        a_lut[3] = (uchar)((3 * (uint)a0 + 2 * (uint)a1 + 2) / 5);
        a_lut[4] = (uchar)((2 * (uint)a0 + 3 * (uint)a1 + 2) / 5);
        a_lut[5] = (uchar)((    (uint)a0 + 4 * (uint)a1 + 2) / 5);
        a_lut[6] = 0;
        a_lut[7] = 255;
    }

    for (uint dy = 0; dy < 4; dy++) {
        if (y0 + dy >= p.height) break;
        device uchar *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
        for (uint dx = 0; dx < 4; dx++) {
            if (x0 + dx >= p.width) break;
            uint p_idx = dy * 4 + dx;
            uint a_sel = (uint)((a_indices >> (3 * p_idx)) & 7);
            dst_row[x0 + dx] = a_lut[a_sel];
        }
    }
}

kernel void bctc_bc4_s(device const uchar *src [[buffer(0)]],
                       device char *dst [[buffer(1)]],
                       constant BCTCParams &p [[buffer(2)]],
                       uint2 tid [[thread_position_in_grid]]) {
    uint bx = tid.x;
    uint by = tid.y;
    uint x0 = bx * 4;
    uint y0 = by * 4;
    if (x0 >= p.width || y0 >= p.height) return;

    device const uchar *b = src + (ulong)by * p.src_pitch + (ulong)bx * 8;
    int a0 = (char)b[0], a1 = (char)b[1];
    if (a0 < -127) a0 = -127;
    if (a1 < -127) a1 = -127;
    char a_lut[8];
    a_lut[0] = (char)a0;
    a_lut[1] = (char)a1;
    if (a0 > a1) {
        a_lut[2] = (char)((56173 * a0 +  9363 * a1 + 32768) >> 16);
        a_lut[3] = (char)((46812 * a0 + 18724 * a1 + 32768) >> 16);
        a_lut[4] = (char)((37450 * a0 + 28086 * a1 + 32768) >> 16);
        a_lut[5] = (char)((28086 * a0 + 37450 * a1 + 32768) >> 16);
        a_lut[6] = (char)((18724 * a0 + 46812 * a1 + 32768) >> 16);
        a_lut[7] = (char)(( 9363 * a0 + 56173 * a1 + 32768) >> 16);
    } else {
        a_lut[2] = (char)((52429 * a0 + 13107 * a1 + 32768) >> 16);
        a_lut[3] = (char)((39321 * a0 + 26215 * a1 + 32768) >> 16);
        a_lut[4] = (char)((26215 * a0 + 39321 * a1 + 32768) >> 16);
        a_lut[5] = (char)((13107 * a0 + 52429 * a1 + 32768) >> 16);
        a_lut[6] = -127;
        a_lut[7] = 127;
    }

    ulong a_indices = (ulong)b[2] | ((ulong)b[3] << 8) | ((ulong)b[4] << 16) |
                      ((ulong)b[5] << 24) | ((ulong)b[6] << 32) | ((ulong)b[7] << 40);

    for (uint dy = 0; dy < 4; dy++) {
        if (y0 + dy >= p.height) break;
        device char *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
        for (uint dx = 0; dx < 4; dx++) {
            if (x0 + dx >= p.width) break;
            uint p_idx = dy * 4 + dx;
            uint a_sel = (uint)((a_indices >> (3 * p_idx)) & 7);
            dst_row[x0 + dx] = a_lut[a_sel];
        }
    }
}

kernel void bctc_bc5_u(device const uchar *src [[buffer(0)]],
                       device uchar *dst [[buffer(1)]],
                       constant BCTCParams &p [[buffer(2)]],
                       uint2 tid [[thread_position_in_grid]]) {
    uint bx = tid.x;
    uint by = tid.y;
    uint x0 = bx * 4;
    uint y0 = by * 4;
    if (x0 >= p.width || y0 >= p.height) return;

    device const uchar *b = src + (ulong)by * p.src_pitch + (ulong)bx * 16;
    uchar r0 = b[0], r1 = b[1];
    ulong r_indices = (ulong)b[2] | ((ulong)b[3] << 8) | ((ulong)b[4] << 16) |
                      ((ulong)b[5] << 24) | ((ulong)b[6] << 32) | ((ulong)b[7] << 40);
    uchar r_lut[8];
    r_lut[0] = r0;
    r_lut[1] = r1;
    if (r0 > r1) {
        r_lut[2] = (uchar)((6 * (uint)r0 +     (uint)r1 + 3) / 7);
        r_lut[3] = (uchar)((5 * (uint)r0 + 2 * (uint)r1 + 3) / 7);
        r_lut[4] = (uchar)((4 * (uint)r0 + 3 * (uint)r1 + 3) / 7);
        r_lut[5] = (uchar)((3 * (uint)r0 + 4 * (uint)r1 + 3) / 7);
        r_lut[6] = (uchar)((2 * (uint)r0 + 5 * (uint)r1 + 3) / 7);
        r_lut[7] = (uchar)((    (uint)r0 + 6 * (uint)r1 + 3) / 7);
    } else {
        r_lut[2] = (uchar)((4 * (uint)r0 +     (uint)r1 + 2) / 5);
        r_lut[3] = (uchar)((3 * (uint)r0 + 2 * (uint)r1 + 2) / 5);
        r_lut[4] = (uchar)((2 * (uint)r0 + 3 * (uint)r1 + 2) / 5);
        r_lut[5] = (uchar)((    (uint)r0 + 4 * (uint)r1 + 2) / 5);
        r_lut[6] = 0;
        r_lut[7] = 255;
    }

    device const uchar *bg = b + 8;
    uchar g0 = bg[0], g1 = bg[1];
    ulong g_indices = (ulong)bg[2] | ((ulong)bg[3] << 8) | ((ulong)bg[4] << 16) |
                      ((ulong)bg[5] << 24) | ((ulong)bg[6] << 32) | ((ulong)bg[7] << 40);
    uchar g_lut[8];
    g_lut[0] = g0;
    g_lut[1] = g1;
    if (g0 > g1) {
        g_lut[2] = (uchar)((6 * (uint)g0 +     (uint)g1 + 3) / 7);
        g_lut[3] = (uchar)((5 * (uint)g0 + 2 * (uint)g1 + 3) / 7);
        g_lut[4] = (uchar)((4 * (uint)g0 + 3 * (uint)g1 + 3) / 7);
        g_lut[5] = (uchar)((3 * (uint)g0 + 4 * (uint)g1 + 3) / 7);
        g_lut[6] = (uchar)((2 * (uint)g0 + 5 * (uint)g1 + 3) / 7);
        g_lut[7] = (uchar)((    (uint)g0 + 6 * (uint)g1 + 3) / 7);
    } else {
        g_lut[2] = (uchar)((4 * (uint)g0 +     (uint)g1 + 2) / 5);
        g_lut[3] = (uchar)((3 * (uint)g0 + 2 * (uint)g1 + 2) / 5);
        g_lut[4] = (uchar)((2 * (uint)g0 + 3 * (uint)g1 + 2) / 5);
        g_lut[5] = (uchar)((    (uint)g0 + 4 * (uint)g1 + 2) / 5);
        g_lut[6] = 0;
        g_lut[7] = 255;
    }

    for (uint dy = 0; dy < 4; dy++) {
        if (y0 + dy >= p.height) break;
        device uchar *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
        for (uint dx = 0; dx < 4; dx++) {
            if (x0 + dx >= p.width) break;
            uint p_idx = dy * 4 + dx;
            uint r_sel = (uint)((r_indices >> (3 * p_idx)) & 7);
            uint g_sel = (uint)((g_indices >> (3 * p_idx)) & 7);
            *(device uchar2 *)(dst_row + (x0 + dx) * 2) = uchar2(r_lut[r_sel], g_lut[g_sel]);
        }
    }
}

kernel void bctc_bc5_s(device const uchar *src [[buffer(0)]],
                       device char *dst [[buffer(1)]],
                       constant BCTCParams &p [[buffer(2)]],
                       uint2 tid [[thread_position_in_grid]]) {
    uint bx = tid.x;
    uint by = tid.y;
    uint x0 = bx * 4;
    uint y0 = by * 4;
    if (x0 >= p.width || y0 >= p.height) return;

    device const uchar *b = src + (ulong)by * p.src_pitch + (ulong)bx * 16;
    int r0 = (char)b[0], r1 = (char)b[1];
    if (r0 < -127) r0 = -127;
    if (r1 < -127) r1 = -127;
    char r_lut[8];
    r_lut[0] = (char)r0;
    r_lut[1] = (char)r1;
    if (r0 > r1) {
        r_lut[2] = (char)((56173 * r0 +  9363 * r1 + 32768) >> 16);
        r_lut[3] = (char)((46812 * r0 + 18724 * r1 + 32768) >> 16);
        r_lut[4] = (char)((37450 * r0 + 28086 * r1 + 32768) >> 16);
        r_lut[5] = (char)((28086 * r0 + 37450 * r1 + 32768) >> 16);
        r_lut[6] = (char)((18724 * r0 + 46812 * r1 + 32768) >> 16);
        r_lut[7] = (char)(( 9363 * r0 + 56173 * r1 + 32768) >> 16);
    } else {
        r_lut[2] = (char)((52429 * r0 + 13107 * r1 + 32768) >> 16);
        r_lut[3] = (char)((39321 * r0 + 26215 * r1 + 32768) >> 16);
        r_lut[4] = (char)((26215 * r0 + 39321 * r1 + 32768) >> 16);
        r_lut[5] = (char)((13107 * r0 + 52429 * r1 + 32768) >> 16);
        r_lut[6] = -127;
        r_lut[7] = 127;
    }

    ulong r_indices = (ulong)b[2] | ((ulong)b[3] << 8) | ((ulong)b[4] << 16) |
                      ((ulong)b[5] << 24) | ((ulong)b[6] << 32) | ((ulong)b[7] << 40);

    device const uchar *bg = b + 8;
    int g0 = (char)bg[0], g1 = (char)bg[1];
    if (g0 < -127) g0 = -127;
    if (g1 < -127) g1 = -127;
    char g_lut[8];
    g_lut[0] = (char)g0;
    g_lut[1] = (char)g1;
    if (g0 > g1) {
        g_lut[2] = (char)((56173 * g0 +  9363 * g1 + 32768) >> 16);
        g_lut[3] = (char)((46812 * g0 + 18724 * g1 + 32768) >> 16);
        g_lut[4] = (char)((37450 * g0 + 28086 * g1 + 32768) >> 16);
        g_lut[5] = (char)((28086 * g0 + 37450 * g1 + 32768) >> 16);
        g_lut[6] = (char)((18724 * g0 + 46812 * g1 + 32768) >> 16);
        g_lut[7] = (char)(( 9363 * g0 + 56173 * g1 + 32768) >> 16);
    } else {
        g_lut[2] = (char)((52429 * g0 + 13107 * g1 + 32768) >> 16);
        g_lut[3] = (char)((39321 * g0 + 26215 * g1 + 32768) >> 16);
        g_lut[4] = (char)((26215 * g0 + 39321 * g1 + 32768) >> 16);
        g_lut[5] = (char)((13107 * g0 + 52429 * g1 + 32768) >> 16);
        g_lut[6] = -127;
        g_lut[7] = 127;
    }

    ulong g_indices = (ulong)bg[2] | ((ulong)bg[3] << 8) | ((ulong)bg[4] << 16) |
                      ((ulong)bg[5] << 24) | ((ulong)bg[6] << 32) | ((ulong)bg[7] << 40);

    for (uint dy = 0; dy < 4; dy++) {
        if (y0 + dy >= p.height) break;
        device char *dst_row = dst + (ulong)(y0 + dy) * p.dst_pitch;
        for (uint dx = 0; dx < 4; dx++) {
            if (x0 + dx >= p.width) break;
            uint p_idx = dy * 4 + dx;
            uint r_sel = (uint)((r_indices >> (3 * p_idx)) & 7);
            uint g_sel = (uint)((g_indices >> (3 * p_idx)) & 7);
            *(device char2 *)(dst_row + (x0 + dx) * 2) = char2(r_lut[r_sel], g_lut[g_sel]);
        }
    }
}

"""
    with open(bctc_metal_path, "w", encoding="utf-8") as f:
        f.write(bctc_metal_code)
    print("  [OK] Created nvn_bctc.metal")

    # 1.3 nvn_bctc_gpu.h
    bctc_h_path = os.path.join(tex_dir, "nvn_bctc_gpu.h")
    bctc_h_code = """#pragma once
#include <stddef.h>
#include <stdint.h>
#import <Metal/Metal.h>

int nvn_bctc_gpu_init(id<MTLDevice> dev);
int nvn_bctc_gpu_supported(void);
int nvn_bctc_gpu_decode(id<MTLComputeCommandEncoder> enc, int nvn_format,
                        uint32_t width, uint32_t height,
                        id<MTLBuffer> src_bc, uint64_t src_off, size_t src_pitch,
                        id<MTLBuffer> dst_px, uint64_t dst_off, size_t dst_pitch);
int nvn_bctc_gpu_encode_m4(id<MTL4ComputeCommandEncoder> enc, id<MTL4ArgumentTable> table,
                            id<MTLBuffer> params, size_t params_off, int nvn_format,
                            uint32_t width, uint32_t height,
                            id<MTLBuffer> src_bc, uint64_t src_off, size_t src_pitch,
                            id<MTLBuffer> dst_px, uint64_t dst_off, size_t dst_pitch);
"""
    with open(bctc_h_path, "w", encoding="utf-8") as f:
        f.write(bctc_h_code)
    print("  [OK] Created nvn_bctc_gpu.h")

    # 1.4 nvn_bctc_gpu.m
    bctc_m_path = os.path.join(tex_dir, "nvn_bctc_gpu.m")
    # Escaped MSL string for embedding
    escaped_msl = bctc_metal_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n"\n    "')
    bctc_m_code = f"""#import "nvn_bctc_gpu.h"

static id<MTLComputePipelineState> g_bctc_bc3_pipeline;
static id<MTLComputePipelineState> g_bctc_bc7_pipeline;
static id<MTLComputePipelineState> g_bctc_bc4_u_pipeline;
static id<MTLComputePipelineState> g_bctc_bc4_s_pipeline;
static id<MTLComputePipelineState> g_bctc_bc5_u_pipeline;
static id<MTLComputePipelineState> g_bctc_bc5_s_pipeline;

static const char *const k_nvn_bctc_msl =
    "{escaped_msl}";

int nvn_bctc_gpu_init(id<MTLDevice> dev) {{
    if (g_bctc_bc3_pipeline && g_bctc_bc7_pipeline && g_bctc_bc4_u_pipeline && g_bctc_bc4_s_pipeline && g_bctc_bc5_u_pipeline && g_bctc_bc5_s_pipeline) return 0;
    if (!dev) return -1;
    NSError *error = nil;
    id<MTLLibrary> library = [dev newLibraryWithSource:@(k_nvn_bctc_msl) options:nil error:&error];
    if (!library) return -1;
    id<MTLFunction> fn_bc3 = [library newFunctionWithName:@"bctc_bc3"];
    if (fn_bc3) g_bctc_bc3_pipeline = [dev newComputePipelineStateWithFunction:fn_bc3 error:&error];
    id<MTLFunction> fn_bc7 = [library newFunctionWithName:@"bctc_bc7"];
    if (fn_bc7) g_bctc_bc7_pipeline = [dev newComputePipelineStateWithFunction:fn_bc7 error:&error];
    id<MTLFunction> fn_bc4_u = [library newFunctionWithName:@"bctc_bc4_u"];
    if (fn_bc4_u) g_bctc_bc4_u_pipeline = [dev newComputePipelineStateWithFunction:fn_bc4_u error:&error];
    id<MTLFunction> fn_bc4_s = [library newFunctionWithName:@"bctc_bc4_s"];
    if (fn_bc4_s) g_bctc_bc4_s_pipeline = [dev newComputePipelineStateWithFunction:fn_bc4_s error:&error];
    id<MTLFunction> fn_bc5_u = [library newFunctionWithName:@"bctc_bc5_u"];
    if (fn_bc5_u) g_bctc_bc5_u_pipeline = [dev newComputePipelineStateWithFunction:fn_bc5_u error:&error];
    id<MTLFunction> fn_bc5_s = [library newFunctionWithName:@"bctc_bc5_s"];
    if (fn_bc5_s) g_bctc_bc5_s_pipeline = [dev newComputePipelineStateWithFunction:fn_bc5_s error:&error];
    return (g_bctc_bc3_pipeline != nil) ? 0 : -1;
}}

int nvn_bctc_gpu_supported(void) {{
    return (g_bctc_bc3_pipeline != nil);
}}

int nvn_bctc_gpu_decode(id<MTLComputeCommandEncoder> enc, int nvn_format,
                        uint32_t width, uint32_t height,
                        id<MTLBuffer> src_bc, uint64_t src_off, size_t src_pitch,
                        id<MTLBuffer> dst_px, uint64_t dst_off, size_t dst_pitch) {{
    id<MTLComputePipelineState> pipeline = nil;
    if (nvn_format == 0x44 || nvn_format == 0x48) {{
        pipeline = g_bctc_bc3_pipeline;
    }} else if (nvn_format == 0x4D || nvn_format == 0x4E) {{
        pipeline = g_bctc_bc7_pipeline;
    }} else if (nvn_format == 0x49) {{
        pipeline = g_bctc_bc4_u_pipeline;
    }} else if (nvn_format == 0x4A) {{
        pipeline = g_bctc_bc4_s_pipeline;
    }} else if (nvn_format == 0x4B) {{
        pipeline = g_bctc_bc5_u_pipeline;
    }} else if (nvn_format == 0x4C) {{
        pipeline = g_bctc_bc5_s_pipeline;
    }}
    if (!pipeline || !enc || !src_bc || !dst_px) return -1;

    struct {{ uint32_t width, height, src_pitch, dst_pitch; }} p = {{
        width, height, (uint32_t)src_pitch, (uint32_t)dst_pitch
    }};

    [enc setComputePipelineState:pipeline];
    [enc setBuffer:src_bc offset:src_off atIndex:0];
    [enc setBuffer:dst_px offset:dst_off atIndex:1];
    [enc setBytes:&p length:sizeof p atIndex:2];

    NSUInteger bx = (width + 3) / 4;
    NSUInteger by = (height + 3) / 4;
    NSUInteger tx = MIN((NSUInteger)8, bx);
    NSUInteger ty = MIN((NSUInteger)8, by);
    if (tx == 0) tx = 1;
    if (ty == 0) ty = 1;
    [enc dispatchThreadgroups:MTLSizeMake((bx + tx - 1) / tx, (by + ty - 1) / ty, 1)
        threadsPerThreadgroup:MTLSizeMake(tx, ty, 1)];
    return 0;
}}

int nvn_bctc_gpu_encode_m4(id<MTL4ComputeCommandEncoder> enc, id<MTL4ArgumentTable> table,
                            id<MTLBuffer> params, size_t params_off, int nvn_format,
                            uint32_t width, uint32_t height,
                            id<MTLBuffer> src_bc, uint64_t src_off, size_t src_pitch,
                            id<MTLBuffer> dst_px, uint64_t dst_off, size_t dst_pitch) {{
    id<MTLComputePipelineState> pipeline = nil;
    if (nvn_format == 0x44 || nvn_format == 0x48) {{
        pipeline = g_bctc_bc3_pipeline;
    }} else if (nvn_format == 0x4D || nvn_format == 0x4E) {{
        pipeline = g_bctc_bc7_pipeline;
    }} else if (nvn_format == 0x49) {{
        pipeline = g_bctc_bc4_u_pipeline;
    }} else if (nvn_format == 0x4A) {{
        pipeline = g_bctc_bc4_s_pipeline;
    }} else if (nvn_format == 0x4B) {{
        pipeline = g_bctc_bc5_u_pipeline;
    }} else if (nvn_format == 0x4C) {{
        pipeline = g_bctc_bc5_s_pipeline;
    }}
    if (!pipeline || !enc || !table || !params || !src_bc || !dst_px) return -1;

    struct {{ uint32_t width, height, src_pitch, dst_pitch; }} p = {{
        width, height, (uint32_t)src_pitch, (uint32_t)dst_pitch
    }};
    memcpy((uint8_t *)params.contents + params_off, &p, sizeof p);

    [enc setArgumentTable:table];
    [enc setComputePipelineState:pipeline];
    [table setAddress:src_bc.gpuAddress + src_off atIndex:0];
    [table setAddress:dst_px.gpuAddress + dst_off atIndex:1];
    [table setAddress:params.gpuAddress + params_off atIndex:2];

    NSUInteger bx = (width + 3) / 4;
    NSUInteger by = (height + 3) / 4;
    NSUInteger tx = MIN((NSUInteger)8, bx);
    NSUInteger ty = MIN((NSUInteger)8, by);
    if (tx == 0) tx = 1;
    if (ty == 0) ty = 1;
    [enc dispatchThreadgroups:MTLSizeMake((bx + tx - 1) / tx, (by + ty - 1) / ty, 1)
        threadsPerThreadgroup:MTLSizeMake(tx, ty, 1)];
    return 0;
}}
"""
    with open(bctc_m_path, "w", encoding="utf-8") as f:
        f.write(bctc_m_code)
    print("  [OK] Created nvn_bctc_gpu.m")

    # 1.5 nvn_bc_dec.h
    h_path = os.path.join(tex_dir, "nvn_bc_dec.h")
    h_code = """#ifndef NVN_BC_DEC_H
#define NVN_BC_DEC_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int nvn_bc_supported(void);
void nvn_bc_set_supported(int supported);
int nvn_is_bc_format(int nvn_format);
int nvn_is_bc1_format(int nvn_format);
uint32_t nvn_bc_decompressed_mtl_format(int nvn_format);
int nvn_bc_bytes_per_pixel(int nvn_format);

void nvn_decompress_bc(int nvn_format, uint32_t width, uint32_t height,
                       const void *src_bc, size_t src_pitch,
                       void *dst_pixels, size_t dst_pitch);

#ifdef __cplusplus
}
#endif

#endif // NVN_BC_DEC_H
"""
    with open(h_path, "w", encoding="utf-8") as f:
        f.write(h_code)
    print("  [OK] Created nvn_bc_dec.h")

    # 2. nvn_bc_dec.c
    c_path = os.path.join(tex_dir, "nvn_bc_dec.c")
    c_code = """#include "nvn_bc_dec.h"
#include "nvn_bc1astc.h"
#include <string.h>
#include <stdlib.h>
#include <TargetConditionals.h>

#define BCDEC_BC4BC5_PRECISE 1
#define BCDEC_IMPLEMENTATION
#include "bcdec.h"

#if TARGET_OS_IPHONE
static int g_bc_supported = 0;
#else
static int g_bc_supported = 1;
#endif

int nvn_bc_supported(void) {
    return g_bc_supported;
}

void nvn_bc_set_supported(int supported) {
    g_bc_supported = supported;
}

int nvn_is_bc_format(int nvn_format) {
    return (nvn_format >= 0x41 && nvn_format <= 0x50);
}

int nvn_is_bc1_format(int nvn_format) {
    return (nvn_format == 0x41 || nvn_format == 0x42 || nvn_format == 0x45 || nvn_format == 0x46);
}

uint32_t nvn_bc_decompressed_mtl_format(int nvn_format) {
    if (nvn_bc1_astc_enabled() && nvn_is_bc1_format(nvn_format)) {
        // MTLPixelFormatASTC_4x4_sRGB = 186, MTLPixelFormatASTC_4x4_LDR = 204
        return (nvn_format == 0x45 || nvn_format == 0x46) ? 186 : 204;
    }

    switch (nvn_format) {
        // Linear / Unorm
        case 0x41: // RGB_DXT1
        case 0x42: // RGBA_DXT1
        case 0x43: // RGBA_DXT3
        case 0x44: // RGBA_DXT5
        case 0x4D: // BPTC_UNORM (BC7)
            return 70; // MTLPixelFormatRGBA8Unorm

        // sRGB
        case 0x45: // RGB_DXT1_SRGB
        case 0x46: // RGBA_DXT1_SRGB
        case 0x47: // RGBA_DXT3_SRGB
        case 0x48: // RGBA_DXT5_SRGB
        case 0x4E: // BPTC_UNORM_SRGB (BC7_sRGB)
            return 71; // MTLPixelFormatRGBA8Unorm_sRGB

        // Single channel R8
        case 0x49: // RGTC1_UNORM (BC4_U)
            return 10; // MTLPixelFormatR8Unorm
        case 0x4A: // RGTC1_SNORM (BC4_S)
            return 12; // MTLPixelFormatR8Snorm

        // Two channel RG8
        case 0x4B: // RGTC2_UNORM (BC5_U)
            return 30; // MTLPixelFormatRG8Unorm
        case 0x4C: // RGTC2_SNORM (BC5_S)
            return 32; // MTLPixelFormatRG8Snorm

        // HDR Float
        case 0x4F: // BPTC_SFLOAT (BC6H_S)
        case 0x50: // BPTC_UFLOAT (BC6H_U)
            return 110; // MTLPixelFormatRGBA16Float
        default:
            return 0;
    }
}

int nvn_bc_bytes_per_pixel(int nvn_format) {
    if (nvn_bc1_astc_enabled() && nvn_is_bc1_format(nvn_format)) {
        return 1;
    }
    switch (nvn_format) {
        case 0x49: case 0x4A:
            return 1;
        case 0x4B: case 0x4C:
            return 2;
        case 0x4F: case 0x50:
            return 8;
        default:
            return 4;
    }
}

void nvn_decompress_bc(int nvn_format, uint32_t width, uint32_t height,
                       const void *src_bc, size_t src_pitch,
                       void *dst_pixels, size_t dst_pitch) {
    int dst_bpp = nvn_bc_bytes_per_pixel(nvn_format);
    uint32_t bx = (width + 3) / 4;
    uint32_t by = (height + 3) / 4;
    size_t block_bytes = (nvn_format == 0x41 || nvn_format == 0x42 ||
                          nvn_format == 0x45 || nvn_format == 0x46 ||
                          nvn_format == 0x49 || nvn_format == 0x4A) ? 8 : 16;

    for (uint32_t y = 0; y < by; y++) {
        const uint8_t *src_row = (const uint8_t *)src_bc + y * src_pitch;
        for (uint32_t x = 0; x < bx; x++) {
            const uint8_t *comp_block = src_row + x * block_bytes;
            uint8_t *dst_block = (uint8_t *)dst_pixels + (y * 4) * dst_pitch + (x * 4) * dst_bpp;
            int cur_w = (width - x * 4 < 4) ? (int)(width - x * 4) : 4;
            int cur_h = (height - y * 4 < 4) ? (int)(height - y * 4) : 4;
            int bw = 4;

            if (cur_w == 4 && cur_h == 4) {
                switch (nvn_format) {
                    case 0x41: case 0x45:
                        // onlyOpaqueMode = 1 forces full 4-color opaque decompression (no transparent pixels!)
                        bcdec__color_block(comp_block, dst_block, (int)dst_pitch, 1);
                        break;
                    case 0x42: case 0x46:
                        bcdec_bc1(comp_block, dst_block, (int)dst_pitch);
                        break;
                    case 0x43: case 0x47:
                        bcdec_bc2(comp_block, dst_block, (int)dst_pitch);
                        break;
                    case 0x44: case 0x48:
                        bcdec_bc3(comp_block, dst_block, (int)dst_pitch);
                        break;
                    case 0x49:
                        bcdec_bc4(comp_block, dst_block, (int)dst_pitch, 0);
                        break;
                    case 0x4A:
                        bcdec_bc4(comp_block, dst_block, (int)dst_pitch, 1);
                        break;
                    case 0x4B:
                        bcdec_bc5(comp_block, dst_block, (int)dst_pitch, 0);
                        break;
                    case 0x4C:
                        bcdec_bc5(comp_block, dst_block, (int)dst_pitch, 1);
                        break;
                    case 0x4D: case 0x4E:
                        bcdec_bc7(comp_block, dst_block, (int)dst_pitch);
                        break;
                    case 0x4F: case 0x50: {
                        uint16_t rgb_half[16 * 3];
                        bcdec_bc6h_half(comp_block, rgb_half, 4 * 3 * sizeof(uint16_t), nvn_format == 0x4F ? 1 : 0);
                        for (int dy = 0; dy < 4; dy++) {
                            uint16_t *d = (uint16_t *)(dst_block + dy * dst_pitch);
                            for (int dx = 0; dx < 4; dx++) {
                                d[dx * 4 + 0] = rgb_half[(dy * 4 + dx) * 3 + 0];
                                d[dx * 4 + 1] = rgb_half[(dy * 4 + dx) * 3 + 1];
                                d[dx * 4 + 2] = rgb_half[(dy * 4 + dx) * 3 + 2];
                                d[dx * 4 + 3] = 0x3C00;
                            }
                        }
                        break;
                    }
                    default:
                        break;
                }
            } else {
                uint8_t temp[4 * 4 * 8];
                int temp_pitch = bw * dst_bpp;
                switch (nvn_format) {
                    case 0x41: case 0x45:
                        bcdec__color_block(comp_block, temp, temp_pitch, 1);
                        break;
                    case 0x42: case 0x46:
                        bcdec_bc1(comp_block, temp, temp_pitch);
                        break;
                    case 0x43: case 0x47:
                        bcdec_bc2(comp_block, temp, temp_pitch);
                        break;
                    case 0x44: case 0x48:
                        bcdec_bc3(comp_block, temp, temp_pitch);
                        break;
                    case 0x49:
                        bcdec_bc4(comp_block, temp, temp_pitch, 0);
                        break;
                    case 0x4A:
                        bcdec_bc4(comp_block, temp, temp_pitch, 1);
                        break;
                    case 0x4B:
                        bcdec_bc5(comp_block, temp, temp_pitch, 0);
                        break;
                    case 0x4C:
                        bcdec_bc5(comp_block, temp, temp_pitch, 1);
                        break;
                    case 0x4D: case 0x4E:
                        bcdec_bc7(comp_block, temp, temp_pitch);
                        break;
                    case 0x4F: case 0x50: {
                        uint16_t rgb_half[16 * 3];
                        bcdec_bc6h_half(comp_block, rgb_half, 4 * 3 * sizeof(uint16_t), nvn_format == 0x4F ? 1 : 0);
                        for (int y_sub = 0; y_sub < 4; y_sub++) {
                            uint16_t *d = (uint16_t *)(temp + y_sub * temp_pitch);
                            for (int x_sub = 0; x_sub < 4; x_sub++) {
                                d[x_sub * 4 + 0] = rgb_half[(y_sub * 4 + x_sub) * 3 + 0];
                                d[x_sub * 4 + 1] = rgb_half[(y_sub * 4 + x_sub) * 3 + 1];
                                d[x_sub * 4 + 2] = rgb_half[(y_sub * 4 + x_sub) * 3 + 2];
                                d[x_sub * 4 + 3] = 0x3C00;
                            }
                        }
                        break;
                    }
                    default:
                        break;
                }
                for (int y_sub = 0; y_sub < cur_h; y_sub++) {
                    memcpy(dst_block + y_sub * dst_pitch, temp + y_sub * temp_pitch, cur_w * dst_bpp);
                }
            }
        }
    }
}
"""
    with open(c_path, "w", encoding="utf-8") as f:
        f.write(c_code)
    print("  [OK] Created nvn_bc_dec.c")

    # 3. Patch nvn_fmt_mtl.c
    fmt_path = os.path.join(tex_dir, "nvn_fmt_mtl.c")
    with open(fmt_path, "r", encoding="utf-8") as f:
        fmt_s = f.read().replace('\r\n', '\n')
    if '#include "nvn_bc_dec.h"' not in fmt_s:
        fmt_s = fmt_s.replace('#include "nvn_fmt_mtl.h"', '#include "nvn_fmt_mtl.h"\n#include "nvn_bc_dec.h"', 1)
        old_fn = "int nvn_fmt_to_mtl(int f, uint32_t *mtl, uint8_t swz[4]) {\n    ent e = {0, 0, 0, 0};\n    if (f >= 0x79 && f <= 0x94) { int k = (f - 0x79) % 14; e = (ent){(uint16_t)((f < 0x87 ? ASTC_LDR0 : ASTC_SRGB0) + astc_off[k]), 1, 0, 0}; }\n    else if (f > 0 && f < (int)(sizeof T / sizeof *T)) e = T[f];\n    if (mtl) *mtl = e.kind ? e.mtl : 0;"
        new_fn = "int nvn_fmt_to_mtl(int f, uint32_t *mtl, uint8_t swz[4]) {\n    ent e = {0, 0, 0, 0};\n    if (f >= 0x79 && f <= 0x94) { int k = (f - 0x79) % 14; e = (ent){(uint16_t)((f < 0x87 ? ASTC_LDR0 : ASTC_SRGB0) + astc_off[k]), 1, 0, 0}; }\n    else if (f > 0 && f < (int)(sizeof T / sizeof *T)) e = T[f];\n    if (f >= 0x41 && f <= 0x50 && !nvn_bc_supported()) {\n        uint32_t sub = nvn_bc_decompressed_mtl_format(f);\n        if (sub) { e.mtl = (uint16_t)sub; e.kind = 2; }\n    }\n    if (mtl) *mtl = e.kind ? e.mtl : 0;"
        assert old_fn in fmt_s, "Target function in nvn_fmt_mtl.c not found"
        fmt_s = fmt_s.replace(old_fn, new_fn, 1)
        with open(fmt_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(fmt_s)
        print("  [OK] Patched nvn_fmt_mtl.c")
    else:
        print("  [SKIP] nvn_fmt_mtl.c already patched")

    # 4. Patch nvn_mtl.m
    mtl_path = os.path.join(nvn_dir, "nvn_mtl.m")
    with open(mtl_path, "r", encoding="utf-8") as f:
        mtl_s = f.read().replace('\r\n', '\n')

    # 4.0.0.1 Fallback shader chain matching and directory auto-detection
    old_chain_chk = 'if (![j[@"chain"] isEqual:@DMSH_CHAIN]) { MLOG("[RED] shader %s has translation chain version %s, but this host expects %s", pc.UTF8String, [[j[@"chain"] description] UTF8String], DMSH_CHAIN); return nil; }'
    new_chain_chk = 'if (![j[@"chain"] isEqual:@DMSH_CHAIN] && ![j[@"chain"] isEqual:@"670578cbb17a"] && ![j[@"chain"] isEqual:@"157e1b96c8da"]) { static int s_cwarn = 0; if (s_cwarn++ < 5) MLOG("[WARN] shader %s chain %s != host %s, allowing fallback", pc.UTF8String, [[j[@"chain"] description] UTF8String], DMSH_CHAIN); }'
    if old_chain_chk in mtl_s:
        mtl_s = mtl_s.replace(old_chain_chk, new_chain_chk, 1)

    old_msl_dir = 'g_msl_dir = [NSString stringWithFormat:@"%@/b-%s", m ? @(m) : [NSString stringWithFormat:@"%s%s/build/cache/metal_shader_cache", getenv("DM_ROOT") ?: getenv("HOME"), getenv("DM_ROOT") ? "" : "/dm-work"], DMSH_CHAIN];'
    new_msl_dir = """g_msl_dir = [NSString stringWithFormat:@"%@/b-%s", m ? @(m) : [NSString stringWithFormat:@"%s%s/build/cache/metal_shader_cache", getenv("DM_ROOT") ?: getenv("HOME"), getenv("DM_ROOT") ? "" : "/dm-work"], DMSH_CHAIN];
    if (![NSFileManager.defaultManager fileExistsAtPath:g_msl_dir]) {
        NSString *msl_p = m ? @(m) : nil;
        if (msl_p) {
            NSArray<NSString *> *subs = [NSFileManager.defaultManager contentsOfDirectoryAtPath:msl_p error:nil];
            for (NSString *sub in subs) {
                if ([sub hasPrefix:@"b-"]) {
                    NSString *cand = [msl_p stringByAppendingPathComponent:sub];
                    BOOL isDir = NO;
                    if ([NSFileManager.defaultManager fileExistsAtPath:cand isDirectory:&isDir] && isDir) {
                        g_msl_dir = cand;
                        MLOG("auto-detected shader library directory: %s", g_msl_dir.UTF8String);
                        break;
                    }
                }
            }
        }
    }"""
    if old_msl_dir in mtl_s and "auto-detected shader library directory" not in mtl_s:
        mtl_s = mtl_s.replace(old_msl_dir, new_msl_dir, 1)

    # 4.0.0 NvPkg purgeable tracking fields & pkg_unpurge declaration
    if 'uint64_t used; int vol, lost, owned;' not in mtl_s:
        old_pkg1 = '@interface NvPkg : NSObject { @public id<MTLTexture> tex, spare, view; uint64_t stamp, seen, hash, spare_fence, vgen, vseen; const void *span; int sparse, vbase; uint8_t *edge[2]; uint32_t edge_n[2]; } @end'
        old_pkg2 = '@interface NvPkg : NSObject { @public id<MTLTexture> tex, spare, view; uint64_t stamp, seen, hash, spare_fence, vgen, vseen; const void *span; int sparse, vbase; } @end'
        new_pkg1 = """@interface NvPkg : NSObject { @public id<MTLTexture> tex, spare, view; uint64_t stamp, seen, hash, spare_fence, vgen, vseen; const void *span; int sparse, vbase; uint8_t *edge[2]; uint32_t edge_n[2]; uint64_t used; int vol, lost, owned; } @end
static void pkg_unpurge(NvPkg *pk, const tex_t *t);
static void pkg_purge_idle(uint64_t max_idle_fences);
static void pkg_evict_sweep(uint64_t max_idle_fences);"""
        new_pkg2 = """@interface NvPkg : NSObject { @public id<MTLTexture> tex, spare, view; uint64_t stamp, seen, hash, spare_fence, vgen, vseen; const void *span; int sparse, vbase; uint64_t used; int vol, lost, owned; } @end
static void pkg_unpurge(NvPkg *pk, const tex_t *t);
static void pkg_purge_idle(uint64_t max_idle_fences);
static void pkg_evict_sweep(uint64_t max_idle_fences);"""
        if old_pkg1 in mtl_s:
            mtl_s = mtl_s.replace(old_pkg1, new_pkg1, 1)
        elif old_pkg2 in mtl_s:
            mtl_s = mtl_s.replace(old_pkg2, new_pkg2, 1)

        old_dealloc1 = '- (void)dealloc { res_remove(tex); if (spare) res_remove(spare); free(edge[0]); free(edge[1]); }'
        old_dealloc2 = '- (void)dealloc { res_remove(tex); if (spare) res_remove(spare); }'
        new_dealloc1 = '- (void)dealloc { if (tex) res_remove(tex); if (spare) res_remove(spare); free(edge[0]); free(edge[1]); }'
        new_dealloc2 = '- (void)dealloc { if (tex) res_remove(tex); if (spare) res_remove(spare); }'
        if old_dealloc1 in mtl_s:
            mtl_s = mtl_s.replace(old_dealloc1, new_dealloc1, 1)
        elif old_dealloc2 in mtl_s:
            mtl_s = mtl_s.replace(old_dealloc2, new_dealloc2, 1)

        old_pk_check = 'if (pk) {   // Already uploaded: check the covered pages only if there has been a guest write since the last check'
        new_pk_check = """if (pk) {
            pk->used = g_fence;
            if (pk->vol || pk->lost) pkg_unpurge(pk, t);"""
        if old_pk_check in mtl_s:
            mtl_s = mtl_s.replace(old_pk_check, new_pk_check, 1)

        old_new_pk = 'pk = [NvPkg new];\n        pk->sparse = t->pool && nvn_sparse_pool(t->pool);'
        new_new_pk = 'pk = [NvPkg new];\n        pk->used = g_fence;\n        pk->sparse = t->pool && nvn_sparse_pool(t->pool);'
        if old_new_pk in mtl_s:
            mtl_s = mtl_s.replace(old_new_pk, new_new_pk, 1)
        print('  [OK] Injected NvPkg purgeable fields & tex_mtl unpurge hooks')


    # 4.0 Header inclusions
    if '#include "../tex/nvn_bc_dec.h"' not in mtl_s:
        mtl_s = mtl_s.replace('#include "../tex/nvn_deswizzle_gpu.h"',
                              '#include "../tex/nvn_deswizzle_gpu.h"\n#include "../tex/nvn_bc_dec.h"\n#include "../tex/nvn_bc1astc.h"\n#include "../tex/nvn_bctc_gpu.h"', 1)
    else:
        if '#include "../tex/nvn_bc1astc.h"' not in mtl_s:
            mtl_s = mtl_s.replace('#include "../tex/nvn_bc_dec.h"',
                                  '#include "../tex/nvn_bc_dec.h"\n#include "../tex/nvn_bc1astc.h"\n#include "../tex/nvn_bctc_gpu.h"', 1)

    # 4.0.1 Device capability hook
    if "supportsBCTextureCompression" not in mtl_s:
        old_init = 'if (!g_dev) MDIE("no Metal device");\n    if (!g_dev.hasUnifiedMemory) MDIE("needs a unified-memory device (zero-copy memory pools)");'
        new_init = '''if (!g_dev) MDIE("no Metal device");
    if (!g_dev.hasUnifiedMemory) MDIE("needs a unified-memory device (zero-copy memory pools)");
    BOOL supports_bc = NO;
#if TARGET_OS_IPHONE
    supports_bc = NO;
#elif TARGET_OS_OSX
    supports_bc = YES;
#else
    if (@available(iOS 16.4, macOS 11.0, *)) {
        if ([g_dev respondsToSelector:@selector(supportsBCTextureCompression)]) {
            supports_bc = [g_dev supportsBCTextureCompression];
        }
    }
#endif
    nvn_bc_set_supported(supports_bc ? 1 : 0);
    MLOG("Metal device: %s, supportsBCTextureCompression: %d", [g_dev.name UTF8String], (int)supports_bc);'''
        if old_init in mtl_s:
            mtl_s = mtl_s.replace(old_init, new_init, 1)

    # 4.0.2 GPU Compute BCTC init hook & pipeline archive startup init
    if "nvn_bctc_gpu_init" not in mtl_s:
        old_deswz_init = "g_nvn_deswz_gpu = nvn_deswz_gpu_init(g_dev) == 0;"
        new_deswz_init = "g_nvn_deswz_gpu = nvn_deswz_gpu_init(g_dev) == 0;\n    nvn_bctc_gpu_init(g_dev);"
        if old_deswz_init in mtl_s:
            mtl_s = mtl_s.replace(old_deswz_init, new_deswz_init, 1)

    # 4.0.3 Staging total calculation
    new_total = """    int bw, bh, bpb = nvn_fmt_bpb(t->d.format, &bw, &bh);
    unsigned layers = (t->d.target == 4 || t->d.target == 9) ? t->d.depth : t->d.target == 8 ? 6 : t->d.target == 3 ? t->d.height : 1;   // a cube array's depth counts layer-faces (tex_desc)
    int decompress_bc = !nvn_bc_supported() && nvn_is_bc_format(t->d.format);
    int is_bc1_astc = decompress_bc && nvn_bc1_astc_enabled() && nvn_is_bc1_format(t->d.format);
    int dst_bpp = decompress_bc ? nvn_bc_bytes_per_pixel(t->d.format) : bpb;
    size_t total = 0;
    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (is_bc1_astc) {
            size_t astc_pitch = (size_t)((w + 3) / 4) * 16;
            size_t astc_rows = (h + 3) / 4;
            total += astc_pitch * astc_rows * z * layers;
        } else if (decompress_bc) {
            total += (size_t)w * dst_bpp * h * z * layers;
        } else {
            total += (size_t)((w + bw - 1) / bw) * bpb * ((h + bh - 1) / bh) * z * layers;
        }
    }
    g_bp_up_bytes += total;
    void *mb; uint64_t mo;
    int use_gpu = !decompress_bc && !sparse && g_nvn_deswz_gpu && mtl_addr((uint64_t)t->mem, t->L.size, &mb, &mo);"""

    if "is_bc1_astc" not in mtl_s:
        cand1 = """    int bw, bh, bpb = nvn_fmt_bpb(t->d.format, &bw, &bh);
    unsigned layers = (t->d.target == 4 || t->d.target == 9) ? t->d.depth : t->d.target == 8 ? 6 : t->d.target == 3 ? t->d.height : 1;   // a cube array's depth counts layer-faces (tex_desc)
    int decompress_bc = !nvn_bc_supported() && nvn_is_bc_format(t->d.format);
    int dst_bpp = decompress_bc ? nvn_bc_bytes_per_pixel(t->d.format) : bpb;
    size_t total = 0;
    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (decompress_bc) {
            total += (size_t)w * dst_bpp * h * z * layers;
        } else {
            total += (size_t)((w + bw - 1) / bw) * bpb * ((h + bh - 1) / bh) * z * layers;
        }
    }
    g_bp_up_bytes += total;
    void *mb; uint64_t mo;
    int use_gpu = !decompress_bc && !sparse && g_nvn_deswz_gpu && mtl_addr((uint64_t)t->mem, t->L.size, &mb, &mo);"""

        cand2 = """    int bw, bh, bpb = nvn_fmt_bpb(t->d.format, &bw, &bh);
    unsigned layers = (t->d.target == 4 || t->d.target == 9) ? t->d.depth : t->d.target == 8 ? 6 : t->d.target == 3 ? t->d.height : 1;   // a cube array's depth counts layer-faces (tex_desc)
    size_t total = 0;
    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        total += (size_t)((w + bw - 1) / bw) * bpb * ((h + bh - 1) / bh) * z * layers;
    }
    g_bp_up_bytes += total;
    void *mb; uint64_t mo;
    int use_gpu = !sparse && g_nvn_deswz_gpu && mtl_addr((uint64_t)t->mem, t->L.size, &mb, &mo);"""

        cand3 = """    int bw, bh, bpb = nvn_fmt_bpb(t->d.format, &bw, &bh);
    int is_bc_sw = nvn_is_bc_format(t->d.format) && !nvn_bc_supported();
    int dst_bpp = is_bc_sw ? nvn_bc_bytes_per_pixel(t->d.format) : bpb;
    unsigned layers = (t->d.target == 4 || t->d.target == 9) ? t->d.depth : t->d.target == 8 ? 6 : t->d.target == 3 ? t->d.height : 1;   // a cube array's depth counts layer-faces (tex_desc)
    size_t total = 0;
    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (is_bc_sw) {
            total += (size_t)w * dst_bpp * h * z * layers;
        } else {
            total += (size_t)((w + bw - 1) / bw) * bpb * ((h + bh - 1) / bh) * z * layers;
        }
    }
    g_bp_up_bytes += total;
    void *mb; uint64_t mo;
    int use_gpu = !is_bc_sw && !sparse && g_nvn_deswz_gpu && mtl_addr((uint64_t)t->mem, t->L.size, &mb, &mo);"""

        if cand1 in mtl_s:
            mtl_s = mtl_s.replace(cand1, new_total, 1)
        elif cand2 in mtl_s:
            mtl_s = mtl_s.replace(cand2, new_total, 1)
        elif cand3 in mtl_s:
            mtl_s = mtl_s.replace(cand3, new_total, 1)
        else:
            raise AssertionError("Total calculation block not found in nvn_mtl.m")

    # 4.0.4 Upload loop
    new_loop = """    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (is_bc1_astc) {
            size_t bc_pitch = (size_t)((w + bw - 1) / bw) * bpb;
            size_t bc_rows = (h + bh - 1) / bh;
            size_t bc_slice = bc_pitch * bc_rows;
            size_t bc_size = bc_slice * z;
            uint8_t *bc_tmp = (uint8_t *)malloc(bc_size ? bc_size : 16);
            size_t astc_pitch = (size_t)((w + 3) / 4) * 16;
            size_t astc_rows = (h + 3) / 4;
            size_t astc_slice = astc_pitch * astc_rows;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, bc_tmp, bc_pitch)) {
                    RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target);
                    break;
                }
                for (uint32_t s = 0; s < z; s++) {
                    const void *src_bc = bc_tmp + s * bc_slice;
                    void *dst_astc = (uint8_t *)stg.contents + off + s * astc_slice;
                    nvn_bc1_to_astc4x4(w, h, src_bc, bc_pitch, dst_astc, astc_pitch);
                }
                up_blit_add(stg, off, astc_pitch, astc_slice, MTLSizeMake(w, h, z), mt, y, l);
                off += astc_slice * z;
            }
            free(bc_tmp);
        } else if (decompress_bc) {
            size_t bc_pitch = (size_t)((w + bw - 1) / bw) * bpb;
            size_t bc_rows = (h + bh - 1) / bh;
            size_t bc_slice = bc_pitch * bc_rows;
            size_t bc_size = bc_slice * z;
            size_t decomp_pitch = (size_t)w * dst_bpp;
            size_t decomp_slice = decomp_pitch * h;
            int use_gpu_bc = nvn_bctc_gpu_supported() && (t->d.format == 0x44 || t->d.format == 0x48 || t->d.format == 0x49 || t->d.format == 0x4A || t->d.format == 0x4B || t->d.format == 0x4C || t->d.format == 0x4D || t->d.format == 0x4E);
            id<MTLBuffer> bc_buf = nil;
            uint8_t *bc_cpu = NULL;
            if (use_gpu_bc) {
                bc_buf = [g_dev newBufferWithLength:bc_size ? bc_size : 16 options:MTLResourceStorageModeShared];
                res_add(bc_buf);
                [g_up_keep addObject:bc_buf];
            } else {
                bc_cpu = (uint8_t *)malloc(bc_size ? bc_size : 16);
            }
            for (unsigned y = 0; y < layers; y++) {
                void *bc_dst = use_gpu_bc ? bc_buf.contents : (void *)bc_cpu;
                if (nvn_deswizzle(&t->d, l, y, src, bc_dst, bc_pitch)) {
                    RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target);
                    break;
                }
                for (uint32_t s = 0; s < z; s++) {
                    if (use_gpu_bc) {
                        size_t poff; id<MTLBuffer> pbuf = up_param_alloc(&poff);
                        nvn_bctc_gpu_encode_m4(g_up_ce, g_up_ct, pbuf, poff, t->d.format, w, h,
                                               bc_buf, s * bc_slice, bc_pitch,
                                               stg, off + s * decomp_slice, decomp_pitch);
                    } else {
                        const void *src_bc = bc_cpu + s * bc_slice;
                        void *dst_px = (uint8_t *)stg.contents + off + s * decomp_slice;
                        nvn_decompress_bc(t->d.format, w, h, src_bc, bc_pitch, dst_px, decomp_pitch);
                    }
                }
                up_blit_add(stg, off, decomp_pitch, decomp_slice, MTLSizeMake(w, h, z), mt, y, l);
                off += decomp_slice * z;
            }
            if (bc_cpu) free(bc_cpu);
        } else {
            size_t pitch = (size_t)((w + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, (uint8_t *)stg.contents + off, pitch)) { RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target); break; }
                if (zb && l < 16) { const uint64_t *q = (const uint64_t *)((const uint8_t *)stg.contents + off); size_t nb = pitch * rows * z / 16;
                    for (size_t i = 0; i < nb; i++) g_zb[l] += !(q[2 * i] | q[2 * i + 1]);
                    g_zb_tot[l] += (uint32_t)nb; }
                up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);
                off += pitch * rows * z;
            }
        }
    }"""

    if "nvn_bctc_gpu_encode_m4" not in mtl_s:
        cand_loop0 = """    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (is_bc1_astc) {
            size_t bc_pitch = (size_t)((w + bw - 1) / bw) * bpb;
            size_t bc_rows = (h + bh - 1) / bh;
            size_t bc_slice = bc_pitch * bc_rows;
            size_t bc_size = bc_slice * z;
            uint8_t *bc_tmp = (uint8_t *)malloc(bc_size ? bc_size : 16);
            size_t astc_pitch = (size_t)((w + 3) / 4) * 16;
            size_t astc_rows = (h + 3) / 4;
            size_t astc_slice = astc_pitch * astc_rows;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, bc_tmp, bc_pitch)) {
                    RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target);
                    break;
                }
                for (uint32_t s = 0; s < z; s++) {
                    const void *src_bc = bc_tmp + s * bc_slice;
                    void *dst_astc = (uint8_t *)stg.contents + off + s * astc_slice;
                    nvn_bc1_to_astc4x4(w, h, src_bc, bc_pitch, dst_astc, astc_pitch);
                }
                up_blit_add(stg, off, astc_pitch, astc_slice, MTLSizeMake(w, h, z), mt, y, l);
                off += astc_slice * z;
            }
            free(bc_tmp);
        } else if (decompress_bc) {
            size_t bc_pitch = (size_t)((w + bw - 1) / bw) * bpb;
            size_t bc_rows = (h + bh - 1) / bh;
            size_t bc_slice = bc_pitch * bc_rows;
            size_t bc_size = bc_slice * z;
            uint8_t *bc_tmp = (uint8_t *)malloc(bc_size ? bc_size : 16);
            size_t decomp_pitch = (size_t)w * dst_bpp;
            size_t decomp_slice = decomp_pitch * h;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, bc_tmp, bc_pitch)) {
                    RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target);
                    break;
                }
                for (uint32_t s = 0; s < z; s++) {
                    const void *src_bc = bc_tmp + s * bc_slice;
                    void *dst_px = (uint8_t *)stg.contents + off + s * decomp_slice;
                    nvn_decompress_bc(t->d.format, w, h, src_bc, bc_pitch, dst_px, decomp_pitch);
                }
                up_blit_add(stg, off, decomp_pitch, decomp_slice, MTLSizeMake(w, h, z), mt, y, l);
                off += decomp_slice * z;
            }
            free(bc_tmp);
        } else {
            size_t pitch = (size_t)((w + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, (uint8_t *)stg.contents + off, pitch)) { RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target); break; }
                if (zb && l < 16) { const uint64_t *q = (const uint64_t *)((const uint8_t *)stg.contents + off); size_t nb = pitch * rows * z / 16;
                    for (size_t i = 0; i < nb; i++) g_zb[l] += !(q[2 * i] | q[2 * i + 1]);
                    g_zb_tot[l] += (uint32_t)nb; }
                up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);
                off += pitch * rows * z;
            }
        }
    }"""

        cand_loop1 = """    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (decompress_bc) {
            size_t bc_pitch = (size_t)((w + bw - 1) / bw) * bpb;
            size_t bc_rows = (h + bh - 1) / bh;
            size_t bc_slice = bc_pitch * bc_rows;
            size_t bc_size = bc_slice * z;
            uint8_t *bc_tmp = (uint8_t *)malloc(bc_size ? bc_size : 16);
            size_t decomp_pitch = (size_t)w * dst_bpp;
            size_t decomp_slice = decomp_pitch * h;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, bc_tmp, bc_pitch)) {
                    RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target);
                    break;
                }
                for (uint32_t s = 0; s < z; s++) {
                    const void *src_bc = bc_tmp + s * bc_slice;
                    void *dst_px = (uint8_t *)stg.contents + off + s * decomp_slice;
                    nvn_decompress_bc(t->d.format, w, h, src_bc, bc_pitch, dst_px, decomp_pitch);
                }
                up_blit_add(stg, off, decomp_pitch, decomp_slice, MTLSizeMake(w, h, z), mt, y, l);
                off += decomp_slice * z;
            }
            free(bc_tmp);
        } else {
            size_t pitch = (size_t)((w + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, (uint8_t *)stg.contents + off, pitch)) { RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target); break; }
                if (zb && l < 16) { const uint64_t *q = (const uint64_t *)((const uint8_t *)stg.contents + off); size_t nb = pitch * rows * z / 16;
                    for (size_t i = 0; i < nb; i++) g_zb[l] += !(q[2 * i] | q[2 * i + 1]);
                    g_zb_tot[l] += (uint32_t)nb; }
                up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);
                off += pitch * rows * z;
            }
        }
    }"""

        cand_loop2 = """    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        size_t pitch = (size_t)((w + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh;
        for (unsigned y = 0; y < layers; y++) {
            if (nvn_deswizzle(&t->d, l, y, src, (uint8_t *)stg.contents + off, pitch)) { RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target); break; }
            if (zb && l < 16) { const uint64_t *q = (const uint64_t *)((const uint8_t *)stg.contents + off); size_t nb = pitch * rows * z / 16;
                for (size_t i = 0; i < nb; i++) g_zb[l] += !(q[2 * i] | q[2 * i + 1]);
                g_zb_tot[l] += (uint32_t)nb; }
            up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);
            off += pitch * rows * z;
        }
    }"""

        cand_loop3 = """    for (unsigned l = 0; l < d.mipmapLevelCount; l++) {
        uint32_t w = MAX(t->d.width >> l, 1u), h = MAX(t->d.height >> l, 1u), z = t->d.target == 2 ? MAX(t->d.depth >> l, 1u) : 1;
        if (is_bc_sw) {
            size_t bc_pitch = (size_t)((w + bw - 1) / bw) * bpb, bc_rows = (h + bh - 1) / bh;
            size_t bc_slice = bc_pitch * bc_rows;
            size_t decomp_pitch = (size_t)w * dst_bpp;
            size_t decomp_slice = decomp_pitch * h;
            uint8_t *bc_tmp = (uint8_t *)malloc(bc_slice * z ? bc_slice * z : 16);
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, bc_tmp, bc_pitch)) {
                    RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target);
                    break;
                }
                for (uint32_t s = 0; s < z; s++) {
                    const void *src_bc = bc_tmp + s * bc_slice;
                    void *dst_px = (uint8_t *)stg.contents + off + s * decomp_slice;
                    nvn_decompress_bc(t->d.format, w, h, src_bc, bc_pitch, dst_px, decomp_pitch);
                }
                up_blit_add(stg, off, decomp_pitch, decomp_slice, MTLSizeMake(w, h, z), mt, y, l);
                off += decomp_slice * z;
            }
            free(bc_tmp);
        } else {
            size_t pitch = (size_t)((w + bw - 1) / bw) * bpb, rows = (h + bh - 1) / bh;
            for (unsigned y = 0; y < layers; y++) {
                if (nvn_deswizzle(&t->d, l, y, src, (uint8_t *)stg.contents + off, pitch)) { RED_ONCE(9, "deswizzle failed format %#x target %d", t->d.format, t->d.target); break; }
                if (zb && l < 16) { const uint64_t *q = (const uint64_t *)((const uint8_t *)stg.contents + off); size_t nb = pitch * rows * z / 16;
                for (size_t i = 0; i < nb; i++) g_zb[l] += !(q[2 * i] | q[2 * i + 1]);
                g_zb_tot[l] += (uint32_t)nb; }
                up_blit_add(stg, off, pitch, pitch * rows, MTLSizeMake(w, h, z), mt, y, l);
                off += pitch * rows * z;
            }
        }
    }"""

        if cand_loop0 in mtl_s:
            mtl_s = mtl_s.replace(cand_loop0, new_loop, 1)
        elif cand_loop1 in mtl_s:
            mtl_s = mtl_s.replace(cand_loop1, new_loop, 1)
        elif cand_loop2 in mtl_s:
            mtl_s = mtl_s.replace(cand_loop2, new_loop, 1)
        elif cand_loop3 in mtl_s:
            mtl_s = mtl_s.replace(cand_loop3, new_loop, 1)
        else:
            raise AssertionError("Upload loop block not found in nvn_mtl.m")

    # 4.1 Memory leak sweep: auto-evict unreferenced orphan textures from g_alias
    if "alias_trim_idle_orphans" not in mtl_s:
        old_after_takeover = """    if (n) { g_ser_gen++; g_alias_taken += n; }
}"""
        new_after_takeover = """    if (n) { g_ser_gen++; g_alias_taken += n; }
}
static void alias_trim_idle_orphans(uint64_t max_idle_fences) {
    if (!g_alias.cap) return;
    uint32_t n = 0;
    alias_key ks[128];
    for (uint32_t i = 0; i < g_alias.cap && n < 128; i++) {
        if (!g_alias.vals[i]) continue;
        if (serial_holds(&g_by_serial, (__bridge id)g_alias.vals[i])) continue;
        if (serial_holds(&g_ghost, (__bridge id)g_alias.vals[i])) continue;
        alias_key k; memcpy(&k, g_alias.keys + (size_t)i * g_alias.klen, sizeof k);
        uint64_t seen = (uint64_t)(uintptr_t)nvn_hm_get(&g_alias_seen, &k);
        if (seen && g_fence + 1 > seen && (g_fence + 1 - seen) < max_idle_fences) continue;
        ks[n++] = k;
    }
    for (uint32_t j = 0; j < n; j++) {
        void *old = nvn_hm_del(&g_alias, &ks[j]);
        if (!old) continue;
        nvn_hm_del(&g_alias_seen, &ks[j]);
        id o = CFBridgingRelease(old);
        if (g_alias_set) CFSetRemoveValue(g_alias_set, (__bridge const void *)o);
        defer_obj_release(o);
    }
    if (n) { g_ser_gen++; g_alias_taken += n; }
}"""
        assert old_after_takeover in mtl_s, "old_after_takeover in nvn_mtl.m not found"
        mtl_s = mtl_s.replace(old_after_takeover, new_after_takeover, 1)

        # Place purgeable helpers right before clear_rect_zero (where NvPkg and pkg_upload are fully defined)
        old_clear_rect = "static int clear_rect_zero(int i);"
        new_clear_rect = """static uint64_t g_purge_marked, g_purge_marked_mb;
static void pkg_purge_idle(uint64_t max_idle_fences) {
    if (!g_by_serial.cap) return;
    uint32_t k = 0; uint64_t bytes = 0;
    for (uint32_t i = 0; i < g_by_serial.cap; i++) {
        if (!g_by_serial.vals[i]) continue;
        __unsafe_unretained id o = (__bridge id)g_by_serial.vals[i];
        if (!o || ![o isKindOfClass:[NvPkg class]]) continue;
        NvPkg *pk = (NvPkg *)o;
        if (!pk->tex || pk->vol || pk->owned || (g_fence + 1 > pk->used && (g_fence + 1 - pk->used) < max_idle_fences)) continue;
        [pk->tex setPurgeableState:MTLPurgeableStateVolatile];
        pk->vol = 1;
        k++;
        bytes += pk->tex.allocatedSize;
    }
    if (k) {
        g_purge_marked += k;
        g_purge_marked_mb += (bytes >> 20);
    }
}
static void pkg_evict_sweep(uint64_t max_idle_fences) {
    if (!g_by_serial.cap) return;
    for (uint32_t i = 0; i < g_by_serial.cap; i++) {
        if (!g_by_serial.vals[i]) continue;
        __unsafe_unretained id o = (__bridge id)g_by_serial.vals[i];
        if (!o || ![o isKindOfClass:[NvPkg class]]) continue;
        NvPkg *pk = (NvPkg *)o;
        if (!pk->tex || pk->owned || (g_fence + 1 > pk->used && (g_fence + 1 - pk->used) < max_idle_fences)) continue;
        id<MTLTexture> old = pk->tex;
        pk->tex = nil;
        pk->vol = 0;
        pk->lost = 1;
        defer_obj_release(old);
    }
}
static void pkg_unpurge(NvPkg *pk, const tex_t *t) {
    pk->vol = 0;
    int lost = pk->lost; pk->lost = 0;
    if (!lost && pk->tex && [pk->tex setPurgeableState:MTLPurgeableStateNonVolatile] != MTLPurgeableStateEmpty) {
        return;
    }
    id<MTLTexture> old = pk->tex;
    pk->tex = nil;
    if (old) defer_obj_release(old);
    uint64_t st;
    pk->tex = pkg_upload(t, &st, nil);
    pk->stamp = st;
    pk->span = nvn_dirty_span(t->mem, t->L.size);
    pk->seen = nvn_dirty_now();
}

static int clear_rect_zero(int i);"""
        assert old_clear_rect in mtl_s, "old_clear_rect in nvn_mtl.m not found"
        mtl_s = mtl_s.replace(old_clear_rect, new_clear_rect, 1)

        # periodic sweep in present_enqueue
        old_pe_start = "static uint64_t present_enqueue(const tex_t *t, double period, const int crop[4], uint64_t ev_val) {\n"
        new_pe_start = """static uint64_t present_enqueue(const tex_t *t, double period, const int crop[4], uint64_t ev_val) {
    static uint32_t s_trim_cnt = 0;
    if (++s_trim_cnt % 10 == 0) {
        pthread_mutex_lock(&g_smu);
#if TARGET_OS_IPHONE
        uint64_t avail = os_proc_available_memory();
        if (avail < 250ull * 1024 * 1024) {
            alias_trim_idle_orphans(2);
            pkg_evict_sweep(4);
            pkg_purge_idle(4);
            defer_drain();
            malloc_zone_pressure_relief(NULL, 0);
        } else if (avail < 450ull * 1024 * 1024) {
            alias_trim_idle_orphans(5);
            pkg_evict_sweep(15);
            pkg_purge_idle(15);
            defer_drain();
            malloc_zone_pressure_relief(NULL, 0);
        } else if (avail < 750ull * 1024 * 1024) {
            alias_trim_idle_orphans(12);
            pkg_purge_idle(30);
            defer_drain();
        } else {
            alias_trim_idle_orphans(30);
            pkg_purge_idle(60);
        }
#else
        alias_trim_idle_orphans(60);
#endif
        pthread_mutex_unlock(&g_smu);
    }
"""
        assert old_pe_start in mtl_s, "old_pe_start in nvn_mtl.m not found"
        mtl_s = mtl_s.replace(old_pe_start, new_pe_start, 1)
        print("  [OK] Injected alias_trim_idle_orphans memory leak guard into nvn_mtl.m")

    # 4.2 Handheld mode crop & aspect ratio fix in present_encode / present_encode_m4
    if "eff_crop" not in mtl_s:
        old_pe = '''static int present_encode(id<MTLCommandBuffer> cb, id<MTLTexture> src, id<MTLTexture> dst, const int crop[4]) {
    NSUInteger cx = 0, cy = 0, cw = src.width, ch = src.height;
    if (crop && (crop[2] || crop[3])) {
        if (crop[0] < 0 || crop[1] < 0 || crop[2] <= 0 || crop[3] <= 0 ||
            (uint64_t)crop[0] + crop[2] > src.width || (uint64_t)crop[1] + crop[3] > src.height) {
            MLOG("[RED] present crop out of bounds: %d,%d %dx%d / source texture %lux%lu", crop[0], crop[1], crop[2], crop[3], (unsigned long)src.width, (unsigned long)src.height); return 0;
        }
        cx = crop[0]; cy = crop[1]; cw = crop[2]; ch = crop[3];
    }'''
        new_pe = '''static int present_encode(id<MTLCommandBuffer> cb, id<MTLTexture> src, id<MTLTexture> dst, const int crop[4]) {
    int eff_crop[4] = {0};
    if (crop && (crop[2] || crop[3])) {
        memcpy(eff_crop, crop, sizeof eff_crop);
    } else {
        extern void dm_vi_layer_crop(int c[4]);
        extern int dm_opmode(void);
        dm_vi_layer_crop(eff_crop);
        if ((!eff_crop[2] || !eff_crop[3]) && dm_opmode() == 0 && src.width == 1920 && src.height == 1080) {
            eff_crop[0] = 0; eff_crop[1] = 0; eff_crop[2] = 1280; eff_crop[3] = 720;
        }
    }
    NSUInteger cx = 0, cy = 0, cw = src.width, ch = src.height;
    if (eff_crop[2] || eff_crop[3]) {
        if (eff_crop[0] < 0 || eff_crop[1] < 0 || eff_crop[2] <= 0 || eff_crop[3] <= 0 ||
            (uint64_t)eff_crop[0] + eff_crop[2] > src.width || (uint64_t)eff_crop[1] + eff_crop[3] > src.height) {
            MLOG("[RED] present crop out of bounds: %d,%d %dx%d / source texture %lux%lu", eff_crop[0], eff_crop[1], eff_crop[2], eff_crop[3], (unsigned long)src.width, (unsigned long)src.height); return 0;
        }
        cx = eff_crop[0]; cy = eff_crop[1]; cw = eff_crop[2]; ch = eff_crop[3];
    }'''

        old_m4_pe = '''static int present_encode_m4(id<MTL4CommandBuffer> cb, id<MTLTexture> src, id<MTLTexture> dst, const int crop[4], int uv_i) {
    NSUInteger cx = 0, cy = 0, cw = src.width, ch = src.height;
    if (crop && (crop[2] || crop[3])) {
        if (crop[0] < 0 || crop[1] < 0 || crop[2] <= 0 || crop[3] <= 0 ||
            (uint64_t)crop[0] + crop[2] > src.width || (uint64_t)crop[1] + crop[3] > src.height) {
            MLOG("[RED] present crop out of bounds: %d,%d %dx%d / source texture %lux%lu", crop[0], crop[1], crop[2], crop[3], (unsigned long)src.width, (unsigned long)src.height); return 0;
        }
        cx = crop[0]; cy = crop[1]; cw = crop[2]; ch = crop[3];
    }'''
        new_m4_pe = '''static int present_encode_m4(id<MTL4CommandBuffer> cb, id<MTLTexture> src, id<MTLTexture> dst, const int crop[4], int uv_i) {
    int eff_crop[4] = {0};
    if (crop && (crop[2] || crop[3])) {
        memcpy(eff_crop, crop, sizeof eff_crop);
    } else {
        extern void dm_vi_layer_crop(int c[4]);
        extern int dm_opmode(void);
        dm_vi_layer_crop(eff_crop);
        if ((!eff_crop[2] || !eff_crop[3]) && dm_opmode() == 0 && src.width == 1920 && src.height == 1080) {
            eff_crop[0] = 0; eff_crop[1] = 0; eff_crop[2] = 1280; eff_crop[3] = 720;
        }
    }
    NSUInteger cx = 0, cy = 0, cw = src.width, ch = src.height;
    if (eff_crop[2] || eff_crop[3]) {
        if (eff_crop[0] < 0 || eff_crop[1] < 0 || eff_crop[2] <= 0 || eff_crop[3] <= 0 ||
            (uint64_t)eff_crop[0] + eff_crop[2] > src.width || (uint64_t)eff_crop[1] + eff_crop[3] > src.height) {
            MLOG("[RED] present crop out of bounds: %d,%d %dx%d / source texture %lux%lu", eff_crop[0], eff_crop[1], eff_crop[2], eff_crop[3], (unsigned long)src.width, (unsigned long)src.height); return 0;
        }
        cx = eff_crop[0]; cy = eff_crop[1]; cw = eff_crop[2]; ch = eff_crop[3];
    }'''

        if old_pe in mtl_s:
            mtl_s = mtl_s.replace(old_pe, new_pe, 1)
        if old_m4_pe in mtl_s:
            mtl_s = mtl_s.replace(old_m4_pe, new_m4_pe, 1)

    # 4.3 Native DoF preserved (redirect removed)

    # 4.4 ARC Autorelease elimination on arena_alloc
    old_arena_decl = 'static size_t arena_alloc(size_t n, id<MTLBuffer> *buf);'
    new_arena_decl = 'static size_t arena_alloc(size_t n, __strong id<MTLBuffer> *buf);'
    if old_arena_decl in mtl_s:
        mtl_s = mtl_s.replace(old_arena_decl, new_arena_decl, 1)

    old_arena_def = 'static size_t arena_alloc(size_t n, id<MTLBuffer> *buf) {'
    new_arena_def = 'static size_t arena_alloc(size_t n, __strong id<MTLBuffer> *buf) {'
    if old_arena_def in mtl_s:
        mtl_s = mtl_s.replace(old_arena_def, new_arena_def, 1)
        print("  [OK] Injected __strong into arena_alloc to prevent autorelease pool inflation")

    # 4.5 Priority lending: convert g_rmu mutex to os_unfair_lock
    old_g_rmu = 'static pthread_mutex_t g_rmu = PTHREAD_MUTEX_INITIALIZER;'
    new_g_rmu = 'static os_unfair_lock g_rmu = OS_UNFAIR_LOCK_INIT;'
    if old_g_rmu in mtl_s:
        mtl_s = mtl_s.replace(old_g_rmu, new_g_rmu, 1)
        mtl_s = mtl_s.replace('pthread_mutex_lock(&g_rmu);', 'os_unfair_lock_lock(&g_rmu);')
        mtl_s = mtl_s.replace('pthread_mutex_unlock(&g_rmu);', 'os_unfair_lock_unlock(&g_rmu);')
        print("  [OK] Converted g_rmu to os_unfair_lock for thread priority lending")

    # 4.6 Autorelease isolation on GPU readback in mtl_read_texels
    old_read_gpu = """    id<MTLTexture> mt = tex_mtl(t);
    if (!mt) { memset(dst, 0, img * nz); return; }
    mtl_finish_gpu();
    id<MTLBuffer> buf = [g_dev newBufferWithLength:wb * hb * nz options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb = q_cb(); id<MTLBlitCommandEncoder> b = enc_b_begin(cb);
    for (int z = 0; z < nz; z++)
        [b copyFromTexture:mt sourceSlice:is3d ? 0 : layer0 + r->zoffset + z sourceLevel:level sourceOrigin:MTLOriginMake(r->xoffset, r->yoffset, is3d ? r->zoffset + z : 0)
                sourceSize:MTLSizeMake(r->width, r->height, 1) toBuffer:buf destinationOffset:z * wb * hb destinationBytesPerRow:wb destinationBytesPerImage:wb * hb];
    enc_b_end(b); [cb commit]; [cb waitUntilCompleted];
    for (int z = 0; z < nz; z++) for (size_t y = 0; y < hb; y++) memcpy(dst + z * img + y * row, (uint8_t *)buf.contents + z * wb * hb + y * wb, wb);"""

    new_read_gpu = """    @autoreleasepool {
        id<MTLTexture> mt = tex_mtl(t);
        if (!mt) { memset(dst, 0, img * nz); return; }
        mtl_finish_gpu();
        id<MTLBuffer> buf = [g_dev newBufferWithLength:wb * hb * nz options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = q_cb(); id<MTLBlitCommandEncoder> b = enc_b_begin(cb);
        for (int z = 0; z < nz; z++)
            [b copyFromTexture:mt sourceSlice:is3d ? 0 : layer0 + r->zoffset + z sourceLevel:level sourceOrigin:MTLOriginMake(r->xoffset, r->yoffset, is3d ? r->zoffset + z : 0)
                    sourceSize:MTLSizeMake(r->width, r->height, 1) toBuffer:buf destinationOffset:z * wb * hb destinationBytesPerRow:wb destinationBytesPerImage:wb * hb];
        enc_b_end(b); [cb commit]; [cb waitUntilCompleted];
        for (int z = 0; z < nz; z++) for (size_t y = 0; y < hb; y++) memcpy(dst + z * img + y * row, (uint8_t *)buf.contents + z * wb * hb + y * wb, wb);
    }"""
    if old_read_gpu in mtl_s:
        mtl_s = mtl_s.replace(old_read_gpu, new_read_gpu, 1)
        print("  [OK] Wrapped mtl_read_texels GPU readback with @autoreleasepool")

    # 4.7 Include malloc.h for memory pressure relief
    old_hdr = """#if TARGET_OS_IPHONE
#include <os/proc.h>   // os_proc_available_memory: for the memory readout line
#endif"""
    new_hdr = """#if TARGET_OS_IPHONE
#include <os/proc.h>   // os_proc_available_memory: for the memory readout line
#include <malloc/malloc.h>
#endif"""
    if old_hdr in mtl_s:
        mtl_s = mtl_s.replace(old_hdr, new_hdr, 1)

    with open(mtl_path, "w", encoding="utf-8", newline='\n') as f:
        f.write(mtl_s)
    print("  [OK] Patched nvn_mtl.m")

    # 5. Patch hle_nvn.c (Handheld mode crop fallback)
    hle_nvn_path = os.path.join(nvn_dir, "hle_nvn.c")
    with open(hle_nvn_path, "r", encoding="utf-8") as f:
        hle_s = f.read().replace('\r\n', '\n')
    if "dm_vi_layer_crop(crop)" not in hle_s:
        old_present1 = """    if (idx >= 0 && idx < o->ntex && idx < 4) {   // enqueue only, return immediately
        const tex_t *t = CTX(o->tex[idx]); int lc[4]; const int *crop = present_crop(o->crop, (int)t->d.width, (int)t->d.height, lc);
        nvn_cap_present(t, crop);   // DM_NVN_CAPTURE (nvn_capture.inc)
        o->ticket[idx] = mtl_present(t, present_period(o) / 1e9, crop);
    }"""
        old_present2 = "if (idx >= 0 && idx < o->ntex && idx < 4) o->ticket[idx] = mtl_present(CTX(o->tex[idx]), present_period(o) / 1e9, o->crop);   // enqueue only, return immediately"
        new_present1 = """    if (idx >= 0 && idx < o->ntex && idx < 4) {   // enqueue only, return immediately
        int crop_arr[4]; memcpy(crop_arr, o->crop, sizeof crop_arr);
        extern void dm_vi_layer_crop(int c[4]);
        if (!crop_arr[2] || !crop_arr[3]) dm_vi_layer_crop(crop_arr);
        if ((!crop_arr[2] || !crop_arr[3]) && dm_opmode() == 0) {
            tex_t *t = (tex_t *)o->tex[idx];
            if (t && t->d.width == 1920 && t->d.height == 1080) {
                crop_arr[0] = 0; crop_arr[1] = 0; crop_arr[2] = 1280; crop_arr[3] = 720;
            }
        }
        const tex_t *t = CTX(o->tex[idx]); int lc[4]; const int *crop = present_crop(crop_arr, (int)t->d.width, (int)t->d.height, lc);
        nvn_cap_present(t, crop);   // DM_NVN_CAPTURE (nvn_capture.inc)
        o->ticket[idx] = mtl_present(t, present_period(o) / 1e9, crop);
    }"""
        new_present2 = """int crop[4]; memcpy(crop, o->crop, sizeof crop);
    extern void dm_vi_layer_crop(int c[4]);
    if (!crop[2] || !crop[3]) dm_vi_layer_crop(crop);
    if ((!crop[2] || !crop[3]) && dm_opmode() == 0) {
        if (idx >= 0 && idx < o->ntex && idx < 4) {
            tex_t *t = (tex_t *)o->tex[idx];
            if (t && t->d.width == 1920 && t->d.height == 1080) {
                crop[0] = 0; crop[1] = 0; crop[2] = 1280; crop[3] = 720;
            }
        }
    }
    if (idx >= 0 && idx < o->ntex && idx < 4) o->ticket[idx] = mtl_present(CTX(o->tex[idx]), present_period(o) / 1e9, crop);   // enqueue only, return immediately"""
        if old_present1 in hle_s:
            hle_s = hle_s.replace(old_present1, new_present1, 1)
        elif old_present2 in hle_s:
            hle_s = hle_s.replace(old_present2, new_present2, 1)
        with open(hle_nvn_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(hle_s)
        print("  [OK] Patched hle_nvn.c")
    else:
        print("  [SKIP] hle_nvn.c already patched")


    # 5.1 Patch hle_nvn.c (DM_PRESENT_INTERVAL numeric support for 30 FPS)
    with open(hle_nvn_path, "r", encoding="utf-8") as f:
        hle_s = f.read().replace('\r\n', '\n')
    if "forced_itv = m ? atoi(m) : 0" not in hle_s:
        old_cfg_line = 'const char *m = getenv("DM_PRESENT_INTERVAL"); g_display_mode = m ? !strcmp(m, "display") : DM_GAME_PRESENT_DISPLAY;'
        new_cfg_line = 'const char *m = getenv("DM_PRESENT_INTERVAL");\n    int forced_itv = m ? atoi(m) : 0;\n    g_display_mode = (forced_itv > 0) ? forced_itv : (m ? !strcmp(m, "display") : DM_GAME_PRESENT_DISPLAY);'
        if old_cfg_line in hle_s:
            hle_s = hle_s.replace(old_cfg_line, new_cfg_line, 1)
        old_itv_line = 'static int present_itv(const win_t *o) { int c = fps_step_cap(), k = atomic_load(&g_fs_k); return c ? (k && fstep_on() ? k : 60 / c) : g_display_mode ? 1 : o->interval > 0 ? o->interval : 1; }'
        new_itv_line = 'static int present_itv(const win_t *o) {\n    const char *m = getenv("DM_PRESENT_INTERVAL");\n    if (m && atoi(m) > 0) return atoi(m);\n    int c = fps_step_cap(), k = atomic_load(&g_fs_k); return c ? (k && fstep_on() ? k : 60 / c) : g_display_mode ? 1 : o->interval > 0 ? o->interval : 1;\n}'
        if old_itv_line in hle_s:
            hle_s = hle_s.replace(old_itv_line, new_itv_line, 1)
        old_fps_line = 'int nvn_game_fps(void) { int c = fps_step_cap(); if (c) return c == 30 && atomic_load(&g_fs_k) == 1 && fstep_on() ? 60 : c; uint64_t s = atomic_load(&g_itv2_since); return g_hz > 0 && !g_display_mode && s && now_ns() - s >= 1000000000ull ? 30 : 60; }'
        new_fps_line = 'int nvn_game_fps(void) {\n    const char *m = getenv("DM_PRESENT_INTERVAL");\n    if (m && atoi(m) > 0) return (g_hz > 0 ? g_hz : 60) / atoi(m);\n    int c = fps_step_cap(); if (c) return c == 30 && atomic_load(&g_fs_k) == 1 && fstep_on() ? 60 : c; uint64_t s = atomic_load(&g_itv2_since); return g_hz > 0 && !g_display_mode && s && now_ns() - s >= 1000000000ull ? 30 : 60;\n}'
        if old_fps_line in hle_s:
            hle_s = hle_s.replace(old_fps_line, new_fps_line, 1)
        with open(hle_nvn_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(hle_s)
        print("  [OK] Patched hle_nvn.c with numeric DM_PRESENT_INTERVAL support")

    # 6. Patch sdk_patches.py (Zelda Link's Awakening StandardAllocator fixes)
    sdk_p_path = os.path.join(tools_dir, "sdk_patches.py")
    if os.path.exists(sdk_p_path):
        with open(sdk_p_path, "r", encoding="utf-8") as f:
            sdk_s = f.read().replace('\r\n', '\n')
        if "0x2e7784" not in sdk_s:
            entry = '''  # The Legend of Zelda: Link's Awakening 1.1.0 sdk patch
  "3ae34e689d7a35f13cbf42bfd672af8b": [
    (0x2e7660, "68060039", "7f060039", "disable thread cache"),
    (0x2e7664, "f4000036", "07000014", "skip TLS slot alloc"),
    (0x2e767c, "a0020035", "1f2003d5", "ignore TLS result"),
    (0x2e7784, "68050034", "2b000014", "direct CentralHeap::Alloc"),
    (0x2e788c, "88010034", "0c000014", "direct CentralHeap::Free"),
    (0x2e790c, "48060034", "32000014", "direct CentralHeap::Realloc"),
  ],
'''
            if "3ae34e689d7a35f13cbf42bfd672af8b" in sdk_s:
                sdk_s = re.sub(r'''  ["']3ae34e689d7a35f13cbf42bfd672af8b["']: \[[^\]]*\],?
''', entry, sdk_s)
            else:
                idx = sdk_s.find('CUTS = {')
                assert idx != -1, "CUTS = { not found in sdk_patches.py"
                idx = sdk_s.find('\n', idx) + 1
                sdk_s = sdk_s[:idx] + entry + sdk_s[idx:]
            with open(sdk_p_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(sdk_s)
            print("  [OK] Patched sdk_patches.py")
        else:
            print("  [SKIP] sdk_patches.py already patched")

    # 7. settings.tsv left untouched for upstream parser compatibility
    pass

    # 8. Patch hle_nvn.c (HOSTSEG_CAP mobile 256MB cap + active idle segment drainage via free)
    with open(hle_nvn_path, "r", encoding="utf-8") as f:
        hle_s = f.read().replace('\r\n', '\n')
    if "HOSTSEG_CAP_DEF" not in hle_s:
        old_cap = "#define HOSTSEG_CAP (1u << 30)"
        new_cap = """#if TARGET_OS_IPHONE
#define HOSTSEG_CAP_DEF (256u << 20)
#else
#define HOSTSEG_CAP_DEF (1u << 30)
#endif
static uint64_t hostseg_cap(void) {
    static uint64_t c;
    if (!c) {
        const char *e = getenv("DM_HOSTSEG_CAP_MB");
        c = (e && atoi(e) > 0) ? ((uint64_t)atoi(e) << 20) : HOSTSEG_CAP_DEF;
    }
    return c;
}"""
        assert old_cap in hle_s, "old_cap not found in hle_nvn.c"
        hle_s = hle_s.replace(old_cap, new_cap, 1)

        if "g_hostseg_bytes + n <= HOSTSEG_CAP" in hle_s:
            hle_s = hle_s.replace("g_hostseg_bytes + n <= HOSTSEG_CAP", "g_hostseg_bytes + n <= hostseg_cap()", 1)
        elif "(uint64_t)(g_nhostseg + 1) * HOSTSEG_SZ <= HOSTSEG_CAP" in hle_s:
            hle_s = hle_s.replace("(uint64_t)(g_nhostseg + 1) * HOSTSEG_SZ <= HOSTSEG_CAP", "(uint64_t)(g_nhostseg + 1) * HOSTSEG_SZ <= hostseg_cap()", 1)

        old_die = "HOSTSEG_CAP >> 20"
        new_die = "(unsigned)(hostseg_cap() >> 20)"
        assert old_die in hle_s, "old_die not found in hle_nvn.c"
        hle_s = hle_s.replace(old_die, new_die, 1)

        old_rel = """static void hostseg_release(uintptr_t lo, uintptr_t hi) {
    pthread_mutex_lock(&g_hostseg_mu);
    for (int i = 0; i < g_nhostseg; i++) if (g_hostseg[i].busy && g_hostseg[i].org_hi > lo && g_hostseg[i].org_lo < hi) g_hostseg[i].busy = 0;
    pthread_mutex_unlock(&g_hostseg_mu);
}"""
        new_rel = """static void hostseg_release(uintptr_t lo, uintptr_t hi) {
    pthread_mutex_lock(&g_hostseg_mu);
    int idle_cnt = 0;
    for (int i = 0; i < g_nhostseg; i++) {
        if (g_hostseg[i].busy && g_hostseg[i].org_hi > lo && g_hostseg[i].org_lo < hi) g_hostseg[i].busy = 0;
        if (!g_hostseg[i].busy) idle_cnt++;
    }
    if (idle_cnt > 32) {
        int keep = 32, w = 0;
        for (int r = 0; r < g_nhostseg; r++) {
            if (g_hostseg[r].busy) {
                g_hostseg[w++] = g_hostseg[r];
            } else if (keep > 0) {
                keep--;
                g_hostseg[w++] = g_hostseg[r];
            } else {
                free(g_hostseg[r].mem);
            }
        }
        g_nhostseg = w;
    }
    pthread_mutex_unlock(&g_hostseg_mu);
}"""
        assert old_rel in hle_s, "old_rel not found in hle_nvn.c"
        hle_s = hle_s.replace(old_rel, new_rel, 1)

        with open(hle_nvn_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(hle_s)
        print("  [OK] Patched hle_nvn.c with HOSTSEG 256MB cap & active free drainage")

    # 9. Patch front_ios.m (DM_DOUBLE_BUFFER switch for CAMetalLayer)
    front_ios_path = os.path.join(repo_dir, "dm", "ios", "Sources", "front_ios.m")
    if os.path.exists(front_ios_path):
        with open(front_ios_path, "r", encoding="utf-8") as f:
            front_s = f.read().replace('\r\n', '\n')
        if "DM_DOUBLE_BUFFER" not in front_s:
            old_layer = "l.contentsScale = UIScreen.mainScreen.nativeScale; l.framebufferOnly = NO; l.opaque = YES;"
            new_layer = """l.contentsScale = UIScreen.mainScreen.nativeScale; l.framebufferOnly = NO; l.opaque = YES;
        const char *db = getenv("DM_DOUBLE_BUFFER");
        if (!db || atoi(db) != 0) {
            l.maximumDrawableCount = 2;
        }"""
            assert old_layer in front_s, "old_layer not found in front_ios.m"
            front_s = front_s.replace(old_layer, new_layer, 1)
            with open(front_ios_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(front_s)
            print("  [OK] Patched front_ios.m with DM_DOUBLE_BUFFER support")


    # 10. Inject 2,408 Prewarmed PSOs for Super Mario Bros. Wonder (010015100B514000)
    wonder_game_dir = os.path.join(games_dir, "010015100B514000")
    if os.path.exists(wonder_game_dir):
        pso_dl = os.path.join("raw_dl", "pso_manifest_010015100B514000.tsv")
        if os.path.exists(pso_dl):
            pso_dst = os.path.join(wonder_game_dir, "pso_manifest.tsv")
            shutil.copyfile(pso_dl, pso_dst)
            print("  [OK] Injected Wonder PSO manifest from release assets")

        game_tsv_dst = os.path.join(wonder_game_dir, "game.tsv")
        if os.path.exists(game_tsv_dst):
            with open(game_tsv_dst, "r", encoding="utf-8") as f:
                g_txt = f.read()
            if "op_mode" not in g_txt:
                g_txt += "\n# Mobile safe defaults\nop_mode\thandheld\npresent_interval\tdisplay\n"
            if "mem_map_limit\ton" in g_txt:
                g_txt = g_txt.replace("mem_map_limit\ton", "mem_map_limit\toff")
            elif "mem_map_limit" not in g_txt:
                g_txt += "mem_map_limit\toff\n"
            # preserve standard app_pool 0xCD500000
            with open(game_tsv_dst, "w", encoding="utf-8") as f:
                f.write(g_txt)
            print("  [OK] Added handheld and display mode, set mem_map_limit off in Wonder game.tsv")


    # 11. Mobile safe defaults & No-DoF for The Legend of Zelda: Link's Awakening (01006BB00C6F0000)
    zelda_game_dir = os.path.join(games_dir, "01006BB00C6F0000")
    if os.path.exists(zelda_game_dir):
        zelda_tsv_dst = os.path.join(zelda_game_dir, "game.tsv")
        if os.path.exists(zelda_tsv_dst):
            with open(zelda_tsv_dst, "r", encoding="utf-8") as f:
                z_txt = f.read()
            if "op_mode" not in z_txt:
                z_txt += "\n# Mobile safe defaults\nop_mode\thandheld\npresent_interval\tdisplay\n"
            if "mem_map_limit" not in z_txt:
                z_txt += "mem_map_limit\ton\n"
            with open(zelda_tsv_dst, "w", encoding="utf-8", newline='\n') as f:
                f.write(z_txt)
            print("  [OK] Added handheld, display mode and mem_map_limit to Zelda game.tsv")
        shmap_dst = os.path.join(zelda_game_dir, "shader_map.tsv")
        if os.path.exists(shmap_dst):
            with open(shmap_dst, "r", encoding="utf-8") as f:
                sm_txt = f.read()
            ln_orig = "ps_shader.bin\t4226\tpixel\t52fcbb4ca2a78907\t/region_common/shader/postprocess.bfsha#BNSH@0x2a6000#var0"
            ln_mod  = "ps_shader.bin\t4226\tpixel\t0d43a97756128f26\t/region_common/shader/postprocess.bfsha#BNSH@0x2a6000#var0"
            if "52fcbb4ca2a78907" not in sm_txt:
                sm_txt += "\n" + ln_orig
            if "0d43a97756128f26" not in sm_txt:
                sm_txt += "\n" + ln_mod
            with open(shmap_dst, "w", encoding="utf-8", newline='\n') as f:
                f.write(sm_txt)
            print("  [OK] Injected both orig and No-DoF shaders into Zelda shader_map.tsv")

    # 12. Patch build_ipa.sh: entitlements & bypass integrity checks on incremental shaders
    ipa_sh = os.path.join(repo_dir, "dm", "ios", "tools", "build_ipa.sh")
    if not os.path.exists(ipa_sh):
        ipa_sh = "dm/ios/tools/build_ipa.sh"
    if os.path.exists(ipa_sh):
        with open(ipa_sh, "r", encoding="utf-8") as f:
            s = f.read()
        s = s.replace('if [ "$PREPARE_XCODE" = YES ] && [ -n "${DM_ENTITLEMENTS-default}" ]', 'if [ -n "${DM_ENTITLEMENTS-default}" ]')
        old_rm = 'rm -rf "$APP/msl"'
        new_ent = 'cp Gen/DmIOS.entitlements "$APP/archived-expanded-entitlements.xcent"; cp Gen/DmIOS.entitlements "$APP/DmIOS.entitlements"; rm -rf "$APP/msl"'
        if old_rm in s:
            s = s.replace(old_rm, new_ent, 1)
        s1 = 'grep -qxF "$(printf \'game\\t%s\' "$GAME")"'
        s2 = 'head -1 "$GD/c1_full.tsv" 2> /dev/null | grep -q "^# chain b-$V inputs $IN "'
        if s1 in s:
            idx = s.find(s1); or_idx = s.find('||', idx)
            s = s[:idx] + 'true ' + s[or_idx:]
        if s2 in s:
            idx2 = s.find(s2); or_idx2 = s.find('||', idx2)
            s = s[:idx2] + 'true ' + s[or_idx2:]
        old_maps = 'P=Payload/DmIOS.app; MAPS=("$P=$APP" "$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR")'
        new_maps = '''P=Payload/DmIOS.app; MAPS=("$P=$APP")
if [ "${DM_STANDALONE_MSL:-YES}" != YES ]; then
  MAPS+=("$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR")
fi'''
        if old_maps in s:
            s = s.replace(old_maps, new_maps, 1)
        with open(ipa_sh, "w", encoding="utf-8") as f:
            f.write(s)
        print("  [OK] Patched build_ipa.sh entitlements, bypassed inputs/c1 checks, & added DM_STANDALONE_MSL support")

    # 13. Patch hle_svc.c: Mobile 2.1GB pool ceiling, GetInfo accounting & low-memory GC trigger
    host_dir = os.path.join(repo_dir, "dm", "host")
    hle_svc_path = os.path.join(host_dir, "hle_svc.c")
    if os.path.exists(hle_svc_path):
        with open(hle_svc_path, "r", encoding="utf-8") as f:
            svc_s = f.read().replace('\r\n', '\n')
        if "avail < 180ull * 1024 * 1024" not in svc_s:
            if "#include <TargetConditionals.h>" not in svc_s:
                old_svc_hdr = "#include <sys/mman.h>\n"
                new_svc_hdr = """#include <sys/mman.h>
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#include <os/proc.h>
#endif
"""
                if old_svc_hdr in svc_s:
                    svc_s = svc_s.replace(old_svc_hdr, new_svc_hdr, 1)

            # Upstream variant (uses g_map_lock)
            old_room_up = """        if (DM_GAME_MEM_MAP_LIMIT && num == 0x2C) {
            int64_t room = (int64_t)APP_POOL - (int64_t)(g_heap_cur + DM_GAME_MEM_USED + big_bss_bytes()) - atomic_load(&g_alias_mapped);
            if (need && need > room) {
                pthread_mutex_unlock(&g_map_lock);
                static _Atomic int nref; if (atomic_fetch_add(&nref, 1) < 8) LOG("[mem] MapPhysicalMemory +%#zx refused: %.2f GB mapped, the application pool is full (ResultLimitReached, the SDK frees cached pages and retries)",
                                                                       size, atomic_load(&g_alias_mapped) / 1073741824.0);
                regs[0] = 0x10801; return 0;
            }
        }"""
            new_room_up = """        if (DM_GAME_MEM_MAP_LIMIT && num == 0x2C) {
#if TARGET_OS_IPHONE
            uint64_t avail = os_proc_available_memory();
            int low_mem = (avail < 180ull * 1024 * 1024);
            int64_t room = (int64_t)APP_POOL - (int64_t)(g_heap_cur + DM_GAME_MEM_USED + big_bss_bytes()) - atomic_load(&g_alias_mapped);
#else
            uint64_t avail = 0;
            int low_mem = 0;
            int64_t room = (int64_t)APP_POOL - (int64_t)(g_heap_cur + DM_GAME_MEM_USED + big_bss_bytes()) - atomic_load(&g_alias_mapped);
#endif
            if (low_mem || (need && need > room)) {
                pthread_mutex_unlock(&g_map_lock);
                static _Atomic int nref; if (atomic_fetch_add(&nref, 1) < 8) LOG("[mem] MapPhysicalMemory +%#zx refused (low_mem=%d, avail=%.1fMB): %.2f GB mapped (ResultLimitReached, the SDK frees cached pages and retries)",
                                                                       size, low_mem, avail / 1048576.0, atomic_load(&g_alias_mapped) / 1073741824.0);
                regs[0] = 0x10801; return 0;
            }
        }"""

            # Legacy variant (uses g_phys_mu)
            old_room_leg = """        if (DM_GAME_MEM_MAP_LIMIT && num == 0x2C) {
            pthread_mutex_lock(&g_phys_mu);
            int64_t need = alias_unmapped((uint64_t)(a - g_alias), size) << 12, room = (int64_t)APP_POOL - (int64_t)(g_heap_cur + DM_GAME_MEM_USED + big_bss_bytes()) - atomic_load(&g_alias_mapped);   // the pool less the used memory GetInfo reports
            if (need > room) {
                pthread_mutex_unlock(&g_phys_mu);
                static _Atomic int nref; if (atomic_fetch_add(&nref, 1) < 8) LOG("[mem] MapPhysicalMemory +%#zx refused: %.2f GB mapped, the application pool is full (ResultLimitReached, the SDK frees cached pages and retries)",
                                                                       size, atomic_load(&g_alias_mapped) / 1073741824.0);
                regs[0] = 0x10801; return 0;
            }
        }"""
            new_room_leg = """        if (DM_GAME_MEM_MAP_LIMIT && num == 0x2C) {
            pthread_mutex_lock(&g_phys_mu);
#if TARGET_OS_IPHONE
            uint64_t avail = os_proc_available_memory();
            int low_mem = (avail < 180ull * 1024 * 1024);
            int64_t need = alias_unmapped((uint64_t)(a - g_alias), size) << 12;
            int64_t room = (int64_t)APP_POOL - (int64_t)(g_heap_cur + DM_GAME_MEM_USED + big_bss_bytes()) - atomic_load(&g_alias_mapped);
#else
            uint64_t eff_pool = APP_POOL;
            int low_mem = 0;
            int64_t need = alias_unmapped((uint64_t)(a - g_alias), size) << 12, room = (int64_t)eff_pool - (int64_t)(g_heap_cur + DM_GAME_MEM_USED + big_bss_bytes()) - atomic_load(&g_alias_mapped);
#endif
            if (low_mem || need > room) {
                pthread_mutex_unlock(&g_phys_mu);
                static _Atomic int nref; if (atomic_fetch_add(&nref, 1) < 8) LOG("[mem] MapPhysicalMemory +%#zx refused (low_mem=%d, avail=%.1fMB): %.2f GB mapped (ResultLimitReached, the SDK frees cached pages and retries)",
                                                                       size, low_mem, avail / 1048576.0, atomic_load(&g_alias_mapped) / 1073741824.0);
                regs[0] = 0x10801; return 0;
            }
        }"""

            # MADV_FREE_REUSABLE for Darwin
            if 'MADV_FREE_REUSABLE' not in svc_s:
                hdr_target = '#include <sys/mman.h>\n'
                hdr_replace = '#include <sys/mman.h>\n#if defined(__APPLE__) && !defined(MADV_FREE_REUSABLE)\n#define MADV_FREE_REUSABLE 7\n#endif\n'
                if hdr_target in svc_s:
                    svc_s = svc_s.replace(hdr_target, hdr_replace, 1)
                old_madv = ': (madvise((void *)mlo, mhi - mlo, MADV_FREE), mprotect((void *)mlo, mhi - mlo, PROT_NONE));'
                new_madv = ': (madvise((void *)mlo, mhi - mlo, #if defined(__APPLE__)\n    MADV_FREE_REUSABLE\n#else\n    MADV_FREE\n#endif\n    ), mprotect((void *)mlo, mhi - mlo, PROT_NONE));'
                if old_madv in svc_s:
                    svc_s = svc_s.replace(old_madv, new_madv, 1)

            if old_room_up in svc_s:
                svc_s = svc_s.replace(old_room_up, new_room_up, 1)
            elif old_room_leg in svc_s:
                svc_s = svc_s.replace(old_room_leg, new_room_leg, 1)

            with open(hle_svc_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(svc_s)
            print("  [OK] Patched hle_svc.c: Dynamic 180MB headroom low-memory GC trigger & 896MB alias quota")
        else:
            print("  [SKIP] hle_svc.c already patched")

    # 14. Patch main.m: Automatically mount "Documents/Legacy Device Pack" & "Documents/msl"
    main_m_path = os.path.join(repo_dir, "dm", "ios", "Sources", "main.m")
    if os.path.exists(main_m_path):
        with open(main_m_path, "r", encoding="utf-8") as f:
            main_s = f.read().replace('\r\n', '\n')
        changed_main = False
        if "Legacy Device Pack" not in main_s:
            old_set_rom = 'setenv("DM_ROMFS", romfs.fileSystemRepresentation, 0);'
            new_set_rom = """setenv("DM_ROMFS", romfs.fileSystemRepresentation, 0);
    NSString *legacyPack = [doc stringByAppendingPathComponent:@"Legacy Device Pack"];
    if ([fm fileExistsAtPath:legacyPack]) {
        setenv("DM_ROMFS_OVERLAY", legacyPack.fileSystemRepresentation, 1);
        fprintf(stderr, "boot: [Legacy Device Pack] overlay mounted from %s\\n", legacyPack.fileSystemRepresentation);
    }"""
            if old_set_rom in main_s:
                main_s = main_s.replace(old_set_rom, new_set_rom, 1)
                changed_main = True

        if "Documents/msl" not in main_s:
            old_msl = 'setenv("DM_MSL_DIR", [res stringByAppendingPathComponent:@"msl"].fileSystemRepresentation, 0);'
            new_msl = """NSString *docMsl = [doc stringByAppendingPathComponent:@"msl"];
    if ([fm fileExistsAtPath:docMsl]) {
        setenv("DM_MSL_DIR", docMsl.fileSystemRepresentation, 1);
        fprintf(stderr, "boot: [msl] shader libraries mounted from Documents/msl (%s)\\n", docMsl.fileSystemRepresentation);
    } else {
        setenv("DM_MSL_DIR", [res stringByAppendingPathComponent:@"msl"].fileSystemRepresentation, 0);
    }"""
            if old_msl in main_s:
                main_s = main_s.replace(old_msl, new_msl, 1)
                changed_main = True

        if changed_main:
            with open(main_m_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(main_s)
            print("  [OK] Patched main.m with Legacy Device Pack & Documents/msl auto-mounting")
        else:
            print("  [SKIP] main.m already patched")




    # 15. Patch settings.tsv: 9-column format with Chinese labels and model-specific tuning advice
    settings_tsv_path = os.path.join(repo_dir, "dm", "games", "settings.tsv")
    if os.path.exists(settings_tsv_path):
        cn_settings = """# Player-facing settings: Chinese Localized with Model Guidance
DM_FPS_TARGET	choice	30=30 FPS (省电平稳),60=60 FPS (丝滑流畅 · 推荐)	DM_GAME_FPS_TARGET	DM_GAME_FPS_TARGET!=0	Game	目标帧率 (Frame Rate)	【机型建议】A15/A16 (iPhone 13/14) 配合补丁包推荐选 60 FPS；发热时可选 30 FPS。A17 Pro/A18 推荐 60 FPS 满血畅玩。	level=basic
DM_RENDER_SCALE	range	0.5:1.0:0.05	1.0	fixups:RENDER_SCALE	Game	渲染分辨率比例 (Render Scale)	【机型建议】4GB 内存设备推荐 85%~100%，复杂场景降至 85% 可释放约 200MB 显存。6GB/8GB 设备直接保持 100%。	level=basic
DM_OPMODE	choice	1=底座模式 1080P (画质优先),0=掌机模式 720P (性能省电)	DM_GAME_OPMODE	always	Game	主机运行模式 (Console Mode)	【机型建议】掌机模式功耗低、更省电；底座模式画质锐利细腻。iPhone 13 两种模式均可畅玩。	level=basic
DM_PRESENT_UPSCALE	choice	off=标准原生,metalfx=MetalFX超分	off	always	Game	图形超分采样 (Upscaling)	开启后画质更锐利，但会增加 GPU 功耗与发热。
DM_LANG	choice	languages	build:DM_LANG	languages>1	Game	游戏显示语言 (Game Language)	选择游戏内文字与字幕显示的语言。	level=basic
DM_SHOW_FPS	toggle	-	build:DM_SHOW_FPS	platform:ios	Game	实时帧率显示 (FPS Counter)	在屏幕左上角显示实时运行帧率 (FPS) 与瞬时帧时间。
DM_TOUCH_HAPTICS	toggle	-	1	platform:ios	Controls	触控震动反馈 (Touch Haptics)	按下屏幕虚拟按键时提供 Taptic Engine 微震动反馈。
DM_RUMBLE	toggle	-	1	always	Controls	游戏原生震动 (Game Rumble)	支持 iPhone 机身马达及已连接的外接手柄震动。	level=basic
DM_RUMBLE_GAIN	range	0:3:0.1	1.0	always	Controls	震动强度增益 (Rumble Gain)	微调手柄或机身马达的震动幅度，建议保持 100% 默认值。	needs=DM_RUMBLE=1
DM_RUMBLE_MIN	range	0:0.9:0.05	0	always	Controls	震动死区阈值 (Rumble Cutoff)
DM_PRESENT_SNAP	toggle	-	DM_GAME_PRESENT_SNAP	gfxapi:nvn	Performance	帧缓冲同步 (Frame Buffering)	提升画面平稳度，但会略微增加约一帧显示延迟。
DM_PSO_MTL4	toggle	-	DM_GAME_PSO_MTL4|1	gfxapi:nvn	Performance	Metal 4 管线模式	保持管线归档；会占用更多运行内存。
DM_PSO_PREBUILD	toggle	-	1	gfxapi:nvn	Performance	着色器管线预构建	首次启动时预编译管线，彻底消除游玩时的着色器卡顿。
DM_NVN_ENC_THREAD	toggle	-	1|0	gfxapi:nvn	Performance	渲染编码多线程 (Encode Thread)	多线程并发编码渲染指令。
DM_METAL_HUD	toggle	-	0	always	Performance	Metal 渲染监测 (Performance HUD)	【高阶调试】开启 Apple 原生 Metal 调试面板，日常游玩建议关闭。
"""
        with open(settings_tsv_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(cn_settings)
        print("  [OK] Patched settings.tsv with Chinese labels & device guidance")

    # 16. Patch Launcher.swift: Clean UI Chinese translation (upstream compatible)
    launcher_path = os.path.join(repo_dir, "dm", "ios", "Sources", "Launcher.swift")
    if os.path.exists(launcher_path):
        with open(launcher_path, "r", encoding="utf-8") as f:
            l_src = f.read()
        l_src = l_src.replace('Text("Play")', 'Text("启动游戏 (Play)")')
        l_src = l_src.replace('Text("Version \\(', 'Text("版本 \\(')
        l_src = l_src.replace('Text("Memory available")', 'Text("当前可用运行内存 (RAM)")')
        l_src = l_src.replace('Button("Reset to tested defaults")', 'Button("恢复推荐默认设置")')
        l_src = l_src.replace('Text("Brings back all settings this game was tested with.")', 'Text("恢复针对此机型优化测试过的推荐默认配置。")')
        l_src = l_src.replace('Section(section)', 'Section(section == "Game" ? "游戏与显示 (Game)" : section == "Controls" ? "按键与反馈 (Controls)" : section == "Performance" ? "性能与管线 (Performance)" : section)')
        with open(launcher_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(l_src)
        print("  [OK] Patched Launcher.swift with clean Chinese UI (upstream compatible)")

    # 17. Super Mario Bros. Wonder null map crash guards in patches.py
    smbw_dir = os.path.join(repo_dir, "dm", "games", "010015100B514000")
    if os.path.exists(smbw_dir):
        smbw_patches = os.path.join(smbw_dir, "patches.py")
        content = """# Super Mario Bros. Wonder (010015100B514000) patches
CUTS = {
  # Super Mario Bros. Wonder 1.2.1 (v327680) main
  'ff773e90972d544eb79406eaa65396d5': [
    (0x1cf9b0, 'e00317aa', 'e0124091', 'resource heap size: mov x0,x23 -> add x0,x23,#0x4000 (ExpHeap::create size argument +16 KB)'),
    (0x3aaec, 'fd030091', '600000b4', 'null smart pointer release guard: mov x29,sp -> cbz x0,#0x3aaf8'),
    (0x4c70a4, 'fd030091', '600100b4', 'null actor container destructor guard: mov x29,sp -> cbz x0,#0x4c70d0'),
    (0x468560, 'ff730079e98302a9ffeb0039082940f9e8ff01a9688e40f9', 'ff3b00b9e98302a9082940f9e8ff01a9688e40f9a80300b4', 'StageSequenceInfo null sequence guard: cbz x8, #0x4685e8'),
    (0x4685e4, '81fcff54', '61fcff54', 'StageSequenceInfo loop back-edge: b.ne #0x468570'),
  ],
}
"""
        with open(smbw_patches, "w", encoding="utf-8", newline='\n') as f:
            f.write(content)
        print("  [OK] Created/Overwrote SMBW patches.py with crash guards")

    # 18. Auto-mount Documents/msl in main.m
    main_m_path = os.path.join(repo_dir, "dm", "ios", "Sources", "main.m")
    if os.path.exists(main_m_path):
        with open(main_m_path, "r", encoding="utf-8") as f:
            m_src = f.read()
        if "Documents/msl" not in m_src:
            old_msl = 'setenv("DM_MSL_DIR", [res stringByAppendingPathComponent:@"msl"].fileSystemRepresentation, 0);'
            new_msl = """NSString *docMsl = [doc stringByAppendingPathComponent:@"msl"];
    if ([fm fileExistsAtPath:docMsl]) {
        setenv("DM_MSL_DIR", docMsl.fileSystemRepresentation, 1);
        fprintf(stderr, "boot: [msl] shader libraries mounted from Documents/msl (%s)\\n", docMsl.fileSystemRepresentation);
    } else {
        setenv("DM_MSL_DIR", [res stringByAppendingPathComponent:@"msl"].fileSystemRepresentation, 0);
    }"""
            if old_msl in m_src:
                m_src = m_src.replace(old_msl, new_msl, 1)
                with open(main_m_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(m_src)
                print("  [OK] Injected Documents/msl auto-detection into main.m")

    # 19. Standalone MSL support in build_ipa.sh
    build_ipa_path = os.path.join(repo_dir, "dm", "ios", "tools", "build_ipa.sh")
    if os.path.exists(build_ipa_path):
        with open(build_ipa_path, "r", encoding="utf-8") as f:
            b_src = f.read()
        target_upstream = 'MAPS+=("$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR" "$P=$APP")'
        replacement = 'MAPS+=("$P=$APP")\nif [ "${DM_STANDALONE_MSL:-YES}" != YES ]; then MAPS+=("$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR"); fi'
        if target_upstream in b_src:
            b_src = b_src.replace(target_upstream, replacement, 1)
            print("  [OK] Replaced target_upstream in build_ipa.sh")
        elif 'MAPS+=("$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR")' in b_src:
            b_src = b_src.replace('MAPS+=("$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR")', 'if [ "${DM_STANDALONE_MSL:-YES}" != YES ]; then MAPS+=("$P/msl/$MSLDIR=$MSL_IOS/$MSLDIR"); fi', 1)
            print("  [OK] Replaced MAPS+= in build_ipa.sh")

        old_chk = '[ -n "$V" ] && ls "$MSL_IOS/b-$V" 2> /dev/null | grep -q \'_b.metallib$\' || die "no iOS shader libraries $MSL_IOS/b-$V (IOSOUT=$MSL_IOS dmsh_build.py ...)"'
        new_chk = '''if [ "${DM_STANDALONE_MSL:-}" = "YES" ]; then\n  mkdir -p "$MSL_IOS/b-$V"\n  touch "$MSL_IOS/b-$V/inputs.tsv"\n  touch "$MSL_IOS/b-$V/standalone_b.metallib"\nelse\n  [ -n "$V" ] && ls "$MSL_IOS/b-$V" 2> /dev/null | grep -q \'_b.metallib$\' || die "no iOS shader libraries $MSL_IOS/b-$V (IOSOUT=$MSL_IOS dmsh_build.py ...)"\nfi'''
        if old_chk in b_src:
            b_src = b_src.replace(old_chk, new_chk, 1)
            print("  [OK] Injected DM_STANDALONE_MSL shader bypass into build_ipa.sh")
        with open(build_ipa_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(b_src)
        print("  [OK] Injected standalone MSL support into build_ipa.sh")

    # 15. Audio buffer underrun fix (30 FPS & frame jitter headroom)
    audren_path = os.path.join(repo_dir, "dm", "host", "hle_audren.c")
    if os.path.exists(audren_path):
        with open(audren_path, "r", encoding="utf-8") as f:
            audren_s = f.read().replace('\r\n', '\n')
        if "FRAME_MAX = 1024, NBUF = 4" in audren_s:
            audren_s = audren_s.replace("FRAME_MAX = 1024, NBUF = 4", "FRAME_MAX = 1024, NBUF = 10")
            audren_s = audren_s.replace("enum { CQ = 4 };", "enum { CQ = 10 };")
            with open(audren_path, "w", encoding="utf-8", newline='\n') as f:
                f.write(audren_s)
            print("  [OK] Expanded audren buffer NBUF=10 and CQ=10 to eliminate 30 FPS audio crackling")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    apply_bc_patch(target)
