// florence2.hpp — Florence-2 image captioning core (ONNX Runtime, C++).
#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace flo {

struct Options {
    std::string model_dir = "/data/models/florence2";
    std::string task = "<MORE_DETAILED_CAPTION>";
    int num_beams = 3;
    int max_new_tokens = 96;
    bool use_cuda = true;
};

class Florence2 {
  public:
    explicit Florence2(const std::string& model_dir, bool use_cuda = true);
    ~Florence2();
    Florence2(const Florence2&) = delete;
    Florence2& operator=(const Florence2&) = delete;

    // Runs captioning/generation. Returns decoded text.
    std::string Caption(const std::string& image_path, const Options& opt, int* out_w = nullptr,
                        int* out_h = nullptr);

    // Human-readable name of the active execution provider ("CUDA" / "CPU").
    const std::string& provider() const;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace flo
