// birefnet_capi.cpp — C ABI wrapper around bref::BgRemover for FFI (comfycli).
#include "birefnet.hpp"

#include <cstdlib>
#include <memory>
#include <mutex>
#include <string>

namespace {
std::mutex g_mutex;
// Intentionally leaked: destroying the ORT CUDA sessions during process exit races
// the CUDA driver teardown. Short-lived process, so never free.
bref::BgRemover* g_model = nullptr;
std::string g_model_path;

std::string DefaultModel() {
    if (const char* m = std::getenv("BIREFNET_MODEL")) return m;
    return "/data/models/birefnet/onnx/model.onnx";
}
}  // namespace

extern "C" {

// Returns 0 on success, -1 on error. Writes result image (and optional mask).
// color_hex: "RRGGBB" / "#RRGGBB", used when mode == MODE_COLOR (4).
int birefnet_remove(const char* in_path, const char* out_path, const char* mask_path,
                    int mode, const char* color_hex) {
    if (!in_path || !out_path) return -1;
    int r = 255, g = 255, b = 255;
    if (color_hex) {
        std::string h = color_hex;
        if (!h.empty() && h[0] == '#') h = h.substr(1);
        try {
            if (h.size() >= 6) {
                r = std::stoi(h.substr(0, 2), nullptr, 16);
                g = std::stoi(h.substr(2, 2), nullptr, 16);
                b = std::stoi(h.substr(4, 2), nullptr, 16);
            }
        } catch (...) {
        }
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    try {
        std::string mp = DefaultModel();
        if (!g_model || g_model_path != mp) {
            g_model = new bref::BgRemover(mp, true);
            g_model_path = mp;
        }
        g_model->Process(in_path, out_path, mask_path ? mask_path : "", mode, r, g, b);
        return 0;
    } catch (...) {
        return -1;
    }
}

}  // extern "C"
