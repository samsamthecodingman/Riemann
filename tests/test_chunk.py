from riemann.abstraction.chunk import MAX_LEAF_WORDS, chunk, word_count


def _words(n: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_tiny_input_gives_one_leaf():
    text = "Just a short sentence about nothing much at all."
    leaves = chunk(text)
    assert len(leaves) == 1
    assert leaves[0].text == text
    assert leaves[0].atomic is False


def test_heading_splits_create_separate_leaves():
    text = f"# Section A\n\n{_words(50)}\n\n# Section B\n\n{_words(50)}\n"
    leaves = chunk(text)
    paths = {leaf.heading_path for leaf in leaves}
    assert ("Section A",) in paths
    assert ("Section B",) in paths
    # leaves from different sections should not be merged together
    section_a_leaves = [l for l in leaves if l.heading_path == ("Section A",)]
    section_b_leaves = [l for l in leaves if l.heading_path == ("Section B",)]
    assert section_a_leaves
    assert section_b_leaves


def test_max_350_word_cap():
    text = "# Section\n\n" + _words(900) + "\n"
    leaves = chunk(text)
    assert len(leaves) > 1
    for leaf in leaves:
        assert word_count(leaf.text) <= MAX_LEAF_WORDS


def test_code_fence_is_atomic_leaf():
    text = (
        f"# Section\n\n{_words(70)}\n\n"
        "```python\ndef f():\n    return 1\n```\n\n"
        f"{_words(70)}\n"
    )
    leaves = chunk(text)
    atomic_leaves = [l for l in leaves if l.atomic]
    assert len(atomic_leaves) == 1
    assert "```" in atomic_leaves[0].text
    assert "def f():" in atomic_leaves[0].text


def test_numbered_procedure_is_atomic_leaf():
    text = (
        f"# Steps\n\n{_words(70)}\n\n"
        "1. First do this.\n2. Then do that.\n3. Finally finish up.\n\n"
        f"{_words(70)}\n"
    )
    leaves = chunk(text)
    atomic_leaves = [l for l in leaves if l.atomic]
    assert len(atomic_leaves) == 1
    assert "1. First do this." in atomic_leaves[0].text


def test_equation_block_is_atomic_leaf():
    text = f"# Math\n\n{_words(70)}\n\n$$E = mc^2$$\n\n{_words(70)}\n"
    leaves = chunk(text)
    atomic_leaves = [l for l in leaves if l.atomic]
    assert len(atomic_leaves) == 1
    assert "E = mc^2" in atomic_leaves[0].text


def test_source_spans_are_within_bounds():
    text = f"# A\n\n{_words(80)}\n\n# B\n\n{_words(80)}\n"
    leaves = chunk(text)
    for leaf in leaves:
        start, end = leaf.source_span
        assert 0 <= start <= end <= len(text)


def test_a_long_markdown_table_is_one_atomic_leaf_never_cut_mid_row():
    header = "| Name | Type | Default | Notes |\n|------|------|---------|-------|\n"
    rows = "".join(f"| option{i} | int | {i} | the {i}th option controls behaviour number {i} in the system |\n" for i in range(40))
    text = f"# Options\n\n{_words(30)}\n\n{header}{rows}\n{_words(30, 'after')}\n"
    leaves = chunk(text)
    tables = [l for l in leaves if l.text.lstrip().startswith("| Name")]
    assert len(tables) == 1
    assert tables[0].atomic is True
    assert tables[0].text.count("\n") == 41  # header, separator and 40 rows, none lost
    assert all(line.startswith("|") and line.endswith("|") for line in tables[0].text.splitlines())
    # prose around it is untouched and not merged into the table
    assert any(l.text.startswith("word0") for l in leaves) and any(l.text.startswith("after0") for l in leaves)


def test_pipes_inside_prose_do_not_make_a_table():
    text = f"# A\n\n{_words(60)} a | b | c inline pipes are fine {_words(30, 'x')}\n"
    assert not any(l.atomic for l in chunk(text))


# --- sentence-aware splitting (schema6) ---------------------------------------------------

def _sentences(n: int, words_each: int = 11) -> str:
    return " ".join(f"S{i}w0 {_words(words_each - 2, f's{i}w')} ends." for i in range(n))


def test_long_paragraph_splits_at_the_latest_sentence_end_under_the_cap():
    # 15 sentences of 11 words = 165 words; the first cut must fall on a full stop,
    # and be as late as fits (10 sentences = 110 words, not an early stub).
    leaves = chunk("# A\n\n" + _sentences(15) + "\n")
    assert len(leaves) == 2
    assert leaves[0].text.endswith("ends.") and leaves[1].text.endswith("ends.")
    assert leaves[0].words == 110


def test_a_sentence_boundary_is_found_even_when_it_is_early_in_the_window():
    # Old rule only looked in the last 40% of the window and cut mid-sentence
    # when the last full stop was earlier than that.
    first = _words(40) + " done."  # 41 words
    second = "Tail " + _words(150, "tail")  # one long run-on sentence, no full stop
    leaves = chunk("# A\n\n" + first + " " + second + ".\n")
    assert leaves[0].text.endswith("done.")


def test_clause_boundary_is_the_fallback_when_there_is_no_sentence_end():
    clauses = ", ".join(_words(9, f"c{i}x") for i in range(20))  # 180 words, commas only
    leaves = chunk("# A\n\n" + clauses + ".\n")
    assert all(l.words <= MAX_LEAF_WORDS for l in leaves)
    assert leaves[0].text.endswith(",") or leaves[0].text.endswith(";")
    # the cut is at a clause, not inside one: the next leaf starts a clause
    assert leaves[1].text.startswith("c")


def test_abbreviations_are_not_sentence_ends():
    text = "# A\n\n" + " ".join(["The result (Fig. 3, e.g. the plot) shows a strong effect, see Smith et al. for detail."] * 10) + "\n"
    for leaf in chunk(text):
        assert not leaf.text.rstrip().endswith(("Fig.", "e.g.", "al."))


def test_a_run_on_with_no_punctuation_still_obeys_the_cap():
    leaves = chunk("# A\n\n" + _words(400) + "\n")
    assert all(l.words <= MAX_LEAF_WORDS for l in leaves)


def test_leaves_never_pack_across_a_sub_heading():
    text = f"# Doc\n\n## Part\n\n{_words(30)}\n\n### Sub\n\n{_words(30, 'sub')}\n\n## Next\n\n{_words(30, 'nx')}\n"
    leaves = chunk(text)
    for leaf in leaves:
        prefixes = {w[:2] for w in leaf.text.split()}
        assert len(prefixes) == 1, leaf.text  # only one section's words per leaf
    assert {l.heading_path for l in leaves} == {("Doc", "Part"), ("Doc", "Part", "Sub"), ("Doc", "Next")}
