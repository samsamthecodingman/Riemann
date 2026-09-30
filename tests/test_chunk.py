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
