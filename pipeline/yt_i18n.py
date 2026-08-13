#!/usr/bin/env python3
"""유튜브 다국어 — ① 제목·설명 현지화(localizations) ② 자막 트랙(captions).

왜 이 구조인가:
  번인 자막(libass)은 어떤 플랫폼도 번역하지 못한다. 그래서 '번역'은 영상 밖에서 붙인다.
    ① localizations : videos.update, ★50 units. 유튜브가 해당 국가 사용자에게 그 나라 말
                      제목/설명을 노출한다 → 노출수 자체가 늘어난다. 가성비 압도적 = 전 토픽.
    ② captions      : captions.insert, ★400 units/언어. 비싸서 SCP(주 2편)에만 건다.
  루틴 프롬프트는 손대지 않는다 — 번역은 기계적인 작업이라 여기서 Claude 로 돌리는 게
  스펙을 비대하게 만드는 것보다 낫다(실패 지점도 한 곳으로 모인다).

★스코프 주의(둘이 다르다):
  localizations → `youtube` 스코프면 된다. token_novel.json 이 이미 갖고 있다.
  captions      → ★`youtube.force-ssl` 이 필요하다. 기존 토큰에는 없다.
                  없으면 조용히 스킵한다(경고 1줄). 켜려면:
                    python pipeline/yt_i18n.py --auth-only
                  → secrets/token_forcessl.json 내용을 Secret `YT_TOKEN_JSON_FORCESSL` 에.
  ★기존 upload_youtube*.py 의 SCOPES 는 건드리지 않는다 — 리프레시 때 스코프가 바뀌면
    매일 도는 업로드가 통째로 깨진다. 그래서 이 모듈이 자기 토큰을 따로 고른다.

모두 best-effort: 어떤 단계가 실패해도 업로드 자체는 이미 끝난 상태라 경고만 남긴다.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time

import config

SCOPE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_MANAGE = "https://www.googleapis.com/auth/youtube"
SCOPE_FORCE = "https://www.googleapis.com/auth/youtube.force-ssl"

LANGS = [s.strip() for s in config.env("I18N_LANGS", "en,ja,zh-Hant").split(",") if s.strip()]
SOURCE_LANG = config.env("I18N_SOURCE_LANG", "ko")
DO_LOCALIZE = config.env("I18N_LOCALIZE", "1") not in ("0", "false", "off", "")
DO_CAPTIONS = config.env("I18N_CAPTIONS", "1") not in ("0", "false", "off", "")
MODEL = config.env("I18N_MODEL") or config.env("CLAUDE_MODEL", "claude-sonnet-4-6")

# 자막 트랙 이름(유튜브 자막 선택 메뉴에 뜨는 문구) + 번역 지시용 언어 이름
LANG_NAME = {
    "en": ("English", "English"),
    "ja": ("日本語", "Japanese"),
    "zh-Hant": ("繁體中文", "Traditional Chinese (Taiwan)"),
    "zh-Hans": ("简体中文", "Simplified Chinese"),
    "es": ("Español", "Spanish"),
    "pt": ("Português", "Portuguese (Brazil)"),
    "id": ("Bahasa Indonesia", "Indonesian"),
    "vi": ("Tiếng Việt", "Vietnamese"),
    "th": ("ไทย", "Thai"),
    "fr": ("Français", "French"),
    "de": ("Deutsch", "German"),
    "ru": ("Русский", "Russian"),
}


def _name(lang: str) -> tuple[str, str]:
    return LANG_NAME.get(lang, (lang, lang))


# ── 토큰/서비스 ────────────────────────────────────────
def _token_paths() -> dict[str, str]:
    root = config.ROOT / "pipeline/secrets"
    return {
        "forcessl": config.env("YT_TOKEN_FORCESSL") or str(root / "token_forcessl.json"),
        "novel": config.env("YT_TOKEN_NOVEL") or str(root / "token_novel.json"),
        "shorts": config.env("YT_TOKEN") or str(root / "token.json"),
    }


def _service(kinds: list[str], scopes: list[str]):
    """kinds 순서대로 존재하는 첫 토큰으로 서비스 생성. 하나도 없으면 None."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 다국어 스킵 — google 라이브러리 없음: {e}\n")
        return None
    paths = _token_paths()
    for k in kinds:
        p = paths.get(k, "")
        if not p or not os.path.exists(p):
            continue
        try:
            creds = Credentials.from_authorized_user_file(p, scopes)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return build("youtube", "v3", credentials=creds)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] 토큰 {os.path.basename(p)} 사용 실패(다음 후보로): {e}\n")
    return None


