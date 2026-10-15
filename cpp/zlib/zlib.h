// zlib.h — 压缩（对标 Python zlib），C ABI；实现走系统 libz.so.1（运行时）
#ifndef ZLIBX_H
#define ZLIBX_H
#ifdef __cplusplus
extern "C" {
#endif
int  zl_compress(const char* in, const char* out, int level);   // zlib 格式
int  zl_gzip(const char* in, const char* out, int level);       // gzip 格式
int  zl_decompress(const char* in, const char* out);            // 自动识别 zlib/gzip
const char* zl_crc32_hex(const char* path);                     // "0x........" 无符号十进制？用十进制
unsigned long zl_crc32(const char* path);
unsigned long zl_adler32(const char* path);
#ifdef __cplusplus
}
#endif
#endif
