// ocr.hpp — PaddleOCR PP-OCRv4 (det+rec) via ONNX Runtime, C++ (stb, no OpenCV).
#pragma once

#include <memory>
#include <string>
#include <vector>

namespace ocr {

struct TextBox {
    int x = 0, y = 0, w = 0, h = 0;
    std::string text;
    float score = 0.0f;
};

class Ocr {
  public:
    Ocr(const std::string& det_model, const std::string& rec_model, const std::string& dict,
        bool use_cuda = true);
    ~Ocr();
    Ocr(const Ocr&) = delete;
    Ocr& operator=(const Ocr&) = delete;

    std::vector<TextBox> Run(const std::string& image_path);

    const std::string& provider() const;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace ocr