# ── 번역(Claude) ───────────────────────────────────────
def _claude(system: str, user: str, max_tokens: int = 4000) -> str | None:
    key = config.env("ANTHROPIC_API_KEY")
    if not key:
        sys.stderr.write("[warn] ANTHROPIC_API_KEY 없음 — 번역 스킵\n")
        return None
    try:
        import anthropic
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 번역 호출 실패: {e}\n")
        return None


def _json_block(text: str):
    """모델이 펜스/설명을 붙여도 JSON 만 뽑아낸다."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = t.find(open_c), t.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                continue
    return None


def translate_meta(title: str, description: str, langs: list[str]) -> dict:
    """제목/설명을 여러 언어로 한 번에 번역 → {lang: {title, description}}."""
    targets = {l: _name(l)[1] for l in langs}
    sysmsg = ("You localize Korean YouTube metadata. Output VALID JSON ONLY, no prose, no fences.\n"
              "Rules:\n"
              "- Localize, don't transliterate: the title must work as a hook for a native speaker.\n"
              "- Keep the title UNDER 90 characters.\n"
              "- Keep hashtags, URLs, emoji, license notices and line breaks exactly as-is; "
              "translate only the surrounding prose.\n"
              "- Keep '#shorts' literally.\n"
              "- Proper nouns that are part of a franchise (e.g. SCP) stay in their standard form "
              "for that language.")
    user = json.dumps({"source_language": SOURCE_LANG, "targets": targets,
                       "title": title, "description": description}, ensure_ascii=False)
    user += ('\n\nReturn exactly: {"<lang>": {"title": "...", "description": "..."}, ...} '
             f'with these keys: {list(targets)}')
    raw = _claude(sysmsg, user, max_tokens=4000)
    if raw is None:
        return {}                         # 키 없음/호출 실패 — 이미 경고를 남겼다
    data = _json_block(raw)
    if not isinstance(data, dict):
        sys.stderr.write("[warn] 메타 번역 결과 파싱 실패 — 현지화 스킵\n")
        return {}
    out = {}
    for lang in langs:
        v = data.get(lang)
        if isinstance(v, dict) and (v.get("title") or "").strip():
            out[lang] = {"title": str(v["title"]).strip()[:100],
                         "description": str(v.get("description") or "").strip()[:5000]}
    if out:
        print(f"   🌐 메타 번역 {len(out)}개 언어: {', '.join(out)}")
    return out


# ── SRT ────────────────────────────────────────────────
_SRT_BLOCK = re.compile(r"(\d+)\s*\n([\d:,]+\s*-->\s*[\d:,]+)\s*\n(.*?)(?=\n\s*\n|\Z)", re.S)


def srt_parse(text: str) -> list[tuple[str, str, str]]:
    return [(m.group(1), m.group(2).strip(), m.group(3).strip())
            for m in _SRT_BLOCK.finditer(text or "")]


def srt_build(blocks: list[tuple[str, str, str]]) -> str:
    return "\n".join(f"{i}\n{tc}\n{tx}\n" for i, tc, tx in blocks)


def translate_srt(srt_text: str, lang: str) -> str | None:
    """자막 ★텍스트만 번역하고 타임코드는 그대로 재조립한다.

    SRT 통째로 모델에 맡기면 타임코드가 흐트러진다. 그래서 텍스트만 배열로 보내고
    개수가 정확히 같을 때만 채택한다(다르면 그 언어는 버린다 — 싱크 깨진 자막보다 없는 게 낫다).
    """
    blocks = srt_parse(srt_text)
    if not blocks:
        return None
    src = [b[2].replace("\n", " ") for b in blocks]
    sysmsg = (f"Translate Korean subtitle lines into {_name(lang)[1]}. "
              "Output VALID JSON ONLY: an array of strings, no prose, no fences.\n"
              "- Return EXACTLY the same number of items, in the same order.\n"
              "- One subtitle line each; keep them short and readable on screen.\n"
              "- Preserve the tone (calm documentary narration). Do not merge or split lines.")
    data = _json_block(_claude(sysmsg, json.dumps(src, ensure_ascii=False),
                               max_tokens=min(16000, 200 + len(srt_text) * 3)) or "")
    if not isinstance(data, list) or len(data) != len(src):
        got = len(data) if isinstance(data, list) else "파싱실패"
        sys.stderr.write(f"[warn] {lang} 자막 번역 개수 불일치({got} vs {len(src)}) — 이 언어 스킵\n")
        return None
    return srt_build([(b[0], b[1], str(t).strip()) for b, t in zip(blocks, data)])


# ── ① 현지화 ───────────────────────────────────────────
def localize(video_id: str, langs: list[str] | None = None, retries: int = 3) -> list[str]:
    """제목·설명 현지화. 성공한 언어 목록 반환. 실패는 경고만(업로드는 이미 끝났다)."""
    if not DO_LOCALIZE:
        return []
    langs = langs or LANGS
    if not langs:
        return []
    if not config.env("ANTHROPIC_API_KEY"):
        # 번역을 못 하는데 videos.list(1 unit)를 먼저 쏘면 쿼터만 낭비된다.
        sys.stderr.write("[warn] 현지화 스킵 — ANTHROPIC_API_KEY 없음\n")
        return []
    yt = _service(["forcessl", "novel", "shorts"], [SCOPE_FORCE, SCOPE_MANAGE, SCOPE_UPLOAD])
    if yt is None:
        sys.stderr.write("[warn] 현지화 스킵 — 사용 가능한 토큰 없음\n")
        return []
    try:
        # ★videos.update 는 snippet 을 통째로 덮어쓴다. 빠뜨린 필드는 초기화되므로
        #   현재 snippet 을 먼저 읽어와서(1 unit) 그 위에 얹는다.
        cur = yt.videos().list(part="snippet", id=video_id).execute()
        items = cur.get("items") or []
        if not items:
            sys.stderr.write(f"[warn] 현지화 스킵 — 영상 조회 실패({video_id})\n")
            return []
        sn = items[0]["snippet"]
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 현지화 스킵 — snippet 조회 실패: {e}\n")
        return []

    loc = translate_meta(sn.get("title", ""), sn.get("description", ""), langs)
    if not loc:
        return []
    body = {
        "id": video_id,
        # localizations 를 쓰려면 defaultLanguage 가 반드시 설정돼 있어야 한다.
        "snippet": {"title": sn.get("title", ""), "description": sn.get("description", ""),
                    "categoryId": sn.get("categoryId", "24"), "tags": sn.get("tags", []),
                    "defaultLanguage": sn.get("defaultLanguage") or SOURCE_LANG},
        "localizations": loc,
    }
    for attempt in range(1, retries + 1):
        try:
            yt.videos().update(part="snippet,localizations", body=body).execute()
            print(f"   🌐 현지화 적용: {', '.join(loc)} (videos.update 50 units)")
            return list(loc)
        except Exception as e:  # noqa: BLE001
            code = getattr(getattr(e, "resp", None), "status", None)
            if code in (403, 401):
                sys.stderr.write(f"[warn] 현지화 권한 부족(스코프 `youtube` 필요) — 스킵: {e}\n")
                return []
            if attempt == retries:
                sys.stderr.write(f"[warn] 현지화 실패 — 스킵: {e}\n")
                return []
            wait = min(2 ** attempt, 10)
            print(f"   … 현지화 {code} 일시오류 — {wait}s 후 재시도({attempt}/{retries - 1})")
            time.sleep(wait)
    return []


# ── ② 자막 트랙 ────────────────────────────────────────
def add_caption_tracks(video_id: str, srt_path: str, langs: list[str] | None = None) -> list[str]:
    """번역 자막 트랙 업로드. ★400 units/언어 — 호출측이 토픽을 골라서 부른다."""
    if not (DO_CAPTIONS and srt_path and os.path.exists(srt_path)):
        return []
    langs = langs or LANGS
    if not langs:
        return []
    yt = _service(["forcessl"], [SCOPE_FORCE])
    if yt is None:
        sys.stderr.write(
            "[warn] 자막 트랙 스킵 — force-ssl 토큰 없음(captions API 는 이 스코프가 필수).\n"
            "       켜려면: python pipeline/yt_i18n.py --auth-only → "
            "secrets/token_forcessl.json 을 Secret `YT_TOKEN_JSON_FORCESSL` 에 저장.\n")
        return []
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return []
    with open(srt_path, encoding="utf-8") as f:
        src = f.read()

    done = []
    workdir = os.path.dirname(os.path.abspath(srt_path))
    for lang in langs:
        tr = translate_srt(src, lang)
        if not tr:
            continue
        p = os.path.join(workdir, f"captions_{lang.replace('-', '_')}.srt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(tr)
        try:
            yt.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": lang,
                                  "name": _name(lang)[0], "isDraft": False}},
                media_body=MediaFileUpload(p, mimetype="application/octet-stream")).execute()
            done.append(lang)
            print(f"   💬 자막 트랙 업로드: {lang} ({_name(lang)[0]}) — 400 units")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] {lang} 자막 트랙 업로드 실패(무시): {e}\n")
    return done


# ── 고수준: 업로드 직후 한 방에 ────────────────────────
def apply(video_id: str, srt_path: str | None = None, langs: list[str] | None = None) -> dict:
    """현지화(항상) + 자막 트랙(srt_path 를 준 파이프라인만)."""
    return {"localized": localize(video_id, langs),
            "captions": add_caption_tracks(video_id, srt_path or "", langs)}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="유튜브 다국어(현지화/자막 트랙)")
    ap.add_argument("--auth-only", action="store_true",
                    help="force-ssl 스코프 토큰 발급(자막 트랙용). 기존 토큰은 건드리지 않는다")
    ap.add_argument("--video-id", help="이 영상에 현지화/자막 적용")
    ap.add_argument("--srt", default="", help="원본(한국어) SRT — 주면 자막 트랙까지")
    ap.add_argument("--langs", default="", help="쉼표 구분(비우면 I18N_LANGS)")
    args = ap.parse_args()
    config.load_dotenv()

    if args.auth_only:
        from google_auth_oauthlib.flow import InstalledAppFlow
        secret = (config.env("YT_CLIENT_SECRET_NOVEL") or config.env("YT_CLIENT_SECRET")
                  or str(config.ROOT / "pipeline/secrets/client_secret.json"))
        # force-ssl 은 상위 스코프라 업로드/재생목록도 포함해 발급해둔다(이 토큰만 따로 쓴다).
        creds = InstalledAppFlow.from_client_secrets_file(
            secret, [SCOPE_FORCE, SCOPE_MANAGE, SCOPE_UPLOAD]).run_local_server(port=0)
        p = _token_paths()["forcessl"]
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(creds.to_json())
        print(f"✅ 발급 완료 — {p}\n"
              f"   이 파일 '내용 전체'를 GitHub Secret 'YT_TOKEN_JSON_FORCESSL' 에 넣으세요.\n"
              f"   (기존 token.json / token_novel.json 은 그대로입니다.)")
        return 0

    if not args.video_id:
        print("[error] --video-id 필요 (또는 최초 인증은 --auth-only)")
        return 1
    langs = [s.strip() for s in args.langs.split(",") if s.strip()] or None
    print(apply(args.video_id, args.srt, langs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
