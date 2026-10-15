// face_capi.cpp — C ABI wrapper around face::FaceEngine for FFI (comfycli).
#include "face.hpp"

#include <mutex>
#include <sstream>
#include <string>

namespace {
std::mutex g_mutex;
// intentionally leaked (CUDA teardown at exit)
face::FaceEngine* g_eng = nullptr;
std::string g_out;

face::FaceEngine* Get() {
    if (!g_eng) g_eng = new face::FaceEngine();
    return g_eng;
}
}  // namespace

extern "C" {

// JSON: [{"score":..,"box":[x1,y1,x2,y2]},...]
const char* face_detect(const char* image_path) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_out.clear();
    if (!image_path) return g_out.c_str();
    try {
        auto fs = Get()->Detect(image_path);
        std::ostringstream os;
        os << "[";
        for (size_t i = 0; i < fs.size(); ++i) {
            if (i) os << ",";
            os << "{\"score\":" << fs[i].score << ",\"box\":[" << fs[i].box[0] << "," << fs[i].box[1] << ","
               << fs[i].box[2] << "," << fs[i].box[3] << "]}";
        }
        os << "]";
        g_out = os.str();
    } catch (...) {
        g_out = "[]";
    }
    return g_out.c_str();
}

// 对齐裁剪最大人脸 -> out_path；返回 0 成功
int face_crop(const char* image_path, const char* out_path, int size) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!image_path || !out_path) return -1;
    try {
        return Get()->CropLargest(image_path, out_path, size > 0 ? size : 512) ? 0 : -1;
    } catch (...) {
        return -1;
    }
}

// 人脸解析 -> out_path；mode: color|face|skin|hair
int face_parse(const char* image_path, const char* out_path, const char* mode) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!image_path || !out_path) return -1;
    try {
        Get()->Parse(image_path, out_path, mode ? mode : "face");
        return 0;
    } catch (...) {
        return -1;
    }
}

}  // extern "C"
