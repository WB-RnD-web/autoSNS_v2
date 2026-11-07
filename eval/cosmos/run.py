"""cosmos3-nano(build.nvidia.com 무료 체험 엔드포인트) 화질 평가 — 업로드하지 않는다(체험 약관: 평가용만).

    NVIDIA_API_KEY=... python eval/cosmos/run.py      # eval/cosmos/in/*.jpg → eval/cosmos/out/*.mp4 + log.json

같은 고양이 견본의 첫 그림(스파크 z-image)을 image2video 로 한 번에 약 8초(720×1280, 193프레임, 24fps) 뽑아
지금 스파크 5B(2초 컷 이어 붙이기)와 나란히 비교하려는 것. 토큰은 환경변수에서만 읽고 찍지 않는다.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import zipfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://ai.api.nvidia.com/v1/cosmos/nvidia/cosmos3-nano"
STATUS = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/status/{}"
NEG = ("text, letters, watermark, logo, human hands, people, extra legs, extra paws, deformed body, "
       "stretched body, melting, blurry, flickering, camera shake, low quality")
CASES = {
    "s01": "A static close-up shot of golden fish-shaped bungeoppang pastries steaming on a black cast-iron "
           "street food grill at night in winter. The pastry in the center slowly comes to life and transforms "
           "into a tiny fluffy golden-brown kitten whose fur looks like baked dough: two small ears pop up, its "
           "eyes open, it lifts its head, stretches its little front paws and looks around curiously. Steam keeps "
           "rising and light snow drifts in the background. Photorealistic, smooth natural motion, static camera.",
    "s04": "A gray British shorthair cat wearing tiny round sunglasses stands upright on its hind legs on a "
           "neon-lit disco dance floor under a spinning mirror ball. The cat dances to an upbeat funk song: it "
           "sways its hips side to side, pumps one front paw up and down to the beat, bobs its head, then waves "
           "both front paws in the air. Colorful disco light spots sweep across the floor. Photorealistic, smooth "
           "natural motion, static camera, the cat stays fully in frame.",
    "s09": "A tiny calico kitten sits on a white windowsill inside a cozy house, watching the first snow of "
           "winter fall outside the window. Its head follows a falling snowflake, its ears twitch, it lifts one "
           "front paw and gently taps the cold window glass, then looks back at the snow with wide curious eyes. "
           "Big soft snowflakes drift down outside. Photorealistic, soft daylight, smooth natural motion, static camera.",
}


def _video_bytes(r: requests.Response) -> bytes:
    ct = r.headers.get("Content-Type", "")
    if "zip" in ct:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for n in z.namelist():
            if n.endswith(".mp4"):
                return z.read(n)
            if n.endswith(".json"):
                return base64.b64decode(json.loads(z.read(n))["b64_video"])
        raise RuntimeError(f"zip 안에 영상 없음: {z.namelist()}")
    if "json" in ct:
        return base64.b64decode(r.json()["b64_video"])
    return r.content


def call(key: str, body: dict) -> tuple[requests.Response, float]:
    auth = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    t0 = time.time()
    r = requests.post(URL, headers={**auth, "Content-Type": "application/json"}, json=body,
                      timeout=900, allow_redirects=False)
    while r.status_code == 202:
        rid = r.headers.get("NVCF-REQID")
        print(f"   대기 중… {time.time() - t0:.0f}초 (req {rid})", flush=True)
        time.sleep(10)
        r = requests.get(STATUS.format(rid), headers=auth, timeout=900, allow_redirects=False)
    if r.status_code in (301, 302, 303, 307, 308):          # 큰 결과는 서명된 주소로 — 토큰을 넘기지 않는다
        r = requests.get(r.headers["Location"], timeout=900)
    return r, time.time() - t0


def main() -> int:
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key:
        print("::error::NVIDIA_API_KEY 없음")
        return 1
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    log, fails = {}, 0
    for cid, prompt in CASES.items():
        with open(os.path.join(HERE, "in", f"{cid}.jpg"), "rb") as f:
            img = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
        body = {"model_mode": "image2video", "prompt": prompt, "negative_prompt": NEG, "input_reference": img,
                "resolution": "720_9_16", "num_frames": 193, "fps": 24, "seed": 7}
        print(f"▶ {cid}", flush=True)
        r, sec = call(key, body)
        if r.status_code == 422 and "negative" in r.text.lower():
            print("   negative_prompt 거절 → 빼고 다시", flush=True)
            body.pop("negative_prompt")
            r, sec = call(key, body)
        info = {"status": r.status_code, "sec": round(sec, 1), "content_type": r.headers.get("Content-Type")}
        if r.status_code != 200:
            fails += 1
            info["error"] = r.text[:1500]
            print(f"::error::{cid} HTTP {r.status_code} ({sec:.0f}초): {r.text[:1500]}")
        else:
            try:
                data = _video_bytes(r)
                with open(os.path.join(out, f"{cid}.mp4"), "wb") as f:
                    f.write(data)
                info["bytes"] = len(data)
                print(f"✅ {cid} {len(data) / 1e6:.1f}MB · {sec:.0f}초", flush=True)
            except Exception as e:  # noqa: BLE001
                fails += 1
                info["error"] = f"{type(e).__name__}: {e}"[:500]
                print(f"::error::{cid} 결과 해석 실패: {info['error']} · 헤더 {sorted(r.headers)}")
        log[cid] = info
    with open(os.path.join(out, "log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(json.dumps(log, ensure_ascii=False))
    return 1 if fails == len(CASES) else 0


if __name__ == "__main__":
    sys.exit(main())
