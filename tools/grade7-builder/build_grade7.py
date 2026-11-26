import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

from openpyxl import load_workbook


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = Path(
    r"E:\【2】学生题库\【13】单词卡\单词闪记5.0"
    r"\知识闪记-鲁教版7年级英语 上册单词表V4-完整版.xlsx"
)

FULL_COUNTS = {
    "Unit 1": 58,
    "Unit 2": 55,
    "Unit 3": 49,
    "Unit 4": 64,
    "Unit 5": 57,
    "Unit 6": 52,
    "Unit 7": 35,
}

CORE_COUNTS = {
    "Unit 1": 50,
    "Unit 2": 51,
    "Unit 3": 49,
    "Unit 4": 63,
    "Unit 5": 44,
    "Unit 6": 52,
    "Unit 7": 35,
}

TEACHING_OVERRIDES = {
    "time zone": (
        "A time zone helps people know the time in different places.",
        "时区帮助人们了解不同地方的时间。",
    ),
    "shine": (
        "The stars shine brightly at night.",
        "星星在夜晚明亮地闪耀。",
    ),
    "drop off": (
        "My father will drop off my school bag at the school gate.",
        "爸爸会把我的书包放在学校门口。",
    ),
    "drive": (
        "My mother will drive me to school on rainy days.",
        "下雨天妈妈会开车送我上学。",
    ),
    "feel like": (
        "This warm drink can feel like a hug on a cold day.",
        "这杯热饮在寒冷的日子里让人感觉很温暖。",
    ),
    "seem": (
        "The plan can seem easy at first.",
        "这个计划一开始似乎很简单。",
    ),
    "germ": (
        "Wash your hands to keep every germ away.",
        "洗手可以让每个细菌远离你。",
    ),
    "create": (
        "The students will create a poster for Earth Day.",
        "学生们将为地球日制作一张海报。",
    ),
    "explore": (
        "We will explore the forest with our teacher.",
        "我们将和老师一起探索森林。",
    ),
    "from... to...": (
        "The phrase from... to... shows when the shop is open.",
        "短语 from... to... 表示商店从什么时候开到什么时候。",
    ),
    "search for": (
        "We will search for the key under the sofa.",
        "我们会在沙发下面寻找钥匙。",
    ),
    "to sb’s surprise": (
        "The phrase to sb’s surprise means making someone surprised.",
        "短语 to sb’s surprise 表示让某人感到惊讶。",
    ),
    "pretend": (
        "The boy likes to pretend to be a brave knight.",
        "这个男孩喜欢假装自己是一位勇敢的骑士。",
    ),
    "praise": (
        "The teacher will praise us for our hard work.",
        "老师会表扬我们的努力。",
    ),
    "search": (
        "They will search the garden for the lost ring.",
        "他们会在花园里寻找丢失的戒指。",
    ),
    "make a promise": (
        "He will make a promise to help his friend.",
        "他会承诺帮助他的朋友。",
    ),
    "set ... free": (
        "The children will set ... free after helping the little bird.",
        "孩子们会帮助小鸟后把它放生。",
    ),
    "succeed in doing sth": (
        "To succeed in doing sth means to finish something successfully.",
        "短语 succeed in doing sth 表示成功完成某事。",
    ),
    "set": (
        "The story will set the scene in a forest.",
        "这个故事将把场景设置在森林里。",
    ),
    "take sb’s breath away": (
        "The beautiful sunrise can take sb’s breath away.",
        "美丽的日出会让人惊叹不已。",
    ),
    "ready to do sth": (
        "She is ready to do sth helpful for the class.",
        "她准备好为班级做有益的事情。",
    ),
    "fight against sb / sth": (
        "The phrase fight against sb / sth means to struggle against someone or something.",
        "短语 fight against sb / sth 表示与某人或某事物作斗争。",
    ),
    "get together": (
        "Our family will get together after the Spring Festival.",
        "春节后我们一家人会聚在一起。",
    ),
    "remind": (
        "This song can remind me of my old school.",
        "这首歌会让我想起我的母校。",
    ),
    "Nazi": (
        "The museum explains what Nazi means in history.",
        "博物馆解释了 Nazi 在历史中的含义。",
    ),
    "invite": (
        "I will invite my friends to the birthday party.",
        "我会邀请朋友们参加生日聚会。",
    ),
    "add sth to sth": (
        "The phrase add sth to sth means putting one thing into another.",
        "短语 add sth to sth 表示把一个事物加到另一个事物中。",
    ),
    "give sb a lift": (
        "The phrase give sb a lift means taking someone somewhere by car.",
        "短语 give sb a lift 表示开车捎某人一段路。",
    ),
    "share sth with sb": (
        "The phrase share sth with sb means giving part of something to another person.",
        "短语 share sth with sb 表示与别人分享某事物。",
    ),
}

ACCEPTANCE_PREFIXES = (
    "During the next lesson, ",
    "After class, ",
    "In the group activity, ",
    "At the end of the day, ",
)

