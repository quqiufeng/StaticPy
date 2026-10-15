#include "zlib.h"
#include <zlib.h>
#include <cstdio>
#include <cstring>
#include <vector>
#include <string>

static int read_file(const char* p, std::vector<unsigned char>& v) {
    FILE* f = fopen(p, "rb"); if (!f) return -1;
    unsigned char buf[65536]; size_t n;
    while ((n = fread(buf, 1, sizeof buf, f)) > 0) v.insert(v.end(), buf, buf + n);
    fclose(f); return 0;
}
static int write_file(const char* p, const std::vector<unsigned char>& v) {
    FILE* f = fopen(p, "wb"); if (!f) return -1;
    if (!v.empty()) fwrite(v.data(), 1, v.size(), f);
    fclose(f); return 0;
}

extern "C" {

int zl_compress(const char* in, const char* out, int level) {
    std::vector<unsigned char> src; if (read_file(in, src)) return -1;
    uLongf dl = compressBound(src.size());
    std::vector<unsigned char> dst(dl);
    if (compress2(dst.data(), &dl, src.data(), src.size(), level) != Z_OK) return -2;
    dst.resize(dl);
    return write_file(out, dst);
}

int zl_gzip(const char* in, const char* out, int level) {
    std::vector<unsigned char> src; if (read_file(in, src)) return -1;
    z_stream zs; memset(&zs, 0, sizeof zs);
    deflateInit2(&zs, level, Z_DEFLATED, 15 + 16, 8, Z_DEFAULT_STRATEGY);
    std::vector<unsigned char> dst(compressBound(src.size()) + 64);
    zs.next_in = src.data(); zs.avail_in = src.size();
    zs.next_out = dst.data(); zs.avail_out = dst.size();
    if (deflate(&zs, Z_FINISH) != Z_STREAM_END) { deflateEnd(&zs); return -2; }
    dst.resize(zs.total_out);
    deflateEnd(&zs);
    return write_file(out, dst);
}

int zl_decompress(const char* in, const char* out) {
    std::vector<unsigned char> src; if (read_file(in, src)) return -1;
    z_stream zs; memset(&zs, 0, sizeof zs);
    if (inflateInit2(&zs, 15 + 32) != Z_OK) return -2;   // 自动 zlib/gzip
    std::vector<unsigned char> dst; dst.reserve(src.size() * 4 + 1024);
    std::vector<unsigned char> chunk(1 << 16);
    zs.next_in = src.data(); zs.avail_in = src.size();
    int ret;
    do {
        zs.next_out = chunk.data(); zs.avail_out = chunk.size();
        ret = inflate(&zs, Z_NO_FLUSH);
        if (ret != Z_OK && ret != Z_STREAM_END) { inflateEnd(&zs); return -3; }
        dst.insert(dst.end(), chunk.data(), chunk.data() + (chunk.size() - zs.avail_out));
    } while (ret != Z_STREAM_END && zs.avail_in > 0);
    inflateEnd(&zs);
    return write_file(out, dst);
}

unsigned long zl_crc32(const char* path) {
    std::vector<unsigned char> v; if (read_file(path, v)) return 0;
    return crc32(0L, v.data(), v.size());
}
unsigned long zl_adler32(const char* path) {
    std::vector<unsigned char> v; if (read_file(path, v)) return 0;
    uLong a = adler32(0L, Z_NULL, 0); return adler32(a, v.data(), v.size());
}

}  // extern "C"
