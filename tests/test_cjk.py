"""CJK text: no spaces between words, so a word count by whitespace sees a
whole paragraph as one word and the chunker never splits it."""
from riemann.abstraction.chunk import MAX_LEAF_WORDS, chunk, word_count


def test_english_count_is_unchanged():
    assert word_count("one two  three\nfour") == 4
    assert word_count("") == 0
    assert word_count("a - b | c") == 5  # bullets and pipes still count, as before


def test_each_han_kana_character_is_about_one_word():
    assert word_count("今天天气很好") == 6
    assert word_count("これは日本語です") == 8  # kana and kanji alike
    assert word_count("カタカナ") == 4


def test_cjk_punctuation_is_not_a_word():
    assert word_count("今天天气很好。") == 6
    assert word_count("你好，世界！") == 4
    assert word_count("「你好」") == 2


def test_hangul_counts_its_space_separated_words():
    assert word_count("안녕하세요 세계") == 2
    assert word_count("저는 학생입니다.") == 2


def test_mixed_text_counts_both():
    assert word_count("Riemann 是一个阅读工具 for Sam") == 3 + 7  # Riemann, for, Sam + 7 characters
    assert word_count("GPT-4 发布了") == 1 + 3


def _cjk_sentences(n: int, chars: int = 20) -> str:
    return "".join("人" * (chars - 1) + "。" for _ in range(n))


def test_cjk_paragraph_is_split_at_sentence_punctuation():
    text = "# 标题\n\n" + _cjk_sentences(15) + "\n"  # 15 sentences x 20 chars = 300 words, no spaces at all
    leaves = chunk(text)
    assert len(leaves) >= 3
    for leaf in leaves:
        assert leaf.words <= MAX_LEAF_WORDS
        assert leaf.text.endswith("。")


def test_cjk_split_keeps_a_closing_quote_with_its_sentence():
    sent = "他说「" + "好" * 17 + "。」"  # the full stop sits inside the quote
    text = "# 标题\n\n" + sent * 12 + "\n"
    for leaf in chunk(text):
        assert leaf.text.endswith("。」"), leaf.text[-6:]


def test_all_the_cjk_sentence_ends_split():
    for end in ("。", "！", "？"):
        text = "# 标题\n\n" + ("字" * 19 + end) * 15 + "\n"
        assert all(l.text.endswith(end) for l in chunk(text)), end


def test_cjk_clause_fallback_and_hard_cut_obey_the_cap():
    clauses = ("字" * 9 + "、") * 30  # 300 characters, only commas
    assert all(l.words <= MAX_LEAF_WORDS for l in chunk("# 标题\n\n" + clauses + "\n"))
    assert chunk("# 标题\n\n" + clauses + "\n")[0].text.endswith("、")
    run_on = "字" * 400
    assert all(l.words <= MAX_LEAF_WORDS for l in chunk("# 标题\n\n" + run_on + "\n"))


def test_spans_still_index_the_source():
    text = "# 标题\n\n" + _cjk_sentences(15) + "\n"
    for leaf in chunk(text):
        a, b = leaf.source_span
        assert text[a:b] == leaf.text


def test_mixed_english_and_cjk_paragraph_splits_cleanly():
    text = "# T\n\n" + ("This is English. 这是中文句子，一共有十几个字。 " * 12) + "\n"
    leaves = chunk(text)
    assert all(l.words <= MAX_LEAF_WORDS for l in leaves)
    assert all(l.text.rstrip().endswith((".", "。")) for l in leaves)


def test_english_quote_after_a_full_stop_still_splits():
    text = "# T\n\n" + ('He said it was done. "Go now," she said. ' * 15) + "\n"
    assert all(l.text.rstrip().endswith(".") for l in chunk(text))


async def test_a_chinese_document_builds_into_a_real_tree():
    from riemann.abstraction.build import start_build
    from riemann.abstraction.summarise import FakeSummariser

    text = "\n\n".join(f"## 第{i}节\n\n" + _cjk_sentences(12) for i in range(4))
    builder = start_build("cjk", "中文文档", text, FakeSummariser())
    await builder.task
    tree = builder.tree
    assert tree.status == "done"
    assert tree.source_words == word_count(text) > 900
    leaves = [n for n in tree.nodes.values() if n.is_leaf]
    assert len(leaves) >= 8 and all(n.words <= MAX_LEAF_WORDS for n in leaves)
    assert tree.max_depth >= 2
