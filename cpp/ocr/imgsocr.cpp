// imgsocr.cpp — CLI: PaddleOCR PP-OCRv4 text recognition on an image.
#include "ocr.hpp"

#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char** argv) {
    std::string dir = "/data/models/ocr";
    if (const char* d = std::getenv("OCR_MODEL_DIR")) dir = d;
    bool json = false, cpu = false;
    std::string input;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--model-dir" && i + 1 < argc) dir = argv[++i];
        else if (a == "--json") json = true;
        else if (a == "--cpu") cpu = true;
        else if (a == "-h" || a == "--help") {
            std::cerr << "usage: " << argv[0] << " [--model-dir DIR] [--json] [--cpu] <image>\n";
            return 0;
        } else input = a;
    }
    if (input.empty()) {
        std::cerr << "error: missing image\n";
        return 2;
    }

    try {
        ocr::Ocr engine(dir + "/ch_PP-OCRv4_det_infer.onnx", dir + "/ch_PP-OCRv4_rec_infer.onnx",
                        dir + "/ppocr_keys_v1.txt", !cpu);
        std::cerr << "[imgsocr] provider=" << engine.provider() << "\n";
        auto boxes = engine.Run(input);
        if (json) {
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
            std::cout << os.str() << std::endl;
        } else {
            for (auto& b : boxes) std::cout << b.text << "\n";
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[imgsocr] error: " << e.what() << "\n";
        return 1;
    }
}
