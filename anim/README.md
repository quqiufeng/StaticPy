# anim —— 动画素材工具（StaticPy 实现，编成 ELF）

> 只依赖 **StaticPy + imgproc**（无 PIL/numpy）。`bgremove`（BiRefNet）为 C++ 工具。
> 目标：把「关键帧/生成帧」变成**游戏可直接用的素材**（透明精灵表 + manifest + 预览 GIF）。

## 工具

| 工具 | 作用 | 用法 |
|---|---|---|
| `pose_walk` | 生成 **OpenPose 走路骨架帧**（含手部 21 点） | `OUTDIR=dir [LEGX/ARMX/YUP/HAND] pose_walk` |
| `pack_sprites` | 透明帧 → **精灵表 PNG + manifest.json**（统一裁切/缩放/镜像/平铺） | `pack_sprites OUT.png MANIFEST.json CROP_W CROP_H SRC_X SRC_Y CELL_W CELL_H COLS FLIP NAME f1.png …` |
| `frames_to_gif` | 帧序列 → **循环 GIF**（预览） | `frames_to_gif OUT.gif FPS f1.png f2.png …` |

- `pose_walk`：环境变量 `LEGX`(步幅)/`ARMX`(摆臂)/`YUP`(上移留白)/`HAND`(手 21 点)；输出 `f00..f15.png` + `preview_*.png`。
- `FLIP=1` → 每帧水平镜像（出"朝右"，帧序不变）。
- 固定裁切 `(SRC_X,SRC_Y,CROP_W,CROP_H)` 即可让同机位生成的帧对齐（脚基线稳定）。

## 构建（编成原生 ELF）
```bash
cd /opt/StaticPy
mkdir -p /tmp/staticpy-cache/anim
bash imgproc/build_app.sh anim/pose_walk.static.py     anim/pose_walk
bash imgproc/build_app.sh anim/pack_sprites.static.py  anim/pack_sprites
bash imgproc/build_app.sh anim/frames_to_gif.static.py anim/frames_to_gif
```
运行需 imgproc 动态库：
```bash
export LD_LIBRARY_PATH=/opt/StaticPy/cpp/imgproc/build
```

## 端到端流水线（0 付费 API）
```
① 关键帧/生成帧（Nano / static_comfyui / AnimateDiff）→ frame_*.png
   或 骨架：OUTDIR=pose LEGX=0.5 HAND=1 pose_walk       （OpenPose 控制图）
② 抠透明底（BiRefNet）
     bash /opt/static_comfyui/cpp/sd/bgremove.sh in.png cut.png transparent
③ 打包（StaticPy）
     pack_sprites name_left.png name_left.json 360 480 140 20 180 240 8 0 walk_left  cut/f*.png
     pack_sprites name_right.png name_right.json 360 480 140 20 180 240 8 1 walk_right cut/f*.png
④ 预览（StaticPy）
     frames_to_gif walk_left.gif 8 cut/f*.png
```

## manifest.json
```json
{
  "name": "walk_left",
  "image": "knight_walk_left.png",
  "frameWidth": 180, "frameHeight": 240,
  "columns": 8, "rows": 2, "frameCount": 16,
  "animations": { "walk_left": { "from": 0, "to": 15, "fps": 8, "loop": true } }
}
```
游戏端按 `frameWidth/Height + columns/rows` 切图；`animations` 给片段的帧区间/fps/loop。

## 依赖
- `libimgproc.so`（`cpp/imgproc/build`）：`img_open/save/new/fill/crop/resize/transpose/alpha_composite_at/append_frame/set_delay`。
- `bgremove.sh`（BiRefNet）：仅抠图步骤用。
