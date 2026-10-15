// pose.h — 人体姿态/骨骼图（YOLOv8-pose ONNX），C ABI
#ifndef POSE_H
#define POSE_H
#ifdef __cplusplus
extern "C" {
#endif
// 在输出图上画骨骼（黑底彩线，COCO-17）；返回检出人数
int pose_draw(const char* in, const char* out, float thresh);
// 关键点 JSON（原图坐标），静态缓冲
const char* pose_keypoints_json(const char* in, float thresh);
#ifdef __cplusplus
}
#endif
#endif
