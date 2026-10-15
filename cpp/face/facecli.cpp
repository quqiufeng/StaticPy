// facecli.cpp — CLI: 人脸检测 / 对齐裁剪 / 人脸解析（face-parsing）
// 批量模式（模型只加载一次，快）：stdin 每行一个路径
//   facecli detect --batch        # 每行: <img>            -> 每行输出 JSON
//   facecli crop   --batch        # 每行: <img>\t<out.png>[ size] -> 每行输出 <out> 或空
#include "face.hpp"

#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>

static std::string faces_json(const std::vector<face::Face>& fs) {
    std::ostringstream os;
    os << "[";
    for (size_t i = 0; i < fs.size(); ++i) {
        if (i) os << ",";
        os << "{\"score\":" << fs[i].score << ",\"box\":[" << fs[i].box[0] << "," << fs[i].box[1] << ","
           << fs[i].box[2] << "," << fs[i].box[3] << "]}";
    }
    os << "]";
    return os.str();
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage:\n"
                     "  facecli detect <img>\n"
                     "  facecli detect --batch            # paths from stdin, JSON per line\n"
                     "  facecli crop   <img> <out.png> [size=512]\n"
                     "  facecli crop   --batch            # '<img>\\t<out.png>[ size]' per line\n"
                     "  facecli parse  <img> <out.png> [color|face|skin|hair]\n";
        return 2;
    }
    std::string cmd = argv[1];
    bool batch = (argc > 2 && std::string(argv[2]) == "--batch");
    try {
        face::FaceEngine eng;   // 只加载一次（含批量场景）
        if (cmd == "detect") {
            if (batch) {
                std::string line;
                while (std::getline(std::cin, line)) {
                    while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
                    if (line.empty()) continue;
                    std::cout << faces_json(eng.Detect(line)) << std::endl;
                }
                return 0;
            }
            if (argc < 3) return 2;
            std::cout << faces_json(eng.Detect(argv[2])) << std::endl;
            return 0;
        } else if (cmd == "crop") {
            if (batch) {
                std::string line;
                while (std::getline(std::cin, line)) {
                    while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
                    if (line.empty()) continue;
                    std::string in, out; int size = 512;
                    // 格式: <in>\t<out>[ size]
                    auto tab = line.find('\t');
                    if (tab == std::string::npos) { std::cout << std::endl; continue; }
                    in = line.substr(0, tab);
                    std::string rest = line.substr(tab + 1);
                    auto sp = rest.find(' ');
                    if (sp == std::string::npos) out = rest;
                    else { out = rest.substr(0, sp); size = std::atoi(rest.substr(sp + 1).c_str()); }
                    bool ok = eng.CropLargest(in, out, size);
                    std::cout << (ok ? out : "") << std::endl;
                }
                return 0;
            }
            if (argc < 4) return 2;
            int size = argc > 4 ? std::atoi(argv[4]) : 512;
            bool ok = eng.CropLargest(argv[2], argv[3], size);
            if (!ok) { std::cerr << "no face detected\n"; return 1; }
            std::cout << argv[3] << std::endl;
            return 0;
        } else if (cmd == "parse") {
            if (argc < 4) return 2;
            std::string mode = argc > 4 ? argv[4] : "face";
            eng.Parse(argv[2], argv[3], mode);
            std::cout << argv[3] << std::endl;
            return 0;
        }
        std::cerr << "unknown command: " << cmd << "\n";
        return 2;
    } catch (const std::exception& e) {
        std::cerr << "[facecli] error: " << e.what() << "\n";
        return 1;
    }
}
