// hashlib.h — 消息摘要（对标 Python hashlib），C ABI；实现走 OpenSSL EVP（运行时 libcrypto.so.3）
#ifndef HASHLIB_H
#define HASHLIB_H
#ifdef __cplusplus
extern "C" {
#endif
// 返回 algo 的摘要字节数（未知算法返回 -1）
int hl_size(const char* algo);
// 对文件求摘要，返回十六进制串（静态缓冲，勿跨调用保留）；失败返回 ""
const char* hl_file_hex(const char* algo, const char* path);
// 对内存字节求摘要，返回十六进制串（静态缓冲）
const char* hl_bytes_hex(const char* algo, const void* data, int len);
// 列出可用算法（逗号分隔，静态缓冲）
const char* hl_algos(void);
#ifdef __cplusplus
}
#endif
#endif
