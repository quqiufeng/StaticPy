// florence2_capi.cpp — C ABI wrapper around flo::Florence2 for FFI (comfycli).
//
// Mirrors the project's existing pattern (sd_pipeline_get_model_version_name):
// returns a pointer to a static string; the Chez `string` foreign return copies
// it. Never returns NULL. Single-threaded (comfycli).
#include "florence2.hpp"

#include <cstdlib>
#include <memory>
#include <mutex>
#include <string>

namespace {
std::mutex g_mutex;
// Intentionally leaked: destroying the ONNX Runtime CUDA sessions during process
// exit (__run_exit_handlers) races the CUDA driver teardown and aborts. The
// process is short-lived, so we never free it.
flo::Florence2* g_model = nullptr;
std::string g_model_dir;
std::string g_out;

std::string DefaultModelDir() {
    if (const char* d = std::getenv("FLORENCE2_MODEL_DIR")) return d;
    return "/data/models/florence2";
}
}  // namespace

extern "C" {

const char* florence2_caption(const char* image_path, const char* task, int num_beams) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_out.clear();
    if (!image_path) return g_out.c_str();
    try {
        flo::Options opt;
        opt.model_dir = DefaultModelDir();
        opt.task = (task && task[0]) ? task : "<MORE_DETAILED_CAPTION>";
        opt.num_beams = num_beams > 0 ? num_beams : 3;
        opt.use_cuda = true;
        if (!g_model || g_model_dir != opt.model_dir) {
            g_model = new flo::Florence2(opt.model_dir, opt.use_cuda);
            g_model_dir = opt.model_dir;
        }
        g_out = g_model->Caption(image_path, opt);
    } catch (...) {
        g_out.clear();
    }
    return g_out.c_str();
}

void florence2_free(const char*) {}

}  // extern "C"