def _is_proper_name(text):
    tokens = [token.strip(".,!?()[]") for token in str(text).split()]
    return any(token and token[0].isupper() for token in tokens)


def _word_pattern(word):
    return re.compile(
        rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])",
        flags=re.IGNORECASE,
    )


def _insert_placeholder(sentence, word):
    matches = list(_word_pattern(word).finditer(sentence))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one occurrence of {word!r} in {sentence!r}; "
            f"found {len(matches)}"
        )
    match = matches[0]
    return f"{sentence[:match.start()]}{{{{word}}}}{sentence[match.end():]}"


def _lowercase_clause_start(sentence, word):
    if sentence.startswith("I "):
        return sentence
    first = sentence.split(maxsplit=1)[0]
    word_first = word.split(maxsplit=1)[0]
    if (
        word_first
        and word_first[0].isupper()
        and first.strip(".,!?()[]").lower() == word_first.lower()
    ):
        return sentence
    return sentence[0].lower() + sentence[1:]


def load_workbook_rows(path=WORKBOOK):
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["单词表"]
    rows = []
    for raw in sheet.iter_rows(min_row=2, values_only=True):
        if not raw[1]:
            continue
        unit, english, ipa, syllable, chinese, part_of_speech, mnemonic, example, example_zh, _ = raw
        override = TEACHING_OVERRIDES.get(english)
        training_sentence, training_zh = override or (example, example_zh)
        proper = _is_proper_name(english)
        rows.append(
            {
                "unit": str(unit),
                "en": str(english).strip(),
                "ipa": str(ipa or "-").strip(),
                "syllable": str(syllable or "").strip(),
                "zh": str(chinese or "").strip(),
                "pos": str(part_of_speech or "").strip(),
                "mnemonic": str(mnemonic or "").strip(),
                "example": str(example or "").strip(),
                "exampleZh": str(example_zh or "").strip(),
                "trainingSentence": _insert_placeholder(training_sentence, english),
                "trainingZh": str(training_zh or "").strip(),
                "proper": proper,
                "core": not proper,
                "group": str(part_of_speech or "other").split(";")[0].strip(),
            }
        )
    return rows


def derive_units(rows):
    units = OrderedDict()
    for row in rows:
        units.setdefault(row["unit"], []).append(row)
    return units


def build_content(words):
    content = {}
    for index, row in enumerate(words):
        prefix = ACCEPTANCE_PREFIXES[index % len(ACCEPTANCE_PREFIXES)]
        acceptance = prefix + _lowercase_clause_start(
            row["trainingSentence"],
            row["en"],
        )
        content[row["en"]] = (
            row["trainingSentence"],
            row["trainingZh"],
            acceptance,
            f"在今天的英语练习中，学生用 {{{{word}}}} 来表达“{row['zh']}”的意思。",
        )
    return content


def _split_scene_sizes(total):
    base, extra = divmod(total, 4)
    return [base + (1 if index < extra else 0) for index in range(4)]


def build_scenes(words, include_non_core):
    content = build_content(words)
    unit_number = words[0]["unit"].split()[-1]
    sizes = _split_scene_sizes(len(words))
    scenes = []
    offset = 0
    for scene_index, size in enumerate(sizes, 1):
        chunk = words[offset : offset + size]
        offset += size
        story = " ".join(
            content[row["en"]][0].replace("{{word}}", row["en"])
            for row in chunk
        )
        story_zh = " ".join(content[row["en"]][1] for row in chunk)
        scenes.append(
            {
                "id": scene_index,
                "title": f"七年级 Unit {unit_number} · 第 {scene_index} 幕",
                "subtitle": f"Grade 7 · Part {scene_index}",
                "wordEns": [
                    row["en"]
                    for row in chunk
                    if include_non_core or row["core"]
                ],
                "story": story,
                "storyZh": story_zh,
            }
        )
    return scenes


def _page_words(words):
    return [
        {
            "en": row["en"],
            "zh": row["zh"],
            "ipa": row["ipa"],
            "pos": row["pos"],
            "group": row["group"],
        }
        for row in words
    ]


def _postprocess_page(path):
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        "../assets/audio/v2.1/en-GB-SoniaNeural/",
        "../assets/audio/g7-v1/en-GB-SoniaNeural/",
    )
    source = source.replace('href="../../"', 'href="../../grade7/"')
    source = source.replace("单词星球 2.1", "单词星球 · 七年级上册")
    source = source.replace(
        "单词星球 · Unit ",
        "单词星球 · 七年级上册 · Unit ",
    )
    path.write_text(source, encoding="utf-8")


def _unit_cards(units):
    cards = []
    for unit_name, words in units.items():
        unit_number = int(unit_name.split()[-1])
        core_count = sum(row["core"] for row in words)
        cards.append(
            f"""
          <article class="unit-card">
            <span class="unit-kicker">UNIT {unit_number:02d}</span>
            <h3>Unit {unit_number}</h3>
            <p class="unit-meta">{len(words)} 条全量 · {core_count} 条核心</p>
            <div class="actions">
              <a class="action primary" href="../outputs/g7-v1-unit{unit_number}/index.html">全部词条版</a>
              <a class="action" href="../outputs/g7-v1-unit{unit_number}-core/index.html">核心词汇版</a>
            </div>
          </article>"""
        )
    return "\n".join(cards)


