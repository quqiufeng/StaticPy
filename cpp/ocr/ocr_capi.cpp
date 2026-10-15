// ocr_capi.cpp — C ABI wrapper around ocr::Ocr for FFI (comfycli).
//
// Returns pointers to static strings (Chez `string` return copies). Never NULL.
// Single-threaded (comfycli). Model instance intentionally leaked (CUDA teardown).
#include "ocr.hpp"

#include <cstdlib>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>

namespace {
std::mutex g_mutex;
ocr::Ocr* g_engine = nullptr;
std::string g_dir;
std::string g_out;

std::string DefaultDir() {
    if (const char* d = std::getenv("OCR_MODEL_DIR")) return d;
    return "/data/models/ocr";
}

ocr::Ocr* Get(const std::string& dir) {
    if (!g_engine || g_dir != dir) {
        g_engine = new ocr::Ocr(dir + "/ch_PP-OCRv4_det_infer.onnx", dir + "/ch_PP-OCRv4_rec_infer.onnx",
                                dir + "/ppocr_keys_v1.txt", true);
        g_dir = dir;
    }
    return g_engine;
}
}  // namespace

extern "C" {

// Newline-joined recognized text.
const char* ocr_image(const char* image_path) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_out.clear();
    if (!image_path) return g_out.c_str();
    try {
        auto boxes = Get(DefaultDir())->Run(image_path);
        for (size_t i = 0; i < boxes.size(); ++i) {
            if (i) g_out += "\n";
            g_out += boxes[i].text;
        }
    } catch (...) {
        g_out.clear();
    }
    return g_out.c_str();
}

// JSON array of text boxes: [{"x","y","w","h","text"},...]
const char* ocr_image_json(const char* image_path) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_out.clear();
    if (!image_path) return g_out.c_str();
    try {
        auto boxes = Get(DefaultDir())->Run(image_path);
        std::ostringstream os;
        os << "[";
        for (size_t i = 0; i < boxes.size(); ++i) {
            if (i) os << ",";
            os << "{\"x\":" << boxes[i].x << ",\"y\":" << boxes[i].y << ",\"w\":" << boxes[i].w
               << ",\"h\":" << boxes[i].h << ",\"text\":\"";
            for (char c : boxes[i].text) {
                if (c == '"' || c == '\\') os << '\\';
                os << c;
            }
            os << "\"}";
        }
        os << "]";
        g_out = os.str();
    } catch (...) {
        g_out = "[]";
    }
    return g_out.c_str();
}

}  // extern "C"
