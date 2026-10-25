// bgremove.cpp — CLI: BiRefNet background removal.
#include "birefnet.hpp"

#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

namespace {
std::string DefaultOut() {
    const char* home = std::getenv("HOME");
    std::string dir = home ? home : ".";
    char buf[64];
    std::time_t t = std::time(nullptr);
    std::strftime(buf, sizeof(buf), "%Y%m%d_%H%M%S", std::localtime(&t));
    return dir + "/" + buf + "_nobg.png";
}

int ParseMode(const std::string& s) {
    if (s == "transparent" || s == "rgba") return bref::MODE_TRANSPARENT;
    if (s == "white") return bref::MODE_WHITE;
    if (s == "black") return bref::MODE_BLACK;
    if (s == "green") return bref::MODE_GREEN;
    if (s == "color") return bref::MODE_COLOR;
    if (s == "mask") return bref::MODE_MASK;
    if (s == "checker" || s == "checkerboard") return bref::MODE_CHECKER;
    return -1;
}
}  // namespace

int main(int argc, char** argv) {
    std::string model = "/data/models/birefnet/onnx/model.onnx";
    if (const char* m = std::getenv("BIREFNET_MODEL")) model = m;
    std::string mode_s = "transparent";
    std::string color_s = "";
    std::string mask_out = "";
    std::string in, out, list_path;
    bool cpu = false;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--model" && i + 1 < argc) model = argv[++i];
        else if (a == "--mode" && i + 1 < argc) mode_s = argv[++i];
        else if (a == "--color" && i + 1 < argc) color_s = argv[++i];
        else if (a == "--mask" && i + 1 < argc) mask_out = argv[++i];
        else if (a == "--list" && i + 1 < argc) list_path = argv[++i];
        else if (a == "--cpu") cpu = true;
        else if (a == "-h" || a == "--help") {
            std::cerr << "usage: " << argv[0]
                      << " [--model PATH] [--mode transparent|white|black|green|color|mask]"
                         " [--color RRGGBB] [--mask mask.png] [--cpu]"
                         " <input> [output] | --list list.tsv\n"
                         "  list.tsv: <input>\\t<output> per line\n";
            return 0;
        } else if (in.empty()) in = a;
        else out = a;
    }
    if (in.empty() && list_path.empty()) {
        std::cerr << "error: missing input image (or --list)\n";
        return 2;
    }
    if (!in.empty() && out.empty()) out = DefaultOut();

    int mode = ParseMode(mode_s);
    if (mode < 0) {
        std::cerr << "error: unknown mode '" << mode_s << "'\n";
        return 2;
    }
    int r = 255, g = 255, b = 255;
    if (mode == bref::MODE_COLOR) {
        std::string hex = color_s;
        if (!hex.empty() && hex[0] == '#') hex = hex.substr(1);
        if (hex.size() >= 6) {
            r = std::stoi(hex.substr(0, 2), nullptr, 16);
            g = std::stoi(hex.substr(2, 2), nullptr, 16);
            b = std::stoi(hex.substr(4, 2), nullptr, 16);
        }
    }

    try {
        std::vector<std::pair<std::string, std::string>> jobs;
        if (!list_path.empty()) {
            std::ifstream lf(list_path);
            if (!lf) { std::cerr << "error: cannot open list " << list_path << "\n"; return 2; }
            std::string line;
            while (std::getline(lf, line)) {
                if (line.empty()) continue;
                auto tab = line.find('\t');
                if (tab == std::string::npos) jobs.emplace_back(line, DefaultOut());
                else jobs.emplace_back(line.substr(0, tab), line.substr(tab + 1));
            }
            if (jobs.empty()) { std::cerr << "error: empty list\n"; return 2; }
        }
        bref::BgRemover model_(model, !cpu);
        std::cerr << "[bgremove] provider=" << model_.provider() << " mode=" << mode_s
                  << (jobs.empty() ? "" : " batch=" + std::to_string(jobs.size())) << "\n";
        if (jobs.empty()) {
            model_.Process(in, out, mask_out, mode, r, g, b);
            std::cout << out << std::endl;
        } else {
            for (const auto& j : jobs) {
                model_.Process(j.first, j.second, mask_out, mode, r, g, b);
                std::cout << j.second << std::endl;
            }
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[bgremove] error: " << e.what() << "\n";
        return 1;
    }
}
