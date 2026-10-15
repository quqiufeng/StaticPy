// birefnet.hpp — BiRefNet background removal core (ONNX Runtime, C++).
#pragma once

#include <memory>
#include <string>

namespace bref {

// Output background handling.
enum Mode {
    MODE_TRANSPARENT = 0,  // RGBA, original RGB + alpha=mask
    MODE_WHITE = 1,        // RGB composite on white
    MODE_BLACK = 2,        // RGB composite on black
    MODE_GREEN = 3,        // RGB composite on green screen (0,255,0)
    MODE_COLOR = 4,        // RGB composite on custom (r,g,b)
    MODE_MASK = 5,         // grayscale alpha matte
    MODE_CHECKER = 6,      // RGB composite on a baked checkerboard (visual "transparent")
};

class BgRemover {
  public:
    explicit BgRemover(const std::string& model_path, bool use_cuda = true);
    ~BgRemover();
    BgRemover(const BgRemover&) = delete;
    BgRemover& operator=(const BgRemover&) = delete;

    // Writes out_path (RGBA/RGB/gray PNG depending on mode). If mask_path is
    // non-empty and mode != MODE_MASK, also writes the grayscale matte there.
    void Process(const std::string& in_path, const std::string& out_path,
                 const std::string& mask_path, int mode, int r, int g, int b);

    const std::string& provider() const;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace bref
