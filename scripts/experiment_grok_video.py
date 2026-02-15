#!/usr/bin/env python3
"""实验脚本：用 Grok Imagine API 把穿搭图片变成动态视频

实验模式（通过 --mode 选择）：
  A) separate  — 每张图单独生成视频，ffmpeg 拼接合集（默认）
  B) collage   — 先把 N 张图横向拼成一张三联图，只调一次 API

预计费用：
  separate: N × 5秒 × $0.05/秒  (3 张 = $0.75)
  collage:  1 × 5秒 × $0.05/秒  (      = $0.25)
"""

import asyncio
import base64
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output")
DATE = "2026-02-14"


# ---------------------------------------------------------------------------
# 图片处理工具
# ---------------------------------------------------------------------------

def compress_image(image_path: Path, max_bytes: int = 3_000_000) -> tuple[bytes, str]:
    """压缩图片到指定大小以内，返回 (bytes, mime_type)。

    API 的 gRPC 消息限制为 4MB，base64 编码后会膨胀约 33%，
    所以原始图片需要控制在 ~3MB 以内。
    """
    from PIL import Image
    import io

    img = Image.open(image_path).convert("RGB")

    # 先尝试直接转 JPEG
    for quality in [85, 70, 55, 40]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            print(f"    压缩: {image_path.name} → JPEG q={quality} ({buf.tell() / 1024:.0f} KB)")
            return buf.getvalue(), "image/jpeg"

    # 还是太大，缩小尺寸
    while True:
        w, h = img.size
        img = img.resize((w * 3 // 4, h * 3 // 4), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        if buf.tell() <= max_bytes:
            print(f"    压缩+缩放: {image_path.name} → {img.size[0]}x{img.size[1]} ({buf.tell() / 1024:.0f} KB)")
            return buf.getvalue(), "image/jpeg"


def compress_pil_image(img, max_bytes: int = 3_000_000) -> tuple[bytes, str]:
    """压缩 PIL Image 对象到指定大小以内，返回 (bytes, mime_type)。"""
    from PIL import Image
    import io

    for quality in [90, 80, 70, 60, 50]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            return buf.getvalue(), "image/jpeg"

    # 缩小尺寸
    while True:
        w, h = img.size
        img = img.resize((w * 3 // 4, h * 3 // 4), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        if buf.tell() <= max_bytes:
            return buf.getvalue(), "image/jpeg"


def make_collage(image_paths: list[Path], target_h: int = 1440, gap: int = 20) -> "Image":
    """将多张图横向拼接为一张三联图（带间距），返回 PIL Image。

    每张图等比缩放到 target_h 高度，之间留 gap 像素白色间距。
    """
    from PIL import Image

    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    resized = []
    for img in imgs:
        ratio = target_h / img.height
        resized.append(img.resize((int(img.width * ratio), target_h), Image.LANCZOS))

    total_w = sum(im.width for im in resized) + gap * (len(resized) - 1)
    canvas = Image.new("RGB", (total_w, target_h), (255, 255, 255))

    x = 0
    for im in resized:
        canvas.paste(im, (x, 0))
        x += im.width + gap

    return canvas


# ---------------------------------------------------------------------------
# 视频生成
# ---------------------------------------------------------------------------

async def generate_video(image_bytes: bytes, mime: str, label: str,
                         prompt: str, output_path: Path, duration: int = 5):
    """通用：调用 Grok Imagine API 生成视频并保存到本地。"""
    import xai_sdk
    import httpx

    client = xai_sdk.AsyncClient()
    image_data = base64.b64encode(image_bytes).decode("utf-8")

    print(f"  🎬 [{label}] 正在生成视频（{duration}秒）...")

    try:
        response = await client.video.generate(
            prompt=prompt,
            model="grok-imagine-video",
            image_url=f"data:{mime};base64,{image_data}",
            duration=duration,
            resolution="720p",
            timeout=timedelta(minutes=10),
            interval=timedelta(seconds=5),
        )

        if not response or not response.url:
            print(f"  ❌ [{label}] 视频生成失败：无返回 URL")
            return None

        async with httpx.AsyncClient() as http:
            r = await http.get(response.url, timeout=60)
            r.raise_for_status()
            output_path.write_bytes(r.content)

        print(f"  ✅ [{label}] 视频已保存: {output_path} "
              f"({output_path.stat().st_size / 1024:.0f} KB, {response.duration}秒)")
        return output_path

    except Exception as e:
        print(f"  ❌ [{label}] 视频生成出错: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# ffmpeg 拼接
# ---------------------------------------------------------------------------

def concat_videos(video_paths: list[Path], output_path: Path):
    """用 ffmpeg 拼接多个视频为一个合集"""
    import subprocess

    list_file = OUTPUT_DIR / "concat_list.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path),
    ]

    print(f"\n🔗 正在拼接 {len(video_paths)} 个视频...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)

    if result.returncode == 0:
        print(f"✅ 合集视频已生成: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
        return True
    else:
        print(f"❌ ffmpeg 拼接失败: {result.stderr[:300]}")
        return False


# ---------------------------------------------------------------------------
# 模式 A：separate（每张图单独生成）
# ---------------------------------------------------------------------------

async def run_separate(images: list[Path], prompt: str):
    print(f"⏱ 每段视频: 5 秒 | 分辨率: 720p")
    print(f"💰 预计费用: {len(images)} × $0.25 = ${len(images) * 0.25:.2f}\n")

    tasks = []
    for img in images:
        city = img.stem.split("_")[0]
        img_bytes, mime = compress_image(img)
        out = OUTPUT_DIR / f"{city}_{DATE}_video.mp4"
        tasks.append(generate_video(img_bytes, mime, city, prompt, out))

    results = await asyncio.gather(*tasks)
    video_paths = [r for r in results if r is not None]
    print(f"\n📊 结果: {len(video_paths)}/{len(images)} 个视频生成成功")

    if len(video_paths) > 1:
        concat_output = OUTPUT_DIR / f"穿搭合集_{DATE}.mp4"
        concat_videos(video_paths, concat_output)


# ---------------------------------------------------------------------------
# 模式 B：collage（拼成一张图，调一次 API）
# ---------------------------------------------------------------------------

async def run_collage(images: list[Path], prompt: str):
    cities = [img.stem.split("_")[0] for img in images]
    label = "+".join(cities)

    print(f"🖼  正在拼接三联图: {' | '.join(cities)}")
    collage = make_collage(images)
    collage_w, collage_h = collage.size
    print(f"    拼接完成: {collage_w}×{collage_h}")

    # 保存一份预览
    preview_path = OUTPUT_DIR / f"穿搭三联图_{DATE}.jpg"
    collage.save(preview_path, format="JPEG", quality=90)
    print(f"    预览已保存: {preview_path} ({preview_path.stat().st_size / 1024:.0f} KB)")

    img_bytes, mime = compress_pil_image(collage)
    print(f"    API 上传大小: {len(img_bytes) / 1024:.0f} KB")
    print(f"\n⏱ 视频: 5 秒 | 分辨率: 720p")
    print(f"💰 预计费用: 1 × $0.25 = $0.25\n")

    collage_prompt = (
        "All the people in the fashion outfits walk forward confidently, "
        "clothes and hair swaying naturally in a gentle breeze, "
        "smooth cinematic camera movement, natural lighting"
    )

    out = OUTPUT_DIR / f"穿搭三联视频_{DATE}.mp4"
    await generate_video(img_bytes, mime, label, collage_prompt, out)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Grok Imagine 穿搭视频实验")
    parser.add_argument("--mode", choices=["separate", "collage"], default="collage",
                        help="生成模式: separate=每张图单独生成, collage=拼图后一次生成 (默认: collage)")
    parser.add_argument("--date", default=DATE, help=f"日期 (默认: {DATE})")
    args = parser.parse_args()

    date = args.date

    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        print("❌ 请先设置 XAI_API_KEY 环境变量")
        sys.exit(1)

    print(f"=== Grok Imagine 穿搭视频实验 [{args.mode}] ===\n")

    images = sorted(OUTPUT_DIR.glob(f"*_{date}.png"))
    if not images:
        print(f"❌ 未找到 {date} 的穿搭图片")
        sys.exit(1)

    print(f"📷 找到 {len(images)} 张穿搭图片:")
    for img in images:
        print(f"  {img.name} ({img.stat().st_size / 1024 / 1024:.1f} MB)")

    prompt = (
        "The person in the fashion outfit walks forward confidently on a city street, "
        "clothes and hair swaying naturally in a gentle breeze, "
        "smooth cinematic camera movement, natural lighting"
    )
    print(f"\n🎬 Prompt: {prompt}")

    if args.mode == "separate":
        await run_separate(images, prompt)
    else:
        await run_collage(images, prompt)

    print("\n✅ 实验完成！")


if __name__ == "__main__":
    asyncio.run(main())