def build_grade7_landing():
    source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        "鲁教版六年级英语上册单词星球 2.1 词汇训练页面集合。",
        "鲁教版七年级英语上册单词星球词汇训练页面集合。",
    )
    source = source.replace(
        "<title>单词星球 · 鲁教版六年级英语上册</title>",
        "<title>单词星球 · 鲁教版七年级英语上册</title>",
    )
    source = source.replace(
        "GRADE 6 · ENGLISH VOCABULARY",
        "GRADE 7 · ENGLISH VOCABULARY",
    )
    source = source.replace(
        "“全部词条版”和“重点词汇版”",
        "“全部词条版”和“核心词汇版”",
    )
    source = source.replace(
        '<strong>Grade 6</strong>',
        '<strong>Grade 7</strong>',
    )
    source = source.replace(
        '<span class="fact"><b>9</b> 个学习单元</span>',
        '<span class="fact"><b>7</b> 个学习单元</span>',
    )
    source = source.replace(
        '<span class="fact"><b>18</b> 套训练页面</span>',
        '<span class="fact"><b>14</b> 套训练页面</span>',
    )
    source = source.replace(
        '<nav class="grade-switch" aria-label="年级切换">\n'
        '          <a class="is-active" href="./">六年级上册</a>\n'
        '          <a href="grade7/">七年级上册</a>\n'
        "        </nav>",
        '<nav class="grade-switch" aria-label="年级切换">\n'
        '          <a href="../">六年级上册</a>\n'
        '          <a class="is-active" href="./">七年级上册</a>\n'
        "        </nav>",
    )
    rows = load_workbook_rows()
    units = derive_units(rows)
    source = re.sub(
        r'<div class="unit-grid">.*?</div>\s*</section>',
        f'<div class="unit-grid">{_unit_cards(units)}\n        </div>\n      </section>',
        source,
        count=1,
        flags=re.DOTALL,
    )
    source = source.replace(
        "单词星球 2.1",
        "单词星球 · 七年级上册",
    )
    output_dir = REPO_ROOT / "grade7"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(source, encoding="utf-8")


def build_all_pages():
    sys.path.insert(0, str(REPO_ROOT / "work" / "v21-unit4"))
    from build_unit4 import build

    rows = load_workbook_rows()
    units = derive_units(rows)
    for unit_name, words in units.items():
        unit_number = int(unit_name.split()[-1])
        content = build_content(words)
        full_scenes = build_scenes(words, include_non_core=True)
        core_scenes = build_scenes(words, include_non_core=False)
        page_words = _page_words(words)
        core_words = [word for word in page_words if word["en"] in {
            row["en"] for row in words if row["core"]
        }]
        slug_base = f"g7-v1-unit{unit_number}"
        variants = [
            {
                "slug": slug_base,
                "unit": unit_number,
                "unit_number": f"{unit_number:02d}",
                "unit_label": f"Unit {unit_number}",
                "unit_tag": f"GRADE 7 · UNIT {unit_number:02d}",
                "progress_prefix": "grade7",
                "label": f"全部 {len(page_words)} 条",
                "eyebrow": "全册词汇",
                "planet_label": f"七年级 Unit {unit_number} 学习星球",
                "description": (
                    f"七年级上册 Unit {unit_number} 全部词汇，共 {len(page_words)} 条。"
                    "完成四种基础训练、四幕语境、语境训练和最终验收。"
                ),
                "words": page_words,
                "scenes": full_scenes,
                "content": content,
            },
            {
                "slug": f"{slug_base}-core",
                "unit": unit_number,
                "unit_number": f"{unit_number:02d}",
                "unit_label": f"Unit {unit_number}",
                "unit_tag": f"GRADE 7 · UNIT {unit_number:02d}",
                "progress_prefix": "grade7",
                "label": f"核心 {len(core_words)} 条",
                "eyebrow": "核心词汇",
                "planet_label": f"七年级 Unit {unit_number} 核心星球",
                "description": (
                    f"七年级上册 Unit {unit_number} 核心词汇，共 {len(core_words)} 条。"
                    "排除人名、地名和专有名词，保留四种训练、四幕语境和完整验收。"
                ),
                "words": core_words,
                "scenes": core_scenes,
                "content": content,
            },
        ]
        for variant in variants:
            build(variant)
            _postprocess_page(REPO_ROOT / "outputs" / variant["slug"] / "index.html")
    build_grade7_landing()


if __name__ == "__main__":
    rows = load_workbook_rows()
    units = derive_units(rows)
    summary = {
        "full": {unit: len(words) for unit, words in units.items()},
        "core": {
            unit: sum(row["core"] for row in words)
            for unit, words in units.items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    build_all_pages()
