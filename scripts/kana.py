#!/usr/bin/env python3
"""ローマ字→ひらがな変換(nameKana の自動生成用)。

TMDb は `language=en-US` で人名をラテン表記(例: Hiroki Hasegawa)、`language=ja-JP` で
日本語表記(例: 長谷川博己)を返す。日本人スタッフ・キャストの nameKana は
「名 姓」のラテン表記を反転してローマ字→ひらがな変換すれば機械生成できる
(Hiroki Hasegawa → はせがわひろき。既存データの表記と一致することを確認済み)。

長音の扱い(Ryusuke → りゆすけ ではなく りゅすけ)など細部は完全ではないが、
nameKana は五十音ソートにしか使われないため先頭かなが合っていれば実害はない。
カタカナ表記の人名・社名は「・」と空白を除いたカタカナをそのまま nameKana にする。
"""
import re

_TABLE = [
    ("kya", "きゃ"), ("kyu", "きゅ"), ("kyo", "きょ"), ("kye", "きぇ"),
    ("gya", "ぎゃ"), ("gyu", "ぎゅ"), ("gyo", "ぎょ"),
    ("sha", "しゃ"), ("shu", "しゅ"), ("sho", "しょ"), ("she", "しぇ"), ("shi", "し"),
    ("cha", "ちゃ"), ("chu", "ちゅ"), ("cho", "ちょ"), ("che", "ちぇ"), ("chi", "ち"),
    ("tsu", "つ"), ("tza", "つぁ"),
    ("nya", "にゃ"), ("nyu", "にゅ"), ("nyo", "にょ"),
    ("hya", "ひゃ"), ("hyu", "ひゅ"), ("hyo", "ひょ"),
    ("mya", "みゃ"), ("myu", "みゅ"), ("myo", "みょ"),
    ("rya", "りゃ"), ("ryu", "りゅ"), ("ryo", "りょ"), ("rye", "りぇ"),
    ("bya", "びゃ"), ("byu", "びゅ"), ("byo", "びょ"),
    ("pya", "ぴゃ"), ("pyu", "ぴゅ"), ("pyo", "ぴょ"),
    ("jya", "じゃ"), ("jyu", "じゅ"), ("jyo", "じょ"),
    ("ja", "じゃ"), ("ju", "じゅ"), ("jo", "じょ"), ("je", "じぇ"), ("ji", "じ"),
    ("dzu", "づ"), ("dya", "ぢゃ"),
    ("fa", "ふぁ"), ("fi", "ふぃ"), ("fe", "ふぇ"), ("fo", "ふぉ"), ("fu", "ふ"),
    ("va", "ゔぁ"), ("vi", "ゔぃ"), ("vu", "ゔ"), ("ve", "ゔぇ"), ("vo", "ゔぉ"),
    ("ka", "か"), ("ki", "き"), ("ku", "く"), ("ke", "け"), ("ko", "こ"),
    ("ga", "が"), ("gi", "ぎ"), ("gu", "ぐ"), ("ge", "げ"), ("go", "ご"),
    ("sa", "さ"), ("si", "し"), ("su", "す"), ("se", "せ"), ("so", "そ"),
    ("za", "ざ"), ("zi", "じ"), ("zu", "ず"), ("ze", "ぜ"), ("zo", "ぞ"),
    ("ta", "た"), ("ti", "ち"), ("tu", "つ"), ("te", "て"), ("to", "と"),
    ("da", "だ"), ("di", "でぃ"), ("du", "づ"), ("de", "で"), ("do", "ど"),
    ("na", "な"), ("ni", "に"), ("nu", "ぬ"), ("ne", "ね"), ("no", "の"),
    ("ha", "は"), ("hi", "ひ"), ("hu", "ふ"), ("he", "へ"), ("ho", "ほ"),
    ("ba", "ば"), ("bi", "び"), ("bu", "ぶ"), ("be", "べ"), ("bo", "ぼ"),
    ("pa", "ぱ"), ("pi", "ぴ"), ("pu", "ぷ"), ("pe", "ぺ"), ("po", "ぽ"),
    ("ma", "ま"), ("mi", "み"), ("mu", "む"), ("me", "め"), ("mo", "も"),
    ("ya", "や"), ("yu", "ゆ"), ("yo", "よ"),
    ("ra", "ら"), ("ri", "り"), ("ru", "る"), ("re", "れ"), ("ro", "ろ"),
    ("la", "ら"), ("li", "り"), ("lu", "る"), ("le", "れ"), ("lo", "ろ"),
    ("wa", "わ"), ("wo", "を"), ("wi", "うぃ"), ("we", "うぇ"),
    ("a", "あ"), ("i", "い"), ("u", "う"), ("e", "え"), ("o", "お"),
    ("n", "ん"),
]

_JP_CHARS = re.compile(r"[ぁ-んァ-ヴー一-龥々〆]")
_KATAKANA_ONLY = re.compile(r"^[ァ-ヴー・\s]+$")


def has_japanese(s: str) -> bool:
    return bool(_JP_CHARS.search(s or ""))


def is_katakana_name(s: str) -> bool:
    return bool(_KATAKANA_ONLY.match((s or "").strip()))


def romaji_to_hiragana(word: str) -> str:
    """1語のローマ字をひらがなに変換する(ベストエフォート)。"""
    s = re.sub(r"[^a-z]", "", (word or "").lower())
    s = s.replace("oh", "o").replace("ou", "ou")
    out = []
    i = 0
    while i < len(s):
        # 促音(同じ子音の連続。nn は「ん」)
        if i + 1 < len(s) and s[i] == s[i + 1] and s[i] not in "aiueon":
            out.append("っ")
            i += 1
            continue
        if s[i] == "n" and i + 1 < len(s) and s[i + 1] == "n":
            out.append("ん")
            i += 2
            continue
        for roma, kana in _TABLE:
            if s.startswith(roma, i):
                out.append(kana)
                i += len(roma)
                break
        else:
            i += 1
    return "".join(out)


def kana_for_person(ja_name: str, en_name: str) -> str:
    """表示名(ja)とラテン表記(en)から nameKana を作る。

    - 表示名がカタカナ(外国人名)…「・」「 」を除いたカタカナ
    - 表示名に漢字・ひらがなを含む(日本人名)…enの「名 姓」を反転してローマ字変換
    - どちらでもない(ラテン表記のまま)…enをそのままローマ字変換(暫定)
    """
    name = (ja_name or "").strip()
    if is_katakana_name(name):
        return re.sub(r"[・\s]", "", name)
    tokens = [t for t in re.split(r"[\s]+", (en_name or "").strip()) if t]
    if has_japanese(name) and tokens:
        return "".join(romaji_to_hiragana(t) for t in reversed(tokens))
    return "".join(romaji_to_hiragana(t) for t in tokens)


def katakana_to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s or "")


def kana_for_title(title: str) -> str:
    """かな・カタカナだけで書ける題名の titleKana を自動生成する。無理なら空文字。

    works.json の titleKana は**すべてひらがな**(インセプション→いんせぷしょん)。
    漢字・ラテン文字・数字を含む題名は機械生成できないので空を返し、fill.txt で指定する。
    """
    t = (title or "").strip()
    if re.search(r"[0-9０-９A-Za-zＡ-Ｚａ-ｚ一-龥々〆]", t):
        return ""
    t = katakana_to_hiragana(t)
    t = re.sub(r"[^ぁ-んー]", "", t)
    return t
