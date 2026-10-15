// hashlib.cpp — OpenSSL EVP 实现
#include "hashlib.h"
#include <openssl/evp.h>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
thread_local char g_hex[2 * EVP_MAX_MD_SIZE + 1];
thread_local char g_algos[512];

int digest(const char* algo, const void* data, size_t len, unsigned char* out) {
    const EVP_MD* md = EVP_get_digestbyname(algo);
    if (!md) return -1;
    unsigned int n = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (!ctx) return -1;
    int ok = EVP_DigestInit_ex(ctx, md, nullptr) == 1
          && EVP_DigestUpdate(ctx, data, len) == 1
          && EVP_DigestFinal_ex(ctx, out, &n) == 1;
    EVP_MD_CTX_free(ctx);
    return ok ? (int)n : -1;
}
void to_hex(const unsigned char* d, int n) {
    static const char* H = "0123456789abcdef";
    for (int i = 0; i < n; ++i) { g_hex[i * 2] = H[d[i] >> 4]; g_hex[i * 2 + 1] = H[d[i] & 15]; }
    g_hex[n * 2] = 0;
}
}  // namespace

extern "C" {

int hl_size(const char* algo) {
    const EVP_MD* md = EVP_get_digestbyname(algo);
    return md ? EVP_MD_get_size(md) : -1;
}

const char* hl_bytes_hex(const char* algo, const void* data, int len) {
    unsigned char out[EVP_MAX_MD_SIZE];
    int n = digest(algo, data, (size_t)len, out);
    if (n < 0) { g_hex[0] = 0; return g_hex; }
    to_hex(out, n);
    return g_hex;
}

const char* hl_file_hex(const char* algo, const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) { g_hex[0] = 0; return g_hex; }
    const EVP_MD* md = EVP_get_digestbyname(algo);
    if (!md) { fclose(f); g_hex[0] = 0; return g_hex; }
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, md, nullptr);
    unsigned char buf[65536]; size_t r;
    while ((r = fread(buf, 1, sizeof(buf), f)) > 0) EVP_DigestUpdate(ctx, buf, r);
    fclose(f);
    unsigned char out[EVP_MAX_MD_SIZE]; unsigned int n = 0;
    EVP_DigestFinal_ex(ctx, out, &n);
    EVP_MD_CTX_free(ctx);
    to_hex(out, (int)n);
    return g_hex;
}

const char* hl_algos(void) {
    g_algos[0] = 0;
    // 常见算法探测
    static const char* names[] = {"md5","sha1","sha224","sha256","sha384","sha512",
                                  "sha3-256","sha3-512","blake2b512","blake2s256"};
    for (auto nm : names) {
        if (EVP_get_digestbyname(nm)) {
            if (g_algos[0]) strncat(g_algos, ",", sizeof(g_algos) - strlen(g_algos) - 1);
            strncat(g_algos, nm, sizeof(g_algos) - strlen(g_algos) - 1);
        }
    }
    return g_algos;
}

}  // extern "C"
