"""出力の 1 枚の HTML の組み立て（雛形 viewer/page.tpl.html への埋めと、図の配置の道具 elkjs の取り寄せ）。

ページは 1 枚で完結し、別のファイルからスクリプトを読まない（viewer/AGENTS.md の E25 の 3）ので、データと elkjs の bundle をページの中に
埋める。elkjs は viewer/elkjs.json の版と照らしの値で止め、利用者のキャッシュ（殻と同じ取り置きの置き場 bin/_lib/place.py の
cache_dir の下の viewer/elkjs-<版>/）に tarball を元の名のまま置く。tarball は読むたびに照らし、合わない・取れない時は書かずに止める。

- render(data, env, get) -> ページの字。get は網の口（既定は lib/webget.py の http_get。試験が差し替える）
- elk(env, get) -> (bundle の字, ページに置く注)。止まる時は Unfetched
"""
import base64
import hashlib
import io
import json
import os
import re
import tarfile
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

import webget   # lib/（viewer/src/__init__.py が sys.path に足す）
from bin._lib import place

HERE = Path(__file__).resolve().parents[1]
TEMPLATE = HERE / "page.tpl.html"
ELK = json.loads((HERE / "elkjs.json").read_text(encoding="utf-8"))
DATA_MARK = "__DATA__"
ELK_MARK = "/*__ELK__*/"
MAX_BODY = 32 * 1024 * 1024
CLOSE = re.compile(r"</(script)", re.I)


class Unfetched(Exception):
    """elkjs が取れない・照らしが合わない（ページを書かずに止まる訳）"""


def render(data: dict, env: Mapping[str, str], get: Callable = webget.http_get) -> str:
    bundle, note = elk(env, get)
    return fill(TEMPLATE.read_text(encoding="utf-8"), {
        # JSON の字の < を全部 \u003c にし、記録の字の </script> や <!-- が script の中身を閉じない・読み方を変えないようにする
        DATA_MARK: json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"),
        # elkjs の字と注（license の字）の </script を、大小に依らず崩す
        ELK_MARK: CLOSE.sub(r"<\\/\1", note + "\n" + bundle),
    })


def fill(template: str, values: dict[str, str]) -> str:
    """雛形の印を 1 度ずつ埋める。埋めた字の中に印の字が在っても埋め直さない（データは雛形の字でない）"""
    pattern = re.compile("|".join(map(re.escape, values)))
    found = pattern.findall(template)
    if sorted(found) != sorted(values):
        raise ValueError(f"雛形の印が 1 つずつでない（{found}）")
    return pattern.sub(lambda hit: values[hit[0]], template)


def elk(env: Mapping[str, str], get: Callable = webget.http_get) -> tuple[str, str]:
    folder = place.cache_dir(env) / "viewer" / f"{ELK['package']}-{ELK['version']}"
    tgz = folder / Path(ELK["tarball"]).name
    body = tgz.read_bytes() if tgz.is_file() else b""
    if integrity(body) != ELK["integrity"]:
        body = _fetch(tgz, get)
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
        bundle, license_text = (tar.extractfile(name).read().decode("utf-8") for name in (ELK["bundle"], ELK["license_file"]))
    note = (f"/* {ELK['package']} {ELK['version']}・{ELK['license']}・取った所 {ELK['tarball']}（{ELK['integrity']}）。"
            f"下はその tarball の {ELK['bundle']} の字のまま。{ELK['license_file']} の字:\n\n"
            + license_text.replace("*/", "* /") + "\n*/")
    return bundle, note


def integrity(body: bytes) -> str:
    """npm の登録所の dist.integrity と同じ形（sha512- と sha512 の base64）"""
    return "sha512-" + base64.b64encode(hashlib.sha512(body).digest()).decode()


def _fetch(tgz: Path, get: Callable) -> bytes:
    where = f"{ELK['tarball']} を {tgz} に置けば網なしで使う（照らしの値 {ELK['integrity']}）"
    try:
        status, body = get(ELK["tarball"], {}, MAX_BODY)
    except webget.FetchError as error:
        raise Unfetched(f"elkjs が取れない（{error}）。{where}") from None
    if status != 200:
        raise Unfetched(f"elkjs が取れない（状態 {status}）。{where}")
    got = integrity(body)
    if got != ELK["integrity"]:
        raise Unfetched(f"取った elkjs の照らしの値が合わない（{got}）。viewer/elkjs.json の版と値を確かめる。{where}")
    tgz.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=tgz.parent, delete=False) as part:
        part.write(body)
    os.replace(part.name, tgz)
    return body
