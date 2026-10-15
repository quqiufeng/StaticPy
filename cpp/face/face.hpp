// face.hpp — Face detect / align-crop / parse (InsightFace SCRFD + BiSeNet), ONNX Runtime C++.
#pragma once

#include <memory>
#include <string>
#include <vector>

namespace face {

struct Face {
    float score = 0.0f;
    float box[4] = {0, 0, 0, 0};   // x1,y1,x2,y2 (原图坐标)
    float kps[10] = {0};           // 5× (x,y) 关键点（原图坐标）
};

struct Options {
    std::string det_model = "/data/models/image/det_10g.onnx";
    std::string parse_model = "/data/models/face/faceparser.onnx";
    float det_thresh = 0.5f;
    float nms_thresh = 0.4f;
    int det_size = 640;   // 检测输入最长边（32 对齐）
};

class FaceEngine {
  public:
    explicit FaceEngine(const Options& opt = {}, bool use_cuda = true);
    ~FaceEngine();
    FaceEngine(const FaceEngine&) = delete;
    FaceEngine& operator=(const FaceEngine&) = delete;

    // 人脸检测（SCRFD），返回按分数降序的人脸。
    std::vector<Face> Detect(const std::string& image_path) const;

    // 检测最大人脸 → 5 点对齐裁剪 → 保存 out_path（默认 512×512 PNG）。
    // 返回是否成功。
    bool CropLargest(const std::string& image_path, const std::string& out_path, int size = 512) const;

    // 人脸解析（BiSeNet 19 类）。mode:
    //   "color"      彩色分割图（所见即所得）
    //   "face"       人脸区域灰度 mask（skin+brows+eyes+nose+mouth+lips）+ 可选 neck
    //   "skin"       仅皮肤(1)
    //   "hair"       仅头发(17)
    // 保存到 out_path。
    bool Parse(const std::string& image_path, const std::string& out_path, const std::string& mode) const;

    const std::string& provider() const;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace face
